"""Publishing contract wrappers for upload metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import ArtifactReference, ContractValidationResult, ValidationIssue


@dataclass(frozen=True)
class UploadPackageContract:
    title: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()
    video: ArtifactReference = field(default_factory=lambda: ArtifactReference(path="", kind="video"))
    thumbnail: ArtifactReference | None = None
    privacy_status: str = "private"
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UploadPackageContract":
        tags = payload.get("tags") or ()
        thumbnail_path = payload.get("thumbnail_path") or payload.get("thumbnail")
        return cls(
            title=str(payload.get("title") or ""),
            description=str(payload.get("description") or ""),
            tags=tuple(str(tag) for tag in tags),
            video=ArtifactReference(path=str(payload.get("video_path") or ""), kind="video"),
            thumbnail=ArtifactReference(path=str(thumbnail_path), kind="thumbnail") if thumbnail_path else None,
            privacy_status=str(payload.get("privacy_status") or "private"),
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data.update(
            {
                "title": self.title,
                "description": self.description,
                "tags": list(self.tags),
                "video_path": self.video.path,
                "thumbnail_path": self.thumbnail.path if self.thumbnail else "",
                "privacy_status": self.privacy_status,
            }
        )
        return data

    def validate(self) -> ContractValidationResult:
        result = ContractValidationResult()
        if not self.title:
            result = result.with_issue(ValidationIssue("missing_title", "Upload title is missing.", "title"))
        if not self.video.path:
            result = result.with_issue(ValidationIssue("missing_video", "Upload video path is missing.", "video"))
        return result

