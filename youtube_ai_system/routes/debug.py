from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify, render_template

from ..models.repository import ProjectRepository
from ..services.scene_debug import SceneDebugStore, debug_video_pipeline_enabled

debug_bp = Blueprint("debug", __name__, url_prefix="/debug")


def _require_debug_enabled() -> None:
    if not debug_video_pipeline_enabled():
        abort(404)


@debug_bp.route("/video-pipeline/projects/<int:project_id>")
def video_pipeline(project_id: int):
    _require_debug_enabled()
    repo = ProjectRepository()
    project = repo.get_project(project_id)
    if not project:
        abort(404)
    scenes = repo.list_scenes(project_id)
    traces = SceneDebugStore().list_project(project_id)
    trace_by_order = {int(item["scene_order"]): item for item in traces if item.get("scene_order") is not None}
    enriched_scenes = []
    for scene in scenes:
        order = int(scene.get("scene_order") or 0)
        enriched = dict(scene)
        enriched["debug_trace"] = trace_by_order.get(order)
        enriched_scenes.append(enriched)
    return render_template(
        "debug/video_pipeline.html",
        project=project,
        scenes=enriched_scenes,
        traces=traces,
        storage_root=str(current_app.config["STORAGE_ROOT"]),
    )


@debug_bp.route("/video-pipeline/projects/<int:project_id>/scene/<int:scene_order>.json")
def video_pipeline_scene_json(project_id: int, scene_order: int):
    _require_debug_enabled()
    trace = SceneDebugStore().load_latest(project_id, scene_order)
    if trace is None:
        abort(404)
    return jsonify(trace.to_dict())
