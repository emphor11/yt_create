from __future__ import annotations

import json
import re
from typing import Any

import requests
from flask import current_app

from .render_spec_service import RenderSpecService
from .run_log import RunLogger


def _numeric_amount(text: str) -> float:
    cleaned = str(text or "").lower().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if not match:
        return 0.0
    value = float(match.group(1))
    if "crore" in cleaned:
        return value * 10_000_000
    if "lakh" in cleaned:
        return value * 100_000
    if re.search(r"\bk\b", cleaned):
        return value * 1_000
    return value


def validate_numeric_logic(start: str, process: str, end: str, concept_type: str) -> tuple[bool, str]:
    """Validate visible finance math before a beat can reach rendering."""

    start_value = _numeric_amount(start)
    end_value = _numeric_amount(end)
    process_text = str(process or "").lower()
    concept = "flow" if str(concept_type or "").lower() == "process" else str(concept_type or "").lower()

    if concept == "emphasis":
        return (start_value > 0 or end_value > 0 or bool(re.search(r"\d+(?:\.\d+)?%", f"{start} {end}"))), "emphasis_number"

    if start_value <= 0 or end_value < 0:
        return False, "missing_start_or_end"

    if re.search(r"\b12\s*months?\b|\byear(?:ly)?\b", process_text):
        expected = round(start_value * 12)
        if abs(end_value - expected) > max(1, expected * 0.02):
            return False, "monthly_yearly_math_mismatch"
        return True, "valid_monthly_yearly"

    if concept == "decay" and not end_value < start_value:
        return False, "decay_must_decrease"
    if concept == "growth" and not end_value > start_value:
        return False, "growth_must_increase"

    pct = re.search(r"(\d+(?:\.\d+)?)%", process_text)
    if pct and start_value > 0:
        rate = float(pct.group(1)) / 100.0
        if concept == "growth":
            expected = start_value * (1 + rate)
        else:
            expected = start_value * (1 - rate)
        rate_amount = start_value * rate
        if abs(end_value - expected) > max(2, expected * 0.03) and not (
            concept == "decay" and abs(end_value - rate_amount) <= max(2, rate_amount * 0.03)
        ):
            return False, "percent_math_mismatch"

    if start_value > 0 and end_value / start_value > 100 and not re.search(r"\b(years?|months?|age|%|return|sip)\b", process_text):
        return False, "implausible_jump"
    return True, "valid"


class ConceptService:
    """Build concept-first, numeric visual beats from narration."""

    CONCEPT_TYPES = {"decay", "growth", "comparison", "flow", "emphasis", "process"}
    ROLE_COLORS = {
        "introduce": "teal",
        "change": "orange",
        "result": "red",
        "emotion": "white",
    }
    COMPONENT_TO_BEAT_TYPE = {
        "FlowDiagram": "flow_diagram",
        "SplitComparison": "split_comparison",
        "StatExplosion": "stat_explosion",
        "TextBurst": "text_burst",
    }
    BANNED_WORDS = {
        "concept",
        "idea",
        "thing",
        "system",
        "flow",
        "contrast",
        "wait what",
        "me every payday",
        "reaction",
        "money decreases",
        "expenses increase",
        "financial stress",
        "value changes",
        "money reality",
    }
    BANNED_LABEL_WORDS = {"flow", "concept", "idea", "thing", "system"}
    STRICT_COMPONENT_BY_CONCEPT = {
        "decay": "flow_diagram",
        "growth": "flow_diagram",
        "flow": "flow_diagram",
        "process": "flow_diagram",
        "comparison": "split_comparison",
        "emphasis": "stat_explosion",
    }

    def __init__(self) -> None:
        self.logger = RunLogger()
        self.render_specs = RenderSpecService()

    def extract_concept(self, narration_text: str, project_id: int | None = None) -> dict[str, Any]:
        narration = str(narration_text or "")
        fallback = self._fallback_concept(narration)
        try:
            payload = self._call_groq_api(
                self._concept_prompt(narration),
                purpose="concept_extraction",
            )
            concept = self._repair_concept(payload, narration)
            self.logger.log("concept_extraction", "completed", "Extracted concept-first visual goal.", project_id)
            return concept
        except Exception as exc:
            self.logger.log("concept_extraction", "failed", f"Concept extraction fallback used: {exc}", project_id)
            return fallback

    def build_visual_explanation(self, concept: dict[str, Any], project_id: int | None = None) -> dict[str, Any]:
        concept = self._repair_concept(concept, str(concept.get("narration") or ""))
        try:
            payload = self._call_groq_api(
                self._visual_explanation_prompt(concept),
                purpose="visual_explanation",
            )
            explanation = self._repair_visual_explanation(payload, concept)
            self.logger.log("visual_explanation", "completed", "Built numeric visual state progression.", project_id)
            return explanation
        except Exception as exc:
            self.logger.log("visual_explanation", "failed", f"Visual explanation fallback used: {exc}", project_id)
            return self._fallback_visual_explanation(concept)

    def build_scene_beats(
        self,
        narration: str,
        duration: int | float,
        project_id: int | None = None,
    ) -> list[dict[str, Any]]:
        concept = self.extract_concept(narration, project_id=project_id)
        concept["narration"] = str(narration or "")
        explanation = self.build_visual_explanation(concept, project_id=project_id)
        visual_states = explanation.get("visual_narrative") if isinstance(explanation, dict) else []
        if not isinstance(visual_states, list) or len(visual_states) < 2:
            visual_states = self._fallback_visual_explanation(concept)["visual_narrative"]

        visual_states = visual_states[:4]
        if len(visual_states) < 2:
            visual_states = self._safe_emphasis_states(concept)
        beat_count = max(2, len(visual_states))
        duration_float = max(float(duration or 0), 2.0)
        beat_duration = max(2.0, min(5.0, duration_float / beat_count))
        beats: list[dict[str, Any]] = []
        for index, state in enumerate(visual_states[:4]):
            if not isinstance(state, dict):
                continue
            role = str(state.get("visual_role") or self._role_for_index(index)).lower()
            beat_type = self._beat_type_for_role(concept, index, role)
            key_value = self._numeric_value(str(state.get("key_value") or ""), concept, index)
            caption = self._clean_supporting_text(str(state.get("supporting_text") or ""), concept)
            start = round(index * beat_duration, 2)
            beat = {
                "beat_index": index,
                "beat_type": beat_type,
                "content": key_value,
                "caption": caption,
                "color": self.ROLE_COLORS.get(role, "orange"),
                "estimated_start_sec": start,
                "estimated_duration_sec": round(beat_duration, 2),
                "concept_metadata": dict(concept),
            }
            if beat_type == "flow_diagram":
                beat["flow_stages"] = list(concept.get("flow_stages") or self.flow_stages(concept, narration))
            beats.append(beat)

        return self.validate_beats(beats, narration, concept, project_id=project_id)

    def validate_beats(
        self,
        beats: list[dict[str, Any]],
        narration: str,
        concept: dict[str, Any],
        project_id: int | None = None,
    ) -> list[dict[str, Any]]:
        concept = self._repair_concept(concept, narration)
        stages = self.flow_stages(concept, narration)
        if not stages and self._concept_type(concept) != "emphasis":
            concept = self._downgrade_to_emphasis(concept, narration, "no_valid_stages")
            stages = self.flow_stages(concept, narration)

        repaired: list[dict[str, Any]] = []
        seen_signatures: dict[str, int] = {}
        for index, beat in enumerate((beats or [])[:4]):
            current = dict(beat) if isinstance(beat, dict) else {}
            current["beat_index"] = len(repaired)
            current.setdefault("estimated_start_sec", round(len(repaired) * 2.0, 2))
            current.setdefault("estimated_duration_sec", 2.0)
            current["concept_metadata"] = dict(concept)

            role = self._role_for_index(len(repaired))
            current["beat_type"] = self._enforced_beat_type(str(current.get("beat_type") or ""), concept, role, len(repaired))
            current["content"] = self._numeric_value(str(current.get("content") or ""), concept, len(repaired))
            current["caption"] = self._clean_supporting_text(str(current.get("caption") or ""), concept)

            valid, reason = self._beat_is_valid(current, concept, narration)
            if not valid:
                self.logger.log("beat_validation", "running", f"Regenerating beat {index}: {reason}", project_id)
                current = self._regenerated_beat(concept, narration, len(repaired), reason)

            if not self._supports_scene_goal(current, concept):
                self.logger.log("beat_validation", "running", f"Regenerating beat {index}: scene_goal_mismatch", project_id)
                current = self._regenerated_beat(concept, narration, len(repaired), "scene_goal_mismatch")

            signature = self._visual_structure_signature(current)
            seen_signatures[signature] = seen_signatures.get(signature, 0) + 1
            if seen_signatures[signature] > 2:
                self.logger.log("beat_validation", "running", f"Regenerating beat {index}: duplicate_structure", project_id)
                current = self._variation_beat(concept, narration, len(repaired))
                signature = self._visual_structure_signature(current)
                seen_signatures[signature] = seen_signatures.get(signature, 0) + 1

            if current.get("beat_type") == "flow_diagram":
                current["flow_stages"] = list(stages)
            repaired.append(current)

        if len(repaired) < 2:
            repaired = self._beats_from_fallback(concept)

        repaired = self._normalize_beat_timing(repaired[:4], narration, concept)
        final: list[dict[str, Any]] = []
        for beat in repaired:
            valid, reason = self._beat_is_valid(beat, concept, narration)
            if not valid or not self._supports_scene_goal(beat, concept):
                self.logger.log("beat_validation", "failed", f"Kill switch safe emphasis: {reason}", project_id)
                final.append(self._safe_emphasis_beat(concept, narration, len(final), reason))
            else:
                final.append(beat)

        self.logger.log(
            "beat_validation",
            "completed",
            f"Validated {len(final)} beat(s); concept={self._concept_type(concept)}; numbers={self._debug_numbers(narration, concept)}.",
            project_id,
        )
        return final

    def flow_stages(self, concept: dict[str, Any], narration: str | None = None) -> list[dict[str, str]]:
        narration_text = str(narration or concept.get("narration") or "")
        explicit = concept.get("flow_stages")
        if isinstance(explicit, list) and len(explicit) >= 3:
            stages = [
                {"label": str(stage.get("label") or self._role_for_index(index)), "value": str(stage.get("value") or "")}
                for index, stage in enumerate(explicit[:3])
                if isinstance(stage, dict) and str(stage.get("value") or "").strip()
            ]
            if len(stages) >= 3 and self._stages_are_valid(stages, concept, narration_text):
                return stages

        start = str(concept.get("start_value") or "")
        end = str(concept.get("end_value") or "")
        lowered = narration_text.lower()
        amounts = self.render_specs._money_tokens(narration_text)
        percents = self.render_specs._percent_tokens(narration_text)
        concept_type = self._concept_type(concept)

        if concept_type == "emphasis":
            value = self._first_number_from_context(narration_text, concept) or "₹5,000"
            return [
                {"label": "number", "value": value},
                {"label": "impact", "value": self._emphasis_impact_value(narration_text, value)},
            ]

        time_match = re.search(r"\bday\s*(\d+)\b", lowered)
        if time_match:
            start_tokens = self.render_specs._money_tokens(start)
            start_value = amounts[0] if amounts else (start_tokens[0] if start_tokens else start)
            end_value = next((amount for amount in amounts[1:] if self.render_specs._first_numeric_value(amount) == 0), "₹0")
            stages = [
                {"label": "start", "value": f"Day 1 {start_value}"},
                {"label": "change", "value": f"Day {time_match.group(1)}"},
                {"label": "result", "value": end_value},
            ]
            return stages if self._stages_are_valid(stages, concept, narration_text) else []

        investment_years = self._investment_years(lowered)
        if concept_type == "growth" and amounts and investment_years:
            end_amount = self._largest_money_token(amounts[1:] or amounts)
            stages = [
                {"label": "start", "value": f"{amounts[0]}/month" if "month" in lowered else amounts[0]},
                {"label": "change", "value": investment_years},
                {"label": "result", "value": end_amount},
            ]
            return stages if self._stages_are_valid(stages, concept, narration_text) else []

        if percents:
            principal = amounts[0] if amounts else start
            if not principal:
                return []
            rate = percents[0]
            output = self._percentage_output(principal, rate, concept_type)
            explicit_output = self._valid_explicit_percent_output(amounts, principal, rate, concept_type)
            if explicit_output:
                output = explicit_output
            stages = [
                {"label": "start", "value": principal},
                {"label": "change", "value": f"{rate} change"},
                {"label": "result", "value": output},
            ]
            return stages if self._stages_are_valid(stages, concept, narration_text) else []

        if amounts and self._supports_monthly_yearly(lowered):
            monthly = amounts[0]
            derived_yearly = self.render_specs._format_rupees(_numeric_amount(monthly) * 12)
            yearly = next((amount for amount in amounts[1:] if abs(_numeric_amount(amount) - _numeric_amount(derived_yearly)) <= 2), derived_yearly)
            stages = [
                {"label": "start", "value": f"{monthly}/month"},
                {"label": "change", "value": "12 months"},
                {"label": "result", "value": f"{yearly}/year"},
            ]
            return stages if self._stages_are_valid(stages, concept, narration_text) else []

        if len(amounts) >= 3 and concept_type in {"flow", "decay", "growth"}:
            stages = [
                {"label": "start", "value": amounts[0]},
                {"label": "change", "value": amounts[1]},
                {"label": "result", "value": amounts[2]},
            ]
            return stages if self._stages_are_valid(stages, concept, narration_text) else []

        if len(amounts) >= 2:
            start_value = amounts[0]
            end_value = amounts[1]
            change_value = self._change_label_from_context(narration_text, start_value, end_value, concept_type)
            stages = [
                {"label": "start", "value": start_value},
                {"label": "change", "value": change_value},
                {"label": "result", "value": end_value},
            ]
            return stages if self._stages_are_valid(stages, concept, narration_text) else []

        if self._has_gravity(start) and self._has_gravity(end):
            middle_value = self._derived_midpoint(start, end, concept_type)
            stages = [
                {"label": "start", "value": start},
                {"label": "change", "value": middle_value},
                {"label": "result", "value": end},
            ]
            return stages if self._stages_are_valid(stages, concept, narration_text) else []

        return []

    def _derive_concept_from_narration(self, narration: str) -> dict[str, Any]:
        narration = str(narration or "")
        logic = self.render_specs.deriveFromNarration(narration)
        logic_type = str(logic.get("type") or "flow") if isinstance(logic, dict) else "flow"
        concept_type = self._infer_concept_type(narration, logic_type)
        scene_goal = self._scene_goal_from_narration(narration, concept_type)
        values = self._values_from_logic(logic)
        start = values[0] if values else ""
        end = values[-1] if len(values) >= 2 else ""
        concept = {
            "scene_goal": scene_goal,
            "concept_name": self._concept_name_from_logic(concept_type),
            "concept_type": concept_type,
            "entities": self._entities_from_narration(narration),
            "transformation": self.render_specs._visual_logic_to_text(logic),
            "start_value": start,
            "end_value": end,
            "outcome": end,
            "explanation_sentence": self.render_specs._visual_logic_to_text(logic),
            "narration": narration,
        }
        stages = self.flow_stages(concept, narration)
        if stages:
            concept["flow_stages"] = stages
            concept["start_value"] = stages[0]["value"]
            concept["end_value"] = stages[-1]["value"]
            concept["transformation"] = " -> ".join(stage["value"] for stage in stages)
            concept["outcome"] = stages[-1]["value"]
            concept["explanation_sentence"] = concept["transformation"]
        elif concept_type != "emphasis":
            concept = self._downgrade_to_emphasis(concept, narration, "unusable_numbers")
        return concept

    def _safe_emphasis_states(self, concept: dict[str, Any]) -> list[dict[str, Any]]:
        stages = self.flow_stages(concept)
        first = stages[0]["value"] if stages else self._first_number_from_context(str(concept.get("narration") or ""), concept) or "₹5,000"
        second = stages[-1]["value"] if len(stages) > 1 else self._emphasis_impact_value(str(concept.get("narration") or ""), first)
        return [
            {"beat_position": 0, "key_value": first, "supporting_text": self._caption_for_role(concept, 0), "visual_role": "introduce", "suggested_component": "StatExplosion"},
            {"beat_position": 1, "key_value": second, "supporting_text": self._caption_for_role(concept, 1), "visual_role": "result", "suggested_component": "StatExplosion"},
        ]

    def _stages_are_valid(self, stages: list[dict[str, str]], concept: dict[str, Any], narration: str) -> bool:
        if len(stages) < 2:
            return False
        concept_type = self._concept_type(concept)
        if concept_type == "emphasis":
            return all(self._has_gravity(stage.get("value", "")) for stage in stages)
        if len(stages) < 3:
            return False
        start = stages[0]["value"]
        process = stages[1]["value"]
        end = stages[-1]["value"]
        if not self._numbers_allowed_by_narration([start, process, end], narration):
            return False
        valid, _reason = validate_numeric_logic(start, process, end, concept_type)
        return valid

    def _supports_monthly_yearly(self, lowered: str) -> bool:
        return bool(
            re.search(r"\b(per\s+month|monthly|/month|every month|each month)\b", lowered)
            and re.search(r"\b(year|yearly|annual|annum|12\s+months?)\b", lowered)
        )

    def _investment_years(self, lowered: str) -> str:
        age_match = re.search(r"\b(?:age\s+of|age)\s+(\d{1,2}).*?\b(?:time\s+you(?:'re| are)?|you\s+are|by)\s+(\d{1,2})\b", lowered)
        if age_match:
            years = int(age_match.group(2)) - int(age_match.group(1))
            if years > 0:
                return f"{years} years"
        years_match = re.search(r"\b(\d{1,2})\s*years?\b", lowered)
        if years_match:
            return f"{years_match.group(1)} years"
        if "long term" in lowered or "long-term" in lowered:
            return "long term"
        return ""

    def _largest_money_token(self, values: list[str]) -> str:
        if not values:
            return ""
        return max(values, key=_numeric_amount)

    def _percentage_output(self, principal: str, rate: str, concept_type: str) -> str:
        principal_value = _numeric_amount(principal)
        rate_value = _numeric_amount(rate) / 100.0
        if concept_type == "growth":
            return self.render_specs._format_rupees(principal_value * (1 + rate_value))
        return self.render_specs._format_rupees(principal_value * (1 - rate_value))

    def _valid_explicit_percent_output(self, amounts: list[str], principal: str, rate: str, concept_type: str) -> str:
        expected = _numeric_amount(self._percentage_output(principal, rate, concept_type))
        rate_amount = _numeric_amount(principal) * (_numeric_amount(rate) / 100.0)
        for amount in amounts[1:]:
            amount_value = _numeric_amount(amount)
            if abs(amount_value - expected) <= max(2, expected * 0.03):
                return amount
            if concept_type == "decay" and abs(amount_value - rate_amount) <= max(2, rate_amount * 0.03):
                return amount
        return ""

    def _change_label_from_context(self, narration: str, start: str, end: str, concept_type: str) -> str:
        lowered = narration.lower()
        if "leak" in lowered:
            return "leak"
        if "expense" in lowered or "spend" in lowered:
            return "spend"
        if "save" in lowered:
            return "saved"
        if concept_type == "growth":
            return "growth"
        if concept_type == "decay":
            return "loss"
        return f"{start} to {end}"

    def _derived_midpoint(self, start: str, end: str, concept_type: str) -> str:
        start_value = _numeric_amount(start)
        end_value = _numeric_amount(end)
        if concept_type == "growth":
            return self.render_specs._format_rupees((start_value + end_value) / 2)
        return self.render_specs._format_rupees(max(end_value, start_value / 2))

    def _first_number_from_context(self, narration: str, concept: dict[str, Any]) -> str:
        numbers = self.render_specs._percent_tokens(narration) + self.render_specs._money_tokens(narration)
        if numbers:
            return numbers[0]
        for key in ("start_value", "end_value", "outcome", "explanation_sentence"):
            values = self._values_from_text(str(concept.get(key) or ""))
            if values:
                return values[0]
        return ""

    def _emphasis_impact_value(self, narration: str, value: str) -> str:
        amounts = self.render_specs._money_tokens(narration)
        percents = self.render_specs._percent_tokens(narration)
        if value in percents and amounts:
            return amounts[0]
        if value in amounts and percents:
            return percents[0]
        return value

    def _downgrade_to_emphasis(self, concept: dict[str, Any], narration: str, reason: str) -> dict[str, Any]:
        value = self._first_number_from_context(narration, concept) or "₹5,000"
        return {
            **concept,
            "concept_type": "emphasis",
            "concept_name": "finance stat",
            "scene_goal": self._clean_phrase(str(concept.get("scene_goal") or "prove the key number"), "prove the key number"),
            "transformation": value,
            "start_value": value,
            "end_value": self._emphasis_impact_value(narration, value),
            "outcome": self._emphasis_impact_value(narration, value),
            "explanation_sentence": f"{value} matters",
            "fallback_reason": reason,
            "narration": narration,
        }

    def _numbers_allowed_by_narration(self, values: list[str], narration: str) -> bool:
        if not narration.strip():
            return True
        allowed = set(self.render_specs._money_tokens(narration) + self.render_specs._percent_tokens(narration))
        derived = self._derived_numbers_from_narration(narration)
        allowed.update(derived)
        for value in values:
            for token in self.render_specs._money_tokens(value) + self.render_specs._percent_tokens(value):
                if token not in allowed:
                    return False
        return True

    def _derived_numbers_from_narration(self, narration: str) -> set[str]:
        lowered = narration.lower()
        amounts = self.render_specs._money_tokens(narration)
        percents = self.render_specs._percent_tokens(narration)
        derived: set[str] = set()
        if amounts and self._supports_monthly_yearly(lowered):
            derived.add(self.render_specs._format_rupees(_numeric_amount(amounts[0]) * 12))
        if amounts and percents:
            derived.add(self._percentage_output(amounts[0], percents[0], "decay"))
            derived.add(self._percentage_output(amounts[0], percents[0], "growth"))
        if any(word in lowered for word in ("vanish", "zero", "₹0", "manual", "emotion")):
            derived.add("₹0")
        if any(word in lowered for word in ("vanish", "salary", "payday", "paycheck")) and not amounts:
            derived.add("₹25,000")
        return derived

    def _debug_numbers(self, narration: str, concept: dict[str, Any]) -> str:
        values = self.render_specs._money_tokens(narration) + self.render_specs._percent_tokens(narration)
        derived = sorted(self._derived_numbers_from_narration(narration))
        return json.dumps({"narration": values, "derived": derived, "concept": concept.get("flow_stages")}, ensure_ascii=False)

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
            return cleaned
        stages = self.flow_stages(concept)
        if index < len(stages):
            return stages[index]["value"]
        return self._first_number_from_context(str(concept.get("narration") or ""), concept) or "₹5,000"

    def _progression_content(self, concept: dict[str, Any]) -> str:
        stages = self.flow_stages(concept)
        if len(stages) < 2:
            return self._first_number_from_context(str(concept.get("narration") or ""), concept) or "₹5,000"
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
        start = _numeric_amount(str(concept.get("start_value") or ""))
        end = _numeric_amount(str(concept.get("end_value") or ""))
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
        if index == 3 or role == "emotion":
            return "text_burst"
        if concept_type == "comparison":
            return "split_comparison" if index == 1 else "stat_explosion"
        if concept_type == "emphasis":
            return "stat_explosion"
        return "flow_diagram" if index == 1 else "stat_explosion"

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
        if not self._numbers_allowed_by_narration([content], narration):
            return False, "number_not_from_narration_or_derivation"
        concept_type = self._concept_type(concept)
        if beat.get("beat_type") == "flow_diagram":
            stages = beat.get("flow_stages") if isinstance(beat.get("flow_stages"), list) else self.flow_stages(concept, narration)
            if len(stages) < 3:
                return False, "flow_missing_start_change_result"
            valid, reason = validate_numeric_logic(stages[0]["value"], stages[1]["value"], stages[-1]["value"], concept_type)
            if not valid:
                return False, reason
            if not self._numbers_allowed_by_narration([stage["value"] for stage in stages], narration):
                return False, "flow_number_not_supported"
        return True, "valid"

    def _regenerated_beat(self, concept: dict[str, Any], narration: str, index: int, reason: str) -> dict[str, Any]:
        stages = self.flow_stages(concept, narration)
        if len(stages) < 2:
            return self._safe_emphasis_beat(concept, narration, index, reason)
        role = self._role_for_index(index)
        beat_type = self._beat_type_for_role(concept, index, role)
        content = " -> ".join(stage["value"] for stage in stages[:3]) if beat_type == "flow_diagram" and len(stages) >= 3 else stages[min(index, len(stages) - 1)]["value"]
        beat = {
            "beat_index": index,
            "beat_type": beat_type,
            "content": content,
            "caption": self._caption_for_role(concept, index),
            "color": self.ROLE_COLORS.get(role, "orange"),
            "estimated_start_sec": round(index * 2.0, 2),
            "estimated_duration_sec": 2.0,
            "concept_metadata": dict(concept),
            "regenerated_reason": reason,
        }
        if beat_type == "flow_diagram":
            beat["flow_stages"] = list(stages)
        return beat

    def _variation_beat(self, concept: dict[str, Any], narration: str, index: int) -> dict[str, Any]:
        beat = self._regenerated_beat(concept, narration, index, "forced_variation")
        if index == 3:
            beat["beat_type"] = "text_burst"
        elif beat["beat_type"] == "flow_diagram":
            beat["caption"] = "change shown"
        else:
            beat["caption"] = self._caption_for_role(concept, index)
        return beat

    def _safe_emphasis_beat(self, concept: dict[str, Any], narration: str, index: int, reason: str) -> dict[str, Any]:
        value = self._first_number_from_context(narration, concept) or "₹5,000"
        impact = self._emphasis_impact_value(narration, value)
        content = value if index == 0 else impact
        return {
            "beat_index": index,
            "beat_type": "stat_explosion" if index < 3 else "text_burst",
            "content": content,
            "caption": self._caption_for_role(concept, index),
            "color": self.ROLE_COLORS.get(self._role_for_index(index), "orange"),
            "estimated_start_sec": round(index * 2.0, 2),
            "estimated_duration_sec": 2.0,
            "concept_metadata": dict(self._downgrade_to_emphasis(concept, narration, reason)),
            "regenerated_reason": reason,
        }

    def _normalize_beat_timing(self, beats: list[dict[str, Any]], narration: str, concept: dict[str, Any]) -> list[dict[str, Any]]:
        count = max(2, min(4, len(beats)))
        if len(beats) < count:
            while len(beats) < count:
                beats.append(self._regenerated_beat(concept, narration, len(beats), "min_beat_count"))
        duration = sum(float(beat.get("estimated_duration_sec") or 2.0) for beat in beats) or count * 2.0
        beat_duration = max(2.0, min(5.0, duration / count))
        normalized = []
        for index, beat in enumerate(beats[:count]):
            current = {key: value for key, value in beat.items() if value is not None}
            current["beat_index"] = index
            current["estimated_start_sec"] = round(index * beat_duration, 2)
            current["estimated_duration_sec"] = round(beat_duration, 2)
            normalized.append(current)
        return normalized

    def _visual_structure_signature(self, beat: dict[str, Any]) -> str:
        stages = beat.get("flow_stages") if isinstance(beat.get("flow_stages"), list) else []
        stage_text = "->".join(str(stage.get("value") or "") for stage in stages if isinstance(stage, dict))
        return self._content_signature(f"{beat.get('beat_type')}|{beat.get('content')}|{stage_text}")

    def _caption_for_role(self, concept: dict[str, Any], index: int) -> str:
        concept_type = self._concept_type(concept)
        if concept_type == "growth":
            labels = ["start amount", "growth step", "final value", "wealth punch"]
        elif concept_type == "decay":
            labels = ["start value", "loss step", "final value", "loss punch"]
        elif concept_type == "comparison":
            labels = ["left value", "right value", "gap shown", "clear winner"]
        elif concept_type == "emphasis":
            labels = ["key number", "impact number", "main stat", "remember this"]
        else:
            labels = ["start value", "change step", "result value", "money punch"]
        return labels[min(index, len(labels) - 1)]

    def _content_number_in_concept(self, content: str, concept: dict[str, Any]) -> bool:
        concept_text = " ".join(
            str(concept.get(key) or "")
            for key in ("transformation", "start_value", "end_value", "outcome", "explanation_sentence")
        )
        content_tokens = set(self.render_specs._money_tokens(content) + self.render_specs._percent_tokens(content))
        concept_tokens = set(self.render_specs._money_tokens(concept_text) + self.render_specs._percent_tokens(concept_text))
        return bool(content_tokens & concept_tokens)

    def _component_for_concept(self, concept: dict[str, Any], index: int) -> str:
        if index == 3:
            return "TextBurst"
        concept_type = self._concept_type(concept)
        if concept_type == "comparison":
            return "SplitComparison"
        if concept_type == "emphasis":
            return "StatExplosion"
        return "FlowDiagram"

    def _role_for_index(self, index: int) -> str:
        return ["introduce", "change", "result", "emotion"][min(index, 3)]

    def _clean_supporting_text(self, text: str, concept: dict[str, Any]) -> str:
        cleaned = self._clean_phrase(text, "")
        if not cleaned or self._contains_banned(cleaned) or self._contains_label_banned(cleaned) or self._is_sentence(cleaned):
            cleaned = self._caption_from_concept(concept)
        words = re.findall(r"[A-Za-z0-9₹%.,/-]+", cleaned)
        cleaned = " ".join(words[:6]).strip()
        if self._contains_label_banned(cleaned):
            return self._caption_for_role(concept, 0)
        return cleaned

    def _caption_from_concept(self, concept: dict[str, Any]) -> str:
        scene_goal = str(concept.get("scene_goal") or "")
        goal_words = [
            word
            for word in re.findall(r"[A-Za-z0-9₹%.,/-]+", scene_goal)
            if word.lower() not in {"prove", "show", "that", "this", "scene"}
        ]
        if goal_words:
            return " ".join(goal_words[:6])
        return self.render_specs._short_overlay(str(concept.get("explanation_sentence") or ""), 6) or "numeric change"

    def _clean_phrase(self, text: str, fallback: str) -> str:
        cleaned = " ".join(str(text or "").replace("→", "->").split()).strip()
        if not cleaned or self._contains_banned(cleaned):
            return fallback
        return cleaned

    def _contains_banned(self, text: str) -> bool:
        lowered = " ".join(str(text or "").lower().split())
        return any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in self.BANNED_WORDS)

    def _contains_label_banned(self, text: str) -> bool:
        lowered = " ".join(str(text or "").lower().split())
        return any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in self.BANNED_LABEL_WORDS)

    def _is_sentence(self, text: str) -> bool:
        words = re.findall(r"\w+", text)
        return len(words) > 6 or text.strip().endswith(".")

    def _has_gravity(self, text: str) -> bool:
        return bool(re.search(r"(₹|%|\d|->|\bvs\b|\bversus\b)", str(text or ""), re.I))

    def _content_signature(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip().lower())

    def _value_or_default(self, value: str, fallback: str) -> str:
        value = str(value or "").strip()
        return value if self._has_gravity(value) else fallback

    def _concrete_entities(self, raw: Any, fallback: list[str]) -> list[str]:
        if not isinstance(raw, list):
            return fallback
        entities = []
        for item in raw[:5]:
            text = self._clean_phrase(str(item), "")
            if text and not self._contains_banned(text):
                entities.append(text)
        return entities or fallback

    def _entities_from_narration(self, narration: str) -> list[str]:
        lowered = narration.lower()
        entities = []
        for candidate in ("salary", "expenses", "inflation", "savings", "debt", "interest", "monthly leak", "auto debit"):
            if candidate in lowered:
                entities.append(candidate)
        return entities[:4] or ["money"]

    def _scene_goal_from_narration(self, narration: str, logic_type: str) -> str:
        lowered = narration.lower()
        if "vanish" in lowered or "day" in lowered:
            return "prove salary disappears quickly"
        if "inflation" in lowered:
            return "prove inflation cuts real value"
        if any(word in lowered for word in ("sip", "invest", "return", "compound", "wealth", "accumulate")):
            return "prove money grows over time"
        if "month" in lowered or "year" in lowered:
            return "prove small monthly loss becomes yearly loss"
        if "auto" in lowered or "automate" in lowered:
            return "prove automation protects savings"
        if logic_type == "comparison":
            return "prove the money gap"
        return "prove money changes visibly"

    def _concept_name_from_logic(self, logic_type: str) -> str:
        return {
            "comparison": "money comparison",
            "decay": "value decay",
            "growth": "money growth",
            "emphasis": "money stat",
            "flow": "money progression",
        }.get(logic_type, "money progression")
