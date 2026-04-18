from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..models.repository import ProjectRepository
from ..services.assembly_service import AssemblyService
from ..services.media_service import MediaService
from ..services.state_machine import InvalidTransitionError, StateMachine

media_bp = Blueprint("media", __name__)


@media_bp.route("/voice/check", methods=["POST"])
def voice_check():
    result = MediaService().run_voice_check()
    if result["status"] == "live":
        flash(
            f"Live voice check passed. Audio saved at {result['audio_path']} ({result['duration']}s).",
            "success",
        )
    elif result["status"] == "demo":
        flash(result["message"], "info")
    else:
        flash(result["message"], "warning")
    return redirect(request.referrer or url_for("projects.project_list"))


@media_bp.route("/projects/<int:project_id>/media/generate", methods=["POST"])
def generate_media(project_id: int):
    project = ProjectRepository().get_project(project_id)
    if project["state"] != "script_approved":
        flash("Media generation is only available after script approval.", "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))

    state_machine = StateMachine()
    media_service = MediaService()
    try:
        state_machine.transition(project_id, "media_generating", "Media generation started.")
        media_service.generate_voice_and_visuals(project_id)
        state_machine.transition(project_id, "scene_review", "Media assets ready for scene review.")
        media_summary = media_service.project_media_summary(project_id)
        flash(
            (
                f"Media generation finished. "
                f"Voice: {media_summary['voice_message']} "
                f"Visuals: {media_summary['visual_message']}"
            ),
            "info",
        )
    except InvalidTransitionError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("media.scene_review", project_id=project_id))


@media_bp.route("/projects/<int:project_id>/scene-review")
def scene_review(project_id: int):
    repo = ProjectRepository()
    project = repo.get_project(project_id)
    if project["state"] not in {"media_generating", "scene_review", "assets_ready"}:
        flash("Scene review is only available after media generation starts.", "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    scenes = repo.list_scenes(project_id)
    media_service = MediaService()
    ratio, _ = media_service.compute_dynamic_visual_ratio(project_id)
    media_summary = media_service.project_media_summary(project_id)
    return render_template(
        "projects/scene_review.html",
        project=project,
        scenes=scenes,
        ratio=ratio,
        threshold=0.6,
        media_summary=media_summary,
    )


@media_bp.route("/projects/<int:project_id>/scene-review/approve", methods=["POST"])
def approve_scenes(project_id: int):
    project = ProjectRepository().get_project(project_id)
    if project["state"] != "scene_review":
        flash("Scene approval is only available during scene review.", "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))

    ratio, scenes = MediaService().compute_dynamic_visual_ratio(project_id)
    if not scenes:
        flash("No scenes generated yet.", "danger")
        return redirect(url_for("media.scene_review", project_id=project_id))
    if ratio < 0.6:
        flash("At least 60% of scenes must use dynamic visuals before approval.", "danger")
        return redirect(url_for("media.scene_review", project_id=project_id))
    try:
        StateMachine().transition(project_id, "assets_ready", "Scene review approved.")
        flash("Scenes approved.", "success")
    except InvalidTransitionError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("projects.project_detail", project_id=project_id))


@media_bp.route("/projects/<int:project_id>/scene/<int:scene_id>/regenerate", methods=["POST"])
def regenerate_scene(project_id: int, scene_id: int):
    repo = ProjectRepository()
    scene = repo.get_scene(scene_id)
    if scene and scene["video_project_id"] == project_id:
        repo.update_scene(scene_id, status="generated")
        flash(
            f"Marked scene {scene['scene_order']} for regeneration. Demo scaffold keeps the generated asset in place.",
            "info",
        )
    return redirect(url_for("media.scene_review", project_id=project_id))


@media_bp.route("/projects/<int:project_id>/assemble", methods=["POST"])
def assemble_project(project_id: int):
    project = ProjectRepository().get_project(project_id)
    if project["state"] != "assets_ready":
        flash("Assembly is only available after scenes are approved.", "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))

    state_machine = StateMachine()
    try:
        state_machine.transition(project_id, "assembling", "Assembly started.")
        AssemblyService().assemble_project(project_id)
        state_machine.transition(project_id, "ready_to_publish", "Assembly complete.")
        flash("Assembly complete. Review before publishing.", "success")
    except InvalidTransitionError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("publish.final_review", project_id=project_id))
