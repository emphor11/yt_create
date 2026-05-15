"""Read-model use cases for pages that assemble existing workflow state."""

from __future__ import annotations

import json

from youtube_ai_system.application.result import UseCaseResult
from youtube_ai_system.infrastructure.persistence import ProjectRepository
from youtube_ai_system.services.media_service import MediaService
from youtube_ai_system.services.script_service import ScriptService
from youtube_ai_system.services.topic_service import TopicService


class BuildProjectDetailUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        media_service: MediaService | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.media_service = media_service or MediaService()

    def execute(self, project_id: int) -> UseCaseResult:
        project = self.repo.get_project(project_id)
        script_version = self.repo.get_latest_script_version(project_id)
        script_payload = json.loads(script_version["full_script_json"]) if script_version else None
        return UseCaseResult.ok(
            data={
                "project": project,
                "script_version": script_version,
                "script_payload": script_payload,
                "scenes": self.repo.list_scenes(project_id),
                "logs": self.repo.list_run_logs(project_id),
                "voice_summary": self.media_service.project_voice_summary(project_id),
                "next_step": next_project_step(project["state"]),
                "available_actions": project_actions(project["state"]),
            }
        )


class BuildProjectListUseCase:
    def __init__(self, repo: ProjectRepository | None = None) -> None:
        self.repo = repo or ProjectRepository()

    def execute(self) -> UseCaseResult:
        return UseCaseResult.ok(data={"projects": self.repo.list_projects()})


class BuildDiscardedProjectsUseCase:
    def __init__(self, repo: ProjectRepository | None = None) -> None:
        self.repo = repo or ProjectRepository()

    def execute(self) -> UseCaseResult:
        projects = [
            project
            for project in self.repo.list_projects(include_discarded=True)
            if project["state"] == "discarded"
        ]
        return UseCaseResult.ok(data={"projects": projects})


class BuildTopicSelectionUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        topic_service: TopicService | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.topic_service = topic_service or TopicService()

    def execute(self, project_id: int) -> UseCaseResult:
        project = self.repo.get_project(project_id)
        comparable = self.topic_service.lookup_comparable_videos(project.get("topic") or "", project.get("angle") or "")
        return UseCaseResult.ok(
            data={
                "project": project,
                "comparable": comparable,
                "topic_lookup_mode": self.topic_service.last_lookup_mode,
                "topic_lookup_message": self.topic_service.last_lookup_message,
            }
        )


class BuildScriptEditorUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        script_service: ScriptService | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.script_service = script_service or ScriptService()

    def execute(self, project_id: int) -> UseCaseResult:
        project = self.repo.get_project(project_id)
        if project["state"] not in {"script_review", "script_approved"}:
            return UseCaseResult.fail(
                "Script editing is only available during script review or immediately after approval.",
                redirect_endpoint="projects.project_detail",
            )
        script_version = self.repo.get_latest_script_version(project_id)
        if not script_version:
            return UseCaseResult.fail("No script version yet. Generate one first.", redirect_endpoint="projects.project_detail")
        script_payload = json.loads(script_version["full_script_json"])
        _, hook_errors, _ = self.script_service.approval_ready(script_version)
        return UseCaseResult.ok(
            data={
                "project": project,
                "script_version": script_version,
                "script_payload": script_payload,
                "hook_errors": hook_errors,
            }
        )


def next_project_step(state: str) -> dict[str, str]:
    steps = {
        "idea": {
            "title": "Set topic and angle",
            "description": "Start by opening topic selection and filling in the topic and angle manually.",
            "label": "Open Topic Selection",
            "endpoint": "projects.topic_selection",
        },
        "topic_selected": {
            "title": "Set topic and angle",
            "description": "Finish topic setup so the project can move into script generation.",
            "label": "Open Topic Selection",
            "endpoint": "projects.topic_selection",
        },
        "drafted": {
            "title": "Generate script",
            "description": "Generate a finance script draft for this project.",
            "label": "Generate Script",
            "endpoint": "projects.generate_script",
        },
        "script_review": {
            "title": "Edit and approve script",
            "description": "Open the script editor, make your own edits, and approve the script.",
            "label": "Open Script Editor",
            "endpoint": "projects.edit_script",
        },
        "script_approved": {
            "title": "Generate media",
            "description": "Create V2 narration, Remotion visuals, and scene assets.",
            "label": "Generate Media",
            "endpoint": "media.generate_media",
        },
        "media_generating": {
            "title": "Wait for media generation",
            "description": "Media is generating. After that, move to scene review.",
            "label": "Open Scene Review",
            "endpoint": "media.scene_review",
        },
        "scene_review": {
            "title": "Approve scenes",
            "description": "Check scenes and make sure the dynamic visual threshold is met.",
            "label": "Open Scene Review",
            "endpoint": "media.scene_review",
        },
        "assets_ready": {
            "title": "Assemble final video",
            "description": "Build the final MP4 using the approved scene assets.",
            "label": "Assemble Video",
            "endpoint": "media.assemble_project",
        },
        "assembling": {
            "title": "Finish assembly",
            "description": "Assembly is in progress. Review the final output once it completes.",
            "label": "Open Final Review",
            "endpoint": "publish.final_review",
        },
        "ready_to_publish": {
            "title": "Review and schedule",
            "description": "Save the title, description, thumbnail choice, upload id, and publish time.",
            "label": "Open Final Review",
            "endpoint": "publish.final_review",
        },
        "scheduled": {
            "title": "Capture analytics later",
            "description": "This project is scheduled. After publish, save analytics snapshots from the analytics page.",
            "label": "Open Analytics",
            "endpoint": "analytics.analytics_table",
        },
        "published": {
            "title": "Capture analytics",
            "description": "Save D1, D7, and D28 analytics snapshots from the analytics page.",
            "label": "Open Analytics",
            "endpoint": "analytics.analytics_table",
        },
        "analyzed": {
            "title": "Review performance",
            "description": "This project is complete. Review its snapshots and logs.",
            "label": "Open Analytics",
            "endpoint": "analytics.analytics_table",
        },
        "failed": {
            "title": "Check logs and retry",
            "description": "Use the run log to understand what failed, then retry the appropriate stage.",
            "label": "View Project",
            "endpoint": "projects.project_detail",
        },
        "discarded": {
            "title": "Project discarded",
            "description": "This project is intentionally stopped and kept only for reference.",
            "label": "View Discarded",
            "endpoint": "projects.discarded_projects",
        },
    }
    return steps.get(state, steps["idea"])


def project_actions(state: str) -> dict[str, bool]:
    return {
        "topic_selection": state in {"idea", "topic_selected", "drafted", "script_review"},
        "generate_script": state in {"drafted", "script_review"},
        "edit_script": state in {"script_review", "script_approved"},
        "generate_media": state == "script_approved",
        "scene_review": state in {"scene_review", "assets_ready", "media_generating"},
        "assemble": state == "assets_ready",
        "final_review": state in {"scene_review", "assets_ready", "ready_to_publish", "scheduled", "published", "analyzed", "assembling"},
    }
