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


def emit_run_event(logger: Any, event: PipelineEvent) -> None:
    """Emit an event through the current run logger API.

    The existing run log table is intentionally preserved in this phase.
    """

    logger.log(event.stage_name, event.status, event.message, event.project_id)

