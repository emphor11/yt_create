from __future__ import annotations

import re


class SceneTextSignalResolver:
    """Derives lightweight visual/story signals from narration text."""

    def scene_text_signals(self, narration: str) -> dict[str, object]:
        return {
            "dominant_entity": self.dominant_entity_from_text(narration),
            "idea_type": self.idea_type_from_text(narration),
            "has_numbers": bool(re.search(r"₹|Rs\.?\s*|\d+|%", narration, re.IGNORECASE)),
            "has_comparison": bool(
                re.search(r"\bvs\b|\bversus\b|\bbut\b|\bhowever\b|\binstead\b|\bcompared to\b", narration, re.IGNORECASE)
            ),
            "has_causation": bool(
                re.search(
                    r"\bbecause\b|\bso\b|\btherefore\b|\bleads to\b|\bresults in\b|\bmeans\b|\bcreates\b|\bcosts\b|\bbecomes\b",
                    narration,
                    re.IGNORECASE,
                )
            ),
        }

    def dominant_entity_from_text(self, narration: str) -> str:
        lowered = narration.lower()
        ordered_entities = (
            "salary",
            "income",
            "debt",
            "loan",
            "credit",
            "interest",
            "emi",
            "savings",
            "investment",
            "sip",
            "fd",
            "inflation",
            "tax",
            "expense",
            "expenses",
            "rent",
        )
        for entity in ordered_entities:
            if re.search(rf"\b{re.escape(entity)}\b", lowered):
                return "expense" if entity == "expenses" else entity
        return "money"

    def idea_type_from_text(self, narration: str) -> str:
        lowered = narration.lower()
        if any(token in lowered for token in ("vs", "versus", "compare", "comparison", "difference", "instead", "while")):
            return "comparison"
        if any(token in lowered for token in ("grow", "grows", "growth", "increase", "rise", "compound", "multiply", "build wealth")):
            return "growth"
        if any(token in lowered for token in ("lose", "lost", "drain", "shrinks", "shrink", "fall", "drop", "gone", "vanish", "disappear", "erode", "leak")):
            return "decay"
        if any(token in lowered for token in ("risk", "danger", "trap", "mistake", "debt", "interest", "minimum due")):
            return "risk"
        if any(token in lowered for token in ("automate", "track", "budget", "allocate", "save first", "invest first")):
            return "process"
        return "emphasis"

    def weight_for_scene_kind(self, kind: str) -> dict[str, object]:
        if kind == "hook":
            return {"level": "high", "score": 0.9}
        if kind == "outro":
            return {"level": "medium", "score": 0.7}
        return {"level": "medium", "score": 0.55}
