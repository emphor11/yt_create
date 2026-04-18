from __future__ import annotations

from datetime import datetime, timezone

from ..models.repository import ProjectRepository
from .run_log import RunLogger


class PublishService:
    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.logger = RunLogger()

    def stage_publish(self, project_id: int) -> int:
        record = self.repo.get_publish_record(project_id)
        if record:
            return record["id"]
        record_id = self.repo.create_publish_record(project_id, "private")
        self.logger.log("publish", "completed", "Created publish record.", project_id)
        return record_id

    def mark_uploaded(self, project_id: int, youtube_video_id: str) -> None:
        record = self.repo.get_publish_record(project_id)
        if not record:
            record_id = self.stage_publish(project_id)
            record = self.repo.get_publish_record(project_id)
        self.repo.update_publish_record(
            record["id"],
            youtube_video_id=youtube_video_id,
            uploaded_at=datetime.now(timezone.utc).isoformat(),
        )
        self.repo.update_project(project_id, youtube_video_id=youtube_video_id)
        self.logger.log("publish", "completed", "Stored upload metadata.", project_id)

    def schedule_publish(self, project_id: int, publish_at: str) -> None:
        record = self.repo.get_publish_record(project_id)
        if not record:
            self.stage_publish(project_id)
            record = self.repo.get_publish_record(project_id)
        self.repo.update_publish_record(record["id"], publish_at=publish_at)
        self.repo.update_project(project_id, scheduled_publish_at=publish_at)
        self.logger.log("publish", "completed", f"Scheduled video for {publish_at}.", project_id)
