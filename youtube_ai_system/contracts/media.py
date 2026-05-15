"""Media artifact compatibility contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import ArtifactReference, ContractValidationResult, ValidationIssue


@dataclass(frozen=True)
class MediaArtifactContract:
    scene_id: int | None = None
    artifact: ArtifactReference = field(default_factory=lambda: ArtifactReference(path=""))
    provider: str = ""
    status: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MediaArtifactContract":
        artifact_payload = payload.get("artifact")
        artifact = (
            ArtifactReference.from_dict(artifact_payload)
            if isinstance(artifact_payload, dict)
            else ArtifactReference(
                path=str(
                    payload.get("path")
                    or payload.get("file_path")
                    or payload.get("video_path")
                    or payload.get("audio_path")
                    or payload.get("visual_path")
                    or ""
                ),
                kind=str(payload.get("kind") or payload.get("artifact_type") or "file"),
            )
        )
        return cls(
            scene_id=payload.get("scene_id") or payload.get("id"),
            artifact=artifact,
            provider=str(payload.get("provider") or ""),
            status=str(payload.get("status") or ""),
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data.update(
            {
                "scene_id": self.scene_id,
                "artifact": self.artifact.to_dict(),
                "provider": self.provider,
                "status": self.status,
            }
        )
        return data

    def validate(self) -> ContractValidationResult:
        result = ContractValidationResult()
        if not self.artifact.path:
            result = result.with_issue(ValidationIssue("missing_artifact_path", "Media artifact path is missing.", "artifact"))
        return result
