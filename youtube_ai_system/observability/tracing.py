"""Small tracing helpers for pipeline stages."""

from __future__ import annotations

import time
from dataclasses import dataclass

from .run_events import StageTiming


@dataclass
class StageTimer:
    stage_name: str
    project_id: int | None = None
    started_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = time.monotonic()

    def finish(self, status: str = "completed") -> StageTiming:
        duration_ms = int(round((time.monotonic() - self.started_at) * 1000))
        return StageTiming(
            project_id=self.project_id,
            stage_name=self.stage_name,
            duration_ms=max(0, duration_ms),
            status=status,
        )

