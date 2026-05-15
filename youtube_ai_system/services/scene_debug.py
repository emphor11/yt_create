from __future__ import annotations

from dataclasses import dataclass, field
import re
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context

from ..observability.scene_debug_files import SceneDebugFileStore
from ..observability.scene_debug_support import (
    TRACE_FIELDS,
    debug_video_pipeline_enabled,
    elapsed_ms,
    safe_json,
    stable_hash,
    stage_timer,
    utcnow,
)
from ..observability.scene_debug_validation import (
    field_view as _field_view,
    frame_probe,
    latest_snapshot_field as _latest_snapshot_field,
    renderer_sequence,
    stale_stages_for,
    validate_visual_contract,
)
from .financial_governance import educational_integrity_report, narrative_progression_report, repetition_report, scene_density_report


@dataclass
class SceneDebugTrace:
    scene_id: str
    narration: str = ""
    project_id: int | None = None
    scene_order: int | None = None
    scene_db_id: int | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.data.setdefault("trace_version", 3)
        self.data.setdefault("created_at", utcnow())
        self.data.setdefault("updated_at", utcnow())
        self.data.setdefault("scene_id", self.scene_id)
        self.data.setdefault("project_id", self.project_id)
        self.data.setdefault("scene_order", self.scene_order)
        self.data.setdefault("scene_db_id", self.scene_db_id)
        self.data.setdefault("narration", self.narration)
        for key in (
            "groq",
            "scene_refiner",
            "normalizer",
            "story_pipeline",
            "visual_director",
            "beat_expansion",
            "scene_builder",
            "render_spec",
            "renderer",
        ):
            self.data.setdefault(key, {})
        for key in (
            "events",
            "snapshots",
            "ownership_graph",
            "lineage_graph",
            "diffs",
            "confidence",
            "fallbacks",
            "warnings",
            "errors",
            "frame_debug",
        ):
            self.data.setdefault(key, [] if key != "lineage_graph" else {"nodes": [], "edges": []})
        self.data.setdefault("metrics", {})
        for key in (
            "numeric_provenance",
            "concept_policy",
            "repetition",
            "scene_density",
            "narrative_progression",
            "educational_integrity",
        ):
            self.data.setdefault(key, [] if key == "numeric_provenance" else {})
        self.data.setdefault("validation", {"status": "healthy", "warnings": [], "errors": []})
        self.data.setdefault("invalidation", {"fingerprints": {}, "stale": []})
        self.data.setdefault("determinism", [])
        self._owners: dict[str, str] = dict(self.data.get("_owners") or {})
        self._last_values: dict[str, Any] = dict(self.data.get("_last_values") or {})

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SceneDebugTrace":
        trace = cls(
            scene_id=str(payload.get("scene_id") or ""),
            narration=str(payload.get("narration") or ""),
            project_id=payload.get("project_id"),
            scene_order=payload.get("scene_order"),
            scene_db_id=payload.get("scene_db_id"),
            data=dict(payload),
        )
        return trace

    def to_dict(self) -> dict[str, Any]:
        self.data["updated_at"] = utcnow()
        self.data["_owners"] = dict(self._owners)
        self.data["_last_values"] = safe_json(self._last_values)
        return safe_json(self.data)

    def event(self, stage: str, status: str, payload: Any = None, *, duration_ms: int | None = None) -> None:
        event = {"at": utcnow(), "stage": stage, "status": status, "payload": safe_json(payload or {})}
        if duration_ms is not None:
            event["duration_ms"] = duration_ms
            self.data["metrics"][f"{stage}.duration_ms"] = duration_ms
        self.data["events"].append(event)
        self._structured_log(stage, event)

    def snapshot(self, stage: str, state: Any, *, owner: str = "", note: str = "") -> None:
        snapshot = {
            "at": utcnow(),
            "stage": stage,
            "owner": owner,
            "note": note,
            "full_scene_state": safe_json(state),
            "fingerprint": stable_hash(state),
        }
        self.data["snapshots"].append(snapshot)
        self.fingerprint(stage, state)

    def ownership(self, field: str, owner: str, value: Any, reason: str) -> None:
        if field not in TRACE_FIELDS:
            return
        previous_owner = self._owners.get(field)
        old_value = self._last_values.get(field)
        safe_value = safe_json(value)
        changed = stable_hash(old_value) != stable_hash(safe_value)
        owner_changed = previous_owner is not None and previous_owner != owner
        if changed or owner_changed or previous_owner is None:
            self.data["ownership_graph"].append(
                {
                    "at": utcnow(),
                    "field": field,
                    "previous_owner": previous_owner,
                    "new_owner": owner,
                    "change_reason": reason,
                    "old_value": safe_json(old_value),
                    "new_value": safe_value,
                }
            )
        self._owners[field] = owner
        self._last_values[field] = safe_value

    def diff(self, stage: str, before: Any, after: Any, *, fields: tuple[str, ...] = TRACE_FIELDS) -> None:
        before_map = _field_view(before)
        after_map = _field_view(after)
        rows = []
        for field in fields:
            old = before_map.get(field)
            new = after_map.get(field)
            if stable_hash(old) != stable_hash(new):
                rows.append(
                    {
                        "field": field,
                        "before": safe_json(old),
                        "after": safe_json(new),
                        "owner": self._owners.get(field),
                    }
                )
        if rows:
            self.data["diffs"].append({"at": utcnow(), "stage": stage, "rows": rows})

    def confidence(self, stage: str, field: str, value: Any, score: float, reasons: list[str] | None = None) -> None:
        score = max(0.0, min(float(score), 1.0))
        record = {
            "at": utcnow(),
            "stage": stage,
            "field": field,
            "value": safe_json(value),
            "score": round(score, 3),
            "reasons": reasons or [],
        }
        self.data["confidence"].append(record)
        if score < 0.5:
            self.warning(stage, f"Low-confidence {field}: {value}", {"score": score, "reasons": reasons or []})

    def fallback(self, stage: str, source: str, reason: str, original_input: Any, fallback_output: Any) -> None:
        record = {
            "at": utcnow(),
            "stage": stage,
            "fallback_used": True,
            "fallback_source": source,
            "fallback_reason": reason,
            "original_input": safe_json(original_input),
            "fallback_output": safe_json(fallback_output),
        }
        self.data["fallbacks"].append(record)
        self.warning(stage, f"Fallback used: {source} ({reason})", record)

    def warning(self, stage: str, message: str, payload: Any = None) -> None:
        record = {"at": utcnow(), "stage": stage, "message": message, "payload": safe_json(payload or {})}
        self.data["warnings"].append(record)
        self.data["validation"]["warnings"].append(record)
        if self.data["validation"].get("status") == "healthy":
            self.data["validation"]["status"] = "warning"

    def error(self, stage: str, message: str, payload: Any = None) -> None:
        record = {"at": utcnow(), "stage": stage, "message": message, "payload": safe_json(payload or {})}
        self.data["errors"].append(record)
        self.data["validation"]["errors"].append(record)
        self.data["validation"]["status"] = "error"

    def lineage_node(
        self,
        node_id: str,
        node_type: str,
        stage: str,
        label: str,
        value: Any,
        *,
        owner: str = "",
        confidence: float | None = None,
        source_ids: list[str] | None = None,
    ) -> str:
        node = {
            "id": node_id,
            "type": node_type,
            "stage": stage,
            "label": label,
            "value": safe_json(value),
            "owner": owner,
            "confidence": confidence,
            "source_ids": source_ids or [],
        }
        nodes = self.data["lineage_graph"]["nodes"]
        existing = next((item for item in nodes if item.get("id") == node_id), None)
        if existing:
            existing.update(node)
        else:
            nodes.append(node)
        return node_id

    def lineage_edge(self, source_id: str, target_id: str, reason: str) -> None:
        edge = {"source": source_id, "target": target_id, "reason": reason}
        edges = self.data["lineage_graph"]["edges"]
        if edge not in edges:
            edges.append(edge)

    def fingerprint(self, name: str, value: Any) -> str:
        digest = stable_hash(value)
        fingerprints = self.data["invalidation"]["fingerprints"]
        previous = fingerprints.get(name)
        if previous and previous != digest:
            self.data["invalidation"]["stale"].append(
                {
                    "at": utcnow(),
                    "changed": name,
                    "old_hash": previous,
                    "new_hash": digest,
                    "stale_stages": stale_stages_for(name),
                }
            )
        fingerprints[name] = digest
        return digest

    def determinism(self, stage: str, input_value: Any, output_value: Any, *, deterministic: bool = True) -> None:
        self.data["determinism"].append(
            {
                "at": utcnow(),
                "stage": stage,
                "input_hash": stable_hash(input_value),
                "output_hash": stable_hash(output_value),
                "deterministic": bool(deterministic),
            }
        )

    def frame_probe(self, scene: dict[str, Any], frame: int, fps: int = 30) -> dict[str, Any]:
        probe = frame_probe(scene, frame, fps)
        self.data["frame_debug"].append(probe)
        beat_id = probe.get("active_beat_lineage_id")
        component_id = probe.get("component_lineage_id")
        if beat_id and component_id:
            self.lineage_edge(str(beat_id), str(component_id), "component_selected_for_active_frame")
        return probe

    def validate_scene(self, scene: dict[str, Any]) -> None:
        density = scene_density_report(scene)
        integrity = educational_integrity_report(scene)
        self.data["scene_density"] = density
        self.data["educational_integrity"] = integrity
        self.data["narrative_progression"] = narrative_progression_report([scene])
        self.data["numeric_provenance"] = integrity.get("numeric_facts") or []
        self.data["concept_policy"] = integrity.get("concept_policy") or {}
        if integrity.get("confidence") is not None:
            self.confidence("educational_integrity", "visual_plan_integrity", integrity.get("status"), float(integrity.get("confidence") or 0), ["numeric provenance", "concept isolation"])
        for warning in density.get("warnings") or []:
            self.warning("scene_density_validator", warning["message"], warning)
        for warning in integrity.get("warnings") or []:
            self.warning("educational_integrity_validator", warning["message"], warning)
        for warning in validate_visual_contract(scene, self.data.get("fallbacks") or [], self.data.get("invalidation") or {}):
            self.warning("visual_contract_validator", warning["message"], warning)
        self.snapshot("visual_contract_validation", self.data.get("validation"), owner="visual_contract_validator")

    def _structured_log(self, stage: str, event: dict[str, Any]) -> None:
        if not has_app_context():
            return
        try:
            payload = event.get("payload") or {}
            current_app.logger.info(
                "[SceneDebug] scene=%s stage=%s fallback=%s duration_ms=%s input_hash=%s output_hash=%s",
                self.scene_order,
                stage,
                bool((payload or {}).get("fallback_used")),
                event.get("duration_ms", ""),
                (payload or {}).get("input_hash", ""),
                (payload or {}).get("output_hash", ""),
            )
        except Exception:
            pass


class SceneDebugStore:
    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            storage_root = Path(current_app.config["STORAGE_ROOT"]).expanduser().resolve()
            root = storage_root / "debug_traces"
        self.root = Path(root)
        self.files = SceneDebugFileStore(self.root)

    def project_dir(self, project_id: int) -> Path:
        return self.files.project_dir(project_id)

    def scene_path(self, project_id: int, scene_order: int, *, replay_stage: str = "") -> Path:
        return self.files.scene_path(project_id, scene_order, replay_stage=replay_stage)

    def save(self, trace: SceneDebugTrace, *, replay_stage: str = "") -> Path:
        if trace.project_id is None or trace.scene_order is None:
            raise ValueError("Trace needs project_id and scene_order before it can be saved.")
        path = self.files.write_scene_payload(
            int(trace.project_id),
            int(trace.scene_order),
            trace.to_dict(),
            replay_stage=replay_stage,
        )
        self._write_index(int(trace.project_id))
        return path

    def load(self, project_id: int, scene_order: int, *, replay_stage: str = "") -> SceneDebugTrace | None:
        payload = self.files.read_scene_payload(project_id, scene_order, replay_stage=replay_stage)
        return SceneDebugTrace.from_dict(payload) if payload is not None else None

    def load_latest(self, project_id: int, scene_order: int) -> SceneDebugTrace | None:
        payload = self.files.read_latest_scene_payload(project_id, scene_order)
        return SceneDebugTrace.from_dict(payload) if payload is not None else None

    def list_project(self, project_id: int) -> list[dict[str, Any]]:
        traces = []
        for path, payload in self.files.read_project_payloads(project_id):
            validation = payload.get("validation") or {}
            traces.append(
                {
                    "path": str(path),
                    "file": path.name,
                    "scene_order": payload.get("scene_order"),
                    "scene_id": payload.get("scene_id"),
                    "health": validation.get("status", "unknown"),
                    "warnings": len(payload.get("warnings") or []),
                    "errors": len(payload.get("errors") or []),
                    "pattern": _latest_snapshot_field(payload, "pattern"),
                    "components": _latest_snapshot_field(payload, "component_sequence"),
                    "updated_at": payload.get("updated_at"),
                }
            )
        return traces

    def _write_index(self, project_id: int) -> None:
        self.files.write_index(project_id, self.list_project(project_id))


def new_trace_for_scene(project_id: int, scene: dict[str, Any]) -> SceneDebugTrace | None:
    if not debug_video_pipeline_enabled():
        return None
    scene_order = int(scene.get("scene_order") or scene.get("scene_index") or 0)
    trace = SceneDebugStore().load(project_id, scene_order) or SceneDebugTrace(
        scene_id=f"scene_{scene_order}",
        project_id=project_id,
        scene_order=scene_order,
        scene_db_id=scene.get("id"),
        narration=str(scene.get("narration_text") or scene.get("narration") or ""),
    )
    trace.project_id = project_id
    trace.scene_order = scene_order
    trace.scene_db_id = scene.get("id")
    trace.scene_id = f"scene_{scene_order}"
    trace.narration = str(scene.get("narration_text") or scene.get("narration") or trace.narration or "")
    trace.data["project_id"] = project_id
    trace.data["scene_order"] = scene_order
    trace.data["scene_db_id"] = scene.get("id")
    trace.data["scene_id"] = f"scene_{scene_order}"
    trace.data["narration"] = trace.narration
    trace.ownership("narration", "scene_db", trace.narration, "scene row narration")
    trace.lineage_node(f"sentence:{scene_order}:all", "narration", "scene_db", "Scene narration", trace.narration, owner="scene_db", confidence=1.0)
    for index, sentence in enumerate(split_sentences(trace.narration)):
        node_id = f"sentence:{scene_order}:{index}"
        trace.lineage_node(node_id, "narration_sentence", "scene_db", f"Sentence {index + 1}", sentence, owner="scene_db", confidence=1.0)
        trace.lineage_edge(f"sentence:{scene_order}:all", node_id, "sentence_split")
    trace.snapshot("scene_db_pre_render", scene, owner="scene_db")
    return trace


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", str(text or "").strip()) if part.strip()]


def confidence_for_mechanism(section: dict[str, Any], mechanism: str) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.35
    visual_scene = section.get("visual_scene") if isinstance(section.get("visual_scene"), dict) else {}
    if visual_scene.get("mechanism"):
        score += 0.35
        reasons.append("explicit visual_scene mechanism")
    if section.get("mechanism") or section.get("concept_type"):
        score += 0.2
        reasons.append("explicit section mechanism/concept_type")
    narration = str(section.get("text") or section.get("narration") or "")
    if mechanism and mechanism.replace("_", " ") in narration.lower():
        score += 0.15
        reasons.append("mechanism phrase appears in narration")
    if not reasons:
        reasons.append("keyword/default inference")
    return min(score, 0.98), reasons


def confidence_for_finance_concept(finance_concept: dict[str, Any]) -> tuple[float, list[str]]:
    raw = finance_concept.get("confidence")
    reasons = ["finance concept extractor"]
    try:
        score = float(raw)
        if score > 1:
            score = score / 100
    except (TypeError, ValueError):
        score = 0.55 if finance_concept.get("concept_name") and finance_concept.get("concept_name") != "Unknown" else 0.3
        reasons.append("heuristic confidence")
    if finance_concept.get("start_value") or finance_concept.get("end_value") or finance_concept.get("percentage"):
        score = min(score + 0.15, 1.0)
        reasons.append("numeric evidence")
    return max(0.0, min(score, 1.0)), reasons
