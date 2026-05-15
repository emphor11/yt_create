from __future__ import annotations

import re
from typing import Any

from ...services.financial_governance import first_fact, numeric_role_map
from .director_types import VisualDirectorInput


class VisualDirectorDebtGrowthDataMixin:
    def _debt_spiral_data(self, text: str, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        semantic_data = self._semantic_debt_spiral_data(director_input)
        if semantic_data:
            return semantic_data
        amounts = self._money_mentions(text)
        principal = self._principal_amount(amounts, text, director_input)
        rate = director_input.percentage if director_input.percentage is not None else self._first_percentage(text)
        lowered = text.lower()
        debt_context = any(token in lowered for token in ("debt trap", "credit card", "minimum payment", "minimum dues", "outstanding balance", "debt grows", "debt grow", "debt"))
        if debt_context and amounts:
            if rate is None:
                rate = 40.0
            if principal is None:
                interest_amount = self._interest_amount(amounts, text)
                if interest_amount is not None and rate:
                    principal = interest_amount / (float(rate) / 100.0 / 12.0)
                else:
                    principal = max(float(item["amount"]) for item in amounts)
        if principal is None or rate is None:
            return None
        minimum = self._minimum_payment(amounts, text, principal)
        months = self._months_from_text(director_input.time_period or text) or 12
        if minimum is None and months is None:
            return None
        monthly_rate = float(rate) / 100.0 / 12.0
        balance = float(principal)
        balances = []
        payment = float(minimum or 0.0)
        for month in range(1, max(months, 12) + 1):
            interest = balance * monthly_rate
            principal_paid = payment - interest if payment else 0.0
            balance = max(balance + interest - payment, 0.0)
            balances.append(
                {
                    "month": month,
                    "balance": round(balance, 2),
                    "interest": round(interest, 2),
                    "principal_paid": round(principal_paid, 2),
                }
            )
        monthly_interest = float(principal) * monthly_rate
        return {
            "principal": {"value": self._format_rupee(principal), "amount": float(principal)},
            "annual_interest_rate": float(rate),
            "monthly_interest": round(monthly_interest, 2),
            "minimum_payment": round(payment, 2) if payment else None,
            "time_period_months": months,
            "balances": balances[:months],
            "month_12_balance": balances[11]["balance"],
            "is_trap": bool(payment and payment < monthly_interest),
        }

    def _interest_amount(self, amounts: list[dict[str, Any]], text: str) -> float | None:
        for item in amounts:
            window = self._window(text, int(item.get("start") or 0), int(item.get("end") or 0), radius=32).lower()
            if "interest" in window:
                return float(item["amount"])
        return None

    def _sip_growth_data(self, text: str, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        semantic_data = self._semantic_sip_growth_data(director_input)
        if semantic_data:
            return semantic_data
        amounts = self._money_mentions(text)
        monthly = self._sip_amount(amounts, text, director_input)
        rate = director_input.percentage if director_input.percentage is not None else self._first_percentage(text)
        years = self._years_from_text(director_input.time_period or text)
        if monthly is None or (rate is None and years is None):
            return None
        annual_rate = max(float(rate if rate is not None else 12.0), 1.0)
        duration_years = int(years or 20)
        months = duration_years * 12
        monthly_rate = annual_rate / 100.0 / 12.0
        if monthly_rate:
            final_corpus = float(monthly) * (((1 + monthly_rate) ** months - 1) / monthly_rate) * (1 + monthly_rate)
        else:
            final_corpus = float(monthly) * months
        total_invested = float(monthly) * months
        returns_earned = final_corpus - total_invested
        return {
            "monthly_sip": {"value": self._format_rupee(monthly), "amount": float(monthly)},
            "duration_years": duration_years,
            "annual_return_rate": annual_rate,
            "total_invested": round(total_invested, 2),
            "final_corpus": round(final_corpus, 2),
            "returns_earned": round(returns_earned, 2),
            "awe_ratio": round(final_corpus / total_invested, 2) if total_invested else 0.0,
        }

    def _inferred_sip_growth_data(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        monthly = self._parse_rupee(director_input.narration_text) or 5000.0
        rate = max(director_input.percentage or self._first_percentage(director_input.narration_text) or 12.0, 1.0)
        years = self._years_from_text(director_input.time_period or director_input.narration_text) or 20
        synthetic = VisualDirectorInput(
            **{
                **director_input.__dict__,
                "percentage": rate,
                "time_period": f"{years} years",
                "start_value": self._format_rupee(monthly),
                "narration_text": f"Invest {self._format_rupee(monthly)} per month at {rate}% for {years} years",
            }
        )
        return self._sip_growth_data(synthetic.narration_text, synthetic) or {
            "monthly_sip": {"value": self._format_rupee(monthly), "amount": monthly},
            "duration_years": years,
            "annual_return_rate": rate,
            "total_invested": monthly * 12 * years,
            "final_corpus": monthly * 12 * years,
            "returns_earned": 0,
            "awe_ratio": 1,
        }
