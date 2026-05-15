from __future__ import annotations

from typing import Any

from .scene_debug_support import (
    MECHANISM_COMPONENTS,
    RENDERER_COMPONENTS,
    REQUIRED_BEAT_DATA,
    TEXT_COMPONENTS,
)


def validate_visual_contract(scene: dict[str, Any], fallbacks: list[dict[str, Any]], invalidation: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    beats = scene.get("beats") or []
    concept_type = str(scene.get("concept_type") or "").strip()
    pattern = str(scene.get("pattern") or "").strip()
    duration = float(scene.get("duration") or scene.get("total_duration") or 0)
    if not concept_type:
        warnings.append({"code": "missing_concept_type", "message": "Scene is missing concept_type."})
    expected = MECHANISM_COMPONENTS.get(concept_type)
    components = [str(beat.get("component") or "") for beat in beats]
    if expected and not any(component in expected for component in components + [pattern]):
        warnings.append(
            {
                "code": "component_mismatch",
                "message": f"Component mismatch with mechanism {concept_type}.",
                "expected": sorted(expected),
                "actual": components,
            }
        )
    if duration > 0 and beats:
        if len(beats) > max(8, int(duration / 1.1) + 1):
            warnings.append({"code": "beat_count_high", "message": "Beat count exceeds narration pacing.", "beat_count": len(beats), "duration": duration})
        total = sum(max(float(beat.get("end_time") or 0) - float(beat.get("start_time") or 0), 0) for beat in beats)
        text_total = sum(
            max(float(beat.get("end_time") or 0) - float(beat.get("start_time") or 0), 0)
            for beat in beats
            if str(beat.get("component") or "") in TEXT_COMPONENTS
        )
        if total > 0 and text_total / total > 0.4:
            warnings.append({"code": "text_dominance", "message": "Text-only components occupy too much scene duration.", "ratio": round(text_total / total, 3)})
    if len(fallbacks) > 2:
        warnings.append({"code": "fallback_chain_depth", "message": "Fallback chain depth > 2.", "fallback_count": len(fallbacks)})
    for index, beat in enumerate(beats):
        component = str(beat.get("component") or "")
        if component not in RENDERER_COMPONENTS:
            warnings.append({"code": "unsupported_component", "message": f"Unsupported component {component}; renderer will fallback.", "beat_index": index})
        required = REQUIRED_BEAT_DATA.get(component)
        if required:
            data = beat.get("data") if isinstance(beat.get("data"), dict) else {}
            missing = [field for field in required if field not in data]
            if missing:
                warnings.append({"code": "missing_component_data", "message": f"{component} missing required data fields.", "beat_index": index, "missing": missing})
    if invalidation.get("stale"):
        warnings.append({"code": "stale_fingerprints", "message": "Trace contains stale downstream stage fingerprints.", "stale": invalidation.get("stale")})
    transition_density = len(beats) / max(duration, 1.0) if duration else 0
    if transition_density > 0.8:
        warnings.append({"code": "transition_density", "message": "Transition density too high.", "density": round(transition_density, 3)})
    return warnings


def frame_probe(scene: dict[str, Any], frame: int, fps: int = 30) -> dict[str, Any]:
    beats = scene.get("beats") or []
    active_index = -1
    active_beat: dict[str, Any] | None = None
    for index, beat in enumerate(beats):
        start_frame = round(float(beat.get("start_time") or 0) * fps)
        end_frame = round(float(beat.get("end_time") or 0) * fps)
        if start_frame <= frame < end_frame:
            active_index = index
            active_beat = beat
            break
    if active_beat is None:
        return {
            "frame": frame,
            "time_sec": round(frame / fps, 3),
            "active_beat": None,
            "active_component": None,
            "fallback_component": None,
            "transition_state": "none",
            "progress": 0,
            "opacity": 0,
        }
    start_frame = round(float(active_beat.get("start_time") or 0) * fps)
    end_frame = round(float(active_beat.get("end_time") or 0) * fps)
    duration_frames = max(end_frame - start_frame, 1)
    frame_within = frame - start_frame
    progress = max(0.0, min(frame_within / duration_frames, 1.0))
    transition_state = "enter" if progress < 0.15 else ("exit" if progress > 0.85 else "hold")
    opacity = min(progress / 0.15, 1.0) if transition_state == "enter" else (max((1.0 - progress) / 0.15, 0.0) if transition_state == "exit" else 1.0)
    component = str(active_beat.get("component") or "ConceptCard")
    fallback_component = "ConceptCard" if component not in RENDERER_COMPONENTS else None
    return {
        "frame": frame,
        "time_sec": round(frame / fps, 3),
        "active_beat": active_index,
        "active_beat_lineage_id": active_beat.get("lineage_id") or f"beat:{active_index}",
        "active_component": component,
        "component_lineage_id": f"component:{active_index}:{component}",
        "fallback_component": fallback_component,
        "frame_within_beat": frame_within,
        "duration_frames": duration_frames,
        "transition_state": transition_state,
        "progress": round(progress, 4),
        "opacity": round(opacity, 4),
    }


def renderer_sequence(scene: dict[str, Any], fps: int = 30) -> dict[str, Any]:
    sequence = []
    for index, beat in enumerate(scene.get("beats") or []):
        component = str(beat.get("component") or "ConceptCard")
        start_frame = round(float(beat.get("start_time") or 0) * fps)
        end_frame = round(float(beat.get("end_time") or 0) * fps)
        sequence.append(
            {
                "beat_index": index,
                "component": component,
                "resolved_component": component if component in RENDERER_COMPONENTS else "ConceptCard",
                "fallback_used": component not in RENDERER_COMPONENTS,
                "start_frame": start_frame,
                "end_frame": end_frame,
            }
        )
    return {"fps": fps, "component_sequence": sequence}


def stale_stages_for(changed: str) -> list[str]:
    cascades = {
        "narration": ["normalizer", "story_pipeline", "visual_director", "beat_expansion", "scene_builder", "render_spec", "renderer"],
        "visual_scene": ["normalizer", "visual_director", "beat_expansion", "scene_builder", "render_spec", "renderer"],
        "normalizer_post": ["story_pipeline", "visual_director", "beat_expansion", "scene_builder", "render_spec", "renderer"],
        "story_pipeline_post_classification": ["visual_director", "beat_expansion", "scene_builder", "render_spec", "renderer"],
        "visual_director_post": ["beat_expansion", "scene_builder", "render_spec", "renderer"],
        "beat_expansion_post": ["scene_builder", "render_spec", "renderer"],
        "scene_builder_timeline": ["render_spec", "renderer"],
    }
    return cascades.get(changed, [])


def field_view(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result = dict(value)
    visual_plan = result.get("visual_plan") or []
    if visual_plan:
        first = visual_plan[0]
        visual = first.get("visual") or {}
        result.setdefault("pattern", visual.get("pattern"))
        result.setdefault("data", visual.get("data"))
        result.setdefault("beats", (first.get("beats") or {}).get("beats"))
    if result.get("beats"):
        result.setdefault("component", [str(beat.get("component") or "") for beat in result.get("beats") or []])
    return result


def latest_snapshot_field(payload: dict[str, Any], field: str) -> Any:
    for snapshot in reversed(payload.get("snapshots") or []):
        state = snapshot.get("full_scene_state")
        if isinstance(state, dict) and field in state:
            return state.get(field)
        if field == "component_sequence" and isinstance(state, dict) and state.get("beats"):
            return [str(beat.get("component") or "") for beat in state.get("beats") or []]
    return None
