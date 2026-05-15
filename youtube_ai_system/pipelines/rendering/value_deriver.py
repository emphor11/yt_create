from __future__ import annotations

from .numbers import RenderNumberUtils


class RenderValueDeriver:
    """Derived money labels used by render-spec visual logic."""

    def __init__(self, number_utils: RenderNumberUtils | None = None) -> None:
        self.number_utils = number_utils or RenderNumberUtils()

    def amount_with_label(self, amount: str, label: str) -> str:
        return amount if label.lower() in amount.lower() else f"{amount} {label}"

    def inflation_output(self, principal: str, rate: str) -> str:
        principal_value = self.number_utils.first_numeric_value(principal)
        rate_value = self.number_utils.first_numeric_value(rate)
        if principal_value <= 0 or rate_value <= 0:
            return "₹94,000"
        return self.number_utils.format_rupees(principal_value * max(0.0, 1 - (rate_value / 100)))

    def derived_rupee(self, amount: str, multiplier: float, label: str) -> str:
        value = self.number_utils.first_numeric_value(amount)
        if value <= 0:
            return f"₹0 {label}"
        return f"{self.number_utils.format_rupees(value * multiplier)} {label}"
