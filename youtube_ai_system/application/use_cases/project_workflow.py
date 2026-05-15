"""Project and script-edit use cases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from youtube_ai_system.application.result import UseCaseResult
from youtube_ai_system.infrastructure.persistence import ProjectRepository
from youtube_ai_system.services.run_log import RunLogger
from youtube_ai_system.services.script_service import ScriptService
from youtube_ai_system.services.state_machine import InvalidTransitionError, StateMachine
from youtube_ai_system.services.topic_service import TopicService


@dataclass(frozen=True)
class TopicSelectionInput:
    topic: str
    angle: str
    target_duration_minutes: int | None
    channel_niche: str | None
    script_tone: str | None

    @classmethod
    def from_form(cls, form: Any) -> "TopicSelectionInput":
        return cls(
            topic=form.get("topic", "").strip(),
            angle=form.get("angle", "").strip(),
            target_duration_minutes=parse_target_duration(form.get("target_duration_minutes")),
            channel_niche=form.get("channel_niche", "").strip() or None,
            script_tone=form.get("script_tone", "").strip() or None,
        )


def parse_target_duration(raw_value: str | None) -> int | None:
    try:
        value = int((raw_value or "").strip())
        return value if value > 0 else None
    except ValueError:
        return None


class CreateProjectUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        logger: RunLogger | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.logger = logger or RunLogger()

    def execute(self, working_title: str) -> UseCaseResult:
        title = working_title.strip() or "Untitled Video Project"
        project_id = self.repo.create_project(title)
        self.logger.log("project_creation", "completed", "Created project.", project_id)
        return UseCaseResult.ok(
            "Project created.",
            data={"project_id": project_id},
            redirect_endpoint="projects.project_detail",
        )


class SaveTopicUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        topic_service: TopicService | None = None,
        state_machine: StateMachine | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.topic_service = topic_service or TopicService()
        self.state_machine = state_machine or StateMachine()

    def execute(
        self,
        project_id: int,
        *,
        topic: str,
        angle: str,
        target_duration_minutes: int | None,
        channel_niche: str | None,
        script_tone: str | None,
    ) -> UseCaseResult:
        self.repo.update_project(
            project_id,
            topic=topic,
            angle=angle,
            target_duration_minutes=target_duration_minutes,
            channel_niche=channel_niche,
            script_tone=script_tone,
        )
        project = self.repo.get_project(project_id)
        comparable = self.topic_service.lookup_comparable_videos(topic, angle)
        try:
            if project["state"] == "idea":
                self.state_machine.transition(project_id, "topic_selected", "Manual topic confirmed.")
                project = self.repo.get_project(project_id)
            if project["state"] == "topic_selected":
                self.state_machine.transition(project_id, "drafted", "Ready for script generation.")
                project = self.repo.get_project(project_id)
        except InvalidTransitionError as exc:
            project = self.repo.get_project(project_id)
            return UseCaseResult.fail(
                str(exc),
                data={
                    "project": project,
                    "comparable": comparable,
                    "topic_lookup_mode": self.topic_service.last_lookup_mode,
                    "topic_lookup_message": self.topic_service.last_lookup_message,
                    "flash_category": "danger",
                },
            )
        return UseCaseResult.ok(
            "Topic saved. Comparable videos have been refreshed below.",
            data={
                "project": project,
                "comparable": comparable,
                "topic_lookup_mode": self.topic_service.last_lookup_mode,
                "topic_lookup_message": self.topic_service.last_lookup_message,
            },
        )

    def execute_form(self, project_id: int, form: Any) -> UseCaseResult:
        parsed = TopicSelectionInput.from_form(form)
        return self.execute(
            project_id,
            topic=parsed.topic,
            angle=parsed.angle,
            target_duration_minutes=parsed.target_duration_minutes,
            channel_niche=parsed.channel_niche,
            script_tone=parsed.script_tone,
        )


class SaveScriptEditsUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        script_service: ScriptService | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.script_service = script_service or ScriptService()

    def execute(self, project_id: int, form: Any) -> UseCaseResult:
        script_version = self.repo.get_latest_script_version(project_id)
        if not script_version:
            return UseCaseResult.fail("No script draft found.", redirect_endpoint="projects.project_detail")

        existing_payload = json.loads(script_version["full_script_json"])
        payload = {
            "hook": {
                "narration": form.get("hook_narration", "").strip(),
                "estimated_duration_sec": float(form.get("hook_duration", 0) or 0),
            },
            "scenes": [],
            "outro": {
                "narration": form.get("outro_narration", "").strip(),
            },
            "titles": [line.strip() for line in form.get("titles", "").splitlines() if line.strip()],
            "description": form.get("description", "").strip(),
            "tags": [tag.strip() for tag in form.get("tags", "").split(",") if tag.strip()],
            "meta": existing_payload.get("meta", {}),
        }

        scene_count = int(form.get("scene_count", 0))
        existing_scenes = existing_payload.get("scenes", [])
        for index in range(scene_count):
            existing_scene = existing_scenes[index] if index < len(existing_scenes) else {}
            scene_payload = dict(existing_scene)
            scene_payload["kind"] = "body"
            scene_payload["narration"] = form.get(f"scene_{index}_narration", "").strip()
            scene_payload.setdefault("scene_index", index + 1)
            payload["scenes"].append(scene_payload)

        self.script_service.save_script_edits(script_version["id"], payload)
        return UseCaseResult.ok(
            "Script saved. Approval is now available once the hook passes.",
            data={"script_version_id": script_version["id"]},
            redirect_endpoint="projects.edit_script",
        )


class DiscardProjectUseCase:
    def __init__(self, state_machine: StateMachine | None = None) -> None:
        self.state_machine = state_machine or StateMachine()

    def execute(self, project_id: int) -> UseCaseResult:
        try:
            self.state_machine.transition(project_id, "discarded", "User discarded project.")
        except InvalidTransitionError as exc:
            return UseCaseResult.fail(
                str(exc),
                data={"flash_category": "danger"},
                redirect_endpoint="projects.project_list",
            )
        return UseCaseResult.ok("Project discarded.", redirect_endpoint="projects.project_list")
