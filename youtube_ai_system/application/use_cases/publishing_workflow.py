"""Assembly and publishing use-case wrappers."""

from __future__ import annotations

from youtube_ai_system.application.result import UseCaseResult
from youtube_ai_system.models.repository import ProjectRepository
from youtube_ai_system.services.assembly_service import AssemblyService
from youtube_ai_system.services.professional_scene_acceptance import ProfessionalSceneAcceptanceService
from youtube_ai_system.services.state_machine import StateMachine
from youtube_ai_system.services.youtube_upload_service import YouTubeUploadService


class AssembleProjectUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        assembly_service: AssemblyService | None = None,
        acceptance_service: ProfessionalSceneAcceptanceService | None = None,
        state_machine: StateMachine | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.assembly_service = assembly_service or AssemblyService()
        self.acceptance_service = acceptance_service or ProfessionalSceneAcceptanceService()
        self.state_machine = state_machine or StateMachine()

    def execute(self, project_id: int) -> UseCaseResult:
        project = self.repo.get_project(project_id)
        if project["state"] != "assets_ready":
            return UseCaseResult.fail(
                "Assembly is only available after scenes are approved.",
                redirect_endpoint="projects.project_detail",
            )

        acceptance_report = self.acceptance_service.evaluate_project(project_id)
        if not acceptance_report.passed:
            return UseCaseResult.fail(
                "Assembly blocked because professional scene QA no longer passes. Review and regenerate weak scenes.",
                data={"acceptance_report": acceptance_report.to_dict()},
                redirect_endpoint="media.scene_review",
            )

        self.state_machine.transition(project_id, "assembling", "Assembly started.")
        final_video_path = self.assembly_service.assemble_project(project_id)
        self.state_machine.transition(project_id, "ready_to_publish", "Assembly complete.")
        return UseCaseResult.ok(
            "Assembly complete. Review before publishing.",
            data={"final_video_path": final_video_path},
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
                data={"youtube_video_id": project["youtube_video_id"], "already_uploaded": True},
                redirect_endpoint="publish.final_review",
            )

        video_id = self.upload_service.upload_private(project_id)
        warning = self.upload_service.last_thumbnail_warning
        message = f"Uploaded to YouTube as a private video: {video_id}"
        if warning:
            message = f"{message}. {warning}"
        return UseCaseResult.ok(
            message,
            data={"youtube_video_id": video_id, "thumbnail_warning": warning},
            redirect_endpoint="publish.final_review",
        )

