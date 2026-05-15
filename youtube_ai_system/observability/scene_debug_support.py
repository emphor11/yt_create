from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context


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
    "semantic_scene",
    "visual_action_graph",
    "visual_state_sequence",
    "visual_state",
    "shot_sequence",
    "active_shot",
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
    "RiskReturnVisualizer",
    "EmergencyFundVisualizer",
    "OutroRecapVisualizer",
    "CinematicScene",
    "UniversalMechanismRenderer",
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
    "risk_return": {"RiskReturnVisualizer", "SplitComparison", "RiskCard"},
    "emergency_fund": {"EmergencyFundVisualizer", "FlowDiagram"},
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
    "RiskReturnVisualizer": ("safe_asset", "growth_asset"),
    "EmergencyFundVisualizer": ("buffer_label", "shock_label"),
    "UniversalMechanismRenderer": ("cinematic_events",),
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
            result[key_text] = "[redacted]" if _is_secret_key(key_text) else safe_json(child)
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


def short_label(value: Any, fallback: str = "") -> str:
    if isinstance(value, dict):
        for key in ("concept_name", "concept_type", "pattern", "mechanism", "component", "text", "label"):
            if value.get(key):
                return str(value.get(key))
        return fallback or "object"
    if isinstance(value, list):
        return f"{len(value)} item(s)"
    text = str(value or fallback or "").strip()
    return text[:90] if len(text) > 90 else text
