from __future__ import annotations

import re
from typing import Any


class VisualBeatExpander:
    """Adds enough visual beats for longer narration without changing the scene concept."""

    OBJECT_TO_VIEWER_TEXT = {
        "phone_account": "Money hits the account",
        "salary_balance": "Salary lands",
        "emi_stack": "Fixed payments stack up",
        "debt_pressure": "Debt starts compounding",
        "inflation_basket": "Buying power starts shrinking",
        "sip_jar": "Compounding starts working",
        "portfolio_grid": "Risk gets distributed",
        "emergency_buffer": "Safety net absorbs the shock",
    }

    def expand_section(self, section: dict[str, Any]) -> dict[str, Any]:
        visual_plan = section.get("visual_plan") or []
        if not visual_plan:
            return section

        item = visual_plan[0]
        beats = list(((item.get("beats") or {}).get("beats") or []))
        text = str(section.get("text") or "")
        sentences = self._sentences(text)
        target = self._target_beat_count(text, sentences)
        if len(beats) >= target or target <= 3:
            return section

        visual = item.get("visual") or {}
        pattern = str(visual.get("pattern") or "").strip()
        concept = item.get("concept") or {}
        mechanism = str(section.get("concept_type") or (concept.get("type") if isinstance(concept, dict) else "") or "").strip()
        data = visual.get("data") if isinstance(visual.get("data"), dict) else {}
        story_state = section.get("story_state") if isinstance(section.get("story_state"), dict) else {}
        story_beats = self._beats_from_story_state(
            story_state=story_state,
            mechanism=mechanism,
            pattern=pattern,
            data=data,
            fallback_beats=beats,
            target=target,
        )
        if story_beats:
            expanded = story_beats
        else:
            expanded = self._beats_from_sentences(
                sentences=sentences,
                mechanism=mechanism,
                pattern=pattern,
                data=data,
                target=target,
                fallback_beats=beats,
            )
        expanded = self._preserve_directed_beats(expanded, beats, pattern, mechanism)
        if len(expanded) <= len(beats):
            return section

        updated_item = dict(item)
        updated_item["beats"] = {"beats": expanded}
        updated_section = dict(section)
        updated_section["visual_plan"] = [updated_item, *visual_plan[1:]]
        return updated_section

    def _beats_from_story_state(
        self,
        *,
        story_state: dict[str, Any],
        mechanism: str,
        pattern: str,
        data: dict[str, Any],
        fallback_beats: list[dict[str, Any]],
        target: int,
    ) -> list[dict[str, Any]]:
        if not story_state:
            return []
        state_change = story_state.get("state_change") or {}
        money = state_change.get("money") if isinstance(state_change.get("money"), dict) else {}
        active_objects = [str(obj) for obj in (story_state.get("active_objects") or []) if str(obj)]
        visual_answer = str(story_state.get("visual_answer") or "").strip()
        visual_question = str(story_state.get("visual_question") or "").strip()
        texts = [
            self._object_setup_text(active_objects, money),
            str(money.get("change_label") or "").strip(),
            self._mechanism_text(pattern, mechanism),
            visual_question,
            visual_answer,
        ]
        texts = [self._sanitize_viewer_text(text) for text in texts if text]
        texts = [text for text in texts if text]
        if len(texts) < target:
            for fallback in self._fallback_texts(fallback_beats, target - len(texts)):
                sanitized = self._sanitize_viewer_text(fallback)
                if sanitized and sanitized not in texts:
                    texts.append(sanitized)
                if len(texts) >= target:
                    break
        if len(texts) < 3:
            return []
        beats: list[dict[str, Any]] = []
        for index, text in enumerate(texts[: max(3, min(target, 7))]):
            is_first = index == 0
            is_last = index == min(len(texts), max(3, min(target, 7))) - 1
            component = self._story_component_for(index, is_first, is_last, pattern, mechanism)
            beat: dict[str, Any] = {
                "component": component,
                "text": text,
                "source_text": text,
                "sentence_index": index,
                "data": {"story_state": story_state, **data} if data else {"story_state": story_state},
            }
            if component in {"FlowDiagram", "FlowBar", "GrowthChart"} and data:
                beat["props"] = data
            beats.append(beat)
        return self._dedupe_adjacent(beats)

    def _story_component_for(self, index: int, is_first: bool, is_last: bool, pattern: str, mechanism: str) -> str:
        if is_first:
            return "StatCard"
        if is_last:
            return "HighlightText"
        if index == 2 and pattern in {"MoneyFlowDiagram", "FlowDiagram"}:
            return "FlowDiagram"
        if index == 2 and pattern in {"DebtSpiralVisualizer", "CalculationStrip"}:
            return "CalculationStrip"
        if index == 2 and pattern in {"GrowthChart", "SIPGrowthEngine"}:
            return "GrowthChart"
        if index == 2 and pattern == "SplitComparison":
            return "SplitComparison"
        return self._component_for("", index, is_first, is_last, pattern, mechanism)

    def _object_setup_text(self, active_objects: list[str], money: dict[str, Any]) -> str:
        primary = active_objects[0] if active_objects else ""
        label = self.OBJECT_TO_VIEWER_TEXT.get(primary, "")
        amount = str(money.get("from") or "").strip()
        if amount and label:
            return f"{amount} - {label}"
        if amount:
            return amount
        if label:
            return label
        return primary.replace("_", " ").title() if primary else ""

    def _mechanism_text(self, pattern: str, mechanism: str) -> str:
        if pattern == "MoneyFlowDiagram":
            return "Money path becomes visible"
        if pattern == "DebtSpiralVisualizer":
            return "Interest beats payment"
        if pattern == "SIPGrowthEngine":
            return "Compounding engine starts"
        if pattern == "GrowthChart":
            return "Value path changes"
        if pattern == "SplitComparison":
            return "Two paths separate"
        return mechanism.replace("_", " ").title()

    def _sanitize_viewer_text(self, text: str) -> str:
        clean = " ".join(str(text or "").replace("_", " ").split()).strip()
        if not clean:
            return ""
        lowered = clean.lower()
        if lowered == "state changes":
            return ""
        internal_map = {
            "phone account": "Money hits the account",
            "salary balance": "Salary lands",
            "emi stack": "Fixed payments stack up",
            "debt pressure": "Debt starts compounding",
            "inflation basket": "Buying power starts shrinking",
            "sip jar": "Compounding starts working",
            "portfolio grid": "Risk gets distributed",
            "emergency buffer": "Safety net absorbs the shock",
        }
        return internal_map.get(lowered, clean)

    def _target_beat_count(self, text: str, sentences: list[str]) -> int:
        words = len(text.split())
        sentence_target = max(len(sentences), 1)
        if words >= 70:
            word_target = 8
        elif words >= 55:
            word_target = 7
        elif words >= 40:
            word_target = 6
        elif words >= 26:
            word_target = 5
        elif words >= 16:
            word_target = 4
        else:
            word_target = 3
        return max(3, min(9, max(sentence_target, word_target)))

    def _beats_from_sentences(
        self,
        *,
        sentences: list[str],
        mechanism: str,
        pattern: str,
        data: dict[str, Any],
        target: int,
        fallback_beats: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        selected = sentences[:target]
        if len(selected) < target:
            selected.extend(self._fallback_texts(fallback_beats, target - len(selected)))
        if not selected:
            return fallback_beats

        beats: list[dict[str, Any]] = []
        for index, sentence in enumerate(selected[:target]):
            is_first = index == 0
            is_last = index == min(target, len(selected)) - 1
            component = self._component_for(sentence, index, is_first, is_last, pattern, mechanism)
            raw_text = self._beat_text(sentence, mechanism, is_last)
            sanitized_text = self._sanitize_viewer_text(raw_text) or raw_text
            beat = {
                "component": component,
                "text": sanitized_text,
                "source_text": sentence,
                "sentence_index": min(index, max(len(sentences) - 1, 0)),
            }
            if component in {"FlowDiagram", "FlowBar"} and data:
                beat["data"] = data
                beat["props"] = data
            if component == "GrowthChart" and data:
                beat["data"] = data
                beat["props"] = data
            if component == "SplitComparison" and data:
                beat["data"] = data
            beats.append(beat)
        return self._dedupe_adjacent(beats)

    def _preserve_directed_beats(
        self,
        expanded: list[dict[str, Any]],
        original: list[dict[str, Any]],
        pattern: str,
        mechanism: str,
    ) -> list[dict[str, Any]]:
        required_components: list[str] = []
        if pattern == "DebtSpiralVisualizer" or mechanism == "debt_trap":
            required_components.append("CalculationStrip")
        if pattern == "SIPGrowthEngine" or mechanism in {"sip_growth", "compounding"}:
            required_components.append("SIPGrowthEngine")
        if pattern == "MoneyFlowDiagram" or mechanism in {"salary_drain", "rent_burden", "tax_drain"}:
            required_components.append("MoneyFlowDiagram")

        result = list(expanded)
        for component in required_components:
            original_beat = next((beat for beat in original if beat.get("component") == component), None)
            existing_index = next((index for index, beat in enumerate(result) if beat.get("component") == component), None)
            if existing_index is not None:
                if original_beat and self._has_component_data(original_beat, component) and not self._has_component_data(result[existing_index], component):
                    merged = dict(result[existing_index])
                    merged["data"] = original_beat.get("data")
                    if original_beat.get("props") is not None:
                        merged["props"] = original_beat.get("props")
                    result[existing_index] = merged
                continue
            if not original_beat:
                continue
            preserved = dict(original_beat)
            preserved.setdefault("source_text", preserved.get("text") or component)
            insert_at = min(2, len(result))
            result.insert(insert_at, preserved)
        return self._dedupe_adjacent(result[:9])

    def _has_component_data(self, beat: dict[str, Any], component: str = "") -> bool:
        data = beat.get("data")
        props = beat.get("props")
        expected_keys = {
            "CalculationStrip": ("steps",),
            "DebtSpiralVisualizer": ("balances", "principal"),
            "MoneyFlowDiagram": ("flows", "source", "remainder"),
            "SIPGrowthEngine": ("monthly_sip", "final_corpus"),
        }.get(component, ("steps", "balances", "flows", "monthly_sip"))
        if isinstance(data, dict) and any(key in data for key in expected_keys):
            return True
        if isinstance(props, dict) and any(key in props for key in expected_keys):
            return True
        return False

    def _component_for(self, sentence: str, index: int, is_first: bool, is_last: bool, pattern: str, mechanism: str) -> str:
        if is_first:
            return "StatCard"
        if is_last:
            return "HighlightText"
        if re.search(r"₹|%|\d", sentence):
            return "StatCard"
        if pattern in {"FlowDiagram", "MoneyFlowDiagram"} or mechanism in {"expense_leakage", "emi_pressure", "lifestyle_inflation", "salary_drain"}:
            return "FlowDiagram" if index in {2, 4} else "StatCard"
        if pattern in {"DebtSpiralVisualizer", "CalculationStrip"} or mechanism == "debt_trap":
            return "CalculationStrip" if index in {2, 4} else "StatCard"
        if pattern in {"GrowthChart", "SIPGrowthEngine"} or mechanism in {"inflation_erosion", "sip_growth", "compounding"}:
            return "GrowthChart" if index in {2, 4} else "StatCard"
        if pattern == "SplitComparison" or mechanism in {"risk_return", "diversification", "speculation_risk"}:
            return "SplitComparison" if index == 2 else "StatCard"
        return "StatCard"

    def _beat_text(self, sentence: str, mechanism: str, is_last: bool) -> str:
        clean = " ".join(sentence.strip().strip(".!?").split())
        lowered = clean.lower()
        money = re.search(r"₹\s?\d[\d,]*(?:\.\d+)?(?:\s*(?:lakh|lakhs|crore|crores|k))?", clean, re.IGNORECASE)
        pct = re.search(r"\d+(?:\.\d+)?\s*%", clean)
        if money:
            tail = self._money_tail(lowered)
            return f"{money.group(0).replace(' ', '')} {tail}".strip()
        if pct:
            return f"{pct.group(0)} {self._percent_tail(lowered)}".strip()
        if is_last:
            return self._consequence_text(clean, mechanism)
        return self._short_phrase(clean)

    def _money_tail(self, lowered: str) -> str:
        for token, label in (
            ("emi", "EMI"),
            ("rent", "rent"),
            ("interest", "interest"),
            ("leaves", "leaves first"),
            ("leak", "leak"),
            ("sip", "SIP"),
            ("invest", "invested"),
            ("salary", "salary"),
        ):
            if token in lowered:
                return label
        return ""

    def _percent_tail(self, lowered: str) -> str:
        if "interest" in lowered:
            return "interest"
        if "return" in lowered:
            return "return"
        if "inflation" in lowered:
            return "inflation"
        return ""

    def _consequence_text(self, clean: str, mechanism: str) -> str:
        if mechanism == "emi_pressure":
            return "Five small payments become one leak"
        if mechanism == "expense_leakage":
            return "The leak is the system"
        if mechanism == "debt_trap":
            return "Interest is still winning"
        if mechanism == "inflation_erosion":
            return "Real value keeps falling"
        if mechanism in {"sip_growth", "compounding"}:
            return "Time does the heavy lifting"
        if mechanism == "speculation_risk":
            return "Do not buy what you cannot explain"
        return self._short_phrase(clean, max_words=6)

    def _short_phrase(self, text: str, max_words: int = 5) -> str:
        words = [word.strip(" ,.-") for word in text.split() if word.strip(" ,.-")]
        if not words:
            return "Key idea"
        phrase = " ".join(words[:max_words])
        return phrase[:1].upper() + phrase[1:]

    def _fallback_texts(self, beats: list[dict[str, Any]], count: int) -> list[str]:
        texts = [str(beat.get("text") or "").strip() for beat in beats if str(beat.get("text") or "").strip()]
        return texts[:count]

    def _sentences(self, text: str) -> list[str]:
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+", str(text or "").strip()) if part.strip()]

    def _dedupe_adjacent(self, beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        previous = ""
        for beat in beats:
            text = str(beat.get("text") or "").lower()
            if text == previous:
                continue
            previous = text
            deduped.append(beat)
        return deduped
