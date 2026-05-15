from __future__ import annotations

from collections.abc import Callable
from typing import Any


class RenderClassifiedContract:
    """Classified-intent rules for structured render beats."""

    VALID_CLASSIFIED_INTENTS = {"EMPHASIS", "COMPARISON", "FLOW", "DECAY"}

    def classify_intent(self, narration: str, *, has_money_tokens: Callable[[str], bool]) -> str:
        text = str(narration or "").lower()
        if any(phrase in text for phrase in ("cannot", "less than", "only")):
            return "EMPHASIS"
        if any(phrase in text for phrase in (" vs ", " versus ", "compared")):
            return "COMPARISON"
        if any(
            word in text
            for word in (
                "vanish",
                "vanished",
                "lost",
                "loss",
                "leak",
                "leaking",
                "reduce",
                "reduced",
                "inflation",
                "fd",
                "fixed deposit",
            )
        ):
            return "DECAY"
        if any(
            word in text
            for word in (
                "earn",
                "earned",
                "spend",
                "spent",
                "left",
                "automate",
                "manual",
                "emotion",
                "auto debit",
                "salary",
                "expense",
                "expenses",
            )
        ):
            return "FLOW"
        return "FLOW" if has_money_tokens(narration) else "EMPHASIS"

    def classified_intent_for_beat(
        self,
        beat: dict[str, Any],
        context: str,
        visual_logic: Any,
        *,
        classify_intent: Callable[[str], str],
        logic_type: Callable[[Any], str],
    ) -> str:
        explicit = str(beat.get("classified_intent") or "").upper()
        if explicit in self.VALID_CLASSIFIED_INTENTS:
            return explicit
        if context.strip():
            return classify_intent(context)
        visual_logic_type = logic_type(visual_logic)
        if visual_logic_type == "emphasis":
            return "EMPHASIS"
        if visual_logic_type == "comparison":
            return "COMPARISON"
        if visual_logic_type == "decay":
            return "DECAY"
        if visual_logic_type == "flow":
            return "FLOW"
        raw_intent = str(beat.get("intent") or "").upper()
        raw_pattern = str(beat.get("pattern") or "").upper()
        if raw_intent in {"HOOK", "EMPHASIS"} or raw_pattern == "EMPHASIS":
            return "EMPHASIS"
        if raw_intent == "COMPARISON" or raw_pattern == "COMPARISON":
            return "COMPARISON"
        if raw_pattern == "VALUE_DECAY":
            return "DECAY"
        if raw_pattern in {"MONEY_FLOW", "LOOP", "GROWTH"} or raw_intent in {"EXPLANATION", "DATA"}:
            return "FLOW"
        return ""

    def enforce_render_contract(
        self,
        classified_intent: str,
        intent: str,
        pattern: str,
        component: str,
        visual_logic_object: Any,
        context: str,
        *,
        logic_type: Callable[[Any], str],
        logic_from_intent: Callable[[str, str], dict[str, Any]],
    ) -> tuple[str, str, str, dict[str, Any]]:
        classified_intent = str(classified_intent or "").upper()
        logic = visual_logic_object if isinstance(visual_logic_object, dict) else logic_from_intent(context, classified_intent)
        resolved_logic_type = logic_type(logic)
        if classified_intent == "EMPHASIS":
            if resolved_logic_type != "emphasis":
                logic = logic_from_intent(context, "EMPHASIS")
            return "EMPHASIS", "EMPHASIS", "StatExplosion", logic
        if classified_intent == "COMPARISON":
            if resolved_logic_type != "comparison":
                logic = logic_from_intent(context, "COMPARISON")
            return "COMPARISON", "COMPARISON", "SplitComparison", logic
        if classified_intent == "FLOW":
            if resolved_logic_type != "flow":
                logic = logic_from_intent(context, "FLOW")
            return "EXPLANATION", "MONEY_FLOW", "FlowDiagram", logic
        if classified_intent == "DECAY":
            if resolved_logic_type not in {"flow", "decay"}:
                logic = logic_from_intent(context, "DECAY")
            return "EXPLANATION", "VALUE_DECAY", "FlowDiagram", logic
        return intent, pattern, component, logic

    def fallback_for_classified_intent(
        self,
        classified_intent: str,
        context: str,
        *,
        logic_from_intent: Callable[[str, str], dict[str, Any]],
    ) -> tuple[str, str, str, dict[str, Any]]:
        classified_intent = str(classified_intent or "").upper()
        if classified_intent == "EMPHASIS":
            return "EMPHASIS", "EMPHASIS", "StatExplosion", logic_from_intent(context, "EMPHASIS")
        if classified_intent == "COMPARISON":
            return "COMPARISON", "COMPARISON", "SplitComparison", logic_from_intent(context, "COMPARISON")
        if classified_intent == "DECAY":
            return "EXPLANATION", "VALUE_DECAY", "FlowDiagram", logic_from_intent(context, "DECAY")
        return "EXPLANATION", "MONEY_FLOW", "FlowDiagram", logic_from_intent(context, "FLOW")
