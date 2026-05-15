"""Assembly use-case wrappers."""

from __future__ import annotations

from youtube_ai_system.application.result import UseCaseResult
from youtube_ai_system.infrastructure.persistence import ProjectRepository
from youtube_ai_system.services.assembly_service import AssemblyService
from youtube_ai_system.services.professional_scene_acceptance import ProfessionalSceneAcceptanceService
from youtube_ai_system.services.state_machine import InvalidTransitionError, StateMachine


class AssembleDraftMasterUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        assembly_service: AssemblyService | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.assembly_service = assembly_service or AssemblyService()

    def execute(self, project_id: int) -> UseCaseResult:
        project = self.repo.get_project(project_id)
        if project["state"] not in {"scene_review", "assets_ready", "assembling", "ready_to_publish", "scheduled"}:
            return UseCaseResult.fail(
                "Draft master assembly is available after scene media is generated.",
                redirect_endpoint="projects.project_detail",
            )
        final_video_path = self.assembly_service.assemble_project(project_id)
        return UseCaseResult.ok(
            "Draft master assembled. Watch the full video before deciding what to fix.",
            data={"final_video_path": final_video_path},
            redirect_endpoint="publish.final_review",
        )


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

        try:
            self.state_machine.transition(project_id, "assembling", "Assembly started.")
        except InvalidTransitionError as exc:
            return UseCaseResult.fail(
                str(exc),
                data={"flash_category": "danger"},
                redirect_endpoint="publish.final_review",
            )
        final_video_path = self.assembly_service.assemble_project(project_id)
        try:
            self.state_machine.transition(project_id, "ready_to_publish", "Assembly complete.")
        except InvalidTransitionError as exc:
            return UseCaseResult.fail(
                str(exc),
                data={"flash_category": "danger", "final_video_path": final_video_path},
                redirect_endpoint="publish.final_review",
            )
        return UseCaseResult.ok(
            "Assembly complete. Review before publishing.",
            data={"final_video_path": final_video_path},
            redirect_endpoint="publish.final_review",
        )
