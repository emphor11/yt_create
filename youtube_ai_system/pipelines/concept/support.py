from __future__ import annotations

import json
import re
from typing import Any

from .generation_support import ConceptGenerationSupportMixin
from .numeric import numeric_amount, validate_numbers


class ConceptSupportMixin(ConceptGenerationSupportMixin):
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
            value = self._first_number_from_context(narration_text, concept) or self._dynamic_fallback_number(narration_text)
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

        if amounts and self._has_time_context(lowered):
            monthly = amounts[0]
            time_label, multiplier = self._time_multiplier_from_narration(lowered)
            derived_total = self.render_specs._format_rupees(numeric_amount(monthly) * multiplier)
            total = next((amount for amount in amounts[1:] if abs(numeric_amount(amount) - numeric_amount(derived_total)) <= max(2, numeric_amount(derived_total) * 0.05)), derived_total)
            stages = [
                {"label": "start", "value": f"{monthly}/month"},
                {"label": "change", "value": time_label},
                {"label": "result", "value": total},
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
        first = stages[0]["value"] if stages else self._first_number_from_context(str(concept.get("narration") or ""), concept) or self._dynamic_fallback_number(str(concept.get("narration") or ""))
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
        valid, _reason = validate_numbers(start, process, end, concept_type, narration)
        return valid

    def _supports_monthly_yearly(self, lowered: str) -> bool:
        return bool(
            re.search(r"\b(per\s+month|monthly|/month|every month|each month)\b", lowered)
            and re.search(r"\b(year|yearly|annual|annum|12\s+months?)\b", lowered)
        )

    def _has_time_context(self, lowered: str) -> bool:
        """More relaxed than _supports_monthly_yearly: accepts month OR year OR time periods."""
        return bool(re.search(
            r"\b(per\s+month|monthly|/month|every month|each month|per\s+year|yearly|annual|every year|\d+\s*years?|\d+\s*months?)\b",
            lowered,
        ))

    def _time_multiplier_from_narration(self, lowered: str) -> tuple[str, int]:
        """Extract time period and multiplier from narration."""
        years_match = re.search(r"(\d+)\s*years?", lowered)
        months_match = re.search(r"(\d+)\s*months?", lowered)
        if years_match:
            years = int(years_match.group(1))
            return f"{years} years", years * 12
        if months_match:
            months = int(months_match.group(1))
            return f"{months} months", months
        if re.search(r"\b(yearly|annual|per\s+year|every year)\b", lowered):
            return "12 months", 12
        return "12 months", 12

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
        return max(values, key=numeric_amount)

    def _percentage_output(self, principal: str, rate: str, concept_type: str) -> str:
        principal_value = numeric_amount(principal)
        rate_value = numeric_amount(rate) / 100.0
        if concept_type == "growth":
            return self.render_specs._format_rupees(principal_value * (1 + rate_value))
        return self.render_specs._format_rupees(principal_value * (1 - rate_value))

    def _valid_explicit_percent_output(self, amounts: list[str], principal: str, rate: str, concept_type: str) -> str:
        expected = numeric_amount(self._percentage_output(principal, rate, concept_type))
        rate_amount = numeric_amount(principal) * (numeric_amount(rate) / 100.0)
        for amount in amounts[1:]:
            amount_value = numeric_amount(amount)
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
        start_value = numeric_amount(start)
        end_value = numeric_amount(end)
        if concept_type == "growth":
            return self.render_specs._format_rupees((start_value + end_value) / 2)
        return self.render_specs._format_rupees(max(end_value, start_value / 2))

    def _first_number_from_context(self, narration: str, concept: dict[str, Any]) -> str:
        # Priority: money tokens first (₹X), then percentages
        money = self.render_specs._money_tokens(narration)
        if money:
            return money[0]
        percents = self.render_specs._percent_tokens(narration)
        if percents:
            return percents[0]
        # Try concept fields
        for key in ("start_value", "end_value", "outcome", "transformation", "explanation_sentence"):
            values = self._values_from_text(str(concept.get(key) or ""))
            if values:
                return values[0]
        # Try narration embedded numbers (e.g. "5 lakh")
        lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*lakhs?", narration, re.I)
        if lakh_match:
            return self.render_specs._format_rupees(float(lakh_match.group(1)) * 100_000)
        crore_match = re.search(r"(\d+(?:\.\d+)?)\s*crores?", narration, re.I)
        if crore_match:
            return self.render_specs._format_rupees(float(crore_match.group(1)) * 10_000_000)
        return ""

    def _dynamic_fallback_number(self, narration: str) -> str:
        """Generate a context-appropriate fallback instead of always using ₹5,000."""
        lowered = narration.lower()
        # Insurance (check before rent/emi since "premium" contains "emi")
        if any(w in lowered for w in ("insurance", "premium", "policy", "cover")):
            return "₹20,000"
        # Salary context
        if any(w in lowered for w in ("salary", "income", "paycheck", "payday", "ctc")):
            return "₹25,000"
        # Investment context
        if any(w in lowered for w in ("sip", "invest", "mutual fund", "portfolio")):
            return "₹10,000"
        # Rent/EMI context (use word boundary to avoid substring matches)
        if re.search(r"\b(rent|emi|loan|mortgage)\b", lowered):
            return "₹15,000"
        # Debt/credit context
        if any(w in lowered for w in ("debt", "credit card", "interest", "borrow")):
            return "₹50,000"
        # Food/dining/subscription
        if any(w in lowered for w in ("food", "dining", "zomato", "swiggy", "subscription", "netflix")):
            return "₹2,000"
        # Generic finance
        return "₹5,000"

    def _emphasis_impact_value(self, narration: str, value: str) -> str:
        amounts = self.render_specs._money_tokens(narration)
        percents = self.render_specs._percent_tokens(narration)
        if value in percents and amounts:
            return amounts[0]
        if value in amounts and percents:
            return percents[0]
        return value

    def _downgrade_to_emphasis(self, concept: dict[str, Any], narration: str, reason: str) -> dict[str, Any]:
        value = self._first_number_from_context(narration, concept) or self._dynamic_fallback_number(narration)
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
        """RELAXED: Accept if number is in narration, derived, OR close to a narration amount."""
        if not narration.strip():
            return True
        allowed = set(self.render_specs._money_tokens(narration) + self.render_specs._percent_tokens(narration))
        derived = self._derived_numbers_from_narration(narration)
        allowed.update(derived)

        # Pre-compute narration amounts for proximity check
        narration_amounts = [numeric_amount(t) for t in allowed if numeric_amount(t) > 0]

        for value in values:
            tokens = self.render_specs._money_tokens(value) + self.render_specs._percent_tokens(value)
            for token in tokens:
                if token in allowed:
                    continue
                # RELAXED: accept if within 5% of any narration/derived amount
                token_amount = numeric_amount(token)
                if token_amount > 0 and any(
                    abs(token_amount - na) <= max(2, na * 0.05) for na in narration_amounts
                ):
                    continue
                # RELAXED: accept time references (e.g. "Day 12", "12 months")
                if re.search(r"\b(day|month|year|week)\b", value, re.I):
                    continue
                # RELAXED: accept ₹0 endpoint (common in decay)
                if token_amount == 0:
                    continue
                return False
        return True

    def _derived_numbers_from_narration(self, narration: str) -> set[str]:
        lowered = narration.lower()
        amounts = self.render_specs._money_tokens(narration)
        percents = self.render_specs._percent_tokens(narration)
        derived: set[str] = set()

        # Monthly → yearly (both strict and relaxed)
        if amounts and self._has_time_context(lowered):
            _label, multiplier = self._time_multiplier_from_narration(lowered)
            for amt in amounts:
                derived.add(self.render_specs._format_rupees(numeric_amount(amt) * multiplier))

        # Percentage derivations: apply to ALL amounts, not just first
        if amounts and percents:
            for amt in amounts:
                for pct in percents:
                    derived.add(self._percentage_output(amt, pct, "decay"))
                    derived.add(self._percentage_output(amt, pct, "growth"))

        # Compound growth: amt * (1 + rate)^years
        years_match = re.search(r"(\d+)\s*years?", lowered)
        if amounts and percents and years_match:
            years = int(years_match.group(1))
            for amt in amounts:
                for pct in percents:
                    rate = float(re.search(r"(\d+(?:\.\d+)?)", pct).group(1)) / 100.0
                    compound = numeric_amount(amt) * ((1 + rate) ** years)
                    derived.add(self.render_specs._format_rupees(compound))

        # Multi-amount derivations: difference between amounts
        if len(amounts) >= 2:
            for i in range(len(amounts)):
                for j in range(i + 1, len(amounts)):
                    diff = abs(numeric_amount(amounts[i]) - numeric_amount(amounts[j]))
                    if diff > 0:
                        derived.add(self.render_specs._format_rupees(diff))

        # Common endpoints
        if any(word in lowered for word in ("vanish", "zero", "₹0", "manual", "emotion", "gone", "nothing")):
            derived.add("₹0")
        if any(word in lowered for word in ("vanish", "salary", "payday", "paycheck")) and not amounts:
            derived.add("₹25,000")

        return derived

    def _debug_numbers(self, narration: str, concept: dict[str, Any]) -> str:
        values = self.render_specs._money_tokens(narration) + self.render_specs._percent_tokens(narration)
        derived = sorted(self._derived_numbers_from_narration(narration))
        return json.dumps({"narration": values, "derived": derived, "concept": concept.get("flow_stages")}, ensure_ascii=False)

