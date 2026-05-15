"""Media and scene-review use-case wrappers."""

from __future__ import annotations

from youtube_ai_system.application.result import UseCaseResult
from youtube_ai_system.infrastructure.persistence import ProjectRepository
from youtube_ai_system.services.media_service import MediaService
from youtube_ai_system.services.professional_scene_acceptance import ProfessionalSceneAcceptanceService
from youtube_ai_system.services.state_machine import InvalidTransitionError, StateMachine


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

        try:
            if project["state"] == "script_approved":
                self.state_machine.transition(project_id, "media_generating", "Media generation started.")
        except InvalidTransitionError as exc:
            return UseCaseResult.fail(
                str(exc),
                data={"flash_category": "danger"},
                redirect_endpoint="media.scene_review",
            )
        self.media_service.generate_voice_and_visuals(project_id)
        try:
            self.state_machine.transition(project_id, "scene_review", "Media assets ready for scene review.")
        except InvalidTransitionError as exc:
            return UseCaseResult.fail(
                str(exc),
                data={"flash_category": "danger"},
                redirect_endpoint="media.scene_review",
            )
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


class RunVoiceCheckUseCase:
    def __init__(self, media_service: MediaService | None = None) -> None:
        self.media_service = media_service or MediaService()

    def execute(self) -> UseCaseResult:
        result = self.media_service.run_voice_check()
        return UseCaseResult.ok(data=result)


class BuildSceneReviewUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        media_service: MediaService | None = None,
        acceptance_service: ProfessionalSceneAcceptanceService | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.media_service = media_service or MediaService()
        self.acceptance_service = acceptance_service or ProfessionalSceneAcceptanceService(self.repo)

    def execute(self, project_id: int) -> UseCaseResult:
        project = self.repo.get_project(project_id)
        if project["state"] not in {"media_generating", "scene_review", "assets_ready"}:
            return UseCaseResult.fail(
                "Scene review is only available after media generation starts.",
                redirect_endpoint="projects.project_detail",
            )
        ratio, _ = self.media_service.compute_dynamic_visual_ratio(project_id)
        acceptance_report = self.acceptance_service.evaluate_project(project_id)
        return UseCaseResult.ok(
            data={
                "project": project,
                "scenes": self.repo.list_scenes(project_id),
                "ratio": ratio,
                "threshold": 0.6,
                "media_summary": self.media_service.project_media_summary(project_id),
                "acceptance_report": acceptance_report.to_dict(),
            }
        )


class RegenerateSceneUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        media_service: MediaService | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.media_service = media_service or MediaService()

    def execute(self, project_id: int, scene_id: int) -> UseCaseResult:
        scene = self.repo.get_scene(scene_id)
        if scene and scene["video_project_id"] == project_id:
            try:
                self.media_service.generate_scene_media(project_id, scene_id)
            except Exception as exc:
                return UseCaseResult.fail(
                    f"Scene {scene['scene_order']} regeneration failed: {exc}",
                    data={"scene": scene},
                    redirect_endpoint="media.scene_review",
                )
            else:
                return UseCaseResult.ok(
                    f"Regenerated scene {scene['scene_order']}.",
                    data={"scene": scene},
                    redirect_endpoint="media.scene_review",
                )
        return UseCaseResult.ok("", redirect_endpoint="media.scene_review")


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

        try:
            self.state_machine.transition(project_id, "assets_ready", "Scene review approved.")
        except InvalidTransitionError as exc:
            return UseCaseResult.fail(
                str(exc),
                data={"flash_category": "danger"},
                redirect_endpoint="projects.project_detail",
            )
        return UseCaseResult.ok("Scenes approved.", redirect_endpoint="projects.project_detail")
