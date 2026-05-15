from __future__ import annotations

import re
from typing import Any

from ...contracts.rendering import RenderSpec
from .flow_helpers import RenderFlowHelpers
from .numbers import RenderNumberUtils
from .value_deriver import RenderValueDeriver


class LegacyFlowStageBuilder:
    """Flow stage extraction for legacy FlowDiagram render specs."""

    def __init__(
        self,
        *,
        flow_helpers: RenderFlowHelpers,
        number_utils: RenderNumberUtils,
        value_deriver: RenderValueDeriver,
    ) -> None:
        self.flow_helpers = flow_helpers
        self.number_utils = number_utils
        self.value_deriver = value_deriver

    def beat_flow_stages(self, beat: dict[str, Any], concept: dict[str, Any], narration: str) -> list[dict[str, str]]:
        for candidate in (beat.get("flow_stages"), concept.get("flow_stages")):
            stages = self.explicit_flow_stages(candidate)
            if len(stages) >= 3:
                return stages

        content = str(beat.get("content") or "")
        parts = [part.strip() for part in re.split(r"\s*(?:->|→)\s*", content) if part.strip()]
        if len(parts) >= 3:
            return [
                {"label": "start", "value": parts[0]},
                {"label": "change", "value": parts[1]},
                {"label": "result", "value": parts[2]},
            ]
        return self.concept_flow_stages(concept, narration)

    def concept_flow_stages(self, concept: dict[str, Any], narration: str) -> list[dict[str, str]]:
        explicit = self.explicit_flow_stages(concept.get("flow_stages"))
        if len(explicit) >= 3:
            return explicit

        lowered = str(narration or "").lower()
        amounts = self.number_utils.money_tokens(narration)
        percents = self.number_utils.percent_tokens(narration)
        start = str(concept.get("start_value") or (amounts[0] if amounts else "₹20,000"))
        end = str(concept.get("end_value") or "₹0")

        time_match = re.search(r"\bday\s*(\d+)\b", lowered)
        if time_match:
            start_tokens = self.number_utils.money_tokens(start)
            start_value = amounts[0] if amounts else (start_tokens[0] if start_tokens else start)
            end_value = next((amount for amount in amounts[1:] if self.number_utils.first_numeric_value(amount) == 0), "₹0")
            return [
                {"label": "start", "value": f"Day 1 {start_value}"},
                {"label": "change", "value": f"Day {time_match.group(1)}"},
                {"label": "result", "value": end_value},
            ]

        if percents:
            principal = amounts[0] if amounts else start
            rate = percents[0]
            output = amounts[1] if len(amounts) > 1 else self.value_deriver.inflation_output(principal, rate)
            return [
                {"label": "start", "value": principal},
                {"label": "change", "value": f"{rate} change"},
                {"label": "result", "value": output},
            ]

        if amounts and any(word in lowered for word in ("month", "monthly", "/month", "year", "yearly", "annual")):
            monthly = amounts[0]
            yearly = amounts[1] if len(amounts) > 1 else self.number_utils.format_rupees(self.number_utils.first_numeric_value(monthly) * 12)
            return [
                {"label": "start", "value": f"{monthly}/month"},
                {"label": "change", "value": "12 months"},
                {"label": "result", "value": f"{yearly}/year"},
            ]

        start_value = amounts[0] if amounts else start
        middle_value = self.number_utils.format_rupees(self.number_utils.first_numeric_value(start_value) * 0.5)
        end_value = "₹0" if self.number_utils.first_numeric_value(end) <= 0 else end
        return [
            {"label": "start", "value": start_value},
            {"label": "change", "value": middle_value},
            {"label": "result", "value": end_value},
        ]

    def explicit_flow_stages(self, candidate: Any) -> list[dict[str, str]]:
        if not isinstance(candidate, list) or len(candidate) < 3:
            return []
        return [
            {"label": str(stage.get("label") or self.flow_helpers.default_node_role(index, 3)), "value": str(stage.get("value") or "")}
            for index, stage in enumerate(candidate[:3])
            if isinstance(stage, dict) and str(stage.get("value") or "").strip()
        ]


class LegacyFlowSpecFactory:
    """Builds legacy FlowDiagram RenderSpec objects from legacy beat payloads."""

    def __init__(self, ops: Any) -> None:
        self.ops = ops

    def flow_diagram_spec(self, beat: dict[str, Any], duration_sec: float, color: str) -> RenderSpec:
        ops = self.ops
        concept = beat.get("concept_metadata") if isinstance(beat.get("concept_metadata"), dict) else {}
        narration = str(concept.get("narration") or beat.get("narration") or beat.get("caption") or beat.get("content") or "")
        stages = ops._beat_flow_stages(beat, concept, narration)
        nodes = [
            {
                "id": stage["label"],
                "label": ops._humanize_money_phrase(stage["value"]),
                "role": "source" if index == 0 else ("result" if index == len(stages) - 1 else "process"),
                "style": ops._node_style(
                    "source" if index == 0 else ("result" if index == len(stages) - 1 else "process"),
                    stage["value"],
                    "VALUE_DECAY" if ops._is_loss_result(" ".join(stage["value"] for stage in stages)) else "MONEY_FLOW",
                ),
                "children": [],
            }
            for index, stage in enumerate(stages)
        ]
        caption = str(beat.get("caption") or concept.get("explanation_sentence") or " -> ".join(stage["value"] for stage in stages))
        caption = ops._complete_caption(ops._short_overlay(caption, 10))
        semantic_color = ops._color_for_label(" ".join(stage["value"] for stage in stages) + " " + caption) or color
        props = {
            "mode": "decay" if semantic_color == "red" else "linear",
            "layout": "horizontal",
            "spacing": "equal",
            "direction": "forward",
            "nodes": nodes,
            "connections": [{"from": nodes[index]["id"], "to": nodes[index + 1]["id"]} for index in range(len(nodes) - 1)],
            "caption": caption,
            "captionColor": ops._color_for_label(caption) or semantic_color,
            "color": semantic_color,
            "durationSec": duration_sec,
            "animationIntent": "progress",
            "animationSpec": ops.ANIMATION_MAP["progress"],
        }
        return RenderSpec(
            composition="FlowDiagram",
            props=ops._polish_flow_display_props(props, " -> ".join(stage["value"] for stage in stages)),
            duration_sec=duration_sec,
            source="remotion_flowdiagram",
        )
