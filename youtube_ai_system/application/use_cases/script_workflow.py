"""Script workflow use-case wrappers.

These wrappers intentionally preserve the current route/service behavior.
Routes can migrate to them later once the characterization tests are broad
enough.
"""

from __future__ import annotations

from urllib import error

from youtube_ai_system.application.result import UseCaseResult
from youtube_ai_system.infrastructure.persistence import ProjectRepository, utcnow
from youtube_ai_system.services.script_service import ScriptService
from youtube_ai_system.services.state_machine import StateMachine


class GenerateScriptUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        script_service: ScriptService | None = None,
        state_machine: StateMachine | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.script_service = script_service or ScriptService()
        self.state_machine = state_machine or StateMachine()

    def execute(self, project_id: int) -> UseCaseResult:
        project = self.repo.get_project(project_id)

        if not project.get("topic") or not project.get("angle"):
            return UseCaseResult.fail(
                "Set topic and angle first.",
                redirect_endpoint="projects.topic_selection",
            )

        if project["state"] not in {"drafted", "script_review"}:
            return UseCaseResult.fail(
                "Script generation is only available before the script is approved.",
                redirect_endpoint="projects.project_detail",
            )

        if project["state"] == "drafted":
            self.state_machine.transition(project_id, "script_review", "Script review started.")

        try:
            script_version_id = self.script_service.generate_script(
                project_id,
                project["topic"],
                project["angle"],
                project.get("target_duration_minutes"),
                project.get("channel_niche"),
                project.get("script_tone"),
            )
        except ValueError as exc:
            return UseCaseResult.fail(
                self._user_facing_generation_error(str(exc)),
                redirect_endpoint="projects.project_detail",
            )
        except error.URLError as exc:
            return UseCaseResult.fail(
                f"AI script generation could not reach the provider: {exc.reason}",
                redirect_endpoint="projects.project_detail",
            )
        return UseCaseResult.ok(
            f"Script draft generated for topic '{project['topic']}' and angle '{project['angle']}'.",
            data={"script_version_id": script_version_id},
            redirect_endpoint="projects.edit_script",
        )

    def _user_facing_generation_error(self, message: str) -> str:
        normalized = message.lower()
        if (
            "api error 429" in normalized
            or "rate_limit_exceeded" in normalized
            or "rate limit" in normalized
            or "too many requests" in normalized
        ):
            return (
                "AI script generation is temporarily rate-limited by the selected provider. "
                "If Gemini fallback is configured, restart the dev server so the new provider settings load."
            )
        if "ScriptBrief topic alignment failed" in message:
            return f"Script strategy brief failed topic alignment: {message.split(':', 1)[-1].strip()}"
        return f"AI script generation failed: {message}"


class ApproveScriptUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        script_service: ScriptService | None = None,
        state_machine: StateMachine | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.script_service = script_service or ScriptService()
        self.state_machine = state_machine or StateMachine()

    def execute(self, project_id: int) -> UseCaseResult:
        project = self.repo.get_project(project_id)
        if project["state"] != "script_review":
            return UseCaseResult.fail(
                "This project is no longer in script review, so approval is not available here.",
                redirect_endpoint="projects.project_detail",
            )

        script_version = self.repo.get_latest_script_version(project_id)
        if not script_version:
            return UseCaseResult.fail("No script draft found.", redirect_endpoint="projects.project_detail")

        ready, errors, payload = self.script_service.approval_ready(script_version)
        if not ready:
            return UseCaseResult.fail(
                "Script is not ready for approval.",
                errors=tuple(errors),
                redirect_endpoint="projects.edit_script",
            )

        self.repo.update_script_version(script_version["id"], approved_at=utcnow())
        self.repo.replace_scenes(
            project_id,
            script_version["id"],
            self.script_service.scene_rows_from_payload(payload),
        )
        self.state_machine.transition(project_id, "script_approved", "Script approved.")
        return UseCaseResult.ok(
            "Script approved and scenes created.",
            data={"script_version_id": script_version["id"]},
            redirect_endpoint="projects.project_detail",
        )
