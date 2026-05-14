"""Story planning compatibility contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StoryPlanContract:
    thesis: str = ""
    format_name: str = ""
    scenes: tuple[dict[str, Any], ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StoryPlanContract":
        return cls(
            thesis=str(payload.get("thesis") or payload.get("core_thesis") or ""),
            format_name=str(payload.get("format") or payload.get("format_name") or ""),
            scenes=tuple(scene for scene in payload.get("scenes", []) if isinstance(scene, dict)),
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data.update({"thesis": self.thesis, "format_name": self.format_name, "scenes": list(self.scenes)})
        return data

