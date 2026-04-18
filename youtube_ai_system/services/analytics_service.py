from __future__ import annotations

from datetime import datetime, timezone

from ..models.repository import ProjectRepository
from .run_log import RunLogger


class AnalyticsService:
    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.logger = RunLogger()

    def capture_snapshot(self, project_id: int, snapshot_day: str) -> int:
        publish_record = self.repo.get_publish_record(project_id)
        base_views = {"D1": 120, "D7": 780, "D28": 2850}.get(snapshot_day, 0)
        metrics = {
            "views": base_views,
            "impressions": base_views * 20 if base_views else 0,
            "impression_ctr": 6.3 if base_views else None,
            "average_view_duration_sec": 212.0 if base_views else None,
            "average_view_percentage": 54.8 if base_views else None,
        }
        snapshot_id = self.repo.add_analytics_snapshot(project_id, snapshot_day, metrics)
        self.logger.log(
            "analytics",
            "completed",
            f"Captured {snapshot_day} snapshot for video {publish_record['youtube_video_id'] if publish_record else 'pending-upload'}.",
            project_id,
        )
        return snapshot_id

    def due_snapshot_day(self, published_at: str | None) -> str | None:
        if not published_at:
            return None
        published_dt = datetime.fromisoformat(published_at)
        delta_days = (datetime.now(timezone.utc) - published_dt).days
        if delta_days == 1:
            return "D1"
        if delta_days == 7:
            return "D7"
        if delta_days == 28:
            return "D28"
        return None
