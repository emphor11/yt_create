from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..models.repository import ProjectRepository
from ..services.assembly_service import AssemblyService
from ..services.final_production_service import FinalProductionService
from ..services.publish_service import PublishService
from ..services.state_machine import InvalidTransitionError, StateMachine
from ..services.thumbnail_service import ThumbnailService
from ..services.youtube_upload_service import YouTubeUploadService

publish_bp = Blueprint("publish", __name__)


@publish_bp.route("/projects/<int:project_id>/review")
def final_review(project_id: int):
    repo = ProjectRepository()
    project = repo.get_project(project_id)
    if project["state"] not in {"scene_review", "assets_ready", "ready_to_publish", "scheduled", "published", "analyzed", "assembling"}:
        flash("Final studio becomes available after scene media exists.", "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    scenes = repo.list_scenes(project_id)
    script_version = repo.get_latest_script_version(project_id)
    script_payload = json.loads(script_version["full_script_json"]) if script_version else None
    titles = script_payload.get("titles", []) if script_payload else []
    thumbnail_options = ThumbnailService().ensure_creator_thumbnails(project_id, titles, scenes)
    final_service = FinalProductionService(repo)
    upload_package = final_service.build_upload_package(project_id)
    youtube_readiness = YouTubeUploadService().readiness(project_id)
    return render_template(
        "projects/final_review.html",
        project=project,
        scenes=scenes,
        script_payload=script_payload,
        thumbnail_options=thumbnail_options,
        upload_package=upload_package,
        publish_readiness=upload_package["publish_checklist"],
        youtube_readiness=youtube_readiness,
        final_video_exists=bool(project.get("final_video_path")) and Path(project["final_video_path"]).exists(),
    )


@publish_bp.route("/projects/<int:project_id>/review/assemble-draft", methods=["POST"])
def assemble_draft_master(project_id: int):
    project = ProjectRepository().get_project(project_id)
    if project["state"] not in {"scene_review", "assets_ready", "assembling", "ready_to_publish", "scheduled"}:
        flash("Draft master assembly is available after scene media is generated.", "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    try:
        AssemblyService().assemble_project(project_id)
        flash("Draft master assembled. Watch the full video before deciding what to fix.", "success")
    except Exception as exc:
        flash(f"Draft master assembly failed: {exc}", "danger")
    return redirect(url_for("publish.final_review", project_id=project_id))


@publish_bp.route("/projects/<int:project_id>/review/thumbnails", methods=["POST"])
def regenerate_thumbnails(project_id: int):
    repo = ProjectRepository()
    script_version = repo.get_latest_script_version(project_id)
    script_payload = json.loads(script_version["full_script_json"]) if script_version else {}
    ThumbnailService().ensure_creator_thumbnails(
        project_id,
        script_payload.get("titles", []),
        repo.list_scenes(project_id),
        force=True,
    )
    flash("Generated fresh creator thumbnail variants.", "success")
    return redirect(url_for("publish.final_review", project_id=project_id))


@publish_bp.route("/projects/<int:project_id>/review/select-thumbnail", methods=["POST"])
def select_thumbnail(project_id: int):
    thumbnail_path = request.form.get("selected_thumbnail_path", "").strip()
    ProjectRepository().update_project(project_id, selected_thumbnail_path=thumbnail_path)
    flash("Thumbnail selected.", "success")
    return redirect(url_for("publish.final_review", project_id=project_id))


@publish_bp.route("/projects/<int:project_id>/review/mark-ready", methods=["POST"])
def mark_master_ready(project_id: int):
    repo = ProjectRepository()
    project = repo.get_project(project_id)
    if not project.get("final_video_path") or not Path(project["final_video_path"]).exists():
        flash("Assemble the full master video before marking the project ready.", "danger")
        return redirect(url_for("publish.final_review", project_id=project_id))
    repo.update_project(project_id, state="ready_to_publish")
    flash("Master marked ready for publish review. QA warnings remain visible on this page.", "success")
    return redirect(url_for("publish.final_review", project_id=project_id))


@publish_bp.route("/projects/<int:project_id>/review/save", methods=["POST"])
def save_final_review(project_id: int):
    ProjectRepository().update_project(
        project_id,
        selected_title=request.form.get("selected_title", "").strip(),
        selected_description=request.form.get("selected_description", "").strip(),
        selected_thumbnail_path=request.form.get("selected_thumbnail_path", "").strip(),
    )
    FinalProductionService().build_upload_package(project_id)
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


@publish_bp.route("/projects/<int:project_id>/publish/youtube-upload", methods=["POST"])
def youtube_upload(project_id: int):
    project = ProjectRepository().get_project(project_id)
    if project["state"] not in {"ready_to_publish", "scheduled"}:
        flash("Mark the master ready before attempting a YouTube upload.", "warning")
        return redirect(url_for("publish.final_review", project_id=project_id))
    if project.get("youtube_video_id"):
        flash(f"This project is already uploaded as YouTube video {project['youtube_video_id']}.", "info")
        return redirect(url_for("publish.final_review", project_id=project_id))
    try:
        upload_service = YouTubeUploadService()
        video_id = upload_service.upload_private(project_id)
        if upload_service.last_thumbnail_warning:
            flash(f"Uploaded to YouTube as a private video: {video_id}. {upload_service.last_thumbnail_warning}", "warning")
        else:
            flash(f"Uploaded to YouTube as a private video: {video_id}", "success")
    except Exception as exc:
        flash(str(exc), "danger")
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
