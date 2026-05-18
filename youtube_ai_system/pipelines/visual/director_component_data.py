from __future__ import annotations

import re
from typing import Any

from ...services.financial_governance import first_fact, numeric_role_map
from .director_types import VisualDirectorInput


class VisualDirectorComponentDataMixin:
    def _emi_stack_data(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        semantic_data = self._semantic_emi_stack_data(director_input)
        if semantic_data:
            return semantic_data
        text = director_input.narration_text
        amounts = self._money_mentions(text)
        salary_amount = self._parse_rupee(director_input.start_value) or 50000.0
        explicit_salary = self._explicit_salary_amount(text)
        if explicit_salary is not None:
            salary_amount = explicit_salary
        for item in amounts:
            if explicit_salary is None and str(item.get("label") or "").lower() in {"salary", "income"}:
                salary_amount = float(item["amount"])
                break
        emi_amounts = [
            float(item["amount"])
            for item in amounts
            if any(token in str(item.get("label") or "").lower() for token in ("emi", "loan", "payment"))
            and float(item["amount"]) < salary_amount
        ]
        if not emi_amounts:
            emi_amounts = [4000.0, 6500.0, 7500.0]
        labels = ["Phone EMI", "Bike EMI", "Personal loan", "Credit card", "Other EMI"]
        emis = [
            {"label": labels[index] if index < len(labels) else f"EMI {index + 1}", "value": self._format_rupee(amount), "amount": amount}
            for index, amount in enumerate(emi_amounts[:5])
        ]
        total_emi = sum(float(item["amount"]) for item in emis)
        if explicit_salary is None and salary_amount <= total_emi * 1.05:
            salary_amount = max(50000.0, round(total_emi * 2.6 / 1000.0) * 1000.0)
        remaining = self._explicit_remaining_amount(text)
        if remaining is None:
            remaining = max(salary_amount - total_emi, 0.0)
        if "nothing" in text.lower() or "trapped" in text.lower():
            remaining = min(remaining, salary_amount * 0.12)
        return {
            "salary": {"value": self._format_rupee(salary_amount), "amount": salary_amount},
            "emis": emis,
            "total_emi": {"value": self._format_rupee(total_emi), "amount": round(total_emi, 2)},
            "remaining": {
                "value": self._format_rupee(remaining),
                "amount": round(remaining, 2),
                "is_critical": remaining / max(salary_amount, 1) < 0.15,
            },
        }

    def _diversification_data(self) -> dict[str, Any]:
        return {
            "assets": [
                {"label": "Equity", "allocation": 45, "color": "#2EC4B6"},
                {"label": "Debt", "allocation": 25, "color": "#4361EE"},
                {"label": "FD", "allocation": 15, "color": "#FF9F1C"},
                {"label": "Gold", "allocation": 10, "color": "#B8A44C"},
                {"label": "Cash", "allocation": 5, "color": "rgba(255,255,255,0.65)"},
            ],
            "shock_asset": "Equity",
            "punch": "One fall does not break all",
        }

    def _fomo_crash_data(self) -> dict[str, Any]:
        return {
            "points": [
                {"x": 0.02, "y": 0.68},
                {"x": 0.18, "y": 0.58},
                {"x": 0.34, "y": 0.42},
                {"x": 0.52, "y": 0.18},
                {"x": 0.66, "y": 0.28},
                {"x": 0.82, "y": 0.62},
                {"x": 0.98, "y": 0.78},
            ],
            "buy_label": "buy at peak",
            "loss_label": "panic after entry",
        }

    def _small_leaks_data(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        text = director_input.narration_text.lower()
        leaks = [
            {"label": "Food apps", "amount": 2400.0},
            {"label": "Subscriptions", "amount": 1200.0},
            {"label": "Impulse buys", "amount": 3500.0},
            {"label": "Convenience fees", "amount": 900.0},
        ]
        if "coffee" in text:
            leaks[0] = {"label": "Coffee runs", "amount": 1800.0}
        if "week" in text:
            leaks.append({"label": "Weekly repeats", "amount": 2600.0})
        return {
            "leaks": [
                {**leak, "value": self._format_rupee(float(leak["amount"]))}
                for leak in leaks[:5]
            ],
            "monthly_loss": round(sum(float(leak["amount"]) for leak in leaks[:5]), 2),
        }

    def _inflation_return_data(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        semantic_data = self._semantic_inflation_return_data(director_input)
        if semantic_data:
            return semantic_data
        explicit_amount = self._parse_rupee(director_input.narration_text) or self._parse_rupee(director_input.start_value)
        explicit_rate = director_input.percentage if director_input.percentage is not None else self._first_percentage(director_input.narration_text)
        explicit_years = self._years_from_text(director_input.time_period or director_input.narration_text)
        if explicit_amount is None and explicit_rate is None and explicit_years is None:
            return {
                "start_value": {"value": "Savings", "amount": 0.0},
                "real_value": {"value": "Buying power falls", "amount": 0.0},
                "inflation_rate": None,
                "years": None,
                "rate_label": "",
            }
        amount = explicit_amount or 100000.0
        rate = max(explicit_rate or 7.0, 1.0)
        years = explicit_years or 10
        real_value = amount / ((1 + rate / 100.0) ** years)
        return {
            "start_value": {"value": self._format_rupee(amount), "amount": amount},
            "real_value": {"value": self._format_rupee(real_value), "amount": round(real_value, 2)},
            "inflation_rate": rate,
            "years": years,
            "rate_label": f"{rate:g}% for {years} years",
        }

    def _inflation_items(self, start_amount: Any, end_amount: Any) -> list[dict[str, Any]]:
        try:
            start = float(start_amount or 0)
            end = float(end_amount or 0)
        except (TypeError, ValueError):
            return []
        if start <= 0 or end <= 0:
            return []
        ratio = max(0.12, min(end / start, 1.0))
        base_items = [
            {"name": "Groceries", "current": 5, "future": max(1, round(5 * ratio))},
            {"name": "Fuel", "current": 4, "future": max(1, round(4 * ratio))},
            {"name": "Bills", "current": 3, "future": max(1, round(3 * ratio))},
        ]
        return base_items

    def _comparison_data(self, director_input: VisualDirectorInput, concept_type: str) -> dict[str, Any]:
        amount = self._semantic_first_money_amount(director_input) or self._parse_rupee(director_input.start_value) or self._parse_rupee(director_input.narration_text)
        mentions = self._money_mentions(director_input.narration_text)
        values = [str(item.get("value") or "") for item in mentions if item.get("value")]
        high_value = values[0] if values else (self._format_rupee(amount) if amount is not None else "full price")
        low_value = values[1] if len(values) > 1 else (self._format_rupee(amount) if amount is not None else "monthly number")
        if concept_type == "affordability_illusion":
            return {
                "left": {"label": "Real price", "value": high_value},
                "right": {"label": "Monthly price", "value": low_value},
                "punch": "Small number hides the full cost",
                "accent": "orange",
            }
        if concept_type == "payment_pain_reduction":
            return {
                "left": {"label": "Cash pain", "value": high_value},
                "right": {"label": "Painless EMI", "value": low_value},
                "punch": "Pain moves to later",
                "accent": "orange",
            }
        if concept_type in {"anchoring", "price_anchoring"}:
            return {
                "left": {"label": "Sticker anchor", "value": high_value},
                "right": {"label": "Offer feels smaller", "value": low_value},
                "punch": "The first number bends value",
                "accent": "orange",
            }
        if concept_type == "delayed_consequence":
            return {
                "left": {"label": "Decision today", "value": low_value},
                "right": {"label": "Bill later", "value": high_value},
                "punch": "The consequence arrives late",
                "accent": "orange",
            }
        if concept_type == "leverage":
            return {
                "left": {"label": "Borrowed money", "value": high_value},
                "right": {"label": "Future obligation", "value": low_value},
                "punch": "Control grows before risk shows",
                "accent": "orange",
            }
        if concept_type == "risk_return":
            return {"left": {"label": "Low Risk / Low Return", "value": "FD"}, "right": {"label": "Higher Risk / Higher Growth", "value": "Equity"}, "punch": "Risk buys upside", "accent": "teal"}
        if concept_type == "diversification":
            return {"left": {"label": "One bet", "value": "100%"}, "right": {"label": "Spread bets", "value": "safer mix"}, "punch": "Spread the risk", "accent": "teal"}
        if concept_type == "tax_saving":
            if amount is not None:
                tax_saved = amount * 0.3
                return {"left": {"label": "Without planning", "value": self._format_rupee(amount)}, "right": {"label": "Tax saved", "value": self._format_rupee(tax_saved)}, "punch": f"{self._format_rupee(tax_saved)} saved", "accent": "teal"}
            return {"left": {"label": "No planning", "value": "tax leak"}, "right": {"label": "Tax plan", "value": "money saved"}, "punch": "Planning reduces leakage", "accent": "teal"}
        if concept_type == "speculation_risk":
            return {"left": {"label": "FOMO trade", "value": "emotion"}, "right": {"label": "Real investing", "value": "understanding"}, "punch": "Do not buy what you cannot explain", "accent": "orange"}
        if concept_type in {"opportunity_cost", "comparison_timeline"}:
            if amount is not None:
                return {"left": {"label": "Spend today", "value": self._format_rupee(amount)}, "right": {"label": "Invest monthly", "value": self._format_rupee(amount)}, "punch": "Small choice compounds", "accent": "orange"}
            return {"left": {"label": "Spend today", "value": "instant"}, "right": {"label": "Invest instead", "value": "future"}, "punch": "Small choice compounds", "accent": "orange"}
        return {"left": {"label": "Path A", "value": "today"}, "right": {"label": "Path B", "value": "future"}, "punch": "Choose the better path", "accent": "teal"}

    def _risk_return_data(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        text = director_input.narration_text
        rates = [float(match.group(1)) for match in re.finditer(r"(\d+(?:\.\d+)?)\s*%", text)]
        fd_rate = next((rate for rate in rates if rate <= 9), 6.0)
        equity_rate = next((rate for rate in rates if rate > 9), 12.0)
        return {
            "safe_asset": "FD",
            "growth_asset": "Equity",
            "safe_rate": f"{fd_rate:g}%",
            "growth_rate": f"{equity_rate:g}%",
            "punch": "Risk buys upside only when you can stay invested",
        }

    def _emergency_fund_data(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        text = director_input.narration_text
        months_match = re.search(r"(\d+)\s*(?:-|to\s*)?(?:month|months)", text, re.IGNORECASE)
        buffer_months = int(months_match.group(1)) if months_match else 6
        amount = self._semantic_first_money_amount(director_input) or self._parse_rupee(director_input.start_value)
        shock = "Unexpected bill"
        lowered = text.lower()
        if "medical" in lowered or "hospital" in lowered:
            shock = "Medical bill"
        elif "job" in lowered or "layoff" in lowered or "income delay" in lowered:
            shock = "Income delay"
        elif "repair" in lowered or "car" in lowered:
            shock = "Repair bill"
        return {
            "buffer_months": buffer_months,
            "buffer_label": f"{buffer_months}-month buffer",
            "buffer_value": self._format_rupee(amount) if amount else f"{buffer_months} months",
            "shock_label": shock,
            "debt_label": "Credit card debt",
            "punch": "The buffer buys breathing room before debt begins",
        }
