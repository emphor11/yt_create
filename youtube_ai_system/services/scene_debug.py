from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context

from .financial_governance import educational_integrity_report, narrative_progression_report, repetition_report, scene_density_report


TRACE_FIELDS = (
    "narration",
    "visual_scene",
    "mechanism",
    "visual_intent",
    "visual_beats",
    "numbers",
    "emotion",
    "concept_type",
    "visual_plan",
    "pattern",
    "data",
    "beats",
    "timed_beats",
    "component",
)

TEXT_COMPONENTS = {"StatCard", "HighlightText", "ConceptCard", "ConceptCardScene", "RiskCard", "RiskCardScene"}
RENDERER_COMPONENTS = {
    "StatCard",
    "CalculationStrip",
    "ConceptCard",
    "ConceptCardScene",
    "HighlightText",
    "FlowBar",
    "FlowDiagram",
    "SplitComparison",
    "SplitComparisonScene",
    "StepFlow",
    "StepFlowScene",
    "GrowthChart",
    "GrowthChartScene",
    "InflationErosionVisualizer",
    "LifestyleCreepVisualizer",
    "RiskCard",
    "RiskCardScene",
    "BalanceBar",
    "MoneyFlowDiagram",
    "DebtSpiralVisualizer",
    "SIPGrowthEngine",
    "EMIStackVisualizer",
    "FOMOPriceCrashVisualizer",
    "PortfolioDiversificationVisualizer",
    "SmallLeaksAccumulator",
    "CinematicScene",
}

MECHANISM_COMPONENTS = {
    "salary_drain": {"MoneyFlowDiagram", "FlowDiagram"},
    "lifestyle_inflation": {"LifestyleCreepVisualizer"},
    "emi_pressure": {"EMIStackVisualizer"},
    "emi_stack": {"EMIStackVisualizer"},
    "debt_trap": {"DebtSpiralVisualizer", "CalculationStrip"},
    "inflation_erosion": {"InflationErosionVisualizer"},
    "sip_growth": {"SIPGrowthEngine", "GrowthChart"},
    "compounding": {"SIPGrowthEngine", "GrowthChart"},
    "risk_return": {"SplitComparison", "RiskCard"},
    "diversification": {"PortfolioDiversificationVisualizer"},
    "speculation_risk": {"FOMOPriceCrashVisualizer"},
    "fomo_risk": {"FOMOPriceCrashVisualizer"},
    "expense_leakage": {"SmallLeaksAccumulator"},
    "subscription_leak": {"SmallLeaksAccumulator"},
}

REQUIRED_BEAT_DATA = {
    "MoneyFlowDiagram": ("source", "flows", "remainder"),
    "DebtSpiralVisualizer": ("principal", "monthly_interest"),
    "SIPGrowthEngine": ("monthly_sip", "final_corpus"),
    "InflationErosionVisualizer": ("start", "end"),
    "LifestyleCreepVisualizer": ("start_income", "end_income"),
    "EMIStackVisualizer": ("salary", "emis", "remaining"),
    "FOMOPriceCrashVisualizer": ("points",),
    "PortfolioDiversificationVisualizer": ("assets",),
    "SmallLeaksAccumulator": ("leaks", "monthly_loss"),
    "CalculationStrip": ("steps",),
    "SplitComparison": ("left", "right"),
}


def debug_video_pipeline_enabled() -> bool:
    if not has_app_context():
        return False
    return bool(current_app.config.get("DEBUG_VIDEO_PIPELINE", False))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, str):
            return _redact(value)
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if _is_secret_key(key_text):
                result[key_text] = "[redacted]"
            else:
                result[key_text] = safe_json(child)
        return result
    if isinstance(value, (list, tuple, set)):
        return [safe_json(item) for item in value]
    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            return safe_json(value.to_dict())
        except Exception:
            return str(value)
    if hasattr(value, "__dict__"):
        try:
            return safe_json(vars(value))
        except Exception:
            return str(value)
    return str(value)


def stable_hash(value: Any) -> str:
    payload = json.dumps(safe_json(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def stage_timer() -> float:
    return time.perf_counter()


def elapsed_ms(started_at: float) -> int:
    return int(round((time.perf_counter() - started_at) * 1000))


def _redact(value: str) -> str:
    if len(value) > 24 and re.search(r"(api[_-]?key|bearer|token|secret)", value, re.IGNORECASE):
        return "[redacted]"
    return value


def _is_secret_key(key: str) -> bool:
    return bool(re.search(r"(api[_-]?key|authorization|bearer|token|secret|password)", key, re.IGNORECASE))


def _short_label(value: Any, fallback: str = "") -> str:
    if isinstance(value, dict):
        for key in ("concept_name", "concept_type", "pattern", "mechanism", "component", "text", "label"):
            if value.get(key):
                return str(value.get(key))
        return fallback or "object"
    if isinstance(value, list):
        return f"{len(value)} item(s)"
    text = str(value or fallback or "").strip()
    return text[:90] if len(text) > 90 else text


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

    def project_dir(self, project_id: int) -> Path:
        return self.root / f"project-{int(project_id)}"

    def scene_path(self, project_id: int, scene_order: int, *, replay_stage: str = "") -> Path:
        name = f"scene-{int(scene_order):02d}.json" if not replay_stage else f"scene-{int(scene_order):02d}-replay-{replay_stage}.json"
        return self.project_dir(project_id) / name

    def save(self, trace: SceneDebugTrace, *, replay_stage: str = "") -> Path:
        if trace.project_id is None or trace.scene_order is None:
            raise ValueError("Trace needs project_id and scene_order before it can be saved.")
        path = self.scene_path(int(trace.project_id), int(trace.scene_order), replay_stage=replay_stage)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(trace.to_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        self._write_index(int(trace.project_id))
        return path

    def load(self, project_id: int, scene_order: int, *, replay_stage: str = "") -> SceneDebugTrace | None:
        path = self.scene_path(project_id, scene_order, replay_stage=replay_stage)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return SceneDebugTrace.from_dict(payload)

    def load_latest(self, project_id: int, scene_order: int) -> SceneDebugTrace | None:
        trace = self.load(project_id, scene_order)
        if trace is not None:
            return trace
        project_dir = self.project_dir(project_id)
        candidates = sorted(
            project_dir.glob(f"scene-{int(scene_order):02d}*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in candidates:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            return SceneDebugTrace.from_dict(payload)
        return None

    def list_project(self, project_id: int) -> list[dict[str, Any]]:
        project_dir = self.project_dir(project_id)
        if not project_dir.exists():
            return []
        traces = []
        for path in sorted(project_dir.glob("scene-*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
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
        project_dir = self.project_dir(project_id)
        index_path = project_dir / "index.json"
        index_path.write_text(
            json.dumps({"project_id": project_id, "updated_at": utcnow(), "scenes": self.list_project(project_id)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


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


def validate_visual_contract(scene: dict[str, Any], fallbacks: list[dict[str, Any]], invalidation: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    beats = scene.get("beats") or []
    concept_type = str(scene.get("concept_type") or "").strip()
    pattern = str(scene.get("pattern") or "").strip()
    duration = float(scene.get("duration") or scene.get("total_duration") or 0)
    narration = str(scene.get("narration") or scene.get("text") or "")
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


def _field_view(value: Any) -> dict[str, Any]:
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


def _latest_snapshot_field(payload: dict[str, Any], field: str) -> Any:
    for snapshot in reversed(payload.get("snapshots") or []):
        state = snapshot.get("full_scene_state")
        if isinstance(state, dict) and field in state:
            return state.get(field)
        if field == "component_sequence" and isinstance(state, dict) and state.get("beats"):
            return [str(beat.get("component") or "") for beat in state.get("beats") or []]
    return None
