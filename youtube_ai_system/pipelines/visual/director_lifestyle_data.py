from __future__ import annotations

import re
from typing import Any

from ...services.financial_governance import first_fact, numeric_role_map
from .director_types import VisualDirectorInput


class VisualDirectorLifestyleDataMixin:
    def _lifestyle_creep_data(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        semantic_data = self._semantic_lifestyle_creep_data(director_input)
        if semantic_data:
            return semantic_data
        text = director_input.narration_text
        numeric_roles = numeric_role_map(text, scene_id="visual_director")
        facts = list(numeric_roles.get("facts") or [])
        amounts = self._money_mentions(text)
        income_mentions = [
            float(item["amount"])
            for item in amounts
            if str(item.get("label") or "").lower() in {"salary", "income"}
        ]
        all_amounts = [float(item["amount"]) for item in amounts]
        lowered = text.lower()
        monthly_payment_context = any(token in lowered for token in ("luxury car", "car emi", "monthly payment", "monthly payments", "5-year loan", "5 year loan"))
        if monthly_payment_context and not income_mentions:
            monthly_amount = next(
                (
                    float(item["amount"])
                    for item in amounts
                    if any(token in str(item.get("label") or "").lower() for token in ("emi", "payment", "monthly"))
                ),
                None,
            )
            if monthly_amount is None:
                small_amounts = [amount for amount in all_amounts if amount < 1000000]
                monthly_amount = small_amounts[0] if small_amounts else 93000.0
            attached_cost = max(monthly_amount * 0.38, 25000.0)
            expanded_cost = monthly_amount + attached_cost
            return {
                "title": "The EMI upgrades the lifestyle.",
                "start_income": {"value": self._format_rupee(monthly_amount), "amount": round(monthly_amount, 2), "source_number_ids": [], "derived": False},
                "end_income": {"value": self._format_rupee(expanded_cost), "amount": round(expanded_cost, 2), "source_number_ids": [], "derived": True},
                "old_spending": {"value": self._format_rupee(monthly_amount), "amount": round(monthly_amount, 2), "derived": True, "derived_from": [], "derivation_method": "monthly payment baseline"},
                "new_spending": {"value": self._format_rupee(expanded_cost), "amount": round(expanded_cost, 2), "derived": True, "derived_from": [], "derivation_method": "monthly payment plus attached lifestyle costs"},
                "old_savings": {"value": self._format_rupee(0), "amount": 0.0, "derived": True, "derived_from": [], "derivation_method": "not an income scene"},
                "new_savings": {"value": self._format_rupee(0), "amount": 0.0, "derived": True, "derived_from": [], "derivation_method": "not an income scene"},
                "raise": {"value": self._format_rupee(attached_cost), "amount": round(attached_cost, 2), "source_number_ids": [], "derived": True, "derived_from": [], "derivation_method": "estimated insurance, fuel, service, and lifestyle add-ons"},
                "accent": "warning",
                "numeric_provenance": facts,
                "truth_mode": "hard",
                "beat_labels": {
                    "income_base": "Car EMI starts",
                    "raise_arrives": "Status costs attach",
                    "expenses_follow": "Lifestyle catches up",
                    "gap_revealed": "Monthly lifestyle cost expands",
                },
            }
        start_fact = first_fact(facts, "start_income", "income")
        end_fact = first_fact(facts, "end_income")
        raise_fact = first_fact(facts, "raise_delta")

        start_income = self._parse_rupee(str(start_fact.get("raw"))) if start_fact else self._parse_rupee(director_input.start_value)
        if start_income is None:
            start_income = income_mentions[0] if income_mentions else (all_amounts[0] if all_amounts else 50000.0)

        end_income = self._parse_rupee(str(end_fact.get("raw"))) if end_fact else self._parse_rupee(director_input.end_value)
        if end_income is None:
            candidates = [amount for amount in [*income_mentions, *all_amounts] if amount > start_income * 1.08]
            end_income = candidates[0] if candidates else start_income * 1.6
        if end_income <= start_income:
            candidates = [amount for amount in [*income_mentions, *all_amounts] if amount > start_income * 1.08]
            end_income = candidates[0] if candidates else start_income * 1.45

        savings_flat = any(token in lowered for token in ("savings stay flat", "saving stays flat", "savings are zero", "savings stay stuck", "zero savings"))
        old_savings = max(start_income * (0.0 if "zero" in lowered and "savings" in lowered else 0.18), 0.0)
        if "savings stay flat" in lowered or "savings stay stuck" in lowered:
            new_savings = old_savings
        elif savings_flat:
            new_savings = max(old_savings * 0.65, 0.0)
        else:
            new_savings = max(end_income * 0.12, old_savings * 0.8)

        old_spending = max(start_income - old_savings, 0.0)
        new_spending = max(end_income - new_savings, old_spending)
        explicit_raise = self._parse_rupee(str(raise_fact.get("raw"))) if raise_fact else None
        raise_amount = explicit_raise if explicit_raise is not None else max(end_income - start_income, 0.0)
        source_ids = [str(fact.get("id")) for fact in (start_fact, end_fact) if fact]

        return {
            "title": "Income rises. Savings don't.",
            "start_income": {"value": self._format_rupee(start_income), "amount": round(start_income, 2), "source_number_ids": [start_fact.get("id")] if start_fact else [], "derived": False},
            "end_income": {"value": self._format_rupee(end_income), "amount": round(end_income, 2), "source_number_ids": [end_fact.get("id")] if end_fact else [], "derived": False},
            "old_spending": {
                "value": self._format_rupee(old_spending),
                "amount": round(old_spending, 2),
                "derived": True,
                "derived_from": source_ids,
                "derivation_method": "estimated baseline spending from income",
            },
            "new_spending": {
                "value": self._format_rupee(new_spending),
                "amount": round(new_spending, 2),
                "derived": True,
                "derived_from": source_ids,
                "derivation_method": "estimated post-raise spending from income and savings",
            },
            "old_savings": {
                "value": self._format_rupee(old_savings),
                "amount": round(old_savings, 2),
                "derived": True,
                "derived_from": source_ids,
                "derivation_method": "estimated baseline savings from income",
            },
            "new_savings": {
                "value": self._format_rupee(new_savings),
                "amount": round(new_savings, 2),
                "derived": True,
                "derived_from": source_ids,
                "derivation_method": "estimated savings after lifestyle expansion",
            },
            "raise": {
                "value": self._format_rupee(raise_amount),
                "amount": round(raise_amount, 2),
                "source_number_ids": [raise_fact.get("id")] if raise_fact else source_ids,
                "derived": explicit_raise is None,
                "derived_from": [] if explicit_raise is not None else source_ids,
                "derivation_method": None if explicit_raise is not None else "end_income - start_income",
            },
            "accent": "warning",
            "numeric_provenance": facts,
            "truth_mode": "hard",
        }
