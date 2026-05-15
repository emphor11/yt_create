from __future__ import annotations

import re
from typing import Any

from .constants import FINANCIAL_NUMBER_KEYWORDS


class StoryNumericSupportMixin:
    def numeric_visual_plan(self, text: str) -> dict[str, Any] | None:
        numeric_phrases = self.numeric_phrases(text)
        if not self._numeric_visual_allowed(text, numeric_phrases):
            return None
        if len(numeric_phrases) >= 2:
            strongest = numeric_phrases[-1]
            return {
                "concept": {"concept": strongest, "type": "numeric"},
                "visual": {
                    "pattern": "NumericComparison",
                    "data": {"values": numeric_phrases[:3]},
                },
                "beats": {
                    "beats": self._numeric_beats(numeric_phrases[:3], strongest),
                },
            }
        strongest = numeric_phrases[0]
        return {
            "concept": {"concept": strongest, "type": "numeric"},
            "visual": {
                "pattern": "NumericComparison",
                "data": {"values": [strongest]},
            },
            "beats": {
                "beats": [{"component": "StatCard", "text": strongest}],
            },
        }

    def numeric_phrases(self, text: str) -> list[str]:
        if not re.search(r"(₹|Rs\.?\s*|\d|%)", text, flags=re.IGNORECASE):
            return []
        pattern = r"(?:₹\s*|Rs\.?\s*)?\d[\d,]*(?:\.\d+)?\s*(?:%|years?|months?|lakhs?)?"
        matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
        phrases: list[str] = []
        for match in matches:
            token = " ".join(match.group(0).strip().split())
            if not token or not re.search(r"\d", token):
                continue
            if not self._is_financial_number(text, token, match.start(), match.end()):
                continue
            label = self._numeric_label(text, match.start(), match.end())
            phrase = f"{token} {label}".strip() if label else token
            phrases.append(" ".join(phrase.split()))
        return self._unique_beat_values(phrases, phrases[-1] if phrases else "")

    def _unique_beat_values(self, values: list[str], strongest: str) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not value.strip():
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(value)
        if strongest.strip() and strongest.lower() not in seen:
            unique.append(strongest)
        return unique[:3]

    def _is_financial_number(self, text: str, token: str, start: int, end: int) -> bool:
        if "₹" in token or "%" in token or token.lower().startswith("rs"):
            return True
        trailing = text[end : min(len(text), end + 2)].lower()
        if trailing.startswith("s"):
            return False
        before_words = re.findall(r"[a-z]+", text[max(0, start - 24) : start].lower())
        after_words = re.findall(r"[a-z]+", text[end : min(len(text), end + 24)].lower())
        if any(word in {"day", "days", "age", "aged", "year", "years"} for word in before_words[-2:]):
            return False
        if any(word in {"day", "days"} for word in after_words[:2]):
            return False
        if any(word in FINANCIAL_NUMBER_KEYWORDS for word in after_words[:4]):
            return True
        if any(word in FINANCIAL_NUMBER_KEYWORDS for word in before_words[-2:]):
            return True
        return False

    def _numeric_label(self, text: str, start: int, end: int) -> str:
        before_words = re.findall(r"[a-z]+", text[max(0, start - 40) : start].lower())
        after_words = re.findall(r"[a-z]+", text[end : min(len(text), end + 40)].lower())
        keywords = {
            "interest": "interest",
            "bill": "bill",
            "balance": "balance",
            "debt": "debt",
            "payment": "payment",
            "salary": "salary",
            "return": "return",
            "returns": "returns",
            "cost": "cost",
            "emi": "emi",
            "principal": "principal",
            "minimum": "payment",
            "due": "payment",
            "leak": "leak",
            "lost": "lost",
            "wasted": "wasted",
            "waste": "wasted",
        }
        for word in after_words[:5]:
            if word in keywords:
                return keywords[word]
        for word in reversed(before_words[-5:]):
            if word in keywords:
                return keywords[word]
        impact = self._numeric_impact_label(text)
        if impact:
            return impact
        return ""

    def _numeric_impact_label(self, text: str) -> str:
        lowered = text.lower()
        if "interest" in lowered:
            return "interest"
        if any(token in lowered for token in ("leak", "leaks")):
            return "leak"
        if any(token in lowered for token in ("lost", "lose", "loss")):
            return "lost"
        if any(token in lowered for token in ("wasted", "waste")):
            return "wasted"
        if "cost" in lowered:
            return "cost"
        return ""

    def _numeric_beats(self, numeric_phrases: list[str], strongest: str) -> list[dict[str, Any]]:
        values = self._unique_beat_values(numeric_phrases, strongest)
        calculation = self._calculation_from_values(values)
        if calculation:
            beats: list[dict[str, Any]] = [
                {"component": "StatCard", "text": values[0], "subtext": self._value_subtext(values[0])},
            ]
            if calculation["rate"]:
                beats.append({"component": "StatCard", "text": calculation["rate"], "subtext": "rate"})
            beats.append(
                {
                    "component": "CalculationStrip",
                    "text": calculation["text"],
                    "steps": calculation["steps"],
                }
            )
            beats.append({"component": "StatCard", "text": calculation["result"], "subtext": self._value_subtext(calculation["result"])})
            return beats
        if len(values) == 2:
            return [
                {"component": "StatCard", "text": values[0], "subtext": self._value_subtext(values[0])},
                {"component": "FlowBar", "text": values[1], "subtext": self._value_subtext(values[1])},
            ]
        if len(values) >= 3:
            return [
                {"component": "StatCard", "text": values[0], "subtext": self._value_subtext(values[0])},
                {"component": "FlowBar", "text": values[1], "subtext": self._value_subtext(values[1])},
                {"component": "StatCard", "text": values[2], "subtext": self._value_subtext(values[2])},
            ]
        return (
            [{"component": "StatCard", "text": values[0], "subtext": self._value_subtext(values[0])}]
            if values
            else [{"component": "StatCard", "text": strongest}]
        )

    def _calculation_from_values(self, values: list[str]) -> dict[str, Any] | None:
        if len(values) < 2:
            return None
        money_values = [value for value in values if "₹" in value or value.lower().startswith("rs")]
        rate_values = [value for value in values if "%" in value]
        if not money_values or not rate_values:
            return None
        base = money_values[0]
        rate = rate_values[0]
        result = money_values[-1] if len(money_values) > 1 else ""
        if not result or result == base:
            estimated = self._estimated_rate_result(base, rate)
            if not estimated:
                return None
            result = estimated
        text = f"{self._strip_value_label(base)} x {self._strip_value_label(rate)} = {self._strip_value_label(result)}"
        return {
            "text": text,
            "rate": rate,
            "result": result,
            "steps": [
                {"label": self._value_subtext(base) or "Amount", "value": self._strip_value_label(base)},
                {"label": self._value_subtext(rate) or "Rate", "value": self._strip_value_label(rate), "operation": "x"},
                {"label": self._value_subtext(result) or "Cost", "value": self._strip_value_label(result), "operation": "="},
            ],
        }

    def _estimated_rate_result(self, base: str, rate: str) -> str:
        base_number = self._numeric_amount(base)
        rate_number = self._numeric_amount(rate)
        if base_number is None or rate_number is None or "%" not in rate:
            return ""
        result = base_number * rate_number / 100
        return self._format_rupee_amount(result)

    def _numeric_amount(self, value: str) -> float | None:
        cleaned = re.sub(r"[^\d.]", "", value)
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _format_rupee_amount(self, amount: float) -> str:
        rounded = int(round(amount))
        digits = str(rounded)
        if len(digits) <= 3:
            grouped = digits
        else:
            grouped = digits[-3:]
            digits = digits[:-3]
            while digits:
                grouped = digits[-2:] + "," + grouped
                digits = digits[:-2]
        return f"₹{grouped}"

    def _strip_value_label(self, value: str) -> str:
        parts = str(value or "").split()
        if not parts:
            return ""
        if re.search(r"₹|%|\d", parts[0]):
            return parts[0]
        return str(value or "").strip()

    def _value_subtext(self, value: str) -> str:
        parts = str(value or "").split()
        if len(parts) <= 1:
            return ""
        return self._short_visual_text(" ".join(parts[1:]))

    def _short_visual_text(self, text: str) -> str:
        words = [word.strip(" ,.-") for word in str(text or "").split() if word.strip(" ,.-")]
        if not words:
            return ""
        return " ".join(words[:5])

    def _numeric_visual_allowed(self, text: str, numeric_phrases: list[str]) -> bool:
        if not numeric_phrases:
            return False
        lowered = text.lower()
        has_comparison = any(word in lowered for word in (" more ", " less ", " vs ", " versus "))
        has_transformation = any(word in lowered for word in (" increase", " increases", " reduce", " reduces", " grow", " grows "))
        if len(numeric_phrases) >= 2:
            return True
        return has_comparison or has_transformation
