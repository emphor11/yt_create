from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .chart_data import RenderChartDataExtractor
from .flow_labels import RenderFlowLabelHelper
from .flow_props import RenderFlowPropsBuilder
from .split_helpers import RenderSplitHelpers
from .text_utils import RenderTextUtils
from .visual_gate import RenderVisualGate


class RenderPropsBuilder:
    """Builds repaired and regenerated Remotion component props."""

    def __init__(
        self,
        *,
        chart_data: RenderChartDataExtractor,
        flow_labels: RenderFlowLabelHelper,
        flow_props: RenderFlowPropsBuilder,
        split_helpers: RenderSplitHelpers,
        text_utils: RenderTextUtils,
        visual_gate: RenderVisualGate,
    ) -> None:
        self.chart_data = chart_data
        self.flow_labels = flow_labels
        self.flow_props = flow_props
        self.split_helpers = split_helpers
        self.text_utils = text_utils
        self.visual_gate = visual_gate

    def regenerate_props(
        self,
        component: str,
        pattern: str,
        visual_logic: str,
        caption: str,
        context: str,
        beat: dict[str, Any],
        *,
        contextual_visual_logic: Callable[[str, dict[str, Any]], str],
        safe_emphasis_logic: Callable[[str], str],
        safe_emphasis_props: Callable[[str, str], dict[str, Any]],
    ) -> dict[str, Any]:
        regenerated_logic = visual_logic if self.visual_gate.passes_text_gate(visual_logic) else contextual_visual_logic(context, beat)
        color = "red" if self.text_utils.sentiment(regenerated_logic) == "negative" else self.text_utils.beat_color(beat.get("color"))
        if component == "FlowDiagram":
            return self.flow_props.flow_props(pattern, regenerated_logic, caption, {}, color, {**beat, "props": {}})
        if component == "SplitComparison":
            left, right = self.split_helpers.concrete_split_from_logic(regenerated_logic, caption)
            return {"leftLabel": "CLAIM", "leftContent": left, "rightLabel": "REALITY", "rightContent": right}
        if component in {"BarChart", "LineChart"}:
            data = self.chart_data.extract_data_points(regenerated_logic)
            if len(data) >= 2:
                return {
                    "title": self.text_utils.short_overlay(regenerated_logic, 8),
                    "data": data,
                    "color": self.text_utils.chart_color(regenerated_logic),
                    "unit": self.text_utils.unit_label(regenerated_logic),
                    "animationSpeed": "fast",
                }
        return safe_emphasis_props(safe_emphasis_logic(context or regenerated_logic), caption)

    def repair_props(
        self,
        component: str,
        pattern: str,
        visual_logic: str,
        caption: str,
        beat: dict[str, Any],
    ) -> dict[str, Any]:
        raw_props = beat.get("props") if isinstance(beat.get("props"), dict) else {}
        color = self.text_utils.beat_color(raw_props.get("color") or beat.get("color"))
        if component == "FlowDiagram":
            return self.flow_props.flow_props(pattern, visual_logic, caption, raw_props, color, beat)
        if component == "SplitComparison":
            left_label, left_content, right_label, right_content = self.text_utils.parse_split(
                str(raw_props.get("leftContent") or visual_logic),
                str(raw_props.get("rightContent") or caption),
            )
            if self.visual_gate.is_abstract_visual_logic(left_content) or self.visual_gate.is_abstract_visual_logic(right_content):
                left_content, right_content = self.split_helpers.concrete_split_from_logic(visual_logic, caption)
            left_content = self.flow_labels.humanize_money_phrase(left_content)
            right_content = self.flow_labels.humanize_money_phrase(right_content)
            left_label = self.text_utils.extract_split_label(left_content)
            right_label = self.text_utils.extract_split_label(right_content)
            return {
                "leftLabel": self.split_helpers.humanize_split_label(str(raw_props.get("leftLabel") or left_label), left_content),
                "leftContent": left_content,
                "rightLabel": self.split_helpers.humanize_split_label(str(raw_props.get("rightLabel") or right_label), right_content),
                "rightContent": right_content,
                "leftColor": self.flow_labels.color_for_label(left_content),
                "rightColor": self.flow_labels.color_for_label(right_content),
            }
        if component in {"BarChart", "LineChart"}:
            data = raw_props.get("data") if isinstance(raw_props.get("data"), list) else self.chart_data.extract_data_points(visual_logic)
            if len(data) < 2:
                return {"content": self.text_utils.short_overlay(visual_logic, 5), "subtext": caption, "color": color}
            chart_color = self.text_utils.extract_color(visual_logic) or (color if color in {"red", "teal", "orange"} else "orange")
            return {
                "title": str(raw_props.get("title") or self.text_utils.short_overlay(visual_logic, 8) or "Financial Trend"),
                "data": data,
                "color": chart_color,
                "unit": str(raw_props.get("unit") or self.text_utils.unit_label(visual_logic)),
                "animationSpeed": "fast",
            }
        if component == "StatExplosion":
            return {
                "headline": str(raw_props.get("headline") or self.text_utils.dominant_phrase(visual_logic)),
                "subtext": caption,
                "color": self.flow_labels.color_for_label(f"{visual_logic} {caption}") or color,
            }
        if component == "TextBurst":
            return {"content": str(raw_props.get("content") or self.text_utils.short_overlay(visual_logic, 5)), "color": color}
        if component == "ReactionCard":
            return {"content": str(raw_props.get("content") or self.text_utils.short_overlay(visual_logic, 5)), "subtext": caption, "color": color}
        if component == "BrollOverlay":
            return {
                "overlayText": caption,
                "query": str(raw_props.get("query") or raw_props.get("searchQuery") or self.text_utils.short_overlay(visual_logic, 5)),
                "brand": "10 Minute Finance",
                "sentiment": self.text_utils.sentiment(f"{visual_logic} {caption}"),
            }
        return {"content": self.text_utils.short_overlay(visual_logic, 5), "color": color}
