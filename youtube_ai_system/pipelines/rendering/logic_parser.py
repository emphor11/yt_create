from __future__ import annotations

import re
from typing import Callable, Any


class RenderLogicParser:
    """Parse concrete visual-logic strings into typed render logic objects."""

    def __init__(
        self,
        *,
        is_abstract_visual_logic: Callable[[str], bool],
        numbers_respect_context: Callable[[str, str], bool],
        has_number: Callable[[str], bool],
    ) -> None:
        self.is_abstract_visual_logic = is_abstract_visual_logic
        self.numbers_respect_context = numbers_respect_context
        self.has_number = has_number

    def string_visual_logic_to_object(self, text: str, context: str = "") -> dict[str, Any] | None:
        cleaned = " ".join(str(text or "").split())
        if not cleaned or self.is_abstract_visual_logic(cleaned):
            return None
        if context and not self.numbers_respect_context(cleaned, context):
            return None

        comparison = re.split(r"\s+vs\.?\s+|\s+versus\s+", cleaned, maxsplit=1, flags=re.I)
        if len(comparison) == 2:
            left = comparison[0].strip()
            right = comparison[1].strip()
            if self.has_number(left) and self.has_number(right):
                return {"type": "comparison", "left": left, "right": right}
            return None

        parts = [part.strip() for part in re.split(r"\s*(?:->|→)\s*", cleaned) if part.strip()]
        if len(parts) >= 3:
            lowered = cleaned.lower()
            if any(word in lowered for word in ("inflation", "tax", "fee", "fees", "real value", "loss", "lose")):
                return {"type": "decay", "input": parts[0], "factor": parts[1], "output": parts[2]}
            if any(word in lowered for word in ("growth", "return", "sip", "compound", "wealth")):
                return {"type": "growth", "input": parts[0], "rate": parts[1], "output": parts[2]}
            return {"type": "flow", "source": parts[0], "process": parts[1], "result": parts[2]}
        return None
