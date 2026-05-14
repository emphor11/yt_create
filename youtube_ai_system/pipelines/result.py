"""Shared pipeline stage result primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from youtube_ai_system.contracts.base import ArtifactReference, ValidationIssue


@dataclass(frozen=True)
class PipelineStageResult:
    stage_name: str
    success: bool
    message: str = ""
    artifacts: tuple[ArtifactReference, ...] = ()
    issues: tuple[ValidationIssue, ...] = ()
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def completed(
        cls,
        stage_name: str,
        message: str = "",
        *,
        artifacts: tuple[ArtifactReference, ...] = (),
        data: dict[str, Any] | None = None,
    ) -> "PipelineStageResult":
        return cls(
            stage_name=stage_name,
            success=True,
            message=message,
            artifacts=artifacts,
            data=data or {},
        )

    @classmethod
    def failed(
        cls,
        stage_name: str,
        message: str,
        *,
        issues: tuple[ValidationIssue, ...] = (),
        data: dict[str, Any] | None = None,
    ) -> "PipelineStageResult":
        return cls(
            stage_name=stage_name,
            success=False,
            message=message,
            issues=issues,
            data=data or {},
        )

