from __future__ import annotations

import re
from typing import Any

from .numbers import RenderNumberUtils
from .text_utils import RenderTextUtils
from .value_deriver import RenderValueDeriver


class RenderNarrationLogicBuilder:
    """Builds typed visual-logic objects from narration text."""

    def __init__(
        self,
        *,
        number_utils: RenderNumberUtils,
        text_utils: RenderTextUtils,
        value_deriver: RenderValueDeriver,
    ) -> None:
        self.number_utils = number_utils
        self.text_utils = text_utils
        self.value_deriver = value_deriver

    def emphasis_logic_from_narration(self, narration: str) -> dict[str, Any]:
        amounts = list(dict.fromkeys(self.number_utils.money_tokens(narration)))
        percents = list(dict.fromkeys(self.number_utils.percent_tokens(narration)))
        headline = percents[0] if percents else (amounts[0] if amounts else "₹5,000")
        lowered = str(narration or "").lower()
        if amounts and any(phrase in lowered for phrase in ("cannot", "can't", "less than")):
            subtext = f"can't even save {amounts[0]}"
        elif amounts and "only" in lowered:
            subtext = f"only {amounts[0]} left"
        else:
            subtext = self.text_utils.short_overlay(narration, 6)
        return {"type": "emphasis", "headline": headline, "subtext": subtext}

    def comparison_logic_from_narration(self, narration: str) -> dict[str, Any]:
        amounts = list(dict.fromkeys(self.number_utils.money_tokens(narration)))
        percents = list(dict.fromkeys(self.number_utils.percent_tokens(narration)))
        if percents and amounts:
            return {"type": "comparison", "left": f"{percents[0]} of people", "right": f"{amounts[0]} savings"}
        if len(amounts) >= 2:
            return {"type": "comparison", "left": amounts[0], "right": amounts[1]}
        return self.contextual_visual_logic_object_without_classification(narration)

    def flow_logic_from_narration(self, narration: str, beat: dict[str, Any] | None = None) -> dict[str, Any]:
        lowered = str(narration or "").lower()
        amounts = list(dict.fromkeys(self.number_utils.money_tokens(narration)))
        if any(word in lowered for word in ("automate", "auto debit", "manual", "emotion", "emotional")):
            amount = amounts[0] if amounts else "₹5,000"
            result = next((item for item in amounts[1:] if self.number_utils.first_numeric_value(item) == 0), "₹0")
            return {
                "type": "flow",
                "source": self.value_deriver.amount_with_label(amount, "Auto Debit"),
                "process": self.value_deriver.amount_with_label(amount, "auto-invested"),
                "result": self.value_deriver.amount_with_label(result, "left to spend"),
            }
        source = self.value_deriver.amount_with_label(amounts[0], "Salary") if amounts else "₹25,000 Salary"
        process = self.value_deriver.amount_with_label(amounts[1], "Expenses") if len(amounts) > 1 else self.value_deriver.derived_rupee(source, 0.92, "Expenses")
        result = self.value_deriver.amount_with_label(amounts[2], "Left") if len(amounts) > 2 else self.value_deriver.derived_rupee(source, 0.08, "Left")
        return {"type": "flow", "source": source, "process": process, "result": result}

    def decay_flow_from_narration(self, narration: str) -> dict[str, Any]:
        lowered = str(narration or "").lower()
        amounts = list(dict.fromkeys(self.number_utils.money_tokens(narration)))
        if any(word in lowered for word in ("salary", "income", "paycheck")) and any(word in lowered for word in ("leak", "lost", "loss")) and len(amounts) >= 2:
            salary_value = self.number_utils.first_numeric_value(amounts[0])
            leak_value = self.number_utils.first_numeric_value(amounts[1])
            left = self.number_utils.format_rupees(salary_value - leak_value) if salary_value > leak_value > 0 else self.value_deriver.derived_rupee(amounts[0], 0.8, "Left")
            return {
                "type": "flow",
                "source": self.value_deriver.amount_with_label(amounts[0], "Salary"),
                "process": self.value_deriver.amount_with_label(amounts[1], "Leak"),
                "result": self.value_deriver.amount_with_label(left, "Left"),
            }
        if "vanish" in lowered or "vanished" in lowered:
            source = self.value_deriver.amount_with_label(amounts[0], "Salary") if amounts else "₹25,000 Salary"
            process = "day 12" if re.search(r"\bday\s*12\b", lowered) else "spending"
            result = self.value_deriver.amount_with_label(amounts[1], "Left") if len(amounts) > 1 else "₹0 Left"
            return {"type": "flow", "source": source, "process": process, "result": result}
        source = self.value_deriver.amount_with_label(amounts[0], "Monthly Leak") if amounts else "₹5,000 Monthly Leak"
        result = self.value_deriver.amount_with_label(amounts[1], "Lost") if len(amounts) > 1 else self.value_deriver.derived_rupee(source, 12, "Lost")
        return {"type": "flow", "source": source, "process": "12 months", "result": result}

    def contextual_visual_logic_object_without_classification(self, context: str) -> dict[str, Any]:
        amounts = list(dict.fromkeys(self.number_utils.money_tokens(context)))
        if len(amounts) >= 2:
            return {"type": "comparison", "left": amounts[0], "right": amounts[1]}
        return self.fallback_numeric_flow()

    def coerce_logic_to_pattern(self, logic: dict[str, Any], context: str, preferred_pattern: str) -> dict[str, Any]:
        amounts = list(dict.fromkeys(self.number_utils.money_tokens(context)))
        percents = list(dict.fromkeys(self.number_utils.percent_tokens(context)))
        if preferred_pattern == "COMPARISON":
            if len(amounts) >= 2:
                return {"type": "comparison", "left": amounts[0], "right": amounts[1]}
            if amounts and percents:
                return {"type": "comparison", "left": percents[0], "right": amounts[0]}
        if preferred_pattern in {"MONEY_FLOW", "VALUE_DECAY", "LOOP", "GROWTH"}:
            if preferred_pattern == "VALUE_DECAY":
                principal = amounts[0] if amounts else "₹1,00,000"
                rate = percents[0] if percents else "6% Inflation"
                return {
                    "type": "decay",
                    "input": principal,
                    "factor": rate if "inflation" in rate.lower() else f"{rate} Inflation",
                    "output": f"{self.value_deriver.inflation_output(principal, rate)} Real Value",
                }
            if preferred_pattern == "GROWTH":
                amount = amounts[0] if amounts else "₹5,000"
                output = amounts[1] if len(amounts) > 1 else self.value_deriver.derived_rupee(amount, 12, "Invested")
                rate = percents[0] if percents else "12 months"
                return {"type": "growth", "input": self.value_deriver.amount_with_label(amount, "SIP"), "rate": rate, "output": output}
            source = amounts[0] if amounts else "₹5,000 Monthly Leak"
            result = amounts[1] if len(amounts) > 1 else self.value_deriver.derived_rupee(source, 12, "Lost")
            return {
                "type": "flow",
                "source": self.value_deriver.amount_with_label(source, "Monthly Leak"),
                "process": "12 months",
                "result": self.value_deriver.amount_with_label(result, "Lost"),
            }
        if preferred_pattern == "EMPHASIS":
            return self.emphasis_logic_from_narration(context)
        return logic

    def minimal_narration_flow(self, context: str) -> dict[str, Any]:
        lowered = str(context or "").lower()
        amounts = list(dict.fromkeys(self.number_utils.money_tokens(context)))
        if any(word in lowered for word in ("vanish", "vanished", "salary", "payday", "paycheck")):
            source = self.value_deriver.amount_with_label(amounts[0], "Salary") if amounts else "₹25,000 Salary"
            process = "day 12" if re.search(r"\bday\s*12\b", lowered) else "spending"
            result = self.value_deriver.amount_with_label(amounts[1], "Left") if len(amounts) > 1 else "₹0 Left"
            return {"type": "flow", "source": source, "process": process, "result": result}
        if len(amounts) >= 2:
            return {"type": "flow", "source": amounts[0], "process": "change", "result": amounts[1]}
        amount = amounts[0] if amounts else "₹25,000"
        return {"type": "flow", "source": self.value_deriver.amount_with_label(amount, "Start"), "process": "change", "result": "₹0 Left"}

    def transformation_logic_to_flow(self, visual_logic: Any) -> dict[str, Any] | None:
        if not isinstance(visual_logic, dict):
            return None
        logic_type = str(visual_logic.get("type") or "").strip().lower()
        if logic_type == "decay":
            return {
                "type": "flow",
                "source": str(visual_logic.get("input") or ""),
                "process": str(visual_logic.get("factor") or ""),
                "result": str(visual_logic.get("output") or ""),
            }
        if logic_type == "growth":
            return {
                "type": "flow",
                "source": str(visual_logic.get("input") or ""),
                "process": str(visual_logic.get("rate") or ""),
                "result": str(visual_logic.get("output") or ""),
            }
        return None

    def fallback_numeric_flow(self) -> dict[str, Any]:
        return {
            "type": "flow",
            "source": "₹25,000 Salary",
            "process": "₹23,000 Expenses",
            "result": "₹2,000 Left",
        }
