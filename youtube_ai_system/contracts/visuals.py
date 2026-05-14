"""Visual planning contract wrappers for renderer-facing scene data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class VisualSceneContract:
    component: str = ""
    narration: str = ""
    visual_intent: str = ""
    visual_beats: tuple[dict[str, Any], ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "VisualSceneContract":
        return cls(
            component=str(payload.get("component") or payload.get("visual_component") or ""),
            narration=str(payload.get("narration") or payload.get("text") or payload.get("source_text") or ""),
            visual_intent=str(payload.get("visual_intent") or payload.get("description") or ""),
            visual_beats=tuple(beat for beat in payload.get("visual_beats", []) if isinstance(beat, dict)),
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data.update(
            {
                "component": self.component,
                "narration": self.narration,
                "visual_intent": self.visual_intent,
                "visual_beats": list(self.visual_beats),
            }
        )
        return data

