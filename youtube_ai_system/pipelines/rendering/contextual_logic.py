from __future__ import annotations

from typing import Any, Callable


class RenderContextualLogicBuilder:
    """Builds typed visual logic from narration context using legacy rules."""

    def __init__(
        self,
        *,
        amount_with_label: Callable[[str, str], str],
        classify_intent: Callable[[str], str],
        concrete_fallback_logic: Callable[[dict[str, Any]], str],
        derived_rupee: Callable[[str, float, str], str],
        fallback_numeric_flow: Callable[[], dict[str, Any]],
        first_numeric_value: Callable[[str], float],
        inflation_output: Callable[[str, str], str],
        logic_from_classified_intent: Callable[[str, str, dict[str, Any] | None], dict[str, Any]],
        money_tokens: Callable[[str], list[str]],
        minimal_narration_flow: Callable[[str, str], dict[str, Any]],
        percent_tokens: Callable[[str], list[str]],
        string_visual_logic_to_object: Callable[[str, str], dict[str, Any] | None],
        typed_visual_logic_is_valid: Callable[[Any], bool],
    ) -> None:
        self.amount_with_label = amount_with_label
        self.classify_intent = classify_intent
        self.concrete_fallback_logic = concrete_fallback_logic
        self.derived_rupee = derived_rupee
        self.fallback_numeric_flow = fallback_numeric_flow
        self.first_numeric_value = first_numeric_value
        self.inflation_output = inflation_output
        self.logic_from_classified_intent = logic_from_classified_intent
        self.money_tokens = money_tokens
        self.minimal_narration_flow = minimal_narration_flow
        self.percent_tokens = percent_tokens
        self.string_visual_logic_to_object = string_visual_logic_to_object
        self.typed_visual_logic_is_valid = typed_visual_logic_is_valid

    def contextual_visual_logic_object(self, context: str, beat: dict[str, Any] | None = None) -> dict[str, Any]:
        classified_intent = str((beat or {}).get("classified_intent") or "").upper()
        if classified_intent in {"EMPHASIS", "COMPARISON", "FLOW", "DECAY"}:
            return self.logic_from_classified_intent(context, classified_intent, beat)
        lowered = context.lower()
        amounts = list(dict.fromkeys(self.money_tokens(context)))
        percents = list(dict.fromkeys(self.percent_tokens(context)))
        if any(word in lowered for word in ("earn", "earned", "spend", "spent", "left", "vanish", "vanished")) and amounts:
            source = self.amount_with_label(amounts[0], "Salary")
            process = self.amount_with_label(amounts[1], "Expenses") if len(amounts) > 1 else self.derived_rupee(amounts[0], 0.92, "Expenses")
            result = self.amount_with_label(amounts[2], "Left") if len(amounts) > 2 else self.derived_rupee(amounts[0], 0.08, "Left")
            return {"type": "flow", "source": source, "process": process, "result": result}
        if any(word in lowered for word in ("tax", "taxes", "elss", "deduction", "80c")):
            paid = self.amount_with_label(amounts[0] if amounts else "₹20,000", "tax paid")
            deduction = self.amount_with_label(amounts[1] if len(amounts) > 1 else "₹1,50,000", "deduction")
            return {"type": "comparison", "left": paid, "right": deduction}
        if percents and amounts and any(word in lowered for word in ("save", "saved", "cannot", "can't", "broke")):
            return {"type": "comparison", "left": f"{percents[0]} of people", "right": f"{amounts[0]} savings"}
        if any(word in lowered for word in ("automate", "auto debit", "manual", "emotion", "emotional")):
            amount = amounts[0] if amounts else "₹5,000"
            result = amounts[1] if len(amounts) > 1 and self.first_numeric_value(amounts[1]) == 0 else "₹0 Saved"
            return {
                "type": "flow",
                "source": self.amount_with_label(amount, "Auto Debit"),
                "process": self.amount_with_label(amount, "Invested"),
                "result": self.amount_with_label(result, "Emotional Spend"),
            }
        if (
            beat
            and isinstance(beat.get("visual_logic"), dict)
            and str(beat["visual_logic"].get("type") or "").lower() == "flow"
            and any(word in lowered for word in ("salary", "paycheck", "income"))
        ):
            salary = amounts[0] if amounts else "₹25,000 Salary"
            expense = amounts[1] if len(amounts) > 1 else self.derived_rupee(salary, 0.92, "Expenses")
            left = amounts[2] if len(amounts) > 2 else self.derived_rupee(salary, 0.08, "Left")
            return {
                "type": "flow",
                "source": self.amount_with_label(salary, "Salary"),
                "process": self.amount_with_label(expense, "Expenses"),
                "result": self.amount_with_label(left, "Left"),
            }
        if any(word in lowered for word in ("salary", "paycheck", "income")) and any(word in lowered for word in ("leak", "defaults", "default")) and len(amounts) >= 2:
            return {
                "type": "comparison",
                "left": self.amount_with_label(amounts[0], "Salary"),
                "right": self.amount_with_label(amounts[1], "Invisible Leak"),
            }
        if any(word in lowered for word in ("budget", "waste", "spend", "spent", "monthly", "leak", "gone")):
            waste = amounts[0] if amounts else "₹5,000 Monthly Leak"
            yearly = amounts[1] if len(amounts) > 1 else self.derived_rupee(waste, 12, "Yearly Loss")
            return {"type": "flow", "source": self.amount_with_label(waste, "Monthly Leak"), "process": "12 months", "result": self.amount_with_label(yearly, "Lost")}
        if any(word in lowered for word in ("fd", "fixed deposit", "inflation")):
            principal = amounts[0] if amounts else "₹1,00,000"
            rate = percents[0] if percents else "6% Inflation"
            output = self.inflation_output(principal, rate) if amounts or percents else "₹94,000 Real Value"
            return {"type": "decay", "input": principal, "factor": rate if "inflation" in rate.lower() else f"{rate} Inflation", "output": f"{output} Real Value"}
        if any(word in lowered for word in ("credit", "debt", "loan", "interest")):
            if len(amounts) >= 2:
                return {"type": "comparison", "left": self.amount_with_label(amounts[0], "Debt"), "right": self.amount_with_label(amounts[1], "Interest")}
            return self.minimal_narration_flow(context, "DECAY")
        if any(word in lowered for word in ("salary", "paycheck", "income", "expense", "expenses")):
            salary = amounts[0] if amounts else "₹25,000 Salary"
            expense = amounts[1] if len(amounts) > 1 else self.derived_rupee(salary, 0.92, "Expenses")
            left = amounts[2] if len(amounts) > 2 else self.derived_rupee(salary, 0.08, "Left")
            return {
                "type": "flow",
                "source": self.amount_with_label(salary, "Salary"),
                "process": self.amount_with_label(expense, "Expenses"),
                "result": self.amount_with_label(left, "Left"),
            }
        if len(amounts) >= 2:
            return {"type": "comparison", "left": amounts[0], "right": amounts[1]}
        if beat:
            fallback = self.concrete_fallback_logic(beat)
            logic = self.string_visual_logic_to_object(fallback, context)
            if logic and self.typed_visual_logic_is_valid(logic):
                return logic
        return self.minimal_narration_flow(context, self.classify_intent(context))
