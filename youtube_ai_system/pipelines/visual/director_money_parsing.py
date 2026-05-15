from __future__ import annotations

import re
from typing import Any

from .director_types import VisualDirectorInput


class VisualDirectorMoneyParsingMixin:
    def _explicit_salary_amount(self, text: str) -> float | None:
        patterns = (
            r"(?:salary|income|paycheck|pay)\D{0,18}(?:₹\s*|Rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)",
            r"(?:₹\s*|Rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)\D{0,18}(?:salary|income|paycheck|pay)",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount = float(match.group(1).replace(",", ""))
                if amount < 1000 and "lakh" in self._window(text, match.start(), match.end(), 16).lower():
                    amount *= 100000
                return amount
        return None

    def _explicit_remaining_amount(self, text: str) -> float | None:
        match = re.search(
            r"(?:left|leftover|remaining|cash\s+left|survive\s+on|only)\D{0,18}(?:₹\s*|Rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        amount = float(match.group(1).replace(",", ""))
        if amount < 1000 and "lakh" in self._window(text, match.start(), match.end(), 16).lower():
            amount *= 100000
        return amount

    def _money_mentions(self, text: str) -> list[dict[str, Any]]:
        pattern = re.compile(r"(?:₹\s*|Rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)\s*(lakh|lakhs|crore|crores|k)?", re.IGNORECASE)
        mentions: list[dict[str, Any]] = []
        finance_window_re = re.compile(
            r"\b(?:rs|emi|rent|salary|sip|payment|balance|food|left|invest|loan|debt|interest|corpus|returns?|wealth|tax|income|savings?)\b",
            re.IGNORECASE,
        )
        for match in pattern.finditer(text):
            raw = match.group(0).strip()
            if text[match.end() : match.end() + 1] == "%":
                continue
            after_unit = text[match.end() : match.end() + 24].lower()
            if re.match(r"\s*(years?\s+old|months?\s+old|days?\s+ago|minutes?|seconds?|hours?)\b", after_unit):
                continue
            before_text = text[max(0, match.start() - 12) : match.start()].lower()
            if "₹" not in raw and not raw.lower().startswith("rs") and re.search(r"(?:day|year|years|month|months)\s*$", before_text):
                continue
            if not raw:
                continue
            if "₹" not in raw and not raw.lower().startswith("rs") and not finance_window_re.search(self._window(text, match.start(), match.end(), radius=60)):
                continue
            amount = float(match.group(1).replace(",", ""))
            unit = (match.group(2) or "").lower()
            if unit.startswith("lakh"):
                amount *= 100000
            elif unit.startswith("crore"):
                amount *= 10000000
            elif unit == "k":
                amount *= 1000
            mentions.append(
                {
                    "value": self._format_rupee(amount),
                    "amount": amount,
                    "label": self._label_for_amount(text, match.start(), match.end()),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
        return mentions

    def _explicit_flows(self, text: str, source: dict[str, Any]) -> list[dict[str, Any]]:
        flows = []
        for item in self._money_mentions(text):
            if item is source or item["amount"] == source["amount"]:
                continue
            label = item["label"] or ""
            if label.lower() in {"left", "leftover", "remaining", "remainder", "salary", "income"}:
                continue
            if not label:
                label = self._nearest_category(text, int(item["start"]), int(item["end"]))
            if label:
                flows.append({"label": label, "value": self._format_rupee(item["amount"]), "amount": float(item["amount"]), "color": "orange", "order": 0})
        return self._dedupe_flows(flows)

    def _percentage_flows(self, text: str, source_amount: float, seen: set[str]) -> list[dict[str, Any]]:
        flows = []
        for match in re.finditer(r"(\d+(?:\.\d+)?)\s*%\s*(?:on|for|to|towards|in)?\s*([A-Za-z ]{0,24})", text, re.IGNORECASE):
            label = self._category_from_text(match.group(2)) or self._nearest_category(text, match.start(), match.end())
            if not label or label.lower() in seen:
                continue
            amount = source_amount * float(match.group(1)) / 100.0
            flows.append({"label": label, "value": self._format_rupee(amount), "amount": round(amount, 2), "color": "orange", "order": 0})
        return flows

    def _estimated_flows(self, text: str, source_amount: float, seen: set[str]) -> list[dict[str, Any]]:
        lowered = text.lower()
        flows = []
        for token, ratio in self.CATEGORY_ESTIMATES.items():
            label = self._label_from_category(token)
            if token in lowered and label.lower() not in seen:
                amount = source_amount * ratio
                flows.append({"label": label, "value": self._format_rupee(amount), "amount": round(amount, 2), "color": "orange", "order": 0})
        return flows[:3]

    def _source_amount(self, amounts: list[dict[str, Any]], text: str) -> dict[str, Any] | None:
        for item in amounts:
            label = str(item.get("label") or "").lower()
            if label in {"salary", "income"}:
                return item
        if "salary" in text.lower() or "income" in text.lower():
            return max(amounts, key=lambda item: float(item["amount"]), default=None)
        return amounts[0] if amounts else None

    def _principal_amount(self, amounts: list[dict[str, Any]], text: str, director_input: VisualDirectorInput) -> float | None:
        for item in amounts:
            label = str(item.get("label") or "").lower()
            if label in {"balance", "debt", "principal", "loan", "card balance", "credit card balance"}:
                return float(item["amount"])
        parsed = self._parse_rupee(director_input.start_value)
        if parsed is not None:
            return parsed
        return float(amounts[0]["amount"]) if amounts else None

    def _minimum_payment(self, amounts: list[dict[str, Any]], text: str, principal: float) -> float | None:
        for item in amounts:
            label = str(item.get("label") or "").lower()
            if "minimum" in label or "payment" in label:
                return float(item["amount"])
        smaller = [float(item["amount"]) for item in amounts if float(item["amount"]) < principal]
        return min(smaller) if smaller else None

    def _sip_amount(self, amounts: list[dict[str, Any]], text: str, director_input: VisualDirectorInput) -> float | None:
        for item in amounts:
            label = str(item.get("label") or "").lower()
            if "sip" in label or "monthly" in label or "invest" in label:
                return float(item["amount"])
        parsed = self._parse_rupee(director_input.start_value)
        if parsed is not None:
            return parsed
        return float(amounts[0]["amount"]) if amounts else None

    def _remainder_amount(self, amounts: list[dict[str, Any]], text: str, source: dict[str, Any], flow_total: float) -> float | None:
        for item in amounts:
            label = str(item.get("label") or "").lower()
            if label in {"left", "leftover", "remaining", "remainder"}:
                return float(item["amount"])
        match = re.search(r"only\s+(?:₹\s*|Rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)\s*(?:is\s+)?left", text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", ""))
        if flow_total:
            return max(float(source["amount"]) - flow_total, 0.0)
        return None

    def _label_for_amount(self, text: str, start: int, end: int) -> str:
        before = text[max(0, start - 24) : start].lower()
        after = text[end : min(len(text), end + 24)].lower()
        if "salary" in before or "salary" in after:
            return "Salary"
        if ("tax" in before or "tax" in after or "gst" in before or "gst" in after) and any(
            token in f"{before} {after}" for token in ("take", "takes", "taken", "cut", "deduct", "before money")
        ):
            return "Tax"
        if "income" in before or "income" in after:
            return "Income"
        if "earn" in before or "earned" in before or "earning" in before:
            return "Salary"
        immediate_category = self._nearest_expense_category(before, after)
        if immediate_category:
            return immediate_category
        if "left" in after or "left" in before or "remaining" in after:
            return "left"
        if "tax" in before or "tax" in after or "gst" in before or "gst" in after:
            return "Tax"
        if "balance" in before or "balance" in after:
            return "Balance"
        if "payment" in before or "payment" in after:
            return "Minimum payment" if "minimum" in before or "minimum" in after else "Payment"
        window = self._window(text, start, end).lower()
        category = self._category_from_text(window)
        if category:
            return category
        return ""

    def _expense_category_from_text(self, text: str) -> str:
        lowered = text.lower()
        for token, label in (
            ("emi", "EMI"),
            ("rent", "Rent"),
            ("food", "Food"),
            ("groceries", "Groceries"),
            ("grocery", "Groceries"),
            ("lifestyle", "Lifestyle"),
            ("shopping", "Shopping"),
            ("subscription", "Subscriptions"),
        ):
            if token in lowered:
                return label
        return ""

    def _nearest_expense_category(self, before: str, after: str) -> str:
        candidates = (
            ("emi", "EMI"),
            ("rent", "Rent"),
            ("food", "Food"),
            ("groceries", "Groceries"),
            ("grocery", "Groceries"),
            ("lifestyle", "Lifestyle"),
            ("shopping", "Shopping"),
            ("subscription", "Subscriptions"),
        )
        best_before_label = ""
        best_before_distance = 10_000
        for token, label in candidates:
            before_index = before.rfind(token)
            if before_index >= 0:
                distance = len(before) - before_index
                if distance < best_before_distance:
                    best_before_label = label
                    best_before_distance = distance
        if best_before_label:
            return best_before_label

        best_label = ""
        best_distance = 10_000
        for token, label in candidates:
            after_index = after.find(token)
            if after_index >= 0 and after_index + 1 < best_distance:
                best_label = label
                best_distance = after_index + 1
        return best_label

    def _nearest_category(self, text: str, start: int, end: int) -> str:
        return self._category_from_text(self._window(text, start, end))

    def _category_from_text(self, text: str) -> str:
        lowered = text.lower()
        category_map = [
            ("emi", "EMI"),
            ("rent", "Rent"),
            ("food", "Food"),
            ("groceries", "Groceries"),
            ("grocery", "Groceries"),
            ("lifestyle", "Lifestyle"),
            ("shopping", "Shopping"),
            ("subscription", "Subscriptions"),
            ("tax", "Tax"),
            ("gst", "Tax"),
            ("salary", "Salary"),
            ("income", "Income"),
            ("sip", "SIP"),
            ("invest", "Investment"),
            ("minimum", "Minimum payment"),
            ("payment", "Payment"),
            ("principal", "Principal"),
            ("debt", "Debt"),
            ("loan", "Loan"),
            ("balance", "Balance"),
        ]
        for token, label in category_map:
            if token in lowered:
                return label
        return ""

    def _label_from_category(self, category: str) -> str:
        return self._category_from_text(category) or category.replace("_", " ").title()

    def _dedupe_flows(self, flows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: dict[str, dict[str, Any]] = {}
        for flow in flows:
            key = str(flow["label"]).lower()
            if key not in deduped or float(flow["amount"]) > float(deduped[key]["amount"]):
                deduped[key] = flow
        return list(deduped.values())

    def _first_percentage(self, text: str) -> float | None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        return float(match.group(1)) if match else None

    def _months_from_text(self, text: str) -> int | None:
        match = re.search(r"(\d+)\s*months?", str(text), re.IGNORECASE)
        if match:
            return int(match.group(1))
        years = self._years_from_text(text)
        return years * 12 if years else None

    def _years_from_text(self, text: str) -> int | None:
        match = re.search(r"(\d+)\s*years?", str(text), re.IGNORECASE)
        return int(match.group(1)) if match else None

    def _parse_rupee(self, value: str | None) -> float | None:
        if not value:
            return None
        match = re.search(r"(?:₹\s*|Rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)\s*(lakh|lakhs|crore|crores|k)?", value, re.IGNORECASE)
        if not match:
            return None
        amount = float(match.group(1).replace(",", ""))
        unit = (match.group(2) or "").lower()
        if unit.startswith("lakh"):
            amount *= 100000
        elif unit.startswith("crore"):
            amount *= 10000000
        elif unit == "k":
            amount *= 1000
        return amount

    def _format_rupee(self, amount: float | int) -> str:
        rounded = int(round(float(amount)))
        sign = "-" if rounded < 0 else ""
        digits = str(abs(rounded))
        if len(digits) <= 3:
            grouped = digits
        else:
            grouped = digits[-3:]
            digits = digits[:-3]
            while digits:
                grouped = digits[-2:] + "," + grouped
                digits = digits[:-2]
        return f"{sign}₹{grouped}"

    def _window(self, text: str, start: int, end: int, radius: int = 36) -> str:
        return text[max(0, start - radius) : min(len(text), end + radius)]

    def _short_phrase(self, text: str, fallback: str) -> str:
        words = [word.strip(" ,.-") for word in text.split() if word.strip(" ,.-")]
        return " ".join(words[:4]) or fallback

