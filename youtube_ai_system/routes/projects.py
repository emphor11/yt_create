from __future__ import annotations

import json

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..models.repository import ProjectRepository, utcnow
from ..services.run_log import RunLogger
from ..services.media_service import MediaService
from ..services.script_service import ScriptService
from ..services.state_machine import InvalidTransitionError, StateMachine
from ..services.topic_service import TopicService

projects_bp = Blueprint("projects", __name__)


@projects_bp.route("/")
def home():
    return redirect(url_for("projects.start_here"))


@projects_bp.route("/start")
def start_here():
    return render_template("projects/start_here.html")


@projects_bp.route("/projects")
def project_list():
    projects = ProjectRepository().list_projects()
    return render_template("projects/list.html", projects=projects)


@projects_bp.route("/projects/discarded")
def discarded_projects():
    projects = [
        project
        for project in ProjectRepository().list_projects(include_discarded=True)
        if project["state"] == "discarded"
    ]
    return render_template("projects/discarded.html", projects=projects)


@projects_bp.route("/projects/new", methods=["GET", "POST"])
def create_project():
    repo = ProjectRepository()
    logger = RunLogger()
    if request.method == "POST":
        working_title = request.form.get("working_title", "").strip() or "Untitled Video Project"
        project_id = repo.create_project(working_title)
        logger.log("project_creation", "completed", "Created project.", project_id)
        flash("Project created.", "success")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    return render_template("projects/create.html")


@projects_bp.route("/projects/<int:project_id>")
def project_detail(project_id: int):
    repo = ProjectRepository()
    project = repo.get_project(project_id)
    script_version = repo.get_latest_script_version(project_id)
    scenes = repo.list_scenes(project_id)
    logs = repo.list_run_logs(project_id)
    voice_summary = MediaService().project_voice_summary(project_id)
    script_payload = None
    if script_version:
        script_payload = json.loads(script_version["full_script_json"])
    next_step = next_project_step(project["state"])
    available_actions = project_actions(project["state"])
    return render_template(
        "projects/detail.html",
        project=project,
        script_version=script_version,
        script_payload=script_payload,
        scenes=scenes,
        logs=logs,
        voice_summary=voice_summary,
        next_step=next_step,
        available_actions=available_actions,
    )


@projects_bp.route("/projects/<int:project_id>/topic", methods=["GET", "POST"])
def topic_selection(project_id: int):
    repo = ProjectRepository()
    project = repo.get_project(project_id)
    topic_service = TopicService()
    state_machine = StateMachine()
    comparable = topic_service.lookup_comparable_videos(project.get("topic") or "", project.get("angle") or "")

    if request.method == "POST":
        topic = request.form.get("topic", "").strip()
        angle = request.form.get("angle", "").strip()
        target_duration_minutes = _parse_target_duration(request.form.get("target_duration_minutes"))
        channel_niche = request.form.get("channel_niche", "").strip() or None
        script_tone = request.form.get("script_tone", "").strip() or None
        repo.update_project(
            project_id,
            topic=topic,
            angle=angle,
            target_duration_minutes=target_duration_minutes,
            channel_niche=channel_niche,
            script_tone=script_tone,
        )
        project = repo.get_project(project_id)
        comparable = topic_service.lookup_comparable_videos(topic, angle)
        try:
            if project["state"] == "idea":
                state_machine.transition(project_id, "topic_selected", "Manual topic confirmed.")
                project = repo.get_project(project_id)
            if project["state"] == "topic_selected":
                state_machine.transition(project_id, "drafted", "Ready for script generation.")
        except InvalidTransitionError as exc:
            flash(str(exc), "danger")
        else:
            flash("Topic saved. Comparable videos have been refreshed below.", "success")
        project = repo.get_project(project_id)
        return render_template(
            "projects/topic_selection.html",
            project=project,
            comparable=comparable,
            topic_lookup_mode=topic_service.last_lookup_mode,
            topic_lookup_message=topic_service.last_lookup_message,
        )

    return render_template(
        "projects/topic_selection.html",
        project=project,
        comparable=comparable,
        topic_lookup_mode=topic_service.last_lookup_mode,
        topic_lookup_message=topic_service.last_lookup_message,
    )


@projects_bp.route("/projects/<int:project_id>/script/generate", methods=["POST"])
def generate_script(project_id: int):
    repo = ProjectRepository()
    project = repo.get_project(project_id)
    script_service = ScriptService()
    state_machine = StateMachine()

    if not project.get("topic") or not project.get("angle"):
        flash("Set topic and angle first.", "danger")
        return redirect(url_for("projects.topic_selection", project_id=project_id))

    if project["state"] not in {"drafted", "script_review"}:
        flash("Script generation is only available before the script is approved.", "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))

    if project["state"] == "drafted":
        state_machine.transition(project_id, "script_review", "Script review started.")
    script_service.generate_script(
        project_id,
        project["topic"],
        project["angle"],
        project.get("target_duration_minutes"),
        project.get("channel_niche"),
        project.get("script_tone"),
    )
    flash(f"Script draft generated for topic '{project['topic']}' and angle '{project['angle']}'.", "success")
    return redirect(url_for("projects.edit_script", project_id=project_id))


@projects_bp.route("/projects/<int:project_id>/script", methods=["GET"])
def edit_script(project_id: int):
    repo = ProjectRepository()
    project = repo.get_project(project_id)
    if project["state"] not in {"script_review", "script_approved"}:
        flash("Script editing is only available during script review or immediately after approval.", "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    script_version = repo.get_latest_script_version(project_id)
    if not script_version:
        flash("No script version yet. Generate one first.", "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))
    script_payload = json.loads(script_version["full_script_json"])
    _, hook_errors, _ = ScriptService().approval_ready(script_version)
    return render_template(
        "projects/script_editor.html",
        project=project,
        script_version=script_version,
        script_payload=script_payload,
        hook_errors=hook_errors,
    )


@projects_bp.route("/projects/<int:project_id>/script/save", methods=["POST"])
def save_script(project_id: int):
    repo = ProjectRepository()
    script_version = repo.get_latest_script_version(project_id)
    if not script_version:
        flash("No script draft found.", "danger")
        return redirect(url_for("projects.project_detail", project_id=project_id))

    existing_payload = json.loads(script_version["full_script_json"])

    payload = {
        "hook": {
            "narration": request.form.get("hook_narration", "").strip(),
            "estimated_duration_sec": float(request.form.get("hook_duration", 0) or 0),
        },
        "scenes": [],
        "outro": {
            "narration": request.form.get("outro_narration", "").strip(),
        },
        "titles": [line.strip() for line in request.form.get("titles", "").splitlines() if line.strip()],
        "description": request.form.get("description", "").strip(),
        "tags": [tag.strip() for tag in request.form.get("tags", "").split(",") if tag.strip()],
        "meta": existing_payload.get("meta", {}),
    }

    scene_count = int(request.form.get("scene_count", 0))
    existing_scenes = existing_payload.get("scenes", [])
    for index in range(scene_count):
        existing_scene = existing_scenes[index] if index < len(existing_scenes) else {}
        payload["scenes"].append(
            {
                "kind": "body",
                "narration": request.form.get(f"scene_{index}_narration", "").strip(),
            }
        )

    ScriptService().save_script_edits(script_version["id"], payload)
    flash("Script saved. Approval is now available once the hook passes.", "success")
    return redirect(url_for("projects.edit_script", project_id=project_id))


def _parse_beats_json(label: str, raw_value: str, fallback):
    try:
        parsed = json.loads(raw_value or "[]")
    except json.JSONDecodeError:
        flash(f"Visual beats JSON for {label} was invalid, so the previous beats were kept.", "warning")
        return fallback or []
    if not isinstance(parsed, list):
        flash(f"Visual beats JSON for {label} must be an array, so the previous beats were kept.", "warning")
        return fallback or []
    return parsed


@projects_bp.route("/projects/<int:project_id>/script/approve", methods=["POST"])
def approve_script(project_id: int):
    repo = ProjectRepository()
    project = repo.get_project(project_id)
    if project["state"] != "script_review":
        flash("This project is no longer in script review, so approval is not available here.", "warning")
        return redirect(url_for("projects.project_detail", project_id=project_id))

    script_version = repo.get_latest_script_version(project_id)
    if not script_version:
        flash("No script draft found.", "danger")
        return redirect(url_for("projects.project_detail", project_id=project_id))

    script_service = ScriptService()
    state_machine = StateMachine()
    ready, errors, payload = script_service.approval_ready(script_version)
    if not ready:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("projects.edit_script", project_id=project_id))

    repo.update_script_version(script_version["id"], approved_at=utcnow())
    repo.replace_scenes(project_id, script_version["id"], script_service.scene_rows_from_payload(payload))
    state_machine.transition(project_id, "script_approved", "Script approved.")
    flash("Script approved and scenes created.", "success")
    return redirect(url_for("projects.project_detail", project_id=project_id))


@projects_bp.route("/projects/<int:project_id>/discard", methods=["POST"])
def discard_project(project_id: int):
    try:
        StateMachine().transition(project_id, "discarded", "User discarded project.")
        flash("Project discarded.", "warning")
    except InvalidTransitionError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("projects.project_list"))


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
        "final_review": state in {"ready_to_publish", "scheduled", "published", "analyzed", "assembling"},
    }


def _parse_target_duration(raw_value: str | None) -> int | None:
    try:
        value = int((raw_value or "").strip())
        return value if value > 0 else None
    except ValueError:
        return None
