from __future__ import annotations

import json
import re
from typing import Any

from .scene_builder_constants import PATTERN_PRIORITY, REQUIRED_BEAT_DATA, TEXT_COMPONENTS


class SceneBuilderContractMixin:
    def _visual_field(self, section: dict[str, Any], key: str) -> Any:
        visual_plan = section.get("visual_plan") or []
        if not visual_plan:
            return None
        visual = visual_plan[0].get("visual") or {}
        return visual.get(key)

    def _scene_visual_contract(self, section: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
        visual_plan = section.get("visual_plan") or []
        best_pattern = ""
        best_data: dict[str, Any] = {}
        best_concept = ""
        best_score = -1

        if visual_plan:
            for item in visual_plan:
                visual = item.get("visual") or {}
                pattern = str(visual.get("pattern") or "").strip()
                data = self._normalize_data_dict(visual.get("data"))
                if not data:
                    data = self._data_from_matching_beat(item, pattern)
                concept = str((item.get("concept") or {}).get("concept") or "").strip()
                pattern, data, concept = self._upgrade_generic_finance_pattern(pattern, data, concept, section)
                score = PATTERN_PRIORITY.get(pattern, 0)
                if pattern and data and concept and score > best_score:
                    best_pattern = pattern
                    best_data = data
                    best_concept = concept
                    best_score = score

            if best_pattern:
                if best_pattern in TEXT_COMPONENTS | {"NumericComparison"} and best_data.get("cinematic_events"):
                    return "UniversalMechanismRenderer", self._enrich_data_with_section("UniversalMechanismRenderer", best_data, section), best_concept
                return best_pattern, self._enrich_data_with_section(best_pattern, best_data, section), best_concept

            inferred = self._infer_contract_from_visual_plan(visual_plan)
            if inferred is not None:
                pattern, data, concept = inferred
                pattern, data, concept = self._upgrade_generic_finance_pattern(pattern, data, concept, section)
                return pattern, self._enrich_data_with_section(pattern, data, section), concept
        fallback_text = self._fallback_text(str(section.get("text") or ""))
        return "ConceptCard", {"title": fallback_text.upper()}, fallback_text

    def _upgrade_generic_finance_pattern(
        self,
        pattern: str,
        data: dict[str, Any],
        concept: str,
        section: dict[str, Any],
    ) -> tuple[str, dict[str, Any], str]:
        mechanism = str(
            data.get("mechanism")
            or section.get("concept_type")
            or ((section.get("visual_scene") or {}).get("mechanism") if isinstance(section.get("visual_scene"), dict) else "")
            or ""
        ).strip().lower()
        combined = " ".join(
            str(value or "")
            for value in [
                concept,
                section.get("text"),
                section.get("narration"),
                section.get("visual_instruction"),
                section.get("visual_intent"),
            ]
        ).lower()
        if pattern in {"SplitComparison", "SplitComparisonScene"} and (
            mechanism == "risk_return"
            or "risk vs return" in combined
            or ("risk" in combined and "return" in combined and any(token in combined for token in ("fd", "equity", "volatility", "upside")))
        ):
            upgraded = dict(data)
            upgraded.setdefault("safe_asset", "FD")
            upgraded.setdefault("growth_asset", "Equity")
            upgraded.setdefault("safe_rate", self._first_percent(combined) or "6%")
            upgraded.setdefault("growth_rate", "12%")
            upgraded.setdefault("mechanism", "risk_return")
            return "RiskReturnVisualizer", upgraded, concept or "Risk vs Return"
        return pattern, data, concept

    def _first_percent(self, text: str) -> str:
        match = re.search(r"\d+(?:\.\d+)?\s*%", text)
        return match.group(0).replace(" ", "") if match else ""

    def _infer_contract_from_visual_plan(self, visual_plan: list[dict[str, Any]]) -> tuple[str, dict[str, Any], str] | None:
        best: tuple[str, dict[str, Any], str] | None = None
        best_score = -1
        for item in visual_plan:
            inferred = self._infer_contract_from_beats(item)
            if inferred is None:
                continue
            pattern, _, _ = inferred
            score = PATTERN_PRIORITY.get(pattern, 0)
            if score > best_score:
                best = inferred
                best_score = score
        return best

    def _infer_contract_from_beats(self, item: dict[str, Any]) -> tuple[str, dict[str, Any], str] | None:
        beats = ((item.get("beats") or {}).get("beats") or [])
        if not beats:
            return None
        last_beat = beats[-1]
        component = str(last_beat.get("component") or "").strip()
        concept = str(last_beat.get("text") or "").strip()
        if not component or not concept:
            return None
        if component == "RiskCard":
            return "RiskCard", {"title": concept.upper()}, concept
        if component == "SplitComparison":
            return "SplitComparison", {"headline": concept}, concept
        if component == "StepFlow":
            return "StepFlow", {"steps": [concept]}, concept
        if component == "GrowthChart":
            return "GrowthChart", {"end": concept, "curve": "up"}, concept
        values = [str(beat.get("text") or "").strip() for beat in beats if str(beat.get("text") or "").strip()]
        if component in {"RiskReturnVisualizer", "EmergencyFundVisualizer", "OutroRecapVisualizer"}:
            data = self._data_from_matching_beat(item, component)
            if data:
                return component, data, concept
        if component == "CalculationStrip":
            flat_steps: list[Any] = []
            for beat in beats:
                data = self._normalize_data_dict(beat.get("data"))
                steps = data.get("steps") or beat.get("steps") or []
                if isinstance(steps, list):
                    flat_steps.extend(steps)
            if flat_steps:
                return "CalculationStrip", {"steps": flat_steps}, concept
            return "CalculationStrip", {"values": values}, concept
        if component == "StatCard":
            return "NumericComparison", {"values": values}, concept
        return "ConceptCard", {"title": concept.upper()}, concept

    def _enrich_data_with_section(self, pattern: str, data: dict[str, Any], section: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(data)
        finance_concept = section.get("finance_concept") or {}
        narrative_arc = section.get("narrative_arc") or {}
        state = section.get("state") or {}

        start_value = self._first_text_value(finance_concept.get("start_value"), narrative_arc.get("start_state"), state.get("money_in"))
        end_value = self._first_text_value(finance_concept.get("end_value"), narrative_arc.get("end_state"), state.get("balance_change"))
        rate = self._first_text_value(narrative_arc.get("rate"), state.get("money_out"), self._percentage_text(finance_concept.get("percentage")))

        if pattern == "NumericComparison":
            values = [str(value).strip() for value in enriched.get("values") or [] if str(value).strip()]
            values = self._append_unique_values(values, [start_value, rate, end_value])
            if values:
                enriched["values"] = values[:3]
            if start_value and not enriched.get("start"):
                enriched["start"] = start_value
            if rate and not enriched.get("rate"):
                enriched["rate"] = rate
            if end_value and not enriched.get("end"):
                enriched["end"] = end_value
        elif pattern == "GrowthChart":
            if start_value and not enriched.get("start"):
                enriched["start"] = start_value
            if end_value and not enriched.get("end"):
                enriched["end"] = end_value
            if rate and not enriched.get("rate"):
                enriched["rate"] = rate
        elif pattern in {"RiskCard", "ConceptCard"}:
            if rate and not enriched.get("subtitle"):
                enriched["subtitle"] = f"{rate} impact"
            if end_value and not enriched.get("value"):
                enriched["value"] = end_value
            if state and not enriched.get("state"):
                enriched["state"] = dict(state)
        elif pattern == "SplitComparison":
            if start_value and not enriched.get("left"):
                enriched["left"] = {"label": start_value}
            if end_value and not enriched.get("right"):
                enriched["right"] = {"label": end_value}
            if rate and not enriched.get("rate"):
                enriched["rate"] = rate
        elif pattern == "RiskReturnVisualizer":
            if rate and not enriched.get("safe_rate"):
                enriched["safe_rate"] = rate
            enriched.setdefault("safe_asset", "FD")
            enriched.setdefault("growth_asset", "Equity")
            enriched.setdefault("growth_rate", "12%")
        elif pattern == "StepFlow":
            steps = [str(step).strip() for step in enriched.get("steps") or [] if str(step).strip()]
            if not enriched.get("steps"):
                enriched["steps"] = self._append_unique_values(steps, [start_value, rate, end_value]) or steps

        visual_type = str(section.get("visual_type") or narrative_arc.get("visual_type") or "").strip()
        if visual_type and not enriched.get("visual_type"):
            enriched["visual_type"] = visual_type
        return enriched

    def _clean_and_dedupe_beats(self, beats: list[dict[str, Any]], section_text: str) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        seen_texts: set[str] = set()
        for beat in beats:
            text = self._clean_beat_text(str(beat.get("text") or "").strip(), section_text)
            if not text:
                continue
            key = text.lower()
            if key in seen_texts:
                continue
            seen_texts.add(key)
            cleaned_beat: dict[str, Any] = {
                "component": str(beat.get("component") or "").strip() or "ConceptCard",
                "text": text,
            }
            for extra_key in ("subtext", "steps", "props", "source_text", "sentence_index", "beat_role", "beat_phase", "emphasis"):
                if extra_key in beat:
                    cleaned_beat[extra_key] = beat[extra_key]
            data = self._normalize_data_dict(beat.get("data"))
            if data:
                cleaned_beat["data"] = data
            cleaned.append(cleaned_beat)
        return cleaned

    def _normalize_data_dict(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError, json.JSONDecodeError):
                return {}
            return dict(parsed) if isinstance(parsed, dict) else {}
        return {}

    def _data_from_matching_beat(self, item: dict[str, Any], pattern: str) -> dict[str, Any]:
        if not pattern:
            return {}
        beats = (item.get("beats") or {}).get("beats") or []
        for beat in beats:
            if str(beat.get("component") or "").strip() == pattern:
                data = self._normalize_data_dict(beat.get("data"))
                if data:
                    return data
        return {}

    def _validate_beat_data(self, beats: list[dict[str, Any]]) -> list[str]:
        warnings: list[str] = []
        for index, beat in enumerate(beats):
            component = str(beat.get("component") or "").strip()
            required_fields = REQUIRED_BEAT_DATA.get(component)
            if not required_fields:
                continue
            data = self._normalize_data_dict(beat.get("data"))
            if not data:
                warnings.append(f"beat {index}: {component} has no data dict")
                continue
            for field in required_fields:
                if field not in data:
                    warnings.append(f"beat {index}: {component} missing required data field '{field}'")
        return warnings

    def _text_dominance_warning(self, beats: list[dict[str, Any]], scene_kind: str) -> str:
        if scene_kind.lower() in {"hook", "outro"} or not beats:
            return ""
        total_duration = sum(max(float(beat.get("end_time") or 0.0) - float(beat.get("start_time") or 0.0), 0.0) for beat in beats)
        if total_duration <= 0:
            return ""
        text_duration = sum(
            max(float(beat.get("end_time") or 0.0) - float(beat.get("start_time") or 0.0), 0.0)
            for beat in beats
            if str(beat.get("component") or "") in TEXT_COMPONENTS
        )
        text_ratio = text_duration / total_duration
        if text_ratio <= 0.40:
            return ""
        components = [str(beat.get("component") or "") for beat in beats]
        return f"text components occupy {text_ratio:.0%} of scene duration; beats={components}"
