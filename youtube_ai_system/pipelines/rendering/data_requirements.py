from __future__ import annotations

import re
from typing import Any

from .chart_data import RenderChartDataExtractor
from .visual_gate import RenderVisualGate


class RenderDataRequirementGate:
    """Checks whether a selected render pattern has enough concrete data."""

    def __init__(
        self,
        *,
        flow_patterns: set[str],
        chart_data: RenderChartDataExtractor,
        visual_gate: RenderVisualGate,
    ) -> None:
        self.flow_patterns = flow_patterns
        self.chart_data = chart_data
        self.visual_gate = visual_gate

    def has_chart_data(self, beat: dict[str, Any], visual_logic: str) -> bool:
        props = beat.get("props") if isinstance(beat.get("props"), dict) else {}
        data = props.get("data")
        return (isinstance(data, list) and len(data) >= 2) or len(self.chart_data.extract_data_points(visual_logic)) >= 2

    def pattern_has_required_concrete_data(
        self,
        intent: str,
        pattern: str,
        beat: dict[str, Any],
        visual_logic: str,
    ) -> bool:
        props = beat.get("props") if isinstance(beat.get("props"), dict) else {}
        if pattern == "COMPARISON":
            left = str(props.get("leftContent") or "")
            right = str(props.get("rightContent") or "")
            text = f"{visual_logic} {left} {right}"
            return bool(
                (
                    left.strip()
                    and right.strip()
                    and self.visual_gate.passes_text_gate(f"{left} vs {right}")
                )
                or re.search(r"\b(vs|versus|compared|than)\b", text.lower())
            )
        if pattern == "GROWTH" and intent == "DATA":
            return self.has_chart_data(beat, visual_logic)
        if pattern in self.flow_patterns:
            nodes = props.get("nodes")
            if isinstance(nodes, list) and len(nodes) >= 2:
                labels = [
                    str(node.get("label") if isinstance(node, dict) else node)
                    for node in nodes
                ]
                return (len(labels) >= 3 and self.visual_gate.passes_text_gate(" -> ".join(labels))) or self.visual_gate.passes_text_gate(visual_logic)
            return self.visual_gate.passes_text_gate(visual_logic)
        return True
