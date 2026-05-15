"""Scene contract wrappers compatible with current scene rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .adapters import load_json_array, load_json_object
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
        for key in ("audio_path", "visual_path", "video_path", "rendered_path", "thumbnail_path"):
            if payload.get(key):
                artifacts.append(ArtifactReference(path=str(payload[key]), kind=key.replace("_path", "")))
        return cls(
            id=payload.get("id"),
            project_id=payload.get("project_id") or payload.get("video_project_id"),
            scene_number=payload.get("scene_number") if payload.get("scene_number") is not None else payload.get("scene_order"),
            title=str(payload.get("title") or payload.get("scene_title") or ""),
            narration=str(
                payload.get("narration")
                or payload.get("narration_text")
                or payload.get("source_text")
                or payload.get("text")
                or ""
            ),
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
                "video_project_id": self.project_id,
                "scene_number": self.scene_number,
                "scene_order": self.scene_number,
                "title": self.title,
                "narration": self.narration,
                "narration_text": self.narration,
                "status": self.status,
            }
        )
        return data

    @property
    def visual_plan(self) -> list[Any]:
        return load_json_array(self.raw.get("visual_plan_json"))

    @property
    def visual_scene(self) -> dict[str, Any]:
        return load_json_object(self.raw.get("visual_scene_json"))

    def validate(self) -> ContractValidationResult:
        result = ContractValidationResult()
        if self.scene_number is None:
            result = result.with_issue(
                ValidationIssue("missing_scene_number", "Scene number is missing.", "scene_number")
            )
        return result
