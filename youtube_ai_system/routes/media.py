from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..application.use_cases import (
    ApproveScenesUseCase,
    AssembleProjectUseCase,
    BuildSceneReviewUseCase,
    GenerateProjectMediaUseCase,
    RegenerateSceneUseCase,
    RunVoiceCheckUseCase,
)

media_bp = Blueprint("media", __name__)


@media_bp.route("/voice/check", methods=["POST"])
def voice_check():
    result = RunVoiceCheckUseCase().execute().data
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
    result = GenerateProjectMediaUseCase().execute(project_id)
    if result.success:
        flash(result.message, "info")
    else:
        flash(result.message, result.data.get("flash_category", "warning"))
        if result.redirect_endpoint == "media.scene_review":
            return redirect(url_for("media.scene_review", project_id=project_id))
        return redirect(url_for("projects.project_detail", project_id=project_id))
    return redirect(url_for("media.scene_review", project_id=project_id))


@media_bp.route("/projects/<int:project_id>/scene-review")
def scene_review(project_id: int):
    result = BuildSceneReviewUseCase().execute(project_id)
    if not result.success:
        flash(result.message, "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    return render_template(
        "projects/scene_review.html",
        **result.data,
    )


@media_bp.route("/projects/<int:project_id>/scene-review/approve", methods=["POST"])
def approve_scenes(project_id: int):
    result = ApproveScenesUseCase().execute(project_id)
    if not result.success and result.message == "Scene approval is only available during scene review.":
        flash(result.message, "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    if not result.success:
        flash(result.message, result.data.get("flash_category", "danger"))
        if result.redirect_endpoint == "projects.project_detail":
            return redirect(url_for("projects.project_detail", project_id=project_id))
        return redirect(url_for("media.scene_review", project_id=project_id))
    flash(result.message, "success")
    return redirect(url_for("projects.project_detail", project_id=project_id))


@media_bp.route("/projects/<int:project_id>/scene/<int:scene_id>/regenerate", methods=["POST"])
def regenerate_scene(project_id: int, scene_id: int):
    result = RegenerateSceneUseCase().execute(project_id, scene_id)
    if result.message:
        flash(result.message, "success" if result.success else "danger")
    return redirect(url_for("media.scene_review", project_id=project_id))


@media_bp.route("/projects/<int:project_id>/assemble", methods=["POST"])
def assemble_project(project_id: int):
    result = AssembleProjectUseCase().execute(project_id)
    if not result.success and result.message == "Assembly is only available after scenes are approved.":
        flash(result.message, "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    if not result.success:
        flash(result.message, result.data.get("flash_category", "danger"))
        if result.redirect_endpoint == "publish.final_review":
            return redirect(url_for("publish.final_review", project_id=project_id))
        return redirect(url_for("media.scene_review", project_id=project_id))
    flash(result.message, "success")
    return redirect(url_for("publish.final_review", project_id=project_id))
