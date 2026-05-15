from __future__ import annotations


class IndianNumberFormatter:
    """Formats numeric chart labels using the current compact Indian style."""

    def format_number(self, value: float) -> str:
        if value >= 10_000_000:
            formatted = f"{value / 10_000_000:.1f}".rstrip("0").rstrip(".")
            return f"{formatted}Cr"
        if value >= 100_000:
            formatted = f"{value / 100_000:.1f}".rstrip("0").rstrip(".")
            return f"{formatted}L"
        if value >= 1000:
            return self.format_indian_grouped_number(int(round(value)))
        if value == int(value):
            return f"{int(value)}"
        return f"{value:.1f}"

    def format_indian_grouped_number(self, value: int) -> str:
        sign = "-" if value < 0 else ""
        digits = str(abs(value))
        if len(digits) <= 3:
            return f"{sign}{digits}"
        grouped = digits[-3:]
        digits = digits[:-3]
        while digits:
            grouped = digits[-2:] + "," + grouped
            digits = digits[:-2]
        return f"{sign}{grouped}"
