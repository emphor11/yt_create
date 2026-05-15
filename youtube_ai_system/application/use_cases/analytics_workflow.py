"""Analytics page and capture use-case wrappers."""

from __future__ import annotations

from youtube_ai_system.application.result import UseCaseResult
from youtube_ai_system.infrastructure.persistence import ProjectRepository
from youtube_ai_system.services.analytics_service import AnalyticsService


class BuildAnalyticsTableUseCase:
    def __init__(self, repo: ProjectRepository | None = None) -> None:
        self.repo = repo or ProjectRepository()

    def execute(self) -> UseCaseResult:
        return UseCaseResult.ok(data={"rows": self.repo.list_analytics_rows()})


class CaptureAnalyticsSnapshotUseCase:
    def __init__(self, analytics_service: AnalyticsService | None = None) -> None:
        self.analytics_service = analytics_service or AnalyticsService()

    def execute(self, project_id: int, snapshot_day: str) -> UseCaseResult:
        resolved_day = snapshot_day.strip() or "D1"
        snapshot_id = self.analytics_service.capture_snapshot(project_id, resolved_day)
        return UseCaseResult.ok(
            f"Captured {resolved_day} analytics snapshot.",
            data={"snapshot_id": snapshot_id, "snapshot_day": resolved_day},
            redirect_endpoint="analytics.analytics_table",
        )
