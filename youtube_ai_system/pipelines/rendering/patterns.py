from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any


class RenderPatternSelector:
    """Intent, pattern, component, and timing selection for structured beats."""

    def __init__(
        self,
        *,
        intent_pattern_map: dict[str, set[str]],
        flow_patterns: set[str],
        duration_by_intent: dict[str, float],
        animation_map: dict[str, dict[str, Any]],
    ) -> None:
        self.intent_pattern_map = intent_pattern_map
        self.flow_patterns = flow_patterns
        self.duration_by_intent = duration_by_intent
        self.animation_map = animation_map

    def all_patterns(self) -> set[str]:
        patterns: set[str] = set()
        for values in self.intent_pattern_map.values():
            patterns.update(values)
        return patterns

    def infer_intent(self, pattern: str, visual_logic: str) -> str:
        text = visual_logic.lower()
        if pattern == "EMPHASIS":
            return "EMPHASIS"
        if pattern == "CONTEXT":
            return "CONTEXT"
        if pattern == "COMPARISON" or re.search(r"\b(vs|versus|compared|reality|instead)\b", text):
            return "COMPARISON"
        if pattern in self.flow_patterns or any(
            word in text for word in ("because", "leads to", "turns into", "cycle", "flow", "moves", "inflation", "tax")
        ):
            return "EXPLANATION"
        if re.search(r"[₹\d%]", visual_logic):
            return "DATA"
        if pattern == "CONTEXT" or any(word in text for word in ("person", "office", "bank", "phone", "background")):
            return "CONTEXT"
        return "EMPHASIS"

    def pattern_for_intent(self, intent: str, visual_logic: str) -> str:
        text = visual_logic.lower()
        if intent == "HOOK":
            return "EMPHASIS"
        if intent == "COMPARISON":
            return "COMPARISON"
        if intent == "DATA":
            return "COMPARISON" if re.search(r"\b(vs|versus|compared|than)\b", text) else "GROWTH"
        if intent == "EXPLANATION":
            if any(word in text for word in ("inflation", "tax", "fee", "fees", "erode", "erosion", "decay", "shrink", "reduced")):
                return "VALUE_DECAY"
            if any(word in text for word in ("debt", "credit", "cycle", "repeat", "trap", "loop")):
                return "LOOP"
            if any(word in text for word in ("compound", "sip", "growth", "grow", "invest", "wealth")):
                return "GROWTH"
            return "MONEY_FLOW"
        if intent == "CONTEXT":
            return "CONTEXT"
        return "EMPHASIS"

    def derive_component(
        self,
        intent: str,
        pattern: str,
        beat: dict[str, Any],
        visual_logic: str,
        *,
        has_chart_data: Callable[[dict[str, Any], str], bool],
    ) -> str:
        if pattern in {"MONEY_FLOW", "VALUE_DECAY", "LOOP"}:
            return "FlowDiagram"
        if pattern == "GROWTH":
            return "LineChart" if intent == "DATA" and has_chart_data(beat, visual_logic) else "FlowDiagram"
        if pattern == "COMPARISON":
            return "SplitComparison"
        if pattern == "CONTEXT":
            return "FlowDiagram"
        props = beat.get("props") if isinstance(beat.get("props"), dict) else {}
        emphasis_text = " ".join(
            str(value)
            for value in (
                visual_logic,
                beat.get("caption") or "",
                props.get("headline") or "",
                props.get("subtext") or "",
                props.get("content") or "",
            )
            if value
        )
        return self.emphasis_component(emphasis_text)

    def emphasis_component(self, text: str) -> str:
        if re.search(r"[₹\d%]", text):
            return "StatExplosion"
        if len(re.findall(r"\S+", text)) <= 3:
            return "TextBurst"
        return "ReactionCard"

    def normalize_animation_intent(self, value: Any) -> str:
        animation = str(value or "reveal").strip().lower()
        return animation if animation in self.animation_map else "reveal"

    def structured_duration(self, intent: str, beat: dict[str, Any]) -> float:
        if beat.get("duration_locked"):
            try:
                return max(1.0, min(float(beat.get("estimated_duration_sec") or 3.0), 6.0))
            except (TypeError, ValueError):
                pass
        return self.duration_by_intent.get(intent, 3.0)
