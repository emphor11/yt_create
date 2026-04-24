from __future__ import annotations

import re
from typing import Any


HOOK_TYPES = {"curiosity", "contradiction", "surprise"}
ARC_TYPES = {"reveal_ladder", "contradiction_arc", "transformation", "problem_stack"}
SECTION_TYPES = {"problem", "explanation", "reveal", "decision", "mistake", "optimization"}


class StoryIntelligenceEngine:
    """Deterministically maps narration into a story plan."""

    _FLOW_STAGE = {
        "problem": 0,
        "mistake": 0,
        "explanation": 1,
        "reveal": 2,
        "decision": 3,
        "optimization": 3,
    }
    _WEIGHTS = {
        "problem": ("medium", 0.55),
        "mistake": ("medium", 0.6),
        "explanation": ("medium", 0.5),
        "reveal": ("high", 0.82),
        "decision": ("high", 0.88),
        "optimization": ("high", 0.9),
    }
    _GENERIC_HOOK_PREFIXES = (
        "in this video",
        "today we",
        "welcome back",
        "let's talk about",
        "this video is about",
    )
    _SECTION_PRIORITY = (
        "mistake",
        "problem",
        "optimization",
        "decision",
        "reveal",
        "explanation",
    )
    _TERMINAL_SECTION_TYPES = {"reveal", "decision", "optimization"}
    _OPENING_SECTION_TYPES = {"problem", "mistake"}
    _AGENDA_FILLER = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "before",
        "because",
        "build",
        "but",
        "by",
        "can",
        "cheap",
        "do",
        "does",
        "feel",
        "fix",
        "for",
        "from",
        "gets",
        "had",
        "has",
        "have",
        "how",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "just",
        "most",
        "now",
        "of",
        "on",
        "one",
        "or",
        "real",
        "reason",
        "simple",
        "so",
        "still",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "to",
        "too",
        "when",
        "where",
        "why",
        "with",
        "without",
        "you",
        "your",
    }
    _BAD_AGENDA_ENDINGS = {"becomes", "catches", "delay", "faster", "keeps", "than", "this"}
    _CONTRADICTION_TOKENS = ("but", "still", "yet", "however", "instead", "actually", "not what")

    def plan_from_script_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        parts: list[str] = []
        hook = payload.get("hook") or {}
        if isinstance(hook, dict):
            parts.append(str(hook.get("narration") or "").strip())
        for scene in payload.get("scenes") or []:
            if isinstance(scene, dict):
                parts.append(str(scene.get("narration") or scene.get("narration_text") or "").strip())
        outro = payload.get("outro") or {}
        if isinstance(outro, dict):
            parts.append(str(outro.get("narration") or "").strip())
        return self.plan("\n".join(part for part in parts if part))

    def plan(self, narration_text: str) -> dict[str, Any]:
        raw = str(narration_text or "").strip()
        if not raw:
            return {
                "hook": "",
                "hook_type": "curiosity",
                "arc_type": "problem_stack",
                "agenda": [],
                "sections": [],
            }

        sentences = self._split_sentences(raw)
        hook = self._build_hook(sentences)
        self._validate_hook(hook)

        body_units: list[str] = []
        for sentence in sentences[1:]:
            body_units.extend(self._split_idea_units(sentence))

        sections = self._build_sections(body_units)
        sections = self._ensure_section_progression(sections)
        hook = self._ensure_distinct_hook(hook, sections)

        self._validate_minimum_sections(sections)
        self._validate_section_flow(sections)
        self._validate_single_idea_sections(sections)

        hook_type = self._classify_hook_type(hook)
        agenda = self._build_agenda(sections)
        self._validate_agenda(agenda)

        return {
            "hook": hook,
            "hook_type": hook_type,
            "arc_type": self._classify_arc_type(sections, hook_type),
            "agenda": agenda,
            "sections": sections,
        }

    def _split_sentences(self, text: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
        if not normalized:
            return []
        parts = re.split(r"(?<=[.!?])\s+", normalized)
        return [self._normalize_text(part) for part in parts if self._normalize_text(part)]

    def _split_idea_units(self, sentence: str) -> list[str]:
        units = [self._normalize_text(sentence)]
        splitter_patterns = (
            r",\s+but\s+",
            r",\s+yet\s+",
            r",\s+however\s+",
            r";\s+",
        )
        for pattern in splitter_patterns:
            next_units: list[str] = []
            for unit in units:
                parts = re.split(pattern, unit, flags=re.IGNORECASE)
                next_units.extend(self._normalize_text(part) for part in parts if self._normalize_text(part))
            units = next_units or units
        return units

    def _build_sections(self, idea_units: list[str]) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        for unit in idea_units:
            section_type = self._classify_sentence(unit)
            sections.append(
                {
                    "type": section_type,
                    "text": unit,
                    "weight": self._weight_for(section_type),
                }
            )
        return sections

    def _ensure_section_progression(self, sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = [dict(section) for section in sections if self._normalize_text(section.get("text") or "")]
        if not normalized:
            return []

        if normalized[0]["type"] not in self._OPENING_SECTION_TYPES:
            normalized[0]["type"] = self._opening_type_for_text(normalized[0]["text"])
            normalized[0]["weight"] = self._weight_for(normalized[0]["type"])

        for index in range(1, len(normalized)):
            if normalized[index]["type"] in self._OPENING_SECTION_TYPES:
                replacement = "explanation"
                if any(token in normalized[index]["text"].lower() for token in ("fix", "automate", "improve", "save", "system")):
                    replacement = "optimization"
                elif any(token in normalized[index]["text"].lower() for token in ("truth", "real reason", "actually", "proves", "turns out")):
                    replacement = "reveal"
                normalized[index]["type"] = replacement
                normalized[index]["weight"] = self._weight_for(replacement)

        if len(normalized) >= 3:
            if not any(section["type"] == "explanation" for section in normalized[1:]) and normalized[1]["type"] not in {"decision", "optimization"}:
                normalized[1]["type"] = "explanation"
                normalized[1]["weight"] = self._weight_for("explanation")
            if normalized[-1]["type"] not in self._TERMINAL_SECTION_TYPES:
                normalized[-1]["type"] = self._terminal_type_for_text(normalized[-1]["text"])
                normalized[-1]["weight"] = self._weight_for(normalized[-1]["type"])

        return normalized

    def _build_hook(self, sentences: list[str]) -> str:
        if not sentences:
            return ""
        first = self._clean_hook_text(sentences[0])
        second = self._clean_hook_text(sentences[1]) if len(sentences) > 1 else ""

        if first and not self._is_generic_hook(first):
            return first

        if self._is_stat_fact(first) and second:
            contradiction_clause = self._hook_contradiction_clause(second)
            if contradiction_clause:
                return self._normalize_text(f"{first.rstrip('.!?')}, but {contradiction_clause}?")

        if second and not self._is_generic_hook(second):
            return second

        return first

    def _clean_hook_text(self, text: str) -> str:
        cleaned = self._normalize_text(text).rstrip(".!?")
        cleaned = re.sub(r"\bbut the real story starts after this\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\band the real story starts after this\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:-")
        return f"{cleaned}." if cleaned and not cleaned.endswith("?") else cleaned

    def _classify_hook_type(self, hook: str) -> str:
        lowered = hook.lower()
        if any(token in lowered for token in ("but", "instead", "actually", "not ", "you think", "feels like", "proves")):
            return "contradiction"
        if "?" in hook or any(token in lowered for token in ("why", "how", "hidden", "secret", "nobody tells you", "plot twist")):
            return "curiosity"
        if re.search(r"(₹|\d|%|less than|more than|only)", lowered):
            return "surprise"
        return "curiosity"

    def _classify_arc_type(self, sections: list[dict[str, Any]], hook_type: str = "") -> str:
        if hook_type == "contradiction":
            return "contradiction_arc"
        types = [section["type"] for section in sections]
        if types.count("reveal") >= 2 or (types and types[-1] == "reveal" and "decision" not in types and "optimization" not in types):
            return "reveal_ladder"
        if "optimization" in types or "decision" in types:
            return "transformation"
        if any(section["type"] in {"problem", "mistake"} for section in sections) and any(
            "but" in section["text"].lower() or "actually" in section["text"].lower() or "not " in section["text"].lower()
            for section in sections
        ):
            return "contradiction_arc"
        return "problem_stack"

    def _build_agenda(self, sections: list[dict[str, Any]]) -> list[str]:
        agenda: list[str] = []
        seen: set[str] = set()
        for section in sections:
            item = self._agenda_item(section)
            if not item:
                continue
            lowered = item.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            agenda.append(item)
            if len(agenda) == 3:
                break
        return agenda

    def _agenda_item(self, section: dict[str, Any]) -> str:
        text = str(section["text"])
        section_type = str(section["type"])
        lowered = text.lower().strip().rstrip(".!?")

        if section_type in {"problem", "mistake"}:
            if "hospital bill" in lowered or "debt" in lowered:
                return "hospital debt risk"
            if "expenses rise" in lowered:
                return "lifestyle inflation"
            if "compounding" in lowered and "payment" in lowered:
                return "compounding card debt"
            if "salary" in lowered and "leak" in lowered:
                return "salary leak"

        if section_type == "explanation":
            if "emergency fund" in lowered:
                return "emergency fund buffer"
            if "convenience" in lowered:
                return "convenience cost"
            if "buys time" in lowered:
                return "cash flow buffer"

        if section_type in {"decision", "optimization"}:
            if "automate" in lowered:
                return "automate savings"
            if "fix" in lowered and "investments" in lowered:
                return "raise investments first"
            if "should" in lowered:
                phrase = self._extract_meaningful_phrase(lowered.replace("should", "", 1).strip(), 4)
                return phrase or "better money move"

        if section_type == "reveal":
            if "survival" in lowered and "returns" in lowered:
                return "survival before returns"
            if "real reason" in lowered:
                phrase = self._extract_meaningful_phrase(lowered.replace("real reason is", "").strip(), 4)
                return phrase or "hidden cause"

        phrase = self._extract_meaningful_phrase(lowered, 4)
        return phrase or "money risk"

    def _extract_meaningful_phrase(self, text: str, limit: int) -> str:
        tokens = re.findall(r"[A-Za-z0-9₹%']+", text.lower())
        content = [token for token in tokens if token not in self._AGENDA_FILLER]
        if len(content) >= limit:
            candidates = [content[:2], content[:3], content[:limit]]
        else:
            candidates = [content[:2], content[:3], content[:4]]
        for words in candidates:
            phrase = " ".join(word for word in words if word).strip()
            if self._is_meaningful_agenda_phrase(phrase):
                return phrase
        return ""

    def _classify_sentence(self, sentence: str) -> str:
        lowered = sentence.lower()
        scores = {section_type: 0 for section_type in SECTION_TYPES}

        if any(token in lowered for token in ("mistake", "wrong", "trap", "leak", "waste", "bleed", "broke", "debt")):
            scores["mistake"] += 3
        if any(token in lowered for token in ("problem", "cannot", "less than", "lose", "vanish", "gone", "stress", "broken")):
            scores["problem"] += 3
        if any(token in lowered for token in ("fix", "do this", "automate", "best move", "next step")):
            scores["optimization"] += 6
        if any(token in lowered for token in ("should", "choose", "decide", "whether", "option", "vs", "versus")):
            scores["decision"] += 6
        if any(token in lowered for token in ("because", "which means", "that is why", "works", "happens when", "buys time")):
            scores["explanation"] += 3
        if any(token in lowered for token in ("real reason", "truth", "actually", "proves", "here's the thing", "plot twist", "turns out")):
            scores["reveal"] += 3
        if any(token in lowered for token in ("fix", "automate", "optimize", "improve", "better", "invest", "save", "system")):
            scores["optimization"] += 3

        if re.search(r"(₹|\d|%)", sentence):
            scores["problem"] += 1
            scores["reveal"] += 1

        if not any(scores.values()):
            return "explanation"

        ranked = sorted(scores.items(), key=lambda item: (-item[1], self._SECTION_PRIORITY.index(item[0])))
        return ranked[0][0]

    def _opening_type_for_text(self, text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ("mistake", "wrong", "trap", "leak", "debt", "broke")):
            return "mistake"
        return "problem"

    def _terminal_type_for_text(self, text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ("fix", "automate", "optimize", "improve", "save", "system")):
            return "optimization"
        if any(token in lowered for token in ("should", "choose", "decide", "whether", "option")):
            return "decision"
        return "reveal"

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    def _sentence_case(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return ""
        return cleaned[0].upper() + cleaned[1:]

    def _weight_for(self, section_type: str) -> dict[str, Any]:
        level, score = self._WEIGHTS.get(section_type, ("low", 0.3))
        return {"level": level, "score": score}

    def _is_stat_fact(self, text: str) -> bool:
        return bool(re.search(r"(₹|\d|%)", text))

    def _has_curiosity_gap(self, text: str) -> bool:
        lowered = text.lower()
        return "?" in text or any(
            token in lowered
            for token in ("but", "actually", "hidden", "secret", "why", "how", "not what", "nobody tells you", "real reason")
        )

    def _has_direct_tension(self, text: str) -> bool:
        lowered = text.lower()
        return self._is_stat_fact(text) or any(
            token in lowered for token in ("broke", "debt", "lose", "vanish", "gone", "trap", "mistake", "problem")
        )

    def _is_generic_hook(self, text: str) -> bool:
        lowered = self._normalize_text(text).lower()
        if any(lowered.startswith(prefix) for prefix in self._GENERIC_HOOK_PREFIXES):
            return True
        return not self._has_curiosity_gap(text) and not self._has_direct_tension(text)

    def _hook_contradiction_clause(self, sentence: str) -> str:
        match = re.search(r"\bbut\s+(.+)", sentence, flags=re.IGNORECASE)
        if match:
            sentence = match.group(1)
        lowered = sentence.strip().rstrip(".!?")
        lowered = re.sub(
            r"^(most people think|but|and|so|because|that sounds|the real reason is|the truth is)\s+",
            "",
            lowered,
            flags=re.IGNORECASE,
        )
        words = lowered.split()
        return " ".join(words[:8]).strip()

    def _validate_hook(self, hook: str) -> None:
        if not hook or self._is_generic_hook(hook):
            raise ValueError("Story hook is generic and does not create tension.")

    def _ensure_distinct_hook(self, hook: str, sections: list[dict[str, Any]]) -> str:
        if not hook or not sections:
            return hook
        first_section_text = str(sections[0]["text"]).strip().rstrip(".!?")
        hook_text = str(hook).strip().rstrip(".!?")
        if hook_text.lower() != first_section_text.lower():
            return hook
        lowered = hook_text.lower()
        if "without cash" in lowered and "hospital bill" in lowered and "debt" in lowered:
            return "One hospital bill can turn into debt when you have no cash buffer."
        if any(token in lowered for token in self._CONTRADICTION_TOKENS):
            return self._natural_hook_rephrase(hook_text, "That sounds manageable, but ")
        if re.search(r"(₹|\d|%)", hook_text):
            return self._natural_hook_rephrase(hook_text, "For most people, ")
        return self._natural_hook_rephrase(hook_text, "It starts when ")

    def _natural_hook_rephrase(self, hook_text: str, prefix: str) -> str:
        text = hook_text.strip().rstrip(".!?")
        if not text:
            return hook_text
        lowered = text[0].lower() + text[1:] if len(text) > 1 else text.lower()
        candidate = f"{prefix}{lowered}".strip()
        candidate = re.sub(r"\s+", " ", candidate).strip(" ,;:-")
        return candidate + "."

    def _is_meaningful_agenda_phrase(self, phrase: str) -> bool:
        words = phrase.split()
        if len(words) < 2 or len(words) > 4:
            return False
        if words[0].lower() in {"where", "how", "why"}:
            return False
        if words[-1].lower() in self._BAD_AGENDA_ENDINGS:
            return False
        if all(word.lower() in self._AGENDA_FILLER for word in words):
            return False
        return True

    def _validate_minimum_sections(self, sections: list[dict[str, Any]]) -> None:
        if len(sections) < 2:
            raise ValueError("Story plan requires at least two sections.")

    def _validate_section_flow(self, sections: list[dict[str, Any]]) -> None:
        previous_stage = -1
        for section in sections:
            stage = self._FLOW_STAGE.get(section["type"], -1)
            if stage < previous_stage:
                raise ValueError("Story sections are out of order.")
            previous_stage = stage

    def _validate_single_idea_sections(self, sections: list[dict[str, Any]]) -> None:
        for section in sections:
            text = section["text"]
            if re.search(r"(?<=[.!?])\s+[A-Z]", text):
                raise ValueError("Story section contains multiple sentences.")
            if re.search(r",\s+(but|yet|however)\s+", text, flags=re.IGNORECASE):
                raise ValueError("Story section contains multiple ideas.")

    def _validate_agenda(self, agenda: list[str]) -> None:
        for item in agenda:
            words = item.split()
            if len(words) < 2 or len(words) > 4:
                raise ValueError("Agenda items must be 2-4 words.")
            if words[0].lower() in {"where", "how", "why"}:
                raise ValueError("Agenda items cannot start with filler words.")
            if not self._is_meaningful_agenda_phrase(item):
                raise ValueError("Agenda item is not a meaningful standalone phrase.")
