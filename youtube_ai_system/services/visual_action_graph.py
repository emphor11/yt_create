from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any


SCHEMA_VERSION = "visual_action_graph_v1"


@dataclass(frozen=True)
class VisualAction:
    id: str
    action: str
    label: str
    motion: str
    intent: str
    semantic_role: str = ""
    source_entity_id: str = ""
    target_entity_id: str = ""
    relationship_id: str = ""
    sentence_index: int | None = None
    value: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    sequence_index: int = 0
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualActionEdge:
    id: str
    type: str
    source_action_id: str
    target_action_id: str
    label: str
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualActionGraph:
    scene_id: str
    primary_concept: dict[str, Any]
    actions: list[VisualAction]
    edges: list[VisualActionEdge]
    warnings: list[dict[str, Any]]
    confidence: float
    source: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "scene_id": self.scene_id,
            "primary_concept": dict(self.primary_concept),
            "actions": [action.to_dict() for action in self.actions],
            "edges": [edge.to_dict() for edge in self.edges],
            "warnings": list(self.warnings),
            "confidence": self.confidence,
        }


class VisualActionGraphBuilder:
    """Derives action-level visual semantics from SemanticSceneContract only."""

    def build(self, semantic_scene: dict[str, Any] | None) -> VisualActionGraph:
        semantic_scene = dict(semantic_scene or {})
        scene_id = str(semantic_scene.get("scene_id") or "scene")
        primary_concept = dict(semantic_scene.get("primary_concept") or {})
        entities = [dict(entity) for entity in semantic_scene.get("entities") or [] if isinstance(entity, dict)]
        relationships = [dict(rel) for rel in semantic_scene.get("relationships") or [] if isinstance(rel, dict)]
        derived_values = [dict(value) for value in semantic_scene.get("derived_values") or [] if isinstance(value, dict)]
        warnings: list[dict[str, Any]] = []
        if semantic_scene.get("source") != "semantic_scene_contract_v1":
            warnings.append({"code": "missing_semantic_scene_contract", "message": "visual actions require SemanticSceneContract input"})
        if not entities:
            warnings.append({"code": "no_semantic_entities", "message": "no semantic entities available for visual actions"})

        concept_key = str(primary_concept.get("key") or "").strip().lower()
        actions = self._actions_for_concept(concept_key, entities, relationships, derived_values)
        if not actions and entities:
            actions = self._generic_entity_actions(entities)
        actions = self._ordered_actions(actions)
        edges = self._sequence_edges(actions)
        confidence = self._confidence(float(semantic_scene.get("confidence") or 0.55), actions, warnings)
        return VisualActionGraph(
            scene_id=scene_id,
            primary_concept=primary_concept,
            actions=actions,
            edges=edges,
            warnings=warnings,
            confidence=confidence,
        )

    def build_dict(self, semantic_scene: dict[str, Any] | None) -> dict[str, Any]:
        return self.build(semantic_scene).to_dict()

    def _actions_for_concept(
        self,
        concept_key: str,
        entities: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        derived_values: list[dict[str, Any]],
    ) -> list[VisualAction]:
        by_role = self._entities_by_role(entities)
        if concept_key in {"salary_drain", "rent_burden", "tax_drain", "expense_leakage", "budgeting", "savings_rate"}:
            return self._money_flow_actions(by_role, relationships, derived_values)
        if concept_key in {"sip_growth", "compounding", "net_worth_growth"}:
            return self._sip_growth_actions(by_role, relationships)
        if concept_key in {"debt_trap", "loan_cost"}:
            return self._debt_actions(by_role, relationships)
        if concept_key in {"emi_pressure", "emi_stack"}:
            return self._emi_actions(by_role)
        if concept_key == "lifestyle_inflation":
            return self._lifestyle_actions(by_role, relationships)
        if concept_key in {"inflation_erosion", "inflation_loss", "fd_vs_inflation", "real_return"}:
            return self._inflation_actions(by_role, relationships)
        return []

    def _money_flow_actions(
        self,
        by_role: dict[str, list[dict[str, Any]]],
        relationships: list[dict[str, Any]],
        derived_values: list[dict[str, Any]],
    ) -> list[VisualAction]:
        actions: list[VisualAction] = []
        salary = self._first(by_role, "salary_income")
        if salary:
            actions.append(self._action("salary_arrives", "Salary arrives", "credit_in", "establish_source", salary, priority=100))
        consumed = [rel for rel in relationships if rel.get("type") == "consumed_by"]
        if consumed:
            entity_by_id = self._entity_by_id(by_role)
            for rel in consumed:
                target = entity_by_id.get(str(rel.get("target_entity_id") or ""))
                if target:
                    actions.append(
                        self._action(
                            "expense_drains",
                            f"{self._entity_label(target)} drains",
                            "collision_drain",
                            "show_outflow",
                            target,
                            source_entity_id=str(rel.get("source_entity_id") or ""),
                            relationship_id=str(rel.get("id") or ""),
                            priority=80,
                        )
                    )
        else:
            for role in ("emi_payment", "rent_expense", "living_expense"):
                for entity in by_role.get(role, []):
                    actions.append(self._action("expense_drains", f"{self._entity_label(entity)} drains", "collision_drain", "show_outflow", entity, priority=80))
        remainder = self._first(by_role, "remaining_balance")
        if remainder:
            actions.append(self._action("balance_revealed", "Remaining balance revealed", "reveal_survivor", "show_consequence", remainder, priority=60))
        else:
            derived_remainder = self._first_derived(derived_values, "remaining_balance")
            if derived_remainder:
                actions.append(self._derived_action("balance_revealed", "Remaining balance revealed", "reveal_survivor", "show_consequence", derived_remainder, priority=55))
        return actions

    def _sip_growth_actions(self, by_role: dict[str, list[dict[str, Any]]], relationships: list[dict[str, Any]]) -> list[VisualAction]:
        actions: list[VisualAction] = []
        monthly = self._first(by_role, "monthly_sip")
        contribution = self._first(by_role, "total_contribution")
        rate = self._first(by_role, "annual_return_rate")
        period = self._first(by_role, "time_period")
        corpus = self._first(by_role, "target_corpus", "target_value")
        if monthly:
            actions.append(self._action("contribution_starts", "Monthly SIP starts", "repeat_deposit", "establish_contribution", monthly, priority=100))
        if contribution:
            rel = self._relationship_targeting(relationships, contribution)
            actions.append(self._action("contributions_accumulate", "Contributions accumulate", "stacking_accumulation", "show_principal_base", contribution, relationship_id=rel, priority=85))
        if rate:
            rel = self._relationship_targeting(relationships, rate, source=True)
            actions.append(self._action("return_rate_activates", "Return rate activates", "growth_curve_pull", "show_growth_force", rate, relationship_id=rel, priority=75))
        if period:
            actions.append(self._action("time_extends", "Time stretches the runway", "timeline_expand", "show_duration", period, priority=70))
        if corpus:
            rel = self._relationship_targeting(relationships, corpus)
            actions.append(self._action("corpus_revealed", "Corpus revealed", "compound_reveal", "show_growth_result", corpus, relationship_id=rel, priority=60))
        return actions

    def _debt_actions(self, by_role: dict[str, list[dict[str, Any]]], relationships: list[dict[str, Any]]) -> list[VisualAction]:
        actions: list[VisualAction] = []
        principal = self._first(by_role, "debt_principal", "principal_balance")
        rate = self._first(by_role, "annual_interest_rate")
        interest = self._first(by_role, "interest_charge")
        minimum = self._first(by_role, "minimum_payment")
        if principal:
            actions.append(self._action("debt_appears", "Debt balance appears", "balance_weight", "establish_liability", principal, priority=100))
        if rate:
            actions.append(self._action("interest_rate_attaches", "Interest rate attaches", "pressure_ring", "show_cost_pressure", rate, relationship_id=self._relationship_targeting(relationships, rate), priority=85))
        if interest:
            actions.append(self._action("interest_accumulates", "Interest accumulates", "compounding_pressure", "show_debt_growth", interest, relationship_id=self._relationship_targeting(relationships, interest), priority=75))
        if minimum:
            actions.append(self._action("minimum_payment_fails", "Minimum payment fails to clear debt", "partial_payback", "show_trap", minimum, relationship_id=self._relationship_targeting(relationships, minimum, source=True), priority=65))
        return actions

    def _emi_actions(self, by_role: dict[str, list[dict[str, Any]]]) -> list[VisualAction]:
        actions: list[VisualAction] = []
        salary = self._first(by_role, "salary_income")
        if salary:
            actions.append(self._action("salary_arrives", "Salary arrives", "credit_in", "establish_source", salary, priority=100))
        for entity in by_role.get("emi_payment") or []:
            actions.append(self._action("emi_stacks", "EMI stacks", "notification_stack", "show_fixed_payment_pressure", entity, priority=80))
        remainder = self._first(by_role, "remaining_balance")
        if remainder:
            actions.append(self._action("balance_revealed", "Remaining balance revealed", "reveal_survivor", "show_consequence", remainder, priority=60))
        return actions

    def _lifestyle_actions(self, by_role: dict[str, list[dict[str, Any]]], relationships: list[dict[str, Any]]) -> list[VisualAction]:
        incomes = by_role.get("salary_income") or []
        actions: list[VisualAction] = []
        if incomes:
            actions.append(self._action("income_baseline", "Old income baseline", "baseline_hold", "establish_before_state", incomes[0], priority=100))
        if len(incomes) > 1:
            actions.append(self._action("income_rises", "Income rises", "upward_step", "show_raise", incomes[1], relationship_id=self._relationship_targeting(relationships, incomes[1]), priority=85))
        raise_delta = self._first(by_role, "raise_delta")
        if raise_delta:
            actions.append(self._action("raise_absorbed", "Raise gets absorbed", "absorption_pull", "show_lifestyle_capture", raise_delta, priority=75))
        for entity in by_role.get("living_expense") or []:
            actions.append(self._action("expenses_follow", "Expenses follow income", "shadow_follow", "show_spending_expansion", entity, priority=70))
        return actions

    def _inflation_actions(self, by_role: dict[str, list[dict[str, Any]]], relationships: list[dict[str, Any]]) -> list[VisualAction]:
        actions: list[VisualAction] = []
        principal = self._first(by_role, "principal_balance", "salary_income")
        rate = self._first(by_role, "inflation_rate", "rate")
        period = self._first(by_role, "time_period")
        if principal:
            actions.append(self._action("value_anchor", "Current value anchors", "value_hold", "establish_starting_value", principal, priority=100))
        if rate:
            actions.append(self._action("inflation_erodes", "Inflation erodes buying power", "value_decay", "show_erosion_force", rate, relationship_id=self._relationship_targeting(relationships, rate, source=True), priority=85))
        if period:
            actions.append(self._action("time_exposes_loss", "Time exposes the loss", "timeline_decay", "show_long_term_effect", period, priority=70))
        return actions

    def _generic_entity_actions(self, entities: list[dict[str, Any]]) -> list[VisualAction]:
        return [
            self._action(
                "semantic_value_presented",
                self._entity_label(entity),
                "emphasis_reveal",
                "present_semantic_value",
                entity,
                priority=max(10, 100 - index * 10),
            )
            for index, entity in enumerate(entities[:5])
        ]

    def _action(
        self,
        action: str,
        label: str,
        motion: str,
        intent: str,
        entity: dict[str, Any],
        *,
        source_entity_id: str = "",
        relationship_id: str = "",
        priority: int = 0,
    ) -> VisualAction:
        action_id = f"act:{action}:{self._entity_id(entity) or len(label)}"
        return VisualAction(
            id=action_id,
            action=action,
            label=label,
            motion=motion,
            intent=intent,
            semantic_role=str(entity.get("role") or ""),
            source_entity_id=source_entity_id,
            target_entity_id=self._entity_id(entity),
            relationship_id=relationship_id,
            sentence_index=self._sentence_index(entity),
            value=self._entity_value(entity),
            priority=priority,
            provenance={
                "source": "semantic_scene_contract",
                "entity_ids": [entity_id for entity_id in (source_entity_id, self._entity_id(entity)) if entity_id],
                "relationship_ids": [relationship_id] if relationship_id else [],
            },
        )

    def _derived_action(
        self,
        action: str,
        label: str,
        motion: str,
        intent: str,
        derived_value: dict[str, Any],
        *,
        priority: int = 0,
    ) -> VisualAction:
        action_id = f"act:{action}:{derived_value.get('id') or len(label)}"
        source_entity_ids = [str(item) for item in derived_value.get("source_entity_ids") or [] if str(item)]
        return VisualAction(
            id=action_id,
            action=action,
            label=label,
            motion=motion,
            intent=intent,
            semantic_role=str(derived_value.get("label") or ""),
            value={
                "amount": derived_value.get("value"),
                "display_value": str(derived_value.get("display_value") or ""),
                "unit": str(derived_value.get("unit") or ""),
            },
            priority=priority,
            provenance={
                "source": "semantic_scene_contract",
                "entity_ids": source_entity_ids,
                "derived_value_id": derived_value.get("id"),
                "derivation_method": derived_value.get("derivation_method"),
            },
        )

    def _sequence_edges(self, actions: list[VisualAction]) -> list[VisualActionEdge]:
        edges: list[VisualActionEdge] = []
        for index, (source, target) in enumerate(zip(actions, actions[1:])):
            edges.append(
                VisualActionEdge(
                    id=f"edge:{index}:then",
                    type="then",
                    source_action_id=source.id,
                    target_action_id=target.id,
                    label=f"{source.action} then {target.action}",
                    provenance={"source": "visual_action_graph", "order": index},
                )
            )
        return edges

    def _ordered_actions(self, actions: list[VisualAction]) -> list[VisualAction]:
        ordered = sorted(enumerate(actions), key=lambda item: (self._sentence_sort(item[1]), -item[1].priority, item[0]))
        return [replace(action, sequence_index=index) for index, (_, action) in enumerate(ordered)]

    def _entities_by_role(self, entities: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        by_role: dict[str, list[dict[str, Any]]] = {}
        for entity in entities:
            role = str(entity.get("role") or "").strip()
            if role:
                by_role.setdefault(role, []).append(entity)
        return by_role

    def _entity_by_id(self, by_role: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for entities in by_role.values():
            for entity in entities:
                entity_id = self._entity_id(entity)
                if entity_id:
                    result[entity_id] = entity
        return result

    def _first(self, by_role: dict[str, list[dict[str, Any]]], *roles: str) -> dict[str, Any] | None:
        for role in roles:
            values = by_role.get(role) or []
            if values:
                return values[0]
        return None

    def _first_derived(self, derived_values: list[dict[str, Any]], label: str) -> dict[str, Any] | None:
        return next((value for value in derived_values if str(value.get("label") or "") == label), None)

    def _relationship_targeting(self, relationships: list[dict[str, Any]], entity: dict[str, Any] | None, *, source: bool = False) -> str:
        entity_id = self._entity_id(entity)
        if not entity_id:
            return ""
        key = "source_entity_id" if source else "target_entity_id"
        rel = next((item for item in relationships if str(item.get(key) or "") == entity_id), None)
        return str((rel or {}).get("id") or "")

    def _entity_id(self, entity: dict[str, Any] | None) -> str:
        return str((entity or {}).get("id") or "")

    def _entity_label(self, entity: dict[str, Any]) -> str:
        label = str(entity.get("label") or entity.get("role") or "value").strip()
        display = str(entity.get("display_value") or "").strip()
        return f"{label}: {display}" if display and display not in label else label

    def _entity_value(self, entity: dict[str, Any]) -> dict[str, Any]:
        return {
            "amount": entity.get("value"),
            "display_value": str(entity.get("display_value") or ""),
            "unit": str(entity.get("unit") or ""),
            "kind": str(entity.get("kind") or ""),
        }

    def _sentence_index(self, entity: dict[str, Any]) -> int | None:
        try:
            return int(entity.get("sentence_index")) if entity.get("sentence_index") is not None else None
        except (TypeError, ValueError):
            return None

    def _sentence_sort(self, action: VisualAction) -> int:
        return action.sentence_index if action.sentence_index is not None else 999

    def _confidence(self, semantic_confidence: float, actions: list[VisualAction], warnings: list[dict[str, Any]]) -> float:
        confidence = semantic_confidence + (0.06 if actions else -0.12) - (0.06 * len(warnings))
        return round(max(0.1, min(confidence, 1.0)), 3)
