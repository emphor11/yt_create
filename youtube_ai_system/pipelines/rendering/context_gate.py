from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .numbers import RenderNumberUtils


class RenderContextGate:
    """Contextual relevance checks for visual logic candidates."""

    def __init__(self, number_utils: RenderNumberUtils | None = None) -> None:
        self.number_utils = number_utils or RenderNumberUtils()

    def visual_logic_relevant_to_context(
        self,
        visual_logic: Any,
        context: str,
        *,
        logic_text: str,
        logic_type: str,
    ) -> bool:
        if not isinstance(visual_logic, dict) or not context.strip():
            return True
        context_numbers = set(self.number_utils.money_tokens(context) + self.number_utils.percent_tokens(context))
        logic_numbers = set(self.number_utils.money_tokens(logic_text) + self.number_utils.percent_tokens(logic_text))
        if logic_type == "comparison" and not self.comparison_units_match(visual_logic):
            return False
        if logic_numbers and not self.numbers_allowed_by_context(logic_numbers, context_numbers, context):
            return False
        logic_keywords = self.meaningful_keywords(logic_text)
        context_keywords = self.meaningful_keywords(context)
        if not context_keywords or not logic_keywords:
            return True
        return bool(logic_keywords & context_keywords)

    def comparison_units_match(self, visual_logic: Any) -> bool:
        if not isinstance(visual_logic, dict):
            return True
        left = str(visual_logic.get("left") or "")
        right = str(visual_logic.get("right") or "")
        left_unit = self.dominant_unit(left)
        right_unit = self.dominant_unit(right)
        if {left_unit, right_unit} == {"percent", "money"}:
            return False
        return True

    def dominant_unit(self, text: str) -> str:
        if self.number_utils.money_tokens(text):
            return "money"
        if self.number_utils.percent_tokens(text):
            return "percent"
        return "number" if re.search(r"\b\d+(?:\.\d+)?\b", text) else "none"

    def numbers_allowed_by_context(
        self,
        logic_numbers: set[str],
        context_numbers: set[str],
        context: str,
    ) -> bool:
        if not logic_numbers:
            return True
        if context_numbers:
            allowed = set(context_numbers)
            allowed.update(self.strict_contextual_number_allowlist(context))
            return logic_numbers.issubset(allowed)
        return bool(self.strict_contextual_number_allowlist(context)) and logic_numbers.issubset(
            self.strict_contextual_number_allowlist(context)
        )

    def strict_contextual_number_allowlist(self, context: str) -> set[str]:
        lowered = str(context or "").lower()
        allowed: set[str] = set()
        if any(word in lowered for word in ("vanish", "vanished", "salary", "payday", "paycheck")):
            allowed.update({"₹25,000", "₹0"})
        if any(word in lowered for word in ("manual", "emotion", "emotional", "automate", "auto debit")):
            allowed.add("₹0")
        return allowed

    def derived_context_number_tokens(
        self,
        context: str,
        *,
        inflation_output: Callable[[str, str], str],
    ) -> set[str]:
        lowered = context.lower()
        derived: set[str] = set()
        amounts = self.number_utils.money_tokens(context)
        percents = self.number_utils.percent_tokens(context)
        if any(word in lowered for word in ("month", "monthly", "year", "yearly", "leak", "lost", "gone")):
            for amount in amounts:
                derived.add(self.number_utils.format_rupees(self.number_utils.first_numeric_value(amount) * 12))
        if amounts and any(word in lowered for word in ("cannot", "can't", "broke", "save", "saved", "emotion", "manual")):
            derived.add("₹0")
        if any(word in lowered for word in ("inflation", "real value", "fd", "fixed deposit")) and amounts and percents:
            derived.add(inflation_output(amounts[0], percents[0]))
        return derived

    def meaningful_keywords(self, text: str) -> set[str]:
        stop = {
            "cannot",
            "cant",
            "save",
            "saved",
            "emergency",
            "fund",
            "money",
            "real",
            "value",
            "left",
            "source",
            "process",
            "result",
            "year",
            "month",
            "months",
        }
        words = set(re.findall(r"[A-Za-z]{3,}", text.lower()))
        return {word for word in words if word not in stop}

    def numbers_respect_context(self, candidate: str, context: str) -> bool:
        context_numbers = set(self.number_utils.money_tokens(context) + self.number_utils.percent_tokens(context))
        candidate_numbers = set(self.number_utils.money_tokens(candidate) + self.number_utils.percent_tokens(candidate))
        if not candidate_numbers:
            return True
        return self.numbers_allowed_by_context(candidate_numbers, context_numbers, context)
