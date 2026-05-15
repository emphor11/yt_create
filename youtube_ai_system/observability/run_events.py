"""Structured event helpers layered over existing run logs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PipelineEvent:
    stage_name: str
    status: str
    message: str
    project_id: int | None = None
    artifact_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_log_message(self) -> str:
        if not self.artifact_path:
            return self.message
        return f"{self.message} Artifact: {self.artifact_path}"


@dataclass(frozen=True)
class ArtifactEvent:
    project_id: int | None
    stage_name: str
    artifact_path: str
    artifact_kind: str = "file"
    status: str = "created"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_pipeline_event(self) -> PipelineEvent:
        return PipelineEvent(
            stage_name=self.stage_name,
            status=self.status,
            message=f"{self.artifact_kind} artifact {self.status}.",
            project_id=self.project_id,
            artifact_path=self.artifact_path,
            metadata=dict(self.metadata),
        )


@dataclass(frozen=True)
class StageTiming:
    project_id: int | None
    stage_name: str
    duration_ms: int
    status: str = "completed"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_pipeline_event(self) -> PipelineEvent:
        return PipelineEvent(
            stage_name=self.stage_name,
            status=self.status,
            message=f"{self.stage_name} {self.status} in {self.duration_ms}ms.",
            project_id=self.project_id,
            metadata={"duration_ms": self.duration_ms, **self.metadata},
        )


@dataclass(frozen=True)
class FailureEvent:
    project_id: int | None
    stage_name: str
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_pipeline_event(self) -> PipelineEvent:
        return PipelineEvent(
            stage_name=self.stage_name,
            status="failed",
            message=self.reason,
            project_id=self.project_id,
            metadata=dict(self.metadata),
        )


def emit_run_event(logger: Any, event: PipelineEvent) -> None:
    """Emit an event through the current run logger API.

    The existing run log table is intentionally preserved in this phase.
    """

    logger.log(event.stage_name, event.status, event.to_log_message(), event.project_id)


def emit_artifact_event(logger: Any, event: ArtifactEvent) -> None:
    emit_run_event(logger, event.to_pipeline_event())


def emit_timing_event(logger: Any, event: StageTiming) -> None:
    emit_run_event(logger, event.to_pipeline_event())


def emit_failure_event(logger: Any, event: FailureEvent) -> None:
    emit_run_event(logger, event.to_pipeline_event())
