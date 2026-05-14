"""Media and scene-review use-case wrappers."""

from __future__ import annotations

from youtube_ai_system.application.result import UseCaseResult
from youtube_ai_system.models.repository import ProjectRepository
from youtube_ai_system.services.media_service import MediaService
from youtube_ai_system.services.professional_scene_acceptance import ProfessionalSceneAcceptanceService
from youtube_ai_system.services.state_machine import StateMachine


class GenerateProjectMediaUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        media_service: MediaService | None = None,
        state_machine: StateMachine | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.media_service = media_service or MediaService()
        self.state_machine = state_machine or StateMachine()

    def execute(self, project_id: int) -> UseCaseResult:
        project = self.repo.get_project(project_id)
        if project["state"] not in {"script_approved", "media_generating"}:
            return UseCaseResult.fail(
                "Media generation is only available after script approval.",
                redirect_endpoint="projects.project_detail",
            )

        if project["state"] == "script_approved":
            self.state_machine.transition(project_id, "media_generating", "Media generation started.")
        self.media_service.generate_voice_and_visuals(project_id)
        self.state_machine.transition(project_id, "scene_review", "Media assets ready for scene review.")
        media_summary = self.media_service.project_media_summary(project_id)
        return UseCaseResult.ok(
            (
                f"Media generation finished. "
                f"Voice: {media_summary['voice_message']} "
                f"Visuals: {media_summary['visual_message']}"
            ),
            data={"media_summary": media_summary},
            redirect_endpoint="media.scene_review",
        )


class ApproveScenesUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        media_service: MediaService | None = None,
        acceptance_service: ProfessionalSceneAcceptanceService | None = None,
        state_machine: StateMachine | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.media_service = media_service or MediaService()
        self.acceptance_service = acceptance_service or ProfessionalSceneAcceptanceService()
        self.state_machine = state_machine or StateMachine()

    def execute(self, project_id: int) -> UseCaseResult:
        project = self.repo.get_project(project_id)
        if project["state"] != "scene_review":
            return UseCaseResult.fail(
                "Scene approval is only available during scene review.",
                redirect_endpoint="projects.project_detail",
            )

        ratio, scenes = self.media_service.compute_dynamic_visual_ratio(project_id)
        if not scenes:
            return UseCaseResult.fail("No scenes generated yet.", redirect_endpoint="media.scene_review")
        if ratio < 0.6:
            return UseCaseResult.fail(
                "At least 60% of scenes must use dynamic visuals before approval.",
                data={"dynamic_visual_ratio": ratio},
                redirect_endpoint="media.scene_review",
            )

        acceptance_report = self.acceptance_service.evaluate_project(project_id)
        if not acceptance_report.passed:
            issue_text = "; ".join(
                f"Scene {issue.scene_order}: {issue.message}" if issue.scene_order is not None else issue.message
                for issue in acceptance_report.blocking_issues[:3]
            )
            return UseCaseResult.fail(
                f"Professional scene QA failed. {issue_text}",
                data={"acceptance_report": acceptance_report.to_dict()},
                redirect_endpoint="media.scene_review",
            )

        self.state_machine.transition(project_id, "assets_ready", "Scene review approved.")
        return UseCaseResult.ok("Scenes approved.", redirect_endpoint="projects.project_detail")

