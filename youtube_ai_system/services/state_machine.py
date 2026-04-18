from __future__ import annotations

from ..models.repository import ProjectRepository
from .run_log import RunLogger


STATE_FLOW = {
    "idea": {"topic_selected", "failed", "discarded"},
    "topic_selected": {"drafted", "failed", "discarded"},
    "drafted": {"script_review", "failed", "discarded"},
    "script_review": {"script_approved", "failed", "discarded"},
    "script_approved": {"media_generating", "failed", "discarded"},
    "media_generating": {"scene_review", "failed", "discarded"},
    "scene_review": {"assets_ready", "failed", "discarded"},
    "assets_ready": {"assembling", "failed", "discarded"},
    "assembling": {"ready_to_publish", "failed", "discarded"},
    "ready_to_publish": {"scheduled", "failed", "discarded"},
    "scheduled": {"published", "failed"},
    "published": {"analyzed", "failed"},
    "analyzed": set(),
    "failed": {
        "topic_selected",
        "drafted",
        "script_review",
        "media_generating",
        "scene_review",
        "assembling",
        "ready_to_publish",
        "scheduled",
        "published",
        "discarded",
    },
    "discarded": set(),
}

ACTIVE_STATES = {
    "idea",
    "topic_selected",
    "drafted",
    "script_review",
    "script_approved",
    "media_generating",
    "scene_review",
    "assets_ready",
    "assembling",
    "ready_to_publish",
    "scheduled",
    "published",
}


class InvalidTransitionError(ValueError):
    pass


class StateMachine:
    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.logger = RunLogger()

    def transition(self, project_id: int, target_state: str, reason: str) -> None:
        project = self.repo.get_project(project_id)
        if not project:
            raise InvalidTransitionError(f"Project {project_id} does not exist.")

        current_state = project["state"]
        allowed = STATE_FLOW.get(current_state, set())
        if target_state not in allowed:
            self.logger.log(
                "state_machine",
                "failed",
                f"Rejected invalid transition from {current_state} to {target_state}: {reason}",
                project_id,
            )
            raise InvalidTransitionError(
                f"Cannot move project {project_id} from {current_state} to {target_state}."
            )

        self.repo.update_project(project_id, state=target_state)
        self.logger.log(
            "state_machine",
            "completed",
            f"Moved project from {current_state} to {target_state}: {reason}",
            project_id,
        )

    def move_to_failed(self, project_id: int, reason: str) -> None:
        project = self.repo.get_project(project_id)
        if not project:
            raise InvalidTransitionError(f"Project {project_id} does not exist.")
        current_state = project["state"]
        if current_state == "discarded":
            raise InvalidTransitionError("Discarded projects cannot transition to failed.")
        if current_state == "failed":
            self.logger.log("state_machine", "completed", f"Project already failed: {reason}", project_id)
            return
        self.repo.update_project(project_id, state="failed")
        self.logger.log(
            "state_machine",
            "failed",
            f"Moved project from {current_state} to failed: {reason}",
            project_id,
        )
