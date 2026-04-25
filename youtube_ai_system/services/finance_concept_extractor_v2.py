from __future__ import annotations

import re
from typing import Any


class FinanceConceptExtractorV2:
    """Maps idea-group sections to strong canonical finance concepts."""

    KEYWORD_RULES: tuple[tuple[tuple[str, ...], str, str], ...] = (
        (("raise", "lifestyle creep", "lifestyle inflation", "upgrade", "fancy phone", "brand new car", "fancy wedding"), "Lifestyle Inflation", "risk"),
        (("credit card", "minimum payment", "minimum dues", "outstanding balance", "interest rate"), "Debt Trap", "risk"),
        (("expense", "expenses", "subscription", "subscriptions", "spending", "dining out", "ordering in", "premium"), "Expense Leakage", "risk"),
        (("emergency fund", "cash buffer", "medical emergency", "lose your job"), "Emergency Fund", "definition"),
        (("compound", "compounding"), "Compounding Growth", "growth"),
        (("investment", "investing", "returns", "mutual fund", "sip"), "Investment Growth", "growth"),
        (("tax", "ppf", "nps", "elss", "tax benefit"), "Tax Saving", "definition"),
        (("budget", "budgeting", "track", "50/30/20", "allocate"), "Budgeting", "process"),
        (("inflation", "buying power", "prices rise"), "Inflation Loss", "risk"),
        (("insurance", "policy", "policies"), "Insurance Drain", "risk"),
        (("negotiating your salary", "negotiate your salary"), "Salary Growth", "growth"),
    )

    ENTITY_DEFAULTS = {
        "salary": ("Salary Leakage", "risk"),
        "income": ("Income Leakage", "risk"),
        "debt": ("Debt Trap", "risk"),
        "loan": ("Debt Trap", "risk"),
        "emi": ("EMI Burden", "risk"),
        "credit": ("Debt Trap", "risk"),
        "savings": ("Emergency Fund", "definition"),
        "investment": ("Investment Growth", "growth"),
        "inflation": ("Inflation Loss", "risk"),
        "expense": ("Expense Leakage", "risk"),
        "expenses": ("Expense Leakage", "risk"),
        "tax": ("Tax Saving", "definition"),
        "wealth": ("Wealth Growth", "growth"),
        "interest": ("Debt Trap", "risk"),
    }

    def extract(self, text: str, *, entity: str | None = None) -> dict[str, Any]:
        normalized = " ".join(str(text or "").strip().split())
        lowered = normalized.lower()
        entity_lower = (entity or "").strip().lower()

        for keywords, concept, concept_type in self.KEYWORD_RULES:
            if any(keyword in lowered for keyword in keywords):
                return {"concept": concept, "type": concept_type}

        if self._is_comparison(lowered):
            left, right = self._comparison_entities(normalized)
            if left and right:
                return {"concept": f"{left} vs {right}", "type": "comparison"}

        return self._derive_manually(normalized, entity_lower)

    def _derive_manually(self, text: str, entity: str) -> dict[str, Any]:
        lowered = text.lower()

        if entity == "salary" and any(token in lowered for token in ("spend", "spending", "expenses", "leak", "leaks", "gone")):
            return {"concept": "Salary Leakage", "type": "risk"}
        if any(token in lowered for token in ("subscription", "subscriptions", "dining", "ordering", "expense", "expenses", "spending")):
            return {"concept": "Expense Leakage", "type": "risk"}
        if any(token in lowered for token in ("credit card", "interest", "minimum", "loan", "emi", "debt")):
            return {"concept": "Debt Trap", "type": "risk"}
        if any(token in lowered for token in ("emergency", "medical emergency", "lose your job", "buffer")):
            return {"concept": "Emergency Fund", "type": "definition"}
        if any(token in lowered for token in ("invest", "returns", "wealth", "grow", "growth")):
            return {"concept": "Investment Growth", "type": "growth"}
        if any(token in lowered for token in ("tax", "ppf", "nps", "elss")):
            return {"concept": "Tax Saving", "type": "definition"}
        if any(token in lowered for token in ("budget", "track", "allocate")):
            return {"concept": "Budgeting", "type": "process"}
        if entity in self.ENTITY_DEFAULTS:
            concept, concept_type = self.ENTITY_DEFAULTS[entity]
            return {"concept": concept, "type": concept_type}
        if re.search(r"₹|%|\d+", text):
            if "salary" in lowered:
                return {"concept": "Salary Leakage", "type": "risk"}
            return {"concept": "Money Impact", "type": "definition"}
        return {"concept": "Money Insight", "type": "definition"}

    def _is_comparison(self, text: str) -> bool:
        return any(token in text for token in (" vs ", " versus ", " compared to ", " however ", " instead "))

    def _comparison_entities(self, text: str) -> tuple[str | None, str | None]:
        for marker in (" vs ", " versus ", " compared to ", " however ", " instead "):
            if marker in text.lower():
                left, right = re.split(marker, text, maxsplit=1, flags=re.IGNORECASE)
                return self._extract_entity(left), self._extract_entity(right)
        return None, None

    def _extract_entity(self, text: str) -> str | None:
        lowered = text.lower()
        ordered = [
            "equity",
            "debt",
            "salary",
            "income",
            "credit",
            "loan",
            "emi",
            "investment",
            "savings",
            "inflation",
            "expense",
            "tax",
            "wealth",
        ]
        for item in ordered:
            if item in lowered:
                return " ".join(part.capitalize() for part in item.split())
        return None
