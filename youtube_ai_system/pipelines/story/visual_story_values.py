from __future__ import annotations

import re
from typing import Any


class VisualStoryValueHelper:
    def read_nested(self, data: dict[str, Any], path: str) -> Any:
        value: Any = data
        for part in path.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value

    def as_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    def format_money_like(self, value: Any) -> str:
        if value is None or value == "":
            return ""
        if isinstance(value, str):
            return value if "₹" in value else value.strip()
        try:
            amount = float(value)
        except (TypeError, ValueError):
            return str(value)
        rounded = int(round(amount))
        digits = str(abs(rounded))
        if len(digits) <= 3:
            formatted = digits
        else:
            formatted = digits[-3:]
            digits = digits[:-3]
            while digits:
                formatted = digits[-2:] + "," + formatted
                digits = digits[:-2]
        return ("-" if rounded < 0 else "") + "₹" + formatted

    def first_money(self, text: str) -> str:
        values = self.money_values(text)
        return values[0] if values else ""

    def money_values(self, text: str) -> list[str]:
        pattern = re.compile(r"(?:₹\s*|Rs\.?\s*)\d[\d,]*(?:\.\d+)?\s*(?:lakh|lakhs|crore|crores|k)?", re.IGNORECASE)
        return [match.group(0).replace(" ", "") for match in pattern.finditer(text)]

    def dedupe(self, items: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result
