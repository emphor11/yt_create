from __future__ import annotations

import re
from typing import Any


class VisualBeatExpander:
    """Adds enough visual beats for longer narration without changing the scene concept."""

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
            beat = {
                "component": component,
                "text": self._beat_text(sentence, mechanism, is_last),
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
            if any(beat.get("component") == component for beat in result):
                continue
            original_beat = next((beat for beat in original if beat.get("component") == component), None)
            if not original_beat:
                continue
            preserved = dict(original_beat)
            preserved.setdefault("source_text", preserved.get("text") or component)
            insert_at = min(2, len(result))
            result.insert(insert_at, preserved)
        return self._dedupe_adjacent(result[:9])

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
