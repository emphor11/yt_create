from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from .director_data_helpers import VisualDirectorDataHelpersMixin
from .director_types import DirectedBeat, VisualDirectorInput


class VisualDirectorPlanHelpersMixin(VisualDirectorDataHelpersMixin):
    def _contextualize_beats(self, beats: list[DirectedBeat], narration_text: str) -> list[DirectedBeat]:
        sentences = self._sentences(narration_text)
        if not sentences:
            return beats
        if len(beats) == 1:
            return [replace(beats[0], source_text=sentences[0], sentence_index=0)]
        contextualized: list[DirectedBeat] = []
        last_sentence_index = max(len(sentences) - 1, 0)
        last_beat_index = max(len(beats) - 1, 1)
        for beat_index, beat in enumerate(beats):
            sentence_index = round((beat_index / last_beat_index) * last_sentence_index)
            sentence_index = max(0, min(sentence_index, last_sentence_index))
            contextualized.append(
                replace(beat, source_text=sentences[sentence_index], sentence_index=sentence_index)
            )
        return contextualized

    def _sentences(self, text: str) -> list[str]:
        parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]
        if parts:
            return parts
        stripped = text.strip()
        return [stripped] if stripped else []

    def _has_finance_numbers(self, director_input: VisualDirectorInput) -> bool:
        return bool(
            director_input.start_value
            or director_input.end_value
            or director_input.percentage is not None
            or self._semantic_entities(director_input)
            or self._money_mentions(director_input.narration_text)
            or self._first_percentage(director_input.narration_text) is not None
        )

    def _semantic_scene(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        semantic_scene = director_input.semantic_scene if isinstance(director_input.semantic_scene, dict) else {}
        return semantic_scene if semantic_scene.get("source") == "semantic_scene_contract_v1" else semantic_scene

    def _semantic_primary_concept_key(self, director_input: VisualDirectorInput) -> str:
        primary = (self._semantic_scene(director_input).get("primary_concept") or {})
        return str(primary.get("key") or "").strip().lower()

    def _semantic_entities(self, director_input: VisualDirectorInput) -> list[dict[str, Any]]:
        entities = self._semantic_scene(director_input).get("entities") or []
        return [dict(entity) for entity in entities if isinstance(entity, dict)]

    def _semantic_entities_by_role(self, director_input: VisualDirectorInput) -> dict[str, list[dict[str, Any]]]:
        by_role: dict[str, list[dict[str, Any]]] = {}
        for entity in self._semantic_entities(director_input):
            role = str(entity.get("role") or "").strip()
            if role:
                by_role.setdefault(role, []).append(entity)
        return by_role

    def _semantic_entity(self, director_input: VisualDirectorInput, *roles: str) -> dict[str, Any] | None:
        by_role = self._semantic_entities_by_role(director_input)
        for role in roles:
            values = by_role.get(role) or []
            if values:
                return values[0]
        return None

    def _semantic_money_amount(self, entity: dict[str, Any] | None) -> float | None:
        if not entity:
            return None
        try:
            value = float(entity.get("value"))
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def _semantic_money_point(self, entity: dict[str, Any] | None, fallback_label: str = "") -> dict[str, Any] | None:
        amount = self._semantic_money_amount(entity)
        if amount is None:
            return None
        return {
            "value": str(entity.get("display_value") or self._format_rupee(amount)),
            "amount": amount,
            "source_number_ids": [self._semantic_source_id(entity)] if self._semantic_source_id(entity) else [],
            "derived": bool((entity.get("attributes") or {}).get("derived", False)),
            "label": fallback_label or str(entity.get("label") or entity.get("role") or ""),
        }

    def _semantic_source_id(self, entity: dict[str, Any] | None) -> str:
        provenance = entity.get("provenance") if isinstance(entity, dict) else {}
        return str((provenance or {}).get("source_number_id") or "")

    def _semantic_first_money_amount(self, director_input: VisualDirectorInput) -> float | None:
        for entity in self._semantic_entities(director_input):
            if str(entity.get("kind") or "") == "money":
                amount = self._semantic_money_amount(entity)
                if amount is not None:
                    return amount
        return None

    def _semantic_rate(self, director_input: VisualDirectorInput, *roles: str) -> float | None:
        entity = self._semantic_entity(director_input, *roles)
        amount = self._semantic_money_amount(entity)
        if amount is not None:
            return amount
        return director_input.percentage

    def _semantic_years(self, director_input: VisualDirectorInput) -> int | None:
        entity = self._semantic_entity(director_input, "time_period")
        amount = self._semantic_money_amount(entity)
        if amount is not None:
            return int(amount)
        return self._years_from_text(director_input.time_period or "")

    def _semantic_money_flow_data(self, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        by_role = self._semantic_entities_by_role(director_input)
        source = self._semantic_entity(director_input, "salary_income")
        source_amount = self._semantic_money_amount(source)
        if source_amount is None:
            return None
        flow_roles = ("emi_payment", "rent_expense", "living_expense")
        flows: list[dict[str, Any]] = []
        for role in flow_roles:
            for entity in by_role.get(role, []):
                amount = self._semantic_money_amount(entity)
                if amount is None or amount >= source_amount:
                    continue
                label = self._semantic_flow_label(role, entity)
                flows.append({"label": label, "value": self._format_rupee(amount), "amount": amount, "color": "orange", "order": 0})
        if not flows:
            return None
        flows = sorted(flows, key=lambda flow: flow["amount"], reverse=True)
        flow_total = sum(float(flow["amount"]) for flow in flows)
        remainder_entity = self._semantic_entity(director_input, "remaining_balance")
        remainder_amount = self._semantic_money_amount(remainder_entity)
        if remainder_amount is None:
            remainder_amount = max(source_amount - flow_total, 0.0)
        for order, flow in enumerate(flows, start=1):
            flow["order"] = order
            flow["color"] = "red" if order == 1 else "orange"
        ratio = remainder_amount / source_amount if source_amount else 0.0
        return {
            "source": {"label": "Salary", "value": self._format_rupee(source_amount), "amount": source_amount},
            "flows": flows,
            "remainder": {
                "value": self._format_rupee(remainder_amount),
                "amount": round(remainder_amount, 2),
                "is_dangerous": ratio < 0.10,
            },
            "numeric_provenance": self._semantic_scene(director_input).get("spoken_values") or [],
            "semantic_source": "semantic_scene_contract",
        }

    def _semantic_flow_label(self, role: str, entity: dict[str, Any]) -> str:
        if role == "emi_payment":
            return "EMI"
        if role == "rent_expense":
            return "Rent"
        if role == "living_expense":
            source = str(entity.get("source_text") or "").lower()
            if "food" in source and "travel" in source:
                return "Food + travel"
            if "subscription" in source:
                return "Subscriptions"
            return "Lifestyle"
        return str(entity.get("label") or role.replace("_", " ").title())

    def _semantic_sip_growth_data(self, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        monthly = self._semantic_entity(director_input, "monthly_sip")
        monthly_amount = self._semantic_money_amount(monthly)
        if monthly_amount is None:
            return None
        annual_rate = max(float(self._semantic_rate(director_input, "annual_return_rate") or 12.0), 1.0)
        duration_years = int(self._semantic_years(director_input) or 20)
        total_entity = self._semantic_entity(director_input, "total_contribution")
        corpus_entity = self._semantic_entity(director_input, "target_corpus", "target_value")
        total_invested = self._semantic_money_amount(total_entity)
        final_corpus = self._semantic_money_amount(corpus_entity)
        if total_invested is None:
            total_invested = monthly_amount * duration_years * 12
        if final_corpus is None:
            months = duration_years * 12
            monthly_rate = annual_rate / 100.0 / 12.0
            final_corpus = monthly_amount * (((1 + monthly_rate) ** months - 1) / monthly_rate) * (1 + monthly_rate) if monthly_rate else total_invested
        returns_earned = final_corpus - total_invested
        return {
            "monthly_sip": {"value": str(monthly.get("display_value") or self._format_rupee(monthly_amount)), "amount": monthly_amount},
            "duration_years": duration_years,
            "annual_return_rate": annual_rate,
            "total_invested": round(total_invested, 2),
            "final_corpus": round(final_corpus, 2),
            "returns_earned": round(returns_earned, 2),
            "awe_ratio": round(final_corpus / total_invested, 2) if total_invested else 0.0,
            "numeric_provenance": self._semantic_scene(director_input).get("spoken_values") or [],
            "semantic_source": "semantic_scene_contract",
        }

    def _semantic_lifestyle_creep_data(self, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        incomes = self._semantic_entities_by_role(director_input).get("salary_income") or []
        if len(incomes) < 2:
            return None
        start_entity, end_entity = incomes[0], incomes[1]
        start_income = self._semantic_money_amount(start_entity)
        end_income = self._semantic_money_amount(end_entity)
        if start_income is None or end_income is None or end_income <= start_income:
            return None
        raise_entity = self._semantic_entity(director_input, "raise_delta")
        raise_amount = self._semantic_money_amount(raise_entity) or max(end_income - start_income, 0.0)
        old_savings = max(start_income * 0.18, 0.0)
        new_savings = old_savings
        old_spending = max(start_income - old_savings, 0.0)
        new_spending = max(end_income - new_savings, old_spending)
        source_ids = [source_id for source_id in (self._semantic_source_id(start_entity), self._semantic_source_id(end_entity)) if source_id]
        return {
            "title": "Income rises. Savings don't.",
            "start_income": {"value": self._format_rupee(start_income), "amount": round(start_income, 2), "source_number_ids": [self._semantic_source_id(start_entity)], "derived": False},
            "end_income": {"value": self._format_rupee(end_income), "amount": round(end_income, 2), "source_number_ids": [self._semantic_source_id(end_entity)], "derived": False},
            "old_spending": {"value": self._format_rupee(old_spending), "amount": round(old_spending, 2), "derived": True, "derived_from": source_ids, "derivation_method": "estimated baseline spending from income"},
            "new_spending": {"value": self._format_rupee(new_spending), "amount": round(new_spending, 2), "derived": True, "derived_from": source_ids, "derivation_method": "estimated post-raise spending from income and savings"},
            "old_savings": {"value": self._format_rupee(old_savings), "amount": round(old_savings, 2), "derived": True, "derived_from": source_ids, "derivation_method": "estimated baseline savings from income"},
            "new_savings": {"value": self._format_rupee(new_savings), "amount": round(new_savings, 2), "derived": True, "derived_from": source_ids, "derivation_method": "estimated savings after lifestyle expansion"},
            "raise": {"value": self._format_rupee(raise_amount), "amount": round(raise_amount, 2), "source_number_ids": [self._semantic_source_id(raise_entity)] if raise_entity else source_ids, "derived": raise_entity is None, "derived_from": [] if raise_entity else source_ids, "derivation_method": None if raise_entity else "end_income - start_income"},
            "accent": "warning",
            "numeric_provenance": self._semantic_scene(director_input).get("spoken_values") or [],
            "truth_mode": "hard",
            "semantic_source": "semantic_scene_contract",
        }

    def _semantic_debt_spiral_data(self, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        principal_entity = self._semantic_entity(director_input, "debt_principal", "principal_balance")
        principal = self._semantic_money_amount(principal_entity) or self._parse_rupee(director_input.start_value)
        rate = self._semantic_rate(director_input, "annual_interest_rate") or director_input.percentage
        if principal is None or rate is None:
            return None
        minimum = self._semantic_money_amount(self._semantic_entity(director_input, "minimum_payment"))
        months = self._semantic_years(director_input) or 12
        monthly_rate = float(rate) / 100.0 / 12.0
        balance = float(principal)
        balances = []
        payment = float(minimum or 0.0)
        for month in range(1, max(months, 12) + 1):
            interest = balance * monthly_rate
            principal_paid = payment - interest if payment else 0.0
            balance = max(balance + interest - payment, 0.0)
            balances.append({"month": month, "balance": round(balance, 2), "interest": round(interest, 2), "principal_paid": round(principal_paid, 2)})
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
            "semantic_source": "semantic_scene_contract",
        }

    def _semantic_emi_stack_data(self, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        by_role = self._semantic_entities_by_role(director_input)
        emi_entities = by_role.get("emi_payment") or []
        if not emi_entities:
            return None
        salary_amount = self._semantic_money_amount(self._semantic_entity(director_input, "salary_income")) or self._parse_rupee(director_input.start_value) or 50000.0
        emis = []
        for index, entity in enumerate(emi_entities[:5]):
            amount = self._semantic_money_amount(entity)
            if amount is None:
                continue
            emis.append({"label": self._semantic_emi_label(entity, index), "value": self._format_rupee(amount), "amount": amount})
        if not emis:
            return None
        total_emi = sum(float(item["amount"]) for item in emis)
        explicit_salary = self._explicit_salary_amount(director_input.narration_text)
        if explicit_salary is not None:
            salary_amount = explicit_salary
        elif salary_amount <= total_emi * 1.05:
            salary_amount = max(50000.0, round(total_emi * 2.6 / 1000.0) * 1000.0)
        remaining_entity = self._semantic_entity(director_input, "remaining_balance")
        remaining = self._semantic_money_amount(remaining_entity)
        if remaining is None:
            remaining = self._explicit_remaining_amount(director_input.narration_text)
        if remaining is None:
            remaining = max(salary_amount - total_emi, 0.0)
        return {
            "salary": {"value": self._format_rupee(salary_amount), "amount": salary_amount},
            "emis": emis,
            "total_emi": {"value": self._format_rupee(total_emi), "amount": round(total_emi, 2)},
            "remaining": {"value": self._format_rupee(remaining), "amount": round(remaining, 2), "is_critical": remaining / max(salary_amount, 1) < 0.15},
            "semantic_source": "semantic_scene_contract",
        }

    def _semantic_emi_label(self, entity: dict[str, Any], index: int) -> str:
        source = str(entity.get("source_text") or "").lower()
        if "car" in source or "mercedes" in source:
            return "Car EMI"
        if "home" in source or "house" in source:
            return "Home loan"
        if "phone" in source:
            return "Phone EMI"
        if "bike" in source:
            return "Bike EMI"
        if "personal" in source:
            return "Personal loan"
        if "credit card" in source:
            return "Credit card"
        return "Monthly payment" if index == 0 else f"Payment {index + 1}"

    def _semantic_inflation_return_data(self, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        rate = self._semantic_rate(director_input, "inflation_rate")
        amount_entity = self._semantic_entity(director_input, "principal_balance", "salary_income")
        amount = self._semantic_money_amount(amount_entity) or self._parse_rupee(director_input.start_value)
        years = self._semantic_years(director_input)
        if amount is None or rate is None:
            return None
        duration_years = years or 10
        real_value = amount / ((1 + float(rate) / 100.0) ** duration_years)
        return {
            "start_value": {"value": self._format_rupee(amount), "amount": amount},
            "real_value": {"value": self._format_rupee(real_value), "amount": round(real_value, 2), "derived": True, "derived_from": [self._semantic_source_id(amount_entity)] if amount_entity else [], "derivation_method": "inflation-adjusted buying power"},
            "inflation_rate": float(rate),
            "years": duration_years,
            "rate_label": f"{float(rate):g}% for {duration_years} years",
            "semantic_source": "semantic_scene_contract",
        }
