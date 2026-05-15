from __future__ import annotations

from typing import Any

from .flow_labels import RenderFlowLabelHelper


class RenderLogicTextFormatter:
    """Converts typed visual logic dictionaries into current render text."""

    def __init__(self, flow_labels: RenderFlowLabelHelper | None = None) -> None:
        self.flow_labels = flow_labels or RenderFlowLabelHelper()

    def visual_logic_to_text(self, visual_logic: Any, *, logic_type: str) -> str:
        if not isinstance(visual_logic, dict):
            return " ".join(str(visual_logic or "").split())
        if logic_type == "comparison":
            return (
                f"{self.flow_labels.humanize_money_phrase(str(visual_logic.get('left', '')))} vs "
                f"{self.flow_labels.humanize_money_phrase(str(visual_logic.get('right', '')))}"
            ).strip()
        if logic_type == "flow":
            return (
                f"{self.flow_labels.humanize_money_phrase(str(visual_logic.get('source', '')))} -> "
                f"{self.flow_labels.humanize_money_phrase(str(visual_logic.get('process', '')))} -> "
                f"{self.flow_labels.humanize_money_phrase(str(visual_logic.get('result', '')))}"
            ).strip()
        if logic_type == "decay":
            return f"{visual_logic.get('input', '')} -> {visual_logic.get('factor', '')} -> {visual_logic.get('output', '')}".strip()
        if logic_type == "growth":
            return f"{visual_logic.get('input', '')} -> {visual_logic.get('rate', '')} -> {visual_logic.get('output', '')}".strip()
        if logic_type == "emphasis":
            return f"{visual_logic.get('headline', '')} {visual_logic.get('subtext', '')}".strip()
        return " ".join(str(value) for value in visual_logic.values() if value).strip()
