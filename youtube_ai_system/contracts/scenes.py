"""Scene contract wrappers compatible with current scene rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import ArtifactReference, ContractValidationResult, ValidationIssue


@dataclass(frozen=True)
class SceneContract:
    id: int | None = None
    project_id: int | None = None
    scene_number: int | None = None
    title: str = ""
    narration: str = ""
    status: str = ""
    artifacts: tuple[ArtifactReference, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SceneContract":
        artifacts = []
        for key in ("audio_path", "visual_path", "video_path", "rendered_path"):
            if payload.get(key):
                artifacts.append(ArtifactReference(path=str(payload[key]), kind=key.replace("_path", "")))
        return cls(
            id=payload.get("id"),
            project_id=payload.get("project_id"),
            scene_number=payload.get("scene_number"),
            title=str(payload.get("title") or ""),
            narration=str(payload.get("narration") or payload.get("source_text") or payload.get("text") or ""),
            status=str(payload.get("status") or ""),
            artifacts=tuple(artifacts),
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data.update(
            {
                "id": self.id,
                "project_id": self.project_id,
                "scene_number": self.scene_number,
                "title": self.title,
                "narration": self.narration,
                "status": self.status,
            }
        )
        return data

    def validate(self) -> ContractValidationResult:
        result = ContractValidationResult()
        if self.scene_number is None:
            result = result.with_issue(
                ValidationIssue("missing_scene_number", "Scene number is missing.", "scene_number")
            )
        return result

