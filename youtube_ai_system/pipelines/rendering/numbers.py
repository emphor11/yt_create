from __future__ import annotations

import re


class RenderNumberUtils:
    """Numeric token and rupee-format helpers for render specs."""

    def first_numeric_value(self, text: str) -> float:
        match = re.search(r"[\d,.]+", text)
        if not match:
            return 0.0
        try:
            return float(match.group(0).replace(",", ""))
        except ValueError:
            return 0.0

    def format_rupees(self, value: float) -> str:
        number = int(round(value / 100.0) * 100) if value >= 1000 else int(round(value))
        raw = str(max(number, 0))
        if len(raw) <= 3:
            return f"₹{raw}"
        last_three = raw[-3:]
        rest = raw[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        return "₹" + ",".join(groups + [last_three])

    def money_tokens(self, text: str) -> list[str]:
        return [
            token.replace(" ", "").rstrip(".,")
            for token in re.findall(r"₹\s?[\d,.]+(?:\s?(?:lakhs?|crores?|k|m)\b)?", text, re.I)
        ]

    def percent_tokens(self, text: str) -> list[str]:
        return re.findall(r"\d+(?:\.\d+)?%", text)

    def numeric_values(self, text: str) -> list[float]:
        values: list[float] = []
        for value in re.findall(r"\d+(?:\.\d+)?", text):
            try:
                values.append(float(value))
            except ValueError:
                continue
        return values
