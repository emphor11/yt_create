from __future__ import annotations

import json

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..models.repository import ProjectRepository
from ..services.publish_service import PublishService
from ..services.state_machine import InvalidTransitionError, StateMachine
from ..services.thumbnail_service import ThumbnailService

publish_bp = Blueprint("publish", __name__)


@publish_bp.route("/projects/<int:project_id>/review")
def final_review(project_id: int):
    repo = ProjectRepository()
    project = repo.get_project(project_id)
    if project["state"] not in {"ready_to_publish", "scheduled", "published", "analyzed", "assembling"}:
        flash("Final review becomes available after assembly.", "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    script_version = repo.get_latest_script_version(project_id)
    script_payload = json.loads(script_version["full_script_json"]) if script_version else None
    thumbnail_options = []
    if script_payload and script_payload.get("titles"):
        thumbnail_options = ThumbnailService().ensure_thumbnails(project_id, script_payload["titles"])
    return render_template(
        "projects/final_review.html",
        project=project,
        script_payload=script_payload,
        thumbnail_options=thumbnail_options,
    )


@publish_bp.route("/projects/<int:project_id>/review/save", methods=["POST"])
def save_final_review(project_id: int):
    ProjectRepository().update_project(
        project_id,
        selected_title=request.form.get("selected_title", "").strip(),
        selected_description=request.form.get("selected_description", "").strip(),
        selected_thumbnail_path=request.form.get("selected_thumbnail_path", "").strip(),
    )
    flash("Review metadata saved.", "success")
    return redirect(url_for("publish.final_review", project_id=project_id))


@publish_bp.route("/projects/<int:project_id>/publish/stage", methods=["POST"])
def stage_publish(project_id: int):
    project = ProjectRepository().get_project(project_id)
    if project["state"] not in {"ready_to_publish", "scheduled"}:
        flash("Publishing can only be prepared from the final review stage.", "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    PublishService().stage_publish(project_id)
    flash("Publish record prepared. Upload integration can fill in the YouTube ID.", "success")
    return redirect(url_for("publish.final_review", project_id=project_id))


@publish_bp.route("/projects/<int:project_id>/publish/mock-upload", methods=["POST"])
def mock_upload(project_id: int):
    project = ProjectRepository().get_project(project_id)
    if project["state"] not in {"ready_to_publish", "scheduled"}:
        flash("Upload metadata can only be stored from the final review stage.", "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    publish_service = PublishService()
    youtube_video_id = request.form.get("youtube_video_id", "").strip() or f"demo-{project_id}"
    publish_service.mark_uploaded(project_id, youtube_video_id)
    flash("Stored a mock upload id. Set a schedule next.", "success")
    return redirect(url_for("publish.final_review", project_id=project_id))


@publish_bp.route("/projects/<int:project_id>/publish/schedule", methods=["POST"])
def schedule_publish(project_id: int):
    project = ProjectRepository().get_project(project_id)
    if project["state"] not in {"ready_to_publish", "scheduled"}:
        flash("Scheduling is only available from the final review stage.", "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    publish_at = request.form.get("publish_at", "").strip()
    publish_service = PublishService()
    state_machine = StateMachine()
    publish_service.schedule_publish(project_id, publish_at)
    project = ProjectRepository().get_project(project_id)
    try:
        if project["state"] == "ready_to_publish":
            state_machine.transition(project_id, "scheduled", "Scheduled publish set.")
    except InvalidTransitionError as exc:
        flash(str(exc), "danger")
    else:
        flash("Scheduled publish saved.", "success")
    return redirect(url_for("publish.final_review", project_id=project_id))
