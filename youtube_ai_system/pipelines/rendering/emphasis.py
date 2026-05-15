from __future__ import annotations

from typing import Any

from .text_utils import RenderTextUtils
from .visual_gate import RenderVisualGate


class RenderEmphasisBuilder:
    """Fallback emphasis text and props for structured render beats."""

    def __init__(
        self,
        *,
        text_utils: RenderTextUtils,
        visual_gate: RenderVisualGate,
    ) -> None:
        self.text_utils = text_utils
        self.visual_gate = visual_gate

    def concrete_fallback_logic(self, beat: dict[str, Any]) -> str:
        props = beat.get("props") if isinstance(beat.get("props"), dict) else {}
        headline = self.text_utils.short_overlay(str(props.get("headline") or props.get("content") or beat.get("content") or ""), 5)
        subtext = self.text_utils.short_overlay(str(props.get("subtext") or props.get("caption") or beat.get("caption") or ""), 8)
        combined = f"{headline} {subtext}".strip()
        if self.visual_gate.passes_text_gate(combined):
            return combined
        return "76% can't save ₹5,000"

    def safe_emphasis_props(self, visual_logic: str, caption: str) -> dict[str, Any]:
        headline = self.text_utils.dominant_phrase(visual_logic)
        words = headline.split()
        if len(words) > 6:
            headline = " ".join(words[:6])
        return {
            "headline": headline,
            "subtext": caption or self.text_utils.short_overlay(visual_logic.replace(headline, ""), 6),
            "color": "red" if self.text_utils.sentiment(visual_logic) == "negative" else "orange",
        }
