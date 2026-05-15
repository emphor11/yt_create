from __future__ import annotations

import json
import re
from typing import Any

import requests
from flask import current_app

from .numeric import numeric_amount, validate_numbers
from .scene_director import SceneDirector
from .sharpness import ConceptSharpnessMixin


class ConceptGenerationSupportMixin(ConceptSharpnessMixin):
    def _call_groq_api(self, prompt: str, purpose: str) -> dict[str, Any]:
        api_key = current_app.config.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not configured.")
        body = {
            "model": current_app.config.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            "messages": [
                {"role": "system", "content": "Return strict JSON only. No markdown, no commentary."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.35,
            "max_tokens": 900,
            "response_format": {"type": "json_object"},
        }
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "YTCreate/1.0",
            },
            timeout=25,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return self._extract_json(text)

    def _extract_json(self, raw_text: str) -> dict[str, Any]:
        cleaned = str(raw_text or "").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Model response did not contain JSON.")
        return json.loads(cleaned[start : end + 1])

    def _concept_prompt(self, narration: str) -> str:
        return (
            "You are a concept extraction engine for finance education videos.\n\n"
            "CRITICAL RULE:\n"
            "Your output must contain visualizable elements:\n"
            "- at least one number OR\n"
            "- a clear transformation OR\n"
            "- a comparison\n\n"
            "NUMBER RULE:\n"
            "Use numbers from narration if present.\n"
            "Do NOT invent unrelated numbers.\n\n"
            "Return JSON:\n\n"
            "{\n"
            '  "scene_goal": "",\n'
            '  "concept_name": "",\n'
            '  "concept_type": "decay|growth|comparison|flow|emphasis|process",\n'
            '  "entities": [],\n'
            '  "transformation": "",\n'
            '  "start_value": "",\n'
            '  "end_value": "",\n'
            '  "outcome": "",\n'
            '  "explanation_sentence": ""\n'
            "}\n\n"
            "Rules:\n"
            "- scene_goal must say what this scene is trying to prove\n"
            "- entities must be concrete\n"
            "- transformation must describe visible change\n"
            "- explanation_sentence must describe numeric states only\n"
            "- Reject vague outputs\n\n"
            f"Narration: {narration}"
        )

    def _visual_explanation_prompt(self, concept: dict[str, Any]) -> str:
        return (
            "You are a visual explanation designer.\n\n"
            "CRITICAL RULE:\n"
            "- NO sentences\n"
            "- ONLY visual states\n"
            "- MUST contain numbers or labeled values\n"
            "- MUST show progression\n"
            "- Every beat must support scene_goal\n"
            "STRICT FORMAT:\n"
            "{\n"
            '  "visual_narrative": [\n'
            "    {\n"
            '      "beat_position": 0,\n'
            '      "key_value": "",\n'
            '      "supporting_text": "",\n'
            '      "visual_role": "introduce|change|result|emotion",\n'
            '      "suggested_component": ""\n'
            "    }\n"
            "  ],\n"
            '  "overall_structure": "",\n'
            '  "story_arc": ""\n'
            "}\n\n"
            "Rules:\n"
            "- 2-4 beats\n"
            "- beat 0 = introduce\n"
            "- beat 1 = change\n"
            "- beat 2 = result\n"
            "- beat 3 = optional emotion\n"
            "- key_value MUST be number OR short value with ₹ or %\n"
            "- supporting_text max 6 words\n"
            "- decay/growth/flow/process -> FlowDiagram\n"
            "- comparison -> SplitComparison\n"
            "- emphasis -> StatExplosion\n"
            "- beat 3 -> TextBurst\n"
            "- BANNED: ReactionCard, descriptive sentences\n\n"
            f"Concept: {json.dumps(concept, ensure_ascii=False)}"
        )

    def _repair_concept(self, payload: dict[str, Any], narration: str) -> dict[str, Any]:
        fallback = self._fallback_concept(narration)
        if not isinstance(payload, dict):
            return fallback
        concept = {**fallback, **payload}
        concept["concept_type"] = self._concept_type(concept)
        concept["entities"] = self._concrete_entities(concept.get("entities"), fallback["entities"])
        concept["scene_goal"] = self._clean_phrase(str(concept.get("scene_goal") or fallback["scene_goal"]), fallback["scene_goal"])
        for key in ("concept_name", "transformation", "start_value", "end_value", "outcome", "explanation_sentence"):
            concept[key] = self._clean_phrase(str(concept.get(key) or fallback[key]), fallback[key])
        if not self._has_gravity(" ".join(str(concept.get(key) or "") for key in ("transformation", "start_value", "end_value", "outcome", "explanation_sentence"))):
            return fallback
        concept["narration"] = narration
        stages = self.flow_stages(concept, narration)
        if stages:
            concept["flow_stages"] = stages
            if concept["concept_type"] != "emphasis":
                concept["start_value"] = stages[0]["value"]
                concept["end_value"] = stages[-1]["value"]
                concept["transformation"] = " -> ".join(stage["value"] for stage in stages)
                concept["outcome"] = stages[-1]["value"]
                concept["explanation_sentence"] = concept["transformation"]
        elif concept["concept_type"] != "emphasis":
            return self._downgrade_to_emphasis(concept, narration, "concept_numbers_failed_validation")
        return concept

    def _fallback_concept(self, narration: str) -> dict[str, Any]:
        return self._derive_concept_from_narration(narration)

    def _repair_visual_explanation(self, payload: dict[str, Any], concept: dict[str, Any]) -> dict[str, Any]:
        raw_beats = payload.get("visual_narrative") if isinstance(payload, dict) else None
        if not isinstance(raw_beats, list):
            return self._fallback_visual_explanation(concept)
        beats: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_beats[:4]):
            if not isinstance(raw, dict):
                continue
            role = str(raw.get("visual_role") or self._role_for_index(index)).lower()
            component = str(raw.get("suggested_component") or self._component_for_concept(concept, index))
            key_value = self._numeric_value(str(raw.get("key_value") or ""), concept, index)
            supporting = self._clean_supporting_text(str(raw.get("supporting_text") or ""), concept)
            beats.append(
                {
                    "beat_position": index,
                    "key_value": key_value,
                    "supporting_text": supporting,
                    "visual_role": role if role in self.ROLE_COLORS else self._role_for_index(index),
                    "suggested_component": component if component in self.COMPONENT_TO_BEAT_TYPE else self._component_for_concept(concept, index),
                }
            )
        if len(beats) < 2:
            return self._fallback_visual_explanation(concept)
        return {
            "visual_narrative": beats,
            "overall_structure": "numeric_progression",
            "story_arc": str(concept.get("scene_goal") or ""),
        }

    def _fallback_visual_explanation(self, concept: dict[str, Any]) -> dict[str, Any]:
        stages = self.flow_stages(concept)
        if len(stages) < 2:
            narrative = self._safe_emphasis_states(concept)
            return {"visual_narrative": narrative, "overall_structure": "safe_emphasis", "story_arc": str(concept.get("scene_goal") or "")}
        concept_type = self._concept_type(concept)
        component = self._component_for_concept(concept, 0)
        if concept_type == "comparison":
            values = self._values_from_text(str(concept.get("transformation") or ""))
            left = values[0] if values else stages[0]["value"]
            right = values[1] if len(values) > 1 else stages[-1]["value"]
            narrative = [
                {"beat_position": 0, "key_value": left, "supporting_text": self._caption_for_role(concept, 0), "visual_role": "introduce", "suggested_component": "SplitComparison"},
                {"beat_position": 1, "key_value": right, "supporting_text": self._caption_for_role(concept, 1), "visual_role": "change", "suggested_component": "SplitComparison"},
                {"beat_position": 2, "key_value": f"{left} vs {right}", "supporting_text": "gap shown", "visual_role": "result", "suggested_component": "SplitComparison"},
            ]
        else:
            narrative = [
                {"beat_position": 0, "key_value": stages[0]["value"], "supporting_text": self._caption_for_role(concept, 0), "visual_role": "introduce", "suggested_component": component},
                {"beat_position": 1, "key_value": " -> ".join(stage["value"] for stage in stages[:3]) if len(stages) >= 3 else stages[1]["value"], "supporting_text": self._caption_for_role(concept, 1), "visual_role": "change", "suggested_component": component},
                {"beat_position": 2, "key_value": stages[-1]["value"], "supporting_text": self._caption_for_role(concept, 2), "visual_role": "result", "suggested_component": component},
            ]
        return {"visual_narrative": narrative, "overall_structure": "numeric_progression", "story_arc": str(concept.get("scene_goal") or "")}

    def _beats_from_fallback(self, concept: dict[str, Any]) -> list[dict[str, Any]]:
        stages = self.flow_stages(concept)
        if len(stages) < 2:
            return [self._safe_emphasis_beat(concept, str(concept.get("narration") or ""), 0, "no_fallback_stages")]
        return [
            {
                "beat_index": index,
                "beat_type": self._beat_type_for_role(concept, index, self._role_for_index(index)),
                "content": stage["value"],
                "caption": self._caption_for_role(concept, index),
                "color": self.ROLE_COLORS.get(self._role_for_index(index), "orange"),
                "estimated_start_sec": index * 2.0,
                "estimated_duration_sec": 2.0,
                "concept_metadata": dict(concept),
                "flow_stages": list(stages) if self._beat_type_for_role(concept, index, self._role_for_index(index)) == "flow_diagram" else None,
            }
            for index, stage in enumerate(stages)
        ]

    def _values_from_logic(self, logic: Any) -> list[str]:
        if not isinstance(logic, dict):
            return []
        if logic.get("type") == "comparison":
            return [str(logic.get("left") or ""), str(logic.get("right") or "")]
        if logic.get("type") == "flow":
            return [str(logic.get("source") or ""), str(logic.get("result") or "")]
        if logic.get("type") in {"decay", "growth"}:
            return [str(logic.get("input") or ""), str(logic.get("output") or "")]
        if logic.get("type") == "emphasis":
            return [str(logic.get("headline") or ""), str(logic.get("subtext") or "")]
        return []

    def _values_from_text(self, text: str) -> list[str]:
        tokens = self.render_specs._money_tokens(text) + self.render_specs._percent_tokens(text)
        if tokens:
            return list(dict.fromkeys(tokens))
        return re.findall(r"\b\d+(?:\.\d+)?\b", text)

    def _numeric_value(self, value: str, concept: dict[str, Any], index: int) -> str:
        cleaned = self._clean_phrase(value, "")
        if cleaned and self._has_gravity(cleaned) and not self._is_sentence(cleaned):
            return self._primary_number_from_text(cleaned) or cleaned
        stages = self.flow_stages(concept)
        if index < len(stages):
            return self._primary_number_from_text(stages[index]["value"]) or stages[index]["value"]
        return self._first_number_from_context(str(concept.get("narration") or ""), concept) or self._dynamic_fallback_number(str(concept.get("narration") or ""))

    def _primary_content_for_index(self, concept: dict[str, Any], narration: str, index: int, requested: str = "") -> str:
        concept_type = self._concept_type(concept)
        if concept_type == "comparison":
            return self._comparison_content_for_index(concept, narration, index)
        stages = self.flow_stages(concept, narration)
        if index < len(stages):
            primary = self._primary_number_from_text(str(stages[index].get("value") or ""))
            if primary:
                return primary
        primary = self._primary_number_from_text(requested)
        if primary:
            return primary
        if index == 1 and len(stages) >= 3:
            return self._primary_number_from_text(str(stages[1].get("value") or "")) or str(stages[1].get("value") or "")
        return self._numeric_value(requested, concept, index)

    def _comparison_content_for_index(self, concept: dict[str, Any], narration: str, index: int) -> str:
        values = self._comparison_values(concept, narration)
        if len(values) >= 2:
            left, right = values[0], values[1]
            if index == 0:
                return self._primary_number_from_text(left) or left
            if index == 1:
                return self._primary_number_from_text(right) or right
            return f"{left} vs {right}"
        return self._first_number_from_context(narration, concept) or self._dynamic_fallback_number(narration)

    def _comparison_values(self, concept: dict[str, Any], narration: str) -> list[str]:
        values = self._values_from_text(str(concept.get("transformation") or ""))
        if len(values) >= 2:
            return values[:2]
        amounts = self.render_specs._money_tokens(narration)
        percents = self.render_specs._percent_tokens(narration)
        values = amounts + percents
        if len(values) >= 2:
            return values[:2]
        stages = self.flow_stages(concept, narration)
        return [str(stage.get("value") or "") for stage in stages[:2] if str(stage.get("value") or "").strip()]

    def _supporting_idea_for_index(self, concept: dict[str, Any], narration: str, index: int, requested: str = "") -> str:
        requested_clean = self._clean_supporting_text(requested, concept) if str(requested or "").strip() else ""
        if requested_clean and not self._generic_caption(requested_clean):
            return requested_clean
        stages = self.flow_stages(concept, narration)
        if index < len(stages):
            idea = self._supporting_idea_from_value(str(stages[index].get("value") or ""), str(stages[index].get("label") or ""))
            semantic = self._semantic_label_for_index(concept, narration, index)
            if semantic and (not idea or idea.lower() in {"start", "change", "result", "day"}):
                return semantic
            if idea:
                return idea
        semantic = self._semantic_label_for_index(concept, narration, index)
        if semantic:
            return semantic
        return self._caption_for_role(concept, index)

    def _semantic_label_for_index(self, concept: dict[str, Any], narration: str, index: int) -> str:
        lowered = f"{narration} {concept.get('scene_goal', '')} {concept.get('transformation', '')}".lower()
        concept_type = self._concept_type(concept)
        if concept_type == "growth":
            return ["Invested", "Growth", "Final Value", "Wealth"][min(index, 3)]
        if "month" in lowered and "year" in lowered:
            return ["Monthly", "12 Months", "Yearly Loss", "Total"][min(index, 3)]
        if "salary" in lowered and index == 0:
            return "Salary"
        if any(word in lowered for word in ("leak", "lost", "loss", "gone", "vanish", "inflation")) and index == 1:
            return "Leak" if "leak" in lowered else ("Day" if "day" in lowered else "Loss")
        if any(word in lowered for word in ("left", "leaves", "save", "saving", "savings", "vanish", "gone")) and index == 2:
            return "Left" if any(word in lowered for word in ("left", "leaves", "vanish", "gone")) else "Saved"
        return ""

    def _supporting_idea_from_value(self, value: str, label: str = "") -> str:
        cleaned = re.sub(r"₹\s?[\d,.]+(?:\s?(?:lakhs?|crores?|k|m)\b)?", " ", str(value or ""), flags=re.I)
        cleaned = re.sub(r"\d+(?:\.\d+)?%", " ", cleaned)
        cleaned = re.sub(r"\b\d+(?:\.\d+)?\b", " ", cleaned)
        words = [word for word in re.findall(r"[A-Za-z]+", cleaned) if word.lower() not in {"per", "month", "year", "years", "change"}]
        if words:
            return " ".join(words[:3]).title()
        label = str(label or "").strip()
        if label and label.lower() not in {"start", "change", "result", "number", "impact"}:
            return label.title()
        return ""

    def _primary_number_from_text(self, text: str) -> str:
        text = str(text or "")
        money = self.render_specs._money_tokens(text)
        if money:
            return money[0]
        percents = self.render_specs._percent_tokens(text)
        if percents:
            return percents[0]
        day = re.search(r"\bday\s*\d+\b", text, re.I)
        if day:
            return day.group(0).title()
        number = re.search(r"\b\d+(?:\.\d+)?\b", text)
        return number.group(0) if number else ""

    def _numeric_token_count(self, text: str) -> int:
        text = str(text or "")
        money = self.render_specs._money_tokens(text)
        percent = self.render_specs._percent_tokens(text)
        stripped = text
        for token in money + percent:
            stripped = stripped.replace(token, " ")
        bare = re.findall(r"\b\d+(?:\.\d+)?\b", stripped)
        return len(money) + len(percent) + len(bare)

    def _generic_caption(self, text: str) -> bool:
        lowered = " ".join(str(text or "").lower().split())
        return lowered in {
            "start value",
            "change step",
            "result value",
            "loss step",
            "growth step",
            "final value",
            "left value",
            "right value",
            "gap shown",
            "key number",
            "impact number",
            "main stat",
            "numeric change",
        } or self._contains_banned(lowered) or self._contains_label_banned(lowered)

    def _progression_content(self, concept: dict[str, Any]) -> str:
        stages = self.flow_stages(concept)
        if len(stages) < 2:
            return self._first_number_from_context(str(concept.get("narration") or ""), concept) or self._dynamic_fallback_number(str(concept.get("narration") or ""))
        return f"{stages[0]['value']} -> {stages[-1]['value']}"

    def _supports_scene_goal(self, beat: dict[str, Any], concept: dict[str, Any]) -> bool:
        text = f"{beat.get('content', '')} {beat.get('caption', '')}"
        if not self._has_gravity(text):
            return False
        if self._contains_label_banned(text):
            return False
        goal_keywords = self.render_specs._meaningful_keywords(str(concept.get("scene_goal") or ""))
        beat_keywords = self.render_specs._meaningful_keywords(f"{text} {concept.get('transformation', '')}")
        return not goal_keywords or bool(goal_keywords & beat_keywords) or self._content_number_in_concept(str(beat.get("content") or ""), concept)

    def _goal_supporting_beat(self, beat: dict[str, Any], concept: dict[str, Any], index: int) -> dict[str, Any]:
        current = dict(beat)
        current["beat_type"] = str(current.get("beat_type") or "flow_diagram")
        current["content"] = self._numeric_value(str(current.get("content") or ""), concept, index)
        current["caption"] = self._caption_from_concept(concept)
        current["concept_metadata"] = dict(concept)
        return current

    def _alternate_beat_type(self, beat_type: str, seen_types: set[str], concept: dict[str, Any]) -> str:
        if "flow_diagram" not in seen_types:
            return "flow_diagram"
        if str(concept.get("concept_type")) == "comparison" and "split_comparison" not in seen_types:
            return "split_comparison"
        if "stat_explosion" not in seen_types:
            return "stat_explosion"
        return "text_burst"

    def _concept_type(self, concept: dict[str, Any]) -> str:
        raw = str(concept.get("concept_type") or "").strip().lower()
        if raw == "process":
            return "flow"
        if raw in {"decay", "growth", "comparison", "flow", "emphasis"}:
            return raw
        start = numeric_amount(str(concept.get("start_value") or ""))
        end = numeric_amount(str(concept.get("end_value") or ""))
        if start > 0 and end >= 0:
            return "growth" if end > start else "decay"
        return "emphasis"

    def _infer_concept_type(self, narration: str, logic_type: str) -> str:
        lowered = str(narration or "").lower()
        if re.search(r"\b(vs|versus|compared|less than|more than)\b", lowered):
            if "cannot" not in lowered and "can't" not in lowered:
                return "comparison"
        if any(word in lowered for word in ("sip", "compound", "invest", "return", "growth", "increase", "accumulate", "wealth")):
            return "growth"
        if any(word in lowered for word in ("inflation", "leak", "lost", "loss", "vanish", "gone", "debt", "interest", "decrease")):
            return "decay"
        if str(logic_type).lower() == "comparison":
            return "comparison"
        if str(logic_type).lower() == "emphasis":
            return "emphasis"
        return "flow"

    def _beat_type_for_role(self, concept: dict[str, Any], index: int, role: str) -> str:
        concept_type = self._concept_type(concept)
        if concept_type == "comparison":
            return "split_comparison"
        if concept_type == "emphasis":
            return "stat_explosion"
        return "flow_diagram"

    def _enforced_beat_type(self, requested: str, concept: dict[str, Any], role: str, index: int) -> str:
        expected = self._beat_type_for_role(concept, index, role)
        requested = str(requested or "").lower()
        if requested != expected and requested != "text_burst":
            return expected
        return requested or expected

    def _beat_is_valid(self, beat: dict[str, Any], concept: dict[str, Any], narration: str) -> tuple[bool, str]:
        content = str(beat.get("content") or "")
        caption = str(beat.get("caption") or "")
        if not self._has_gravity(content):
            return False, "content_missing_number"
        if not content.strip():
            return False, "empty_content"
        if not caption.strip() or self._contains_banned(caption) or self._contains_label_banned(caption):
            return False, "vague_caption"
        if not self._visual_simplification_valid(beat, concept):
            return False, "too_many_primary_numbers"
        if not self._beat_matches_concept_type(beat, concept):
            return False, "concept_component_mismatch"
        # RULE 5 — Meaningful contrast only
        if self._concept_type(concept) in {"comparison", "emphasis"} and not self._has_required_contrast(beat, concept, narration):
            return False, "missing_contrast"
        if not self._numbers_allowed_by_narration([content], narration):
            return False, "number_not_from_narration_or_derivation"
        concept_type = self._concept_type(concept)
        if beat.get("beat_type") == "flow_diagram":
            stages = beat.get("flow_stages") if isinstance(beat.get("flow_stages"), list) else self.flow_stages(concept, narration)
            if len(stages) < 3:
                return False, "flow_missing_start_change_result"
            valid, reason = validate_numbers(stages[0]["value"], stages[1]["value"], stages[-1]["value"], concept_type, narration)
            if not valid:
                return False, reason
            if not self._numbers_allowed_by_narration([stage["value"] for stage in stages], narration):
                return False, "flow_number_not_supported"
            # RULE 6 — Real transformation: reject identical start/change/end
            if not self._flow_has_real_transformation(stages):
                return False, "fake_transformation"
            # RULE 7 — Flow change rule: middle stage must show measurable change
            if not self._flow_middle_has_change(stages):
                return False, "flow_middle_no_change"
        return True, "valid"

    def _visual_simplification_valid(self, beat: dict[str, Any], concept: dict[str, Any]) -> bool:
        count = self._numeric_token_count(str(beat.get("content") or ""))
        if self._concept_type(concept) == "comparison" and int(beat.get("beat_index") or 0) >= 2:
            return count <= 2
        return count <= 1

    def _beat_matches_concept_type(self, beat: dict[str, Any], concept: dict[str, Any]) -> bool:
        beat_type = str(beat.get("beat_type") or "").lower()
        concept_type = self._concept_type(concept)
        strict = self.STRICT_COMPONENT_BY_CONCEPT.get(concept_type, "flow_diagram")
        if beat_type == strict:
            return True
        # Also accept types from visual_verb component mapping (SceneDirector sequences)
        visual_verb = str(concept.get("visual_verb") or "")
        if visual_verb and visual_verb in SceneDirector.VERB_COMPONENT_MAP:
            return beat_type in SceneDirector.VERB_COMPONENT_MAP[visual_verb]
        # text_burst is always acceptable as a final/punch beat
        return beat_type == "text_burst"

    def _has_required_contrast(self, beat: dict[str, Any], concept: dict[str, Any], narration: str) -> bool:
        concept_type = self._concept_type(concept)
        if concept_type == "comparison":
            return len(self._comparison_values(concept, narration)) >= 2 or bool(re.search(r"\bvs\b|\bversus\b", str(beat.get("content") or ""), re.I))
        if concept_type == "emphasis":
            numbers = self.render_specs._money_tokens(narration) + self.render_specs._percent_tokens(narration)
            return len(set(numbers)) >= 2 or self._numeric_token_count(str(beat.get("content") or "")) == 1
        return True

    def _simplify_beat(self, beat: dict[str, Any], concept: dict[str, Any], narration: str, index: int) -> dict[str, Any]:
        current = dict(beat)
        role = self._role_for_index(index)
        current["beat_index"] = index
        current["beat_type"] = self._beat_type_for_role(concept, index, role)
        current["content"] = self._primary_content_for_index(concept, narration, index, str(current.get("content") or ""))
        current["caption"] = self._supporting_idea_for_index(concept, narration, index, str(current.get("caption") or ""))
        current["concept_metadata"] = dict(concept)
        if current["beat_type"] == "flow_diagram":
            current["flow_stages"] = list(self.flow_stages(concept, narration))
        return current

    # ------------------------------------------------------------------
    # RULE 6 — Real transformation check
    # ------------------------------------------------------------------

    def _flow_has_real_transformation(self, stages: list[dict[str, str]]) -> bool:
        """Reject flows where all stages show the same value (e.g. ₹5000 → ₹5000 → ₹5000)."""
        if len(stages) < 3:
            return False
        values = [numeric_amount(stage["value"]) for stage in stages]
        # If all numeric values are identical and non-zero, it's fake
        if values[0] > 0 and values[0] == values[1] == values[2]:
            return False
        return True

    # ------------------------------------------------------------------
    # RULE 7 — Flow middle must show measurable change
    # ------------------------------------------------------------------

    def _flow_middle_has_change(self, stages: list[dict[str, str]]) -> bool:
        """Middle stage must show measurable change (time, %, amount difference)."""
        if len(stages) < 3:
            return False
        middle = stages[1]["value"].lower()
        # Accept if middle contains: time reference, percentage, or a numeric value
        if re.search(r"(day|month|year|week|%|\d+\s*months?|\d+\s*years?)", middle, re.I):
            return True
        # Accept if middle has a numeric value different from start
        middle_amount = numeric_amount(middle)
        start_amount = numeric_amount(stages[0]["value"])
        if middle_amount > 0 and middle_amount != start_amount:
            return True
        # Accept descriptive change labels (e.g. "leak", "growth", "spend")
        change_words = {"leak", "loss", "growth", "spend", "saved", "change", "inflation", "interest"}
        if any(w in middle for w in change_words):
            return True
        return False

    # ------------------------------------------------------------------
    # RULE 8 — Fragmented beat check
    # ------------------------------------------------------------------

    def _is_fragmented(self, beat: dict[str, Any]) -> bool:
        """Reject single-word meaningless beats. Each beat must be self-contained."""
        content = str(beat.get("content") or "").strip()
        caption = str(beat.get("caption") or "").strip()
        # A beat with no numbers and only one word is fragmented
        if not self._has_gravity(content) and len(content.split()) <= 1:
            return True
        # Caption must exist
        if not caption:
            return True
        return False

    # ------------------------------------------------------------------
    # RULE 13 — Overloaded beat check
    # ------------------------------------------------------------------

    def _is_overloaded(self, beat: dict[str, Any]) -> bool:
        """Each beat must be understandable in 2 seconds. Reject if too many tokens."""
        content = str(beat.get("content") or "")
        caption = str(beat.get("caption") or "")
        # More than 2 numeric tokens in content = overloaded (RULE 3: one idea per beat)
        if self._numeric_token_count(content) > 2:
            return True
        # Caption too long to read in 2 seconds
        if len(caption.split()) > 8:
            return True
        return False

    # ------------------------------------------------------------------
    # RULE 11 — Visual rhythm enforcement
    # ------------------------------------------------------------------

    def _enforce_visual_rhythm(self, beats: list[dict[str, Any]], concept: dict[str, Any], narration: str) -> list[dict[str, Any]]:
        """Ensure at least 2 different component types. Convert middle beat if all same."""
        if len(beats) < 2:
            return beats
        unique_types = {beat["beat_type"] for beat in beats}
        if len(unique_types) >= 2:
            return beats

        # All beats are the same type — convert middle beat
        concept_type = self._concept_type(concept)
        mid_index = len(beats) // 2
        current_type = beats[mid_index]["beat_type"]

        if current_type == "stat_explosion":
            new_type = "flow_diagram" if concept_type != "emphasis" else "text_burst"
        elif current_type == "flow_diagram":
            new_type = "split_comparison" if concept_type == "comparison" else "stat_explosion"
        else:
            new_type = "stat_explosion"

        beats[mid_index] = dict(beats[mid_index])
        beats[mid_index]["beat_type"] = new_type
        if new_type == "flow_diagram":
            beats[mid_index]["flow_stages"] = list(self.flow_stages(concept, narration))
        return beats

    # ------------------------------------------------------------------
    # RULES 14-18 — Semantic Sharpness helpers
    # ------------------------------------------------------------------

