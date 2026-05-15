from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..application.use_cases import (
    ApproveScriptUseCase,
    BuildDiscardedProjectsUseCase,
    BuildProjectDetailUseCase,
    BuildProjectListUseCase,
    BuildScriptEditorUseCase,
    BuildTopicSelectionUseCase,
    CreateProjectUseCase,
    DiscardProjectUseCase,
    GenerateScriptUseCase,
    SaveScriptEditsUseCase,
    SaveTopicUseCase,
)

projects_bp = Blueprint("projects", __name__)


@projects_bp.route("/")
def home():
    return redirect(url_for("projects.start_here"))


@projects_bp.route("/start")
def start_here():
    return render_template("projects/start_here.html")


@projects_bp.route("/projects")
def project_list():
    return render_template("projects/list.html", **BuildProjectListUseCase().execute().data)


@projects_bp.route("/projects/discarded")
def discarded_projects():
    return render_template("projects/discarded.html", **BuildDiscardedProjectsUseCase().execute().data)


@projects_bp.route("/projects/new", methods=["GET", "POST"])
def create_project():
    if request.method == "POST":
        result = CreateProjectUseCase().execute(request.form.get("working_title", ""))
        project_id = result.data["project_id"]
        flash(result.message, "success")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    return render_template("projects/create.html")


@projects_bp.route("/projects/<int:project_id>")
def project_detail(project_id: int):
    return render_template(
        "projects/detail.html",
        **BuildProjectDetailUseCase().execute(project_id).data,
    )


@projects_bp.route("/projects/<int:project_id>/topic", methods=["GET", "POST"])
def topic_selection(project_id: int):
    page_result = BuildTopicSelectionUseCase().execute(project_id)

    if request.method == "POST":
        result = SaveTopicUseCase().execute_form(project_id, request.form)
        page_result = result
        if result.success:
            flash(result.message, "success")
        else:
            flash(result.message, result.data.get("flash_category", "danger"))
        return render_template(
            "projects/topic_selection.html",
            **page_result.data,
        )

    return render_template(
        "projects/topic_selection.html",
        **page_result.data,
    )


@projects_bp.route("/projects/<int:project_id>/script/generate", methods=["POST"])
def generate_script(project_id: int):
    result = GenerateScriptUseCase().execute(project_id)
    if not result.success and result.message == "Set topic and angle first.":
        flash(result.message, "danger")
        return redirect(url_for("projects.topic_selection", project_id=project_id))
    if not result.success:
        flash(result.message, "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    flash(result.message, "success")
    return redirect(url_for("projects.edit_script", project_id=project_id))


@projects_bp.route("/projects/<int:project_id>/script", methods=["GET"])
def edit_script(project_id: int):
    result = BuildScriptEditorUseCase().execute(project_id)
    if not result.success:
        flash(result.message, "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    return render_template(
        "projects/script_editor.html",
        **result.data,
    )


@projects_bp.route("/projects/<int:project_id>/script/save", methods=["POST"])
def save_script(project_id: int):
    result = SaveScriptEditsUseCase().execute(project_id, request.form)
    if not result.success:
        flash(result.message, "danger")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    flash(result.message, "success")
    return redirect(url_for("projects.edit_script", project_id=project_id))


@projects_bp.route("/projects/<int:project_id>/script/approve", methods=["POST"])
def approve_script(project_id: int):
    result = ApproveScriptUseCase().execute(project_id)
    if (
        not result.success
        and result.message == "This project is no longer in script review, so approval is not available here."
    ):
        flash(result.message, "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    if not result.success and result.message == "No script draft found.":
        flash(result.message, "danger")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    if not result.success:
        for error in result.errors:
            flash(error, "danger")
        return redirect(url_for("projects.edit_script", project_id=project_id))
    flash(result.message, "success")
    return redirect(url_for("projects.project_detail", project_id=project_id))


@projects_bp.route("/projects/<int:project_id>/discard", methods=["POST"])
def discard_project(project_id: int):
    result = DiscardProjectUseCase().execute(project_id)
    flash(result.message, "warning" if result.success else result.data.get("flash_category", "danger"))
    return redirect(url_for("projects.project_list"))
