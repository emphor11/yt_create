from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from flask import current_app

from youtube_ai_system import create_app
from youtube_ai_system.models.repository import ProjectRepository
from youtube_ai_system.services.media_service import MediaService
from youtube_ai_system.services.render_spec_service import RenderSpec
from youtube_ai_system.services.scene_builder import build_scenes
from youtube_ai_system.services.financial_governance import educational_integrity_report, narrative_progression_report, numeric_role_map, repetition_report, scene_density_report
from youtube_ai_system.services.scene_debug import SceneDebugStore, SceneDebugTrace, frame_probe, stable_hash


STAGES = {
    "normalizer",
    "visual-director",
    "beat-expansion",
    "scene-builder",
    "render-spec",
    "frame-probe",
    "validator",
    "numeric-provenance",
    "concept-isolation",
    "script-governance",
    "integrity-validator",
    "all",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay visual pipeline stages without rendering MP4s or mutating scene rows.")
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--scene-order", type=int, required=True)
    parser.add_argument("--stage", choices=sorted(STAGES), default="all")
    parser.add_argument("--frame", type=int, default=0)
    args = parser.parse_args()

    app = create_app({"DEBUG_VIDEO_PIPELINE": True})
    with app.app_context():
        path = replay(args.project_id, args.scene_order, args.stage, args.frame)
        print(path)


def replay(project_id: int, scene_order: int, stage: str, frame: int = 0) -> Path:
    repo = ProjectRepository()
    scenes = repo.list_scenes(project_id)
    scene = next((item for item in scenes if int(item.get("scene_order") or -1) == int(scene_order)), None)
    if not scene:
        raise ValueError(f"Scene {scene_order} was not found for project {project_id}.")

    service = MediaService()
    trace = SceneDebugTrace(
        scene_id=f"scene_{scene_order}",
        project_id=project_id,
        scene_order=scene_order,
        scene_db_id=scene.get("id"),
        narration=str(scene.get("narration_text") or ""),
    )
    trace.snapshot("replay_input_scene", scene, owner="debug_replay")
    trace.fingerprint("narration", scene.get("narration_text"))

    audio_path = Path(str(scene.get("audio_path") or Path(current_app.config["STORAGE_ROOT"]) / "debug-replay.wav"))
    audio_duration = float(scene.get("audio_duration_sec") or service._estimate_duration(str(scene.get("narration_text") or "")))

    if stage in {"numeric-provenance", "all"}:
        trace.data["numeric_provenance"] = numeric_role_map(str(scene.get("narration_text") or ""), scene_id=f"scene_{scene_order}").get("facts") or []
        trace.snapshot("replay_numeric_provenance", trace.data["numeric_provenance"], owner="debug_replay")

    if stage in {"script-governance", "all"}:
        trace.data["repetition"] = repetition_report([scene])
        trace.data["narrative_progression"] = narrative_progression_report([scene])
        trace.snapshot("replay_script_governance", trace.data["repetition"], owner="debug_replay")

    if stage in {"normalizer", "visual-director", "beat-expansion", "scene-builder", "render-spec", "frame-probe", "validator", "concept-isolation", "integrity-validator", "all"}:
        section = service._section_for_scene_render(scene, audio_duration, audio_path, debug_trace=trace)
        trace.snapshot("replay_section", section, owner="debug_replay")

    if stage in {"concept-isolation", "integrity-validator", "all"}:
        target = section if "section" in locals() else scene
        trace.data["scene_density"] = scene_density_report(target)
        trace.data["educational_integrity"] = educational_integrity_report(target)
        trace.data["concept_policy"] = trace.data["educational_integrity"].get("concept_policy") or {}
        trace.snapshot("replay_integrity_governance", {"density": trace.data["scene_density"], "integrity": trace.data["educational_integrity"]}, owner="debug_replay")

    scene_result: dict[str, Any] | None = None
    if stage in {"scene-builder", "render-spec", "frame-probe", "validator", "all"}:
        scene_result = build_scenes([section], debug_trace=trace)["scenes"][0]
        trace.snapshot("replay_scene_builder_output", scene_result, owner="debug_replay")

    if stage in {"render-spec", "all"} and scene_result is not None:
        spec = RenderSpec(
            composition="VideoRenderer",
            props={"scenes": [scene_result]},
            duration_sec=float(scene_result.get("duration") or 0),
            source="remotion_scene_builder",
        )
        trace.snapshot("replay_render_spec", {"composition": spec.composition, "props": spec.props, "duration_sec": spec.duration_sec, "source": spec.source}, owner="debug_replay")
        trace.determinism("replay_render_spec", scene_result, {"composition": spec.composition, "duration_sec": spec.duration_sec, "source": spec.source})

    if stage in {"frame-probe", "all"} and scene_result is not None:
        probe = frame_probe(scene_result, frame)
        trace.data["frame_debug"].append(probe)
        trace.snapshot("replay_frame_probe", probe, owner="debug_replay")

    if stage in {"validator"} and scene_result is not None:
        trace.validate_scene(scene_result)

    trace.event("debug_replay", "completed", {"stage": stage, "output_hash": stable_hash(trace.to_dict())})
    return SceneDebugStore().save(trace, replay_stage=stage)


if __name__ == "__main__":
    main()
