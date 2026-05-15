"""Publishing command use-case wrappers."""

from __future__ import annotations

from youtube_ai_system.application.result import UseCaseResult
from youtube_ai_system.infrastructure.persistence import ProjectRepository
from youtube_ai_system.services.publish_service import PublishService
from youtube_ai_system.services.state_machine import InvalidTransitionError, StateMachine
from youtube_ai_system.services.youtube_upload_service import YouTubeUploadService


class StagePublishUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        publish_service: PublishService | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.publish_service = publish_service or PublishService()

    def execute(self, project_id: int) -> UseCaseResult:
        project = self.repo.get_project(project_id)
        if project["state"] not in {"ready_to_publish", "scheduled"}:
            return UseCaseResult.fail(
                "Publishing can only be prepared from the final review stage.",
                redirect_endpoint="projects.project_detail",
            )
        record_id = self.publish_service.stage_publish(project_id)
        return UseCaseResult.ok(
            "Publish record prepared. Upload integration can fill in the YouTube ID.",
            data={"publish_record_id": record_id},
            redirect_endpoint="publish.final_review",
        )


class MockUploadUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        publish_service: PublishService | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.publish_service = publish_service or PublishService()

    def execute(self, project_id: int, youtube_video_id: str) -> UseCaseResult:
        project = self.repo.get_project(project_id)
        if project["state"] not in {"ready_to_publish", "scheduled"}:
            return UseCaseResult.fail(
                "Upload metadata can only be stored from the final review stage.",
                redirect_endpoint="projects.project_detail",
            )
        resolved_video_id = youtube_video_id.strip() or f"demo-{project_id}"
        self.publish_service.mark_uploaded(project_id, resolved_video_id)
        return UseCaseResult.ok(
            "Stored a mock upload id. Set a schedule next.",
            data={"youtube_video_id": resolved_video_id},
            redirect_endpoint="publish.final_review",
        )


class UploadPrivateVideoUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        upload_service: YouTubeUploadService | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.upload_service = upload_service or YouTubeUploadService()

    def execute(self, project_id: int, *, force_upload: bool = False) -> UseCaseResult:
        project = self.repo.get_project(project_id)
        if project["state"] not in {"ready_to_publish", "scheduled"}:
            return UseCaseResult.fail(
                "Mark the master ready before attempting a YouTube upload.",
                redirect_endpoint="publish.final_review",
            )

        if project.get("youtube_video_id") and not force_upload:
            return UseCaseResult.ok(
                f"This project is already uploaded as YouTube video {project['youtube_video_id']}.",
                data={"youtube_video_id": project["youtube_video_id"], "already_uploaded": True, "flash_category": "info"},
                redirect_endpoint="publish.final_review",
            )

        video_id = self.upload_service.upload_private(project_id)
        warning = self.upload_service.last_thumbnail_warning
        message = f"Uploaded to YouTube as a private video: {video_id}"
        if warning:
            message = f"{message}. {warning}"
        return UseCaseResult.ok(
            message,
            data={
                "youtube_video_id": video_id,
                "thumbnail_warning": warning,
                "flash_category": "warning" if warning else "success",
            },
            redirect_endpoint="publish.final_review",
        )


class SchedulePublishUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        publish_service: PublishService | None = None,
        state_machine: StateMachine | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.publish_service = publish_service or PublishService()
        self.state_machine = state_machine or StateMachine()

    def execute(self, project_id: int, publish_at: str) -> UseCaseResult:
        project = self.repo.get_project(project_id)
        if project["state"] not in {"ready_to_publish", "scheduled"}:
            return UseCaseResult.fail(
                "Scheduling is only available from the final review stage.",
                redirect_endpoint="projects.project_detail",
            )
        self.publish_service.schedule_publish(project_id, publish_at.strip())
        project = self.repo.get_project(project_id)
        if project["state"] == "ready_to_publish":
            try:
                self.state_machine.transition(project_id, "scheduled", "Scheduled publish set.")
            except InvalidTransitionError as exc:
                return UseCaseResult.fail(
                    str(exc),
                    data={"flash_category": "danger"},
                    redirect_endpoint="publish.final_review",
                )
        return UseCaseResult.ok("Scheduled publish saved.", redirect_endpoint="publish.final_review")
