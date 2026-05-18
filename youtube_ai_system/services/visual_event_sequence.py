from __future__ import annotations

from typing import Any

from ..contracts.visual_event_sequence import VisualEvent, VisualEventSequence


class VisualEventSequenceBuilder:
    """Converts action-level semantics into renderer-facing perceptual events."""

    MOTION_TO_PRIMITIVE = {
        "absorption_pull": "compression",
        "balance_weight": "trap",
        "baseline_hold": "arrival",
        "collision_drain": "attack",
        "compound_reveal": "reveal",
        "compounding_pressure": "acceleration",
        "credit_in": "arrival",
        "emphasis_reveal": "reveal",
        "growth_curve_pull": "acceleration",
        "notification_stack": "stack",
        "partial_payback": "trap",
        "pressure_ring": "compression",
        "repeat_deposit": "growth_seed",
        "reveal_survivor": "isolation",
        "shadow_follow": "attack",
        "stacking_accumulation": "stack",
        "timeline_decay": "erosion",
        "timeline_expand": "timeline",
        "upward_step": "growth",
        "value_decay": "erosion",
        "value_hold": "arrival",
    }

    PRIMITIVE_TO_WORLD = {
        "acceleration": "growth_acceleration",
        "arrival": "value_arrival",
        "attack": "expense_attack",
        "compression": "pressure_compression",
        "erosion": "value_erosion",
        "growth": "growth_reveal",
        "growth_seed": "growth_seed",
        "isolation": "survivor_isolation",
        "reveal": "semantic_reveal",
        "stack": "commitment_stack",
        "timeline": "delayed_timeline",
        "trap": "trap_reveal",
    }

    CONCEPT_DIRECTION = {
        "affordability_illusion": "revealing",
        "anchoring": "revealing",
        "cash_flow_squeeze": "tightening",
        "commitment_stacking": "tightening",
        "compounding": "building",
        "debt_trap": "warning",
        "delayed_consequence": "warning",
        "emi_pressure": "tightening",
        "expense_leakage": "clarity",
        "inflation_erosion": "tightening",
        "leverage": "clarity",
        "lifestyle_inflation": "tightening",
        "payment_pain_reduction": "revealing",
        "price_anchoring": "revealing",
        "salary_drain": "warning",
        "sip_growth": "building",
    }

    def build(self, section: dict[str, Any] | None) -> VisualEventSequence:
        section = dict(section or {})
        graph = dict(section.get("visual_action_graph") or {})
        semantic_scene = dict(section.get("semantic_scene") or {})
        primary_concept = dict(graph.get("primary_concept") or semantic_scene.get("primary_concept") or {})
        scene_id = str(graph.get("scene_id") or semantic_scene.get("scene_id") or section.get("idea_group_id") or "scene")
        warnings = [dict(item) for item in graph.get("warnings") or [] if isinstance(item, dict)]
        actions = [dict(action) for action in graph.get("actions") or [] if isinstance(action, dict)]
        if graph.get("source") != "visual_action_graph_v1":
            warnings.append(
                {
                    "code": "missing_visual_action_graph",
                    "message": "visual event sequence requires VisualActionGraph input",
                }
            )
        events = [
            self._event_for_action(action, index, len(actions), primary_concept, section)
            for index, action in enumerate(actions)
        ]
        if not events:
            warnings.append({"code": "no_visual_events", "message": "no visual events could be derived"})
        confidence = self._confidence(float(graph.get("confidence") or semantic_scene.get("confidence") or 0.5), events, warnings)
        return VisualEventSequence(
            scene_id=scene_id,
            primary_concept=primary_concept,
            events=events,
            warnings=warnings,
            confidence=confidence,
        )

    def build_dict(self, section: dict[str, Any] | None) -> dict[str, Any]:
        return self.build(section).to_dict()

    def _event_for_action(
        self,
        action: dict[str, Any],
        index: int,
        total: int,
        primary_concept: dict[str, Any],
        section: dict[str, Any],
    ) -> VisualEvent:
        value = dict(action.get("value") or {})
        active_entity = self._active_entity(action, value)
        primitive = self.MOTION_TO_PRIMITIVE.get(str(action.get("motion") or ""), "reveal")
        world_object = self._world_object(action, value, primary_concept, primitive)
        direction = self._emotional_direction(primary_concept, section, primitive)
        timing = self._timing(index, total)
        return VisualEvent(
            id=f"ves:{index}:{action.get('action') or 'event'}",
            sequence_index=index,
            active_entity=active_entity,
            world_object=world_object,
            primitive_type=primitive,
            perceptual_world=self.PRIMITIVE_TO_WORLD.get(primitive, "semantic_reveal"),
            emotional_direction=direction,
            narration_anchor=self._narration_anchor(action, value),
            suppression_target=self._suppression_target(primary_concept, primitive),
            visual_purpose=str(action.get("intent") or "focus_attention"),
            source_action_id=str(action.get("id") or ""),
            source_motion=str(action.get("motion") or ""),
            semantic_role=str(action.get("semantic_role") or ""),
            value=value,
            timing=timing,
            provenance={"source": "visual_action_graph", "source_action_id": str(action.get("id") or "")},
        )

    def _active_entity(self, action: dict[str, Any], value: dict[str, Any]) -> str:
        display = str(value.get("display_value") or value.get("amount") or "").strip()
        label = str(action.get("label") or "").strip()
        return display or label or str(action.get("semantic_role") or "money")

    def _narration_anchor(self, action: dict[str, Any], value: dict[str, Any]) -> str:
        display = str(value.get("display_value") or value.get("amount") or "").strip()
        label = str(action.get("label") or "").strip()
        if display and label:
            return f"{label}: {display}"
        return display or label or "spoken money moment"

    def _world_object(
        self,
        action: dict[str, Any],
        value: dict[str, Any],
        primary_concept: dict[str, Any],
        primitive: str,
    ) -> str:
        concept_key = str(primary_concept.get("key") or "").strip().lower()
        semantic_role = str(action.get("semantic_role") or "").strip().lower()
        action_name = str(action.get("action") or "").strip().lower()
        intent = str(action.get("intent") or "").strip().lower()
        label = " ".join([semantic_role, action_name, intent, str(value.get("kind") or "")]).lower()
        if "emi" in label or "monthly" in label:
            return "monthly_payment"
        if "interest" in label or "future" in label or "obligation" in label:
            return "future_obligation"
        if "salary" in label:
            return "salary_balance"
        if "debt" in label:
            return "debt_pressure"
        if "inflation" in label or "purchasing" in label:
            return "inflation_basket"
        if "sip" in label or "corpus" in label or "compound" in label:
            return "investment_engine"
        if concept_key in {"payment_pain_reduction", "affordability_illusion", "price_anchoring", "anchoring"}:
            try:
                if float(value.get("amount") or 0) and float(value.get("amount") or 0) < 100000:
                    return "monthly_payment"
            except (TypeError, ValueError):
                pass
            return "monthly_payment" if "payment" in label else "full_price"
        if concept_key == "leverage":
            return "capital_pool"
        if concept_key in {"opportunity_cost", "compounding", "sip_growth"}:
            return "investment_engine" if primitive in {"growth", "growth_seed", "acceleration", "reveal"} else "capital_pool"
        if concept_key in {"commitment_stacking", "cash_flow_squeeze", "emi_pressure"}:
            return "future_obligation" if primitive in {"stack", "compression", "trap"} else "monthly_payment"
        if concept_key == "lifestyle_inflation":
            return "status_upgrade"
        if concept_key in {"delayed_consequence", "debt_trap"}:
            return "future_obligation"
        return "money_decision"

    def _emotional_direction(self, primary_concept: dict[str, Any], section: dict[str, Any], primitive: str) -> str:
        concept_key = str(primary_concept.get("key") or section.get("concept_type") or "").strip().lower()
        if concept_key in self.CONCEPT_DIRECTION:
            return self.CONCEPT_DIRECTION[concept_key]
        if primitive in {"trap", "compression", "erosion", "attack"}:
            return "tightening"
        if primitive in {"growth", "growth_seed", "reveal"}:
            return "revealing"
        return "clarity"

    def _suppression_target(self, primary_concept: dict[str, Any], primitive: str) -> str:
        concept_key = str(primary_concept.get("key") or "").strip().lower()
        if concept_key in {"affordability_illusion", "payment_pain_reduction", "price_anchoring", "anchoring"}:
            return "full_price_blindness"
        if concept_key in {"cash_flow_squeeze", "commitment_stacking", "emi_pressure"}:
            return "future_obligation_invisibility"
        if concept_key in {"debt_trap", "delayed_consequence"}:
            return "painless_now_framing"
        if primitive in {"growth", "growth_seed", "acceleration"}:
            return "short_term_noise"
        return "generic_dashboard_noise"

    def _timing(self, index: int, total: int) -> dict[str, Any]:
        total = max(total, 1)
        start = round(index / total, 4)
        end = round((index + 1) / total, 4)
        return {"start_progress": start, "end_progress": end}

    def _confidence(self, base: float, events: list[VisualEvent], warnings: list[dict[str, Any]]) -> float:
        score = max(0.0, min(1.0, base))
        if events:
            score += 0.08
        score -= 0.06 * len(warnings)
        return round(max(0.0, min(1.0, score)), 2)
