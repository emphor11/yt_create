from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..application.use_cases import (
    AssembleDraftMasterUseCase,
    BuildFinalReviewUseCase,
    MarkMasterReadyUseCase,
    MockUploadUseCase,
    RegenerateThumbnailsUseCase,
    SaveUploadPackageUseCase,
    SchedulePublishUseCase,
    SelectThumbnailUseCase,
    StagePublishUseCase,
    UploadPrivateVideoUseCase,
)

publish_bp = Blueprint("publish", __name__)


@publish_bp.route("/projects/<int:project_id>/review")
def final_review(project_id: int):
    result = BuildFinalReviewUseCase().execute(project_id)
    if not result.success:
        flash(result.message, "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    return render_template(
        "projects/final_review.html",
        **result.data,
    )


@publish_bp.route("/projects/<int:project_id>/review/assemble-draft", methods=["POST"])
def assemble_draft_master(project_id: int):
    try:
        result = AssembleDraftMasterUseCase().execute(project_id)
    except Exception as exc:
        flash(f"Draft master assembly failed: {exc}", "danger")
    else:
        if result.success:
            flash(result.message, "success")
        else:
            flash(result.message, "warning")
            return redirect(url_for("projects.project_detail", project_id=project_id))
    return redirect(url_for("publish.final_review", project_id=project_id))


@publish_bp.route("/projects/<int:project_id>/review/thumbnails", methods=["POST"])
def regenerate_thumbnails(project_id: int):
    result = RegenerateThumbnailsUseCase().execute(project_id)
    flash(result.message, "success")
    return redirect(url_for("publish.final_review", project_id=project_id))


@publish_bp.route("/projects/<int:project_id>/review/select-thumbnail", methods=["POST"])
def select_thumbnail(project_id: int):
    result = SelectThumbnailUseCase().execute(project_id, request.form.get("selected_thumbnail_path", ""))
    flash(result.message, "success")
    return redirect(url_for("publish.final_review", project_id=project_id))


@publish_bp.route("/projects/<int:project_id>/review/mark-ready", methods=["POST"])
def mark_master_ready(project_id: int):
    result = MarkMasterReadyUseCase().execute(project_id)
    if not result.success:
        flash(result.message, "danger")
        return redirect(url_for("publish.final_review", project_id=project_id))
    flash(result.message, "success")
    return redirect(url_for("publish.final_review", project_id=project_id))


@publish_bp.route("/projects/<int:project_id>/review/save", methods=["POST"])
def save_final_review(project_id: int):
    result = SaveUploadPackageUseCase().execute(project_id, request.form)
    flash(result.message, "success")
    return redirect(url_for("publish.final_review", project_id=project_id))


@publish_bp.route("/projects/<int:project_id>/publish/stage", methods=["POST"])
def stage_publish(project_id: int):
    result = StagePublishUseCase().execute(project_id)
    if not result.success:
        flash(result.message, "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    flash(result.message, "success")
    return redirect(url_for("publish.final_review", project_id=project_id))


@publish_bp.route("/projects/<int:project_id>/publish/mock-upload", methods=["POST"])
def mock_upload(project_id: int):
    result = MockUploadUseCase().execute(project_id, request.form.get("youtube_video_id", ""))
    if not result.success:
        flash(result.message, "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    flash(result.message, "success")
    return redirect(url_for("publish.final_review", project_id=project_id))


@publish_bp.route("/projects/<int:project_id>/publish/youtube-upload", methods=["POST"])
def youtube_upload(project_id: int):
    force_upload = request.form.get("force_upload") == "1"
    try:
        result = UploadPrivateVideoUseCase().execute(project_id, force_upload=force_upload)
        if not result.success:
            flash(result.message, "warning")
        else:
            flash(result.message, result.data.get("flash_category", "success"))
    except Exception as exc:
        flash(str(exc), "danger")
    return redirect(url_for("publish.final_review", project_id=project_id))


@publish_bp.route("/projects/<int:project_id>/publish/schedule", methods=["POST"])
def schedule_publish(project_id: int):
    result = SchedulePublishUseCase().execute(project_id, request.form.get("publish_at", ""))
    if result.success:
        flash(result.message, "success")
    else:
        flash(result.message, result.data.get("flash_category", "warning"))
        if result.redirect_endpoint == "publish.final_review":
            return redirect(url_for("publish.final_review", project_id=project_id))
        return redirect(url_for("projects.project_detail", project_id=project_id))
    return redirect(url_for("publish.final_review", project_id=project_id))
