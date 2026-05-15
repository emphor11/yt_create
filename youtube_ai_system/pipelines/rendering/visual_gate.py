from __future__ import annotations

import re
from collections.abc import Iterable

from .numbers import RenderNumberUtils


class RenderVisualGate:
    """Deterministic concreteness and impact checks for renderable visual text."""

    def __init__(
        self,
        *,
        abstract_visual_words: Iterable[str],
        generic_visual_words: Iterable[str],
        number_utils: RenderNumberUtils | None = None,
    ) -> None:
        self.abstract_visual_words = set(abstract_visual_words)
        self.generic_visual_words = set(generic_visual_words)
        self.number_utils = number_utils or RenderNumberUtils()

    def is_concrete_visual_logic(self, text: str) -> bool:
        if not text or len(text.strip()) < 6:
            return False
        if self.is_abstract_visual_logic(text):
            return False
        if self.contains_generic_visual_words(text):
            return False
        return self.has_number(text)

    def is_abstract_visual_logic(self, text: str) -> bool:
        lowered = " ".join(str(text or "").lower().replace("_", " ").split())
        if not lowered:
            return True
        if lowered in self.abstract_visual_words:
            return True
        if any(re.search(rf"\b{re.escape(bad)}\b", lowered) for bad in self.abstract_visual_words):
            return True
        if self.contains_generic_visual_words(lowered):
            return True
        return any(bad in lowered for bad in {"static image", "split screen", "display statistic", "show comparison", "display data"})

    def contains_generic_visual_words(self, text: str) -> bool:
        lowered = " ".join(str(text or "").lower().replace("_", " ").split())
        return any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in self.generic_visual_words)

    def has_number(self, text: str) -> bool:
        return bool(re.search(r"(?:₹\s?[\d,.]+(?:\s?(?:lakhs?|crores?|k|m)\b)?|\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?\b)", text, re.I))

    def has_visual_structure(self, text: str) -> bool:
        lowered = text.lower()
        if re.search(r"\s(?:->|→)\s", text):
            return len([part for part in re.split(r"\s*(?:->|→)\s*", text) if part.strip()]) >= 3
        if re.search(r"\b(vs|versus|compared|than)\b", lowered):
            return len(re.split(r"\b(?:vs|versus|compared|than)\b", lowered, maxsplit=1)) == 2
        if any(word in lowered for word in ("left", "loss", "interest/year", "real value", "after inflation", "yearly loss")):
            return True
        return False

    def has_impact(self, text: str) -> bool:
        lowered = text.lower()
        if any(word in lowered for word in ("loss", "lose", "lost", "left", "debt", "interest", "broke", "can't", "cannot", "real value", "inflation", "less than", "more than")):
            return True
        if re.search(r"\b(vs|versus|compared|than)\b", lowered):
            return True
        if re.search(r"(?:->|→)", text):
            numbers = self.number_utils.numeric_values(text)
            if len(numbers) >= 2:
                high = max(numbers)
                low = min(numbers)
                return high > 0 and ((high - low) / high) >= 0.05
        return bool(re.search(r"\b(?:[7-9]\d|100)%", text))

    def passes_text_gate(self, text: str) -> bool:
        return self.is_concrete_visual_logic(text) and self.has_visual_structure(text) and self.has_impact(text)
