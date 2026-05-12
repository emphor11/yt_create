from __future__ import annotations

from copy import deepcopy
from typing import Any


SCHEMA_VERSION = "shot_director_v1"


class ShotDirector:
    """Derives intra-scene shot choreography from timed semantic beats."""

    STATE_SHOT_MAP = {
        "centered_focus": {
            "shot_type": "wide_context",
            "focus_target": "salary_income",
            "framing_profile": "stable_wide",
            "composition_emphasis": "source_context",
            "attention_weight": 0.58,
        },
        "pressure_cluster": {
            "shot_type": "pressure_closeup",
            "focus_target": "expense_group",
            "framing_profile": "compressed_push",
            "composition_emphasis": "drain_pressure",
            "attention_weight": 0.86,
        },
        "isolate_survivor": {
            "shot_type": "survivor_isolation",
            "focus_target": "remaining_balance",
            "framing_profile": "isolated_hold",
            "composition_emphasis": "aftermath_focus",
            "attention_weight": 0.92,
        },
        "optimistic_seed": {
            "shot_type": "wide_context",
            "focus_target": "monthly_sip",
            "framing_profile": "open_seed",
            "composition_emphasis": "disciplined_start",
            "attention_weight": 0.56,
        },
        "growth_acceleration": {
            "shot_type": "upward_momentum",
            "focus_target": "corpus_growth",
            "framing_profile": "upward_push",
            "composition_emphasis": "growth_velocity",
            "attention_weight": 0.78,
        },
        "layered_growth": {
            "shot_type": "focused_growth",
            "focus_target": "compounding_layers",
            "framing_profile": "vertical_dominance",
            "composition_emphasis": "accumulation_stack",
            "attention_weight": 0.88,
        },
        "awe_reveal": {
            "shot_type": "reward_hero",
            "focus_target": "final_corpus",
            "framing_profile": "hero_reward",
            "composition_emphasis": "wealth_reveal",
            "attention_weight": 0.98,
        },
    }

    ACTION_SHOT_MAP = {
        "salary_arrives": "wide_context",
        "expense_drains": "pressure_closeup",
        "balance_revealed": "survivor_isolation",
        "contribution_starts": "wide_context",
        "return_rate_activates": "upward_momentum",
        "time_extends": "upward_momentum",
        "contributions_accumulate": "focused_growth",
        "corpus_revealed": "reward_hero",
    }

    COMPONENT_SHOT_MAP = {
        "StatCard": "wide_context",
        "ConceptCard": "emotional_pause",
        "ConceptCardScene": "emotional_pause",
        "HighlightText": "emotional_pause",
        "RiskCard": "pressure_closeup",
        "RiskCardScene": "pressure_closeup",
        "CalculationStrip": "focused_growth",
        "FlowBar": "focused_growth",
        "FlowDiagram": "focused_growth",
        "BalanceBar": "survivor_isolation",
        "SplitComparison": "comparison_focus",
        "SplitComparisonScene": "comparison_focus",
        "StepFlow": "focused_growth",
        "StepFlowScene": "focused_growth",
        "GrowthChart": "upward_momentum",
        "GrowthChartScene": "upward_momentum",
        "MoneyFlowDiagram": "pressure_closeup",
        "DebtSpiralVisualizer": "pressure_closeup",
        "SIPGrowthEngine": "upward_momentum",
        "InflationErosionVisualizer": "pressure_closeup",
        "LifestyleCreepVisualizer": "pressure_closeup",
        "EMIStackVisualizer": "pressure_closeup",
        "FOMOPriceCrashVisualizer": "pressure_closeup",
        "PortfolioDiversificationVisualizer": "comparison_focus",
        "SmallLeaksAccumulator": "pressure_closeup",
        "CinematicScene": "emotional_pause",
    }

    def build_sequence(self, timed_beats: list[dict[str, Any]], *, fps: int = 30) -> dict[str, Any] | None:
        shots = [
            self._shot_from_beat(beat, index, fps=fps)
            for index, beat in enumerate(timed_beats)
        ]
        shots = [shot for shot in shots if shot]
        if not shots:
            return None
        return {
            "source": SCHEMA_VERSION,
            "shots": shots,
            "shot_count": len(shots),
            "fps": fps,
        }

    def attach_to_beats(self, timed_beats: list[dict[str, Any]], shot_sequence: dict[str, Any] | None) -> list[dict[str, Any]]:
        shots = list((shot_sequence or {}).get("shots") or [])
        if not shots:
            return timed_beats
        enriched: list[dict[str, Any]] = []
        for beat in timed_beats:
            next_beat = dict(beat)
            shot = self._shot_for_beat(next_beat, shots)
            if shot:
                next_beat["active_shot"] = shot
                data = next_beat.get("data")
                if isinstance(data, dict):
                    next_beat["data"] = {**data, "active_shot": shot}
            enriched.append(next_beat)
        return enriched

    def _shot_from_beat(self, beat: dict[str, Any], beat_index: int, *, fps: int) -> dict[str, Any] | None:
        action = self._active_action(beat)
        visual_state = self._visual_state(beat)
        action_name = str((action or {}).get("action") or "")
        state_type = str((visual_state or {}).get("state_type") or "")
        template = dict(self.STATE_SHOT_MAP.get(state_type) or {})
        if not template:
            shot_type = self.ACTION_SHOT_MAP.get(action_name) or self._fallback_shot_type(beat)
            template = self._template_for_shot_type(shot_type, action, visual_state)
        window = self._frame_window(beat, fps=fps)
        overlap_group = self._overlap_group(beat, visual_state)
        shot = {
            **template,
            "composition_window": window,
            "start_frame": window["start_frame"],
            "end_frame": window["end_frame"],
            "derived_from_action": action_name,
            "derived_from_state": state_type,
            "component": str(beat.get("component") or ""),
            "overlap_group": overlap_group,
            "source_beat_indices": [beat_index],
            "source_action_ids": [str(action.get("id") or "")] if action and action.get("id") else [],
            "shot_index": beat_index,
        }
        return shot

    def _template_for_shot_type(
        self,
        shot_type: str,
        action: dict[str, Any] | None,
        visual_state: dict[str, Any] | None,
    ) -> dict[str, Any]:
        focus = str((visual_state or {}).get("focus_entity") or (action or {}).get("semantic_role") or "semantic_value")
        if focus == "semantic_value":
            focus = str((visual_state or {}).get("focus_target") or "active_beat")
        defaults = {
            "wide_context": ("stable_wide", "context_first", 0.56),
            "focused_growth": ("growth_focus", "compound_hierarchy", 0.84),
            "pressure_closeup": ("compressed_push", "pressure_focus", 0.86),
            "survivor_isolation": ("isolated_hold", "aftermath_focus", 0.92),
            "reward_hero": ("hero_reward", "wealth_reveal", 0.98),
            "comparison_focus": ("split_attention", "contrast_focus", 0.76),
            "upward_momentum": ("upward_push", "growth_velocity", 0.78),
            "emotional_pause": ("slow_hold", "reflection_focus", 0.82),
        }
        framing, emphasis, weight = defaults.get(shot_type, defaults["wide_context"])
        return {
            "shot_type": shot_type,
            "focus_target": focus,
            "framing_profile": framing,
            "composition_emphasis": emphasis,
            "attention_weight": weight,
        }

    def _fallback_shot_type(self, beat: dict[str, Any]) -> str:
        phase = str(beat.get("beat_phase") or "").strip()
        component = str(beat.get("component") or "").strip()
        role = str(beat.get("beat_role") or beat.get("emphasis") or "").strip()
        component_default = self.COMPONENT_SHOT_MAP.get(component)
        if phase in {"corpus", "remainder", "consequence"}:
            return "reward_hero" if component in {"SIPGrowthEngine", "GrowthChart", "GrowthChartScene"} else "survivor_isolation"
        if phase in {"drain", "pressure", "stacking"}:
            return "pressure_closeup"
        if phase in {"growth", "contribution"}:
            return "upward_momentum"
        if role in {"result", "punch"}:
            if component in {"GrowthChart", "GrowthChartScene", "SIPGrowthEngine"}:
                return "reward_hero"
            return component_default or "emotional_pause"
        if role == "hero":
            if component in {"GrowthChart", "GrowthChartScene", "SIPGrowthEngine"}:
                return "reward_hero"
            if component in {"ConceptCard", "ConceptCardScene", "HighlightText", "CinematicScene"}:
                return "emotional_pause"
            return component_default or "emotional_pause"
        if role in {"process", "change"}:
            return component_default or "focused_growth"
        if component_default:
            return component_default
        return "wide_context"

    def _shot_for_beat(self, beat: dict[str, Any], shots: list[dict[str, Any]]) -> dict[str, Any] | None:
        start_frame = int(round(float(beat.get("start_time") or 0.0) * 30))
        end_frame = int(round(float(beat.get("end_time") or 0.0) * 30))
        action = self._active_action(beat)
        action_id = str((action or {}).get("id") or "")
        try:
            sequence_index = int((action or {}).get("sequence_index"))
        except (TypeError, ValueError):
            sequence_index = -1
        for shot in shots:
            if action_id and action_id in (shot.get("source_action_ids") or []):
                return deepcopy(shot)
            if sequence_index in (shot.get("source_beat_indices") or []):
                return deepcopy(shot)
        return next((deepcopy(shot) for shot in shots if self._overlaps(start_frame, end_frame, shot)), None)

    def _frame_window(self, beat: dict[str, Any], *, fps: int) -> dict[str, int]:
        try:
            start_frame = int(round(float(beat.get("start_time") or 0.0) * fps))
            end_frame = int(round(float(beat.get("end_time") or 0.0) * fps))
        except (TypeError, ValueError):
            start_frame = 0
            end_frame = 0
        return {"start_frame": start_frame, "end_frame": max(end_frame, start_frame + 1)}

    def _overlaps(self, start_frame: int, end_frame: int, shot: dict[str, Any]) -> bool:
        return start_frame < int(shot.get("end_frame") or 0) and end_frame > int(shot.get("start_frame") or 0)

    def _active_action(self, beat: dict[str, Any]) -> dict[str, Any] | None:
        data = beat.get("data") if isinstance(beat.get("data"), dict) else {}
        action = data.get("active_action") if isinstance(data.get("active_action"), dict) else None
        return dict(action) if action else None

    def _visual_state(self, beat: dict[str, Any]) -> dict[str, Any] | None:
        direct = beat.get("visual_state") if isinstance(beat.get("visual_state"), dict) else None
        if direct:
            return dict(direct)
        data = beat.get("data") if isinstance(beat.get("data"), dict) else {}
        state = data.get("visual_state") if isinstance(data.get("visual_state"), dict) else None
        return dict(state) if state else None

    def _overlap_group(self, beat: dict[str, Any], visual_state: dict[str, Any] | None) -> str:
        if visual_state and visual_state.get("overlap_group"):
            return str(visual_state.get("overlap_group") or "")
        timing = beat.get("semantic_timing") if isinstance(beat.get("semantic_timing"), dict) else {}
        if timing.get("overlap_group"):
            return str(timing.get("overlap_group") or "")
        data = beat.get("data") if isinstance(beat.get("data"), dict) else {}
        choreography = data.get("action_choreography") if isinstance(data.get("action_choreography"), dict) else {}
        return str(choreography.get("overlap_group") or "")
