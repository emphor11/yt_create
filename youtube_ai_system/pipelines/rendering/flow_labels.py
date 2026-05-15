from __future__ import annotations

import re

from .numbers import RenderNumberUtils


class RenderFlowLabelHelper:
    """Normalizes flow labels/captions and semantic colors."""

    def __init__(self, number_utils: RenderNumberUtils | None = None) -> None:
        self.number_utils = number_utils or RenderNumberUtils()

    def humanize_money_phrase(self, text: str) -> str:
        cleaned = " ".join(str(text or "").replace("₹0.", "₹0").split())
        cleaned = re.sub(r"₹0\s+Saved\s+Emotional Spend\b", "₹0 left to spend", cleaned, flags=re.I)
        cleaned = re.sub(r"₹0\s+Emotional Spend\b", "₹0 left to spend", cleaned, flags=re.I)
        cleaned = re.sub(r"₹0\s+left\s+to\b(?!\s+spend)", "₹0 left to spend", cleaned, flags=re.I)
        cleaned = re.sub(r"\bmonthly leak\b", "leaks every month", cleaned, flags=re.I)
        cleaned = re.sub(r"\bauto\s+(?:invested|investment)\b", "auto-invested", cleaned, flags=re.I)
        cleaned = re.sub(r"\bgoes to investment\b", "auto-invested", cleaned, flags=re.I)
        cleaned = re.sub(r"\b(?:Invested|Investment)\b", "auto-invested", cleaned, flags=re.I)
        cleaned = cleaned.replace("auto-auto-invested", "auto-invested")
        return cleaned

    def complete_caption(self, caption: str) -> str:
        cleaned = self.humanize_money_phrase(caption)
        cleaned = re.sub(r"₹0\s+left\s+to\b(?!\s+spend)", "₹0 left to spend", cleaned, flags=re.I)
        return cleaned

    def color_for_label(self, label: str) -> str:
        lowered = str(label or "").lower()
        if "₹0" in str(label or "") or any(word in lowered for word in ("lost", "loss", "leak", "leaks", "debt", "expense", "expenses")):
            return "red"
        if any(word in lowered for word in ("investment", "invested", "auto-invested", "saved", "growth")):
            return "teal"
        return ""

    def is_loss_result(self, text: str) -> bool:
        lowered = str(text or "").lower()
        return "₹0" in str(text or "") or any(word in lowered for word in ("loss", "lost", "leak", "leaks", "debt", "expense"))

    def looks_like_outro_loss(self, text: str) -> bool:
        lowered = str(text or "").lower()
        return (
            any(word in lowered for word in ("month", "monthly", "leaks every month", "/month"))
            and any(word in lowered for word in ("gone", "lost", "loss"))
            and len(self.number_utils.money_tokens(text)) >= 2
        )
