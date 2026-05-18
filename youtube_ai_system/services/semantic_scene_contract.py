from __future__ import annotations

import re
from typing import Any

from ..contracts.semantic import (
    SCHEMA_VERSION,
    SemanticDerivedValue,
    SemanticEntity,
    SemanticRelationship,
    SemanticSceneContract,
)
from .financial_governance import numeric_role_map, split_sentences


class SemanticSceneContractExtractor:
    """Builds the canonical semantic object consumed by later pipeline phases."""

    def extract(
        self,
        section: dict[str, Any],
        finance_concept: dict[str, Any] | None = None,
        *,
        scene_id: str = "scene",
    ) -> SemanticSceneContract:
        narration = self._section_text(section)
        finance_concept = dict(finance_concept or section.get("finance_concept") or {})
        facts = list(finance_concept.get("numeric_facts") or [])
        if not facts:
            facts = list(numeric_role_map(narration, scene_id=scene_id).get("facts") or [])
        sentences = split_sentences(narration)

        entities = [
            self._entity_from_fact(fact, sentences, index)
            for index, fact in enumerate(facts)
            if isinstance(fact, dict)
        ]
        relationships = self._relationships(entities, narration, finance_concept)
        derived_values = self._derived_values(entities)
        warnings = self._warnings(section, finance_concept, entities, relationships)
        confidence = self._confidence(finance_concept, entities, relationships, warnings)

        return SemanticSceneContract(
            scene_id=scene_id,
            narration=narration,
            primary_concept=self._primary_concept(section, finance_concept, entities),
            entities=entities,
            relationships=relationships,
            derived_values=derived_values,
            spoken_values=[str(fact.get("raw") or "") for fact in facts if str(fact.get("raw") or "").strip()],
            warnings=warnings,
            confidence=confidence,
        )

    def extract_dict(
        self,
        section: dict[str, Any],
        finance_concept: dict[str, Any] | None = None,
        *,
        scene_id: str = "scene",
    ) -> dict[str, Any]:
        return self.extract(section, finance_concept, scene_id=scene_id).to_dict()

    def _section_text(self, section: dict[str, Any]) -> str:
        return " ".join(str(section.get("text") or section.get("narration") or section.get("narration_text") or "").split())

    def _entity_from_fact(self, fact: dict[str, Any], sentences: list[str], index: int) -> SemanticEntity:
        sentence_index = fact.get("sentence_index")
        try:
            sentence_index_int = int(sentence_index) if sentence_index is not None else None
        except (TypeError, ValueError):
            sentence_index_int = None
        sentence = sentences[sentence_index_int] if sentence_index_int is not None and 0 <= sentence_index_int < len(sentences) else ""
        role = self._semantic_role(fact, sentence)
        direction = self._direction_for_role(role, sentence)
        kind = self._kind_for_fact(fact, role)
        raw = str(fact.get("raw") or "").strip()
        return SemanticEntity(
            id=f"ent:{index}:{role}",
            label=self._label_for_role(role, raw),
            kind=kind,
            role=role,
            value=self._float_or_none(fact.get("amount")),
            display_value=raw,
            unit=str(fact.get("unit") or ""),
            direction=direction,
            source_text=sentence,
            sentence_index=sentence_index_int,
            confidence=float(fact.get("confidence") or 0.0),
            provenance={
                "source_number_id": fact.get("id"),
                "numeric_role": fact.get("role"),
                "owner": fact.get("owner") or "numeric_provenance",
            },
            attributes={"derived": bool(fact.get("derived"))},
        )

    def _semantic_role(self, fact: dict[str, Any], sentence: str) -> str:
        numeric_role = str(fact.get("role") or "").strip().lower()
        lowered = sentence.lower()
        raw = str(fact.get("raw") or "")
        window = self._window_for_raw(sentence, raw).lower()
        before_raw, after_raw = self._context_for_raw(sentence, raw)
        if numeric_role in {"start_income", "end_income", "income"}:
            if not any(token in lowered for token in ("salary", "income", "raise", "hike", "earns", "earning")):
                return self._non_income_money_role(lowered, window, before_raw, after_raw)
            return "salary_income"
        if numeric_role == "monthly_sip":
            return "monthly_sip"
        if numeric_role == "total_contribution":
            return "total_contribution"
        if numeric_role == "target_value":
            if (
                "total invested" in window
                or "contribution" in window
                or "invest about" in before_raw
                or "from your pocket" in after_raw
            ):
                return "total_contribution"
            if any(token in lowered for token in ("corpus", "turn", "become", "lakh", "wealth")):
                return "target_corpus"
            return "target_value"
        if numeric_role == "raise_delta":
            return "raise_delta"
        if numeric_role == "principal":
            if "debt" in lowered or "credit card" in lowered or "balance" in lowered:
                return "debt_principal"
            if self._is_strong_full_price_context(window, before_raw):
                return "full_price"
            if self._is_monthly_payment_context(window, before_raw, after_raw):
                return "monthly_payment"
            if self._is_full_price_context(lowered, window, before_raw, after_raw):
                return "full_price"
            return "principal_balance"
        if numeric_role == "rate":
            if "inflation" in lowered or "prices" in lowered:
                return "inflation_rate"
            if "return" in lowered or "sip" in lowered or "compounding" in lowered:
                return "annual_return_rate"
            if "interest" in lowered or "credit card" in lowered or "debt" in lowered:
                return "annual_interest_rate"
            return "rate"
        if numeric_role == "duration":
            return "time_period"
        if numeric_role == "money_amount":
            if "salary" in lowered or "income" in lowered:
                if self._is_monthly_payment_context(window, before_raw, after_raw):
                    return "emi_payment"
                return "salary_income"
            if self._is_strong_full_price_context(window, before_raw):
                return "full_price"
            if self._is_monthly_payment_context(window, before_raw, after_raw):
                if any(token in lowered for token in ("salary", "income", "paycheck")) or self._is_expense_drain_context(window, before_raw, after_raw):
                    return "emi_payment"
                return "monthly_payment"
            if self._is_full_price_context(lowered, window, before_raw, after_raw):
                return "full_price"
            if any(token in window or token in before_raw or token in after_raw for token in ("invest", "capital", "liquidity", "cash reserve", "cash stays", "bank account")):
                return "capital_pool"
            if any(token in window or token in before_raw or token in after_raw for token in ("return", "profit", "yield", "missed", "opportunity")):
                return "investment_return"
            if "emi" in lowered:
                return "emi_payment"
            if "rent" in lowered:
                return "rent_expense"
            if any(token in lowered for token in ("food", "travel", "spend", "expense", "subscription", "shopping")):
                return "living_expense"
            if any(token in lowered for token in ("left", "remaining", "breathing", "survives")):
                return "remaining_balance"
            if "minimum payment" in lowered or "minimum due" in lowered:
                return "minimum_payment"
            if "interest" in lowered:
                return "interest_charge"
        return numeric_role or "number"

    def _direction_for_role(self, role: str, sentence: str) -> str:
        if role in {"salary_income", "target_corpus", "target_value"}:
            return "inflow"
        if role in {"emi_payment", "monthly_payment", "rent_expense", "living_expense", "minimum_payment"}:
            return "outflow"
        if role in {"inflation_rate", "interest_charge", "annual_interest_rate"}:
            return "pressure"
        if role in {"monthly_sip", "total_contribution"}:
            return "allocation"
        if role in {"annual_return_rate"}:
            return "growth"
        if role == "remaining_balance":
            return "remainder"
        if "leaves" in sentence.lower() or "goes to" in sentence.lower():
            return "outflow"
        return ""

    def _kind_for_fact(self, fact: dict[str, Any], role: str) -> str:
        unit = str(fact.get("unit") or "").lower()
        if unit == "percent" or role.endswith("_rate"):
            return "rate"
        if role == "time_period":
            return "duration"
        if unit == "inr" or role in {"monthly_sip", "salary_income", "target_corpus", "full_price", "monthly_payment", "capital_pool", "investment_return"}:
            return "money"
        return "number"

    def _relationships(
        self,
        entities: list[SemanticEntity],
        narration: str,
        finance_concept: dict[str, Any],
    ) -> list[SemanticRelationship]:
        relationships: list[SemanticRelationship] = []
        by_role: dict[str, list[SemanticEntity]] = {}
        for entity in entities:
            by_role.setdefault(entity.role, []).append(entity)

        def add(source: SemanticEntity | None, target: SemanticEntity | None, rel_type: str, label: str, confidence: float = 0.9) -> None:
            if not source or not target:
                return
            relationships.append(
                SemanticRelationship(
                    id=f"rel:{len(relationships)}:{rel_type}",
                    type=rel_type,
                    source_entity_id=source.id,
                    target_entity_id=target.id,
                    label=label,
                    confidence=confidence,
                    provenance={"source": "semantic_scene_contract"},
                )
            )

        salary = self._first(by_role, "salary_income")
        for role in ("emi_payment", "rent_expense", "living_expense"):
            for expense in by_role.get(role, []):
                add(salary, expense, "consumed_by", f"{salary.label if salary else 'income'} consumed by {expense.label}")
        for remainder in by_role.get("remaining_balance", []):
            add(salary, remainder, "leaves_remainder", "income leaves remaining balance")

        monthly_sip = self._first(by_role, "monthly_sip")
        contribution = self._first(by_role, "total_contribution")
        corpus = self._first(by_role, "target_corpus", "target_value")
        return_rate = self._first(by_role, "annual_return_rate")
        time_period = self._first(by_role, "time_period")
        add(monthly_sip, contribution, "accumulates_into", "monthly SIP accumulates into total contribution")
        add(contribution or monthly_sip, corpus, "compounds_to", "investment compounds to target corpus")
        add(return_rate, corpus, "growth_rate_drives", "return rate drives corpus growth")
        add(time_period, corpus, "over_time", "time period enables compounding")

        debt = self._first(by_role, "debt_principal", "principal_balance")
        interest_rate = self._first(by_role, "annual_interest_rate")
        interest = self._first(by_role, "interest_charge")
        minimum = self._first(by_role, "minimum_payment")
        add(debt, interest_rate, "charged_at", "debt is charged at interest rate")
        add(interest_rate, interest, "creates", "interest rate creates monthly interest")
        add(minimum, debt, "pays_down", "minimum payment attempts to pay down debt")

        principal = self._first(by_role, "principal_balance", "salary_income")
        inflation = self._first(by_role, "inflation_rate")
        add(inflation, principal, "erodes", "inflation erodes buying power")

        start_income, end_income = self._income_range(entities, narration, finance_concept)
        add(start_income, end_income, "increases_to", "income increases to new income")
        return relationships

    def _derived_values(self, entities: list[SemanticEntity]) -> list[SemanticDerivedValue]:
        salary = next((entity for entity in entities if entity.role == "salary_income" and entity.value), None)
        expenses = [
            entity
            for entity in entities
            if entity.role in {"emi_payment", "rent_expense", "living_expense"} and entity.value is not None
        ]
        has_remainder = any(entity.role == "remaining_balance" for entity in entities)
        if not salary or not expenses or has_remainder:
            return []
        value = max(float(salary.value or 0) - sum(float(entity.value or 0) for entity in expenses), 0.0)
        return [
            SemanticDerivedValue(
                id="derived:remaining_balance",
                label="remaining_balance",
                value=round(value, 2),
                display_value=self._format_rupee(value),
                unit="INR",
                source_entity_ids=[salary.id, *[entity.id for entity in expenses]],
                derivation_method="salary_income - known_outflows",
                confidence=0.78,
            )
        ]

    def _warnings(
        self,
        section: dict[str, Any],
        finance_concept: dict[str, Any],
        entities: list[SemanticEntity],
        relationships: list[SemanticRelationship],
    ) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        visual_scene = section.get("visual_scene") if isinstance(section.get("visual_scene"), dict) else {}
        mechanism = str(visual_scene.get("mechanism") or section.get("mechanism") or "").strip().lower()
        concept_key = self._concept_key(finance_concept)
        if mechanism and concept_key and mechanism != concept_key:
            warnings.append(
                {
                    "code": "mechanism_concept_mismatch",
                    "message": "visual_scene mechanism differs from extracted finance concept",
                    "mechanism": mechanism,
                    "concept_key": concept_key,
                }
            )
        if entities and not relationships:
            warnings.append({"code": "no_semantic_relationships", "message": "numeric entities found without relationships"})
        return warnings

    def _primary_concept(
        self,
        section: dict[str, Any],
        finance_concept: dict[str, Any],
        entities: list[SemanticEntity],
    ) -> dict[str, Any]:
        visual_scene = section.get("visual_scene") if isinstance(section.get("visual_scene"), dict) else {}
        concept_key = self._concept_key(finance_concept) or str(visual_scene.get("mechanism") or section.get("mechanism") or "").strip().lower() or "definition"
        return {
            "key": concept_key,
            "name": str(finance_concept.get("concept_name") or "").strip() or "Unknown",
            "category": str(finance_concept.get("concept_type") or section.get("idea_type") or "").strip().lower() or "definition",
            "action": str(finance_concept.get("action") or "").strip(),
            "primary_entity": self._primary_entity(concept_key, finance_concept, section),
            "confidence": float(finance_concept.get("confidence") or 0.0),
            "evidence_roles": sorted({entity.role for entity in entities}),
        }

    def _confidence(
        self,
        finance_concept: dict[str, Any],
        entities: list[SemanticEntity],
        relationships: list[SemanticRelationship],
        warnings: list[dict[str, Any]],
    ) -> float:
        base = float(finance_concept.get("confidence") or 0.55)
        if entities:
            base += 0.08
        if relationships:
            base += 0.08
        base -= 0.08 * len(warnings)
        return round(max(0.1, min(base, 1.0)), 3)

    def _concept_key(self, finance_concept: dict[str, Any]) -> str:
        name = str(finance_concept.get("concept_name") or "").strip().lower()
        mapping = {
            "salary drain": "salary_drain",
            "emi pressure": "emi_pressure",
            "sip growth": "sip_growth",
            "lifestyle inflation": "lifestyle_inflation",
            "debt trap": "debt_trap",
            "inflation loss": "inflation_erosion",
            "inflation erosion": "inflation_erosion",
            "compounding growth": "compounding",
            "fomo risk": "speculation_risk",
            "investing vs speculation": "speculation_risk",
            "diversification": "diversification",
            "opportunity cost": "opportunity_cost",
            "savings rate": "savings_rate",
            "tax saving": "tax_saving",
            "risk return": "risk_return",
            "expense leakage": "expense_leakage",
            "emergency fund": "emergency_fund",
        }
        return mapping.get(name, name.replace(" ", "_") if name else "")

    def _primary_entity(self, concept_key: str, finance_concept: dict[str, Any], section: dict[str, Any]) -> str:
        if concept_key in {"sip_growth", "compounding"}:
            return "investment"
        if concept_key in {"emi_pressure", "debt_trap"}:
            return "debt"
        if concept_key in {"inflation_erosion"}:
            return "buying_power"
        return str(finance_concept.get("primary_entity") or section.get("dominant_entity") or "money")

    def _income_range(
        self,
        entities: list[SemanticEntity],
        narration: str,
        finance_concept: dict[str, Any],
    ) -> tuple[SemanticEntity | None, SemanticEntity | None]:
        lowered = narration.lower()
        if not re.search(r"\b(salary|income)\s+(?:rises?|increases?|moves?|goes?)\s+from\b", lowered):
            return None, None
        incomes = [entity for entity in entities if entity.role == "salary_income"]
        if len(incomes) >= 2:
            return incomes[0], incomes[1]
        start = str(finance_concept.get("start_value") or "")
        end = str(finance_concept.get("end_value") or "")
        if start and end and start != end:
            start_entity = next((entity for entity in entities if entity.display_value == start), None)
            end_entity = next((entity for entity in entities if entity.display_value == end), None)
            return start_entity, end_entity
        return None, None

    def _first(self, by_role: dict[str, list[SemanticEntity]], *roles: str) -> SemanticEntity | None:
        for role in roles:
            values = by_role.get(role) or []
            if values:
                return values[0]
        return None

    def _label_for_role(self, role: str, raw: str) -> str:
        label = role.replace("_", " ")
        return f"{label}: {raw}" if raw else label

    def _float_or_none(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _format_rupee(self, amount: float) -> str:
        rounded = int(round(amount))
        sign = "-" if rounded < 0 else ""
        digits = str(abs(rounded))
        if len(digits) <= 3:
            return f"{sign}₹{digits}"
        last_three = digits[-3:]
        head = re.sub(r"\B(?=(\d{2})+(?!\d))", ",", digits[:-3])
        return f"{sign}₹{head},{last_three}"

    def _window_for_raw(self, sentence: str, raw: str, radius: int = 42) -> str:
        if not sentence or not raw:
            return sentence
        index = sentence.find(raw)
        if index < 0:
            return sentence
        return sentence[max(0, index - radius) : index + len(raw) + radius]

    def _context_for_raw(self, sentence: str, raw: str, radius: int = 48) -> tuple[str, str]:
        if not sentence or not raw:
            return sentence.lower(), sentence.lower()
        index = sentence.find(raw)
        if index < 0:
            return sentence.lower(), sentence.lower()
        before = sentence[max(0, index - radius) : index].lower()
        after = sentence[index + len(raw) : index + len(raw) + radius].lower()
        return before, after

    def _non_income_money_role(self, lowered: str, window: str, before_raw: str, after_raw: str) -> str:
        if self._is_monthly_payment_context(window, before_raw, after_raw):
            return "monthly_payment"
        if self._is_full_price_context(lowered, window, before_raw, after_raw):
            return "full_price"
        if any(token in window or token in before_raw or token in after_raw for token in ("invest", "capital", "liquidity", "cash", "bank account")):
            return "capital_pool"
        return "principal_balance"

    def _is_monthly_payment_context(self, window: str, before_raw: str, after_raw: str) -> bool:
        context = f"{before_raw} {window} {after_raw}"
        return any(
            token in context
            for token in (
                "emi",
                "monthly payment",
                "per month",
                "a month",
                "each month",
                "monthly number",
                "lease",
                "instalment",
                "installment",
            )
        )

    def _is_full_price_context(self, lowered: str, window: str, before_raw: str, after_raw: str) -> bool:
        context = f"{before_raw} {window} {after_raw}"
        return any(
            token in context
            for token in (
                "full price",
                "price tag",
                "sticker",
                "costs",
                "cost ",
                "cash price",
                "upfront",
                "mercedes",
                "luxury car",
                "car",
                "asset",
                "purchase",
            )
        ) and not self._is_monthly_payment_context(window, before_raw, after_raw)

    def _is_strong_full_price_context(self, window: str, before_raw: str) -> bool:
        context = f"{before_raw} {window}"
        return any(token in context for token in ("full price", "price tag", "sticker", "cash price", "cost is", "costs", "upfront"))

    def _is_expense_drain_context(self, window: str, before_raw: str, after_raw: str) -> bool:
        context = f"{before_raw} {window} {after_raw}"
        return any(token in context for token in ("goes to", "takes", "leaves", "drains", "auto-debit", "autodebit", "claimed by"))
