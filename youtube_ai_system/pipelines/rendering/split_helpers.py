from __future__ import annotations

import re

from .text_utils import RenderTextUtils


class RenderSplitHelpers:
    """SplitComparison text and label helpers."""

    def __init__(self, text_utils: RenderTextUtils | None = None) -> None:
        self.text_utils = text_utils or RenderTextUtils()

    def concrete_split_from_logic(self, visual_logic: str, caption: str) -> tuple[str, str]:
        parts = re.split(r"\s+vs\.?\s+|\s+versus\s+|\s+\|\s+", visual_logic, maxsplit=1, flags=re.I)
        if len(parts) == 2:
            return self.text_utils.short_overlay(parts[0], 6), self.text_utils.short_overlay(parts[1], 6)
        numbers = re.findall(r"(?:₹\s?[\d,.]+(?:\s?(?:lakhs?|crores?|k|m)\b)?|\d+(?:\.\d+)?%)", visual_logic, re.I)
        if len(numbers) >= 2:
            return numbers[0], numbers[1]
        return self.text_utils.short_overlay(visual_logic, 6) or "Claim", self.text_utils.short_overlay(caption, 6) or "Reality"

    def humanize_split_label(self, label: str, content: str) -> str:
        if label.strip().upper() in {"WHAT YOU THINK", "REALITY", "CLAIM"}:
            return self.text_utils.extract_split_label(content)
        return self.text_utils.extract_split_label(content) or label
