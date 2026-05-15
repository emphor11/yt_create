from __future__ import annotations

import re
from typing import Any

from .flow_labels import RenderFlowLabelHelper
from .text_utils import RenderTextUtils


class RenderCaptionBuilder:
    """Caption and narration context helpers for render specs."""

    def __init__(
        self,
        *,
        text_utils: RenderTextUtils | None = None,
        flow_labels: RenderFlowLabelHelper | None = None,
    ) -> None:
        self.text_utils = text_utils or RenderTextUtils()
        self.flow_labels = flow_labels or RenderFlowLabelHelper()

    def repair_caption(self, caption: str, visual_logic: str, narration: str = "") -> str:
        caption = " ".join(re.findall(r"[A-Za-z0-9₹%.,'-]+", caption)).strip()
        narration_clean = " ".join(re.findall(r"[A-Za-z0-9₹%.,'-]+", narration)).strip().lower()
        if not caption or caption.lower() == narration_clean:
            caption = self.text_utils.short_overlay(visual_logic, 10)
        words = caption.split()
        if len(words) > 10:
            caption = " ".join(words[:10])
        return self.flow_labels.complete_caption(caption) or "watch the money move"

    def beat_context(self, beat: dict[str, Any]) -> str:
        pieces = [
            beat.get("narration"),
            beat.get("visual_instruction"),
            beat.get("content"),
            beat.get("caption"),
        ]
        return " ".join(str(piece) for piece in pieces if piece).strip()
