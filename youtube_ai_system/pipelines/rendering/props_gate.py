from __future__ import annotations

from typing import Any

from .visual_gate import RenderVisualGate


class RenderPropsGate:
    """Concrete-data checks for generated Remotion props."""

    def __init__(self, visual_gate: RenderVisualGate) -> None:
        self.visual_gate = visual_gate

    def passes_visual_gate(self, intent: str, pattern: str, visual_logic: str) -> bool:
        if intent == "CONTEXT" or pattern == "CONTEXT":
            return True
        if intent == "EMPHASIS" or pattern == "EMPHASIS":
            return (
                self.visual_gate.has_number(visual_logic)
                and self.visual_gate.has_impact(visual_logic)
                and not self.visual_gate.is_abstract_visual_logic(visual_logic)
            )
        return self.visual_gate.passes_text_gate(visual_logic)

    def props_pass_visual_gate(
        self,
        component: str,
        pattern: str,
        visual_logic: str,
        props: dict[str, Any],
    ) -> bool:
        if component == "BrollOverlay":
            return True
        if component == "FlowDiagram":
            nodes = props.get("nodes")
            if not isinstance(nodes, list) or len(nodes) < 3:
                return False
            labels = [str(node.get("label") if isinstance(node, dict) else node) for node in nodes]
            return self.visual_gate.passes_text_gate(" -> ".join(labels))
        if component == "SplitComparison":
            return self.visual_gate.passes_text_gate(f"{props.get('leftContent', '')} vs {props.get('rightContent', '')}")
        if component in {"BarChart", "LineChart"}:
            data = props.get("data")
            title = str(props.get("title") or visual_logic)
            return isinstance(data, list) and len(data) >= 2 and not self.visual_gate.is_abstract_visual_logic(title)
        if component in {"StatExplosion", "TextBurst", "ReactionCard", "StatReveal"}:
            text = " ".join(str(props.get(key) or "") for key in ("headline", "content", "subtext", "kicker"))
            candidate = text or visual_logic
            return (
                self.visual_gate.has_number(candidate)
                and self.visual_gate.has_impact(candidate)
                and not self.visual_gate.is_abstract_visual_logic(candidate)
            )
        return self.visual_gate.passes_text_gate(visual_logic)
