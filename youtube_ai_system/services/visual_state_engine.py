from __future__ import annotations

from copy import deepcopy
from typing import Any


SCHEMA_VERSION = "visual_state_engine_v1"


class VisualStateEngine:
    """Derives compositional state evolution from timed semantic action beats."""

    ACTION_STATE_MAP = {
        "salary_arrives": {
            "state_type": "centered_focus",
            "focus_entity": "salary_income",
            "composition_density": "low",
            "emotional_posture": "optimistic",
            "framing": "wide",
            "transition_behavior": "soft_enter",
        },
        "expense_drains": {
            "state_type": "pressure_cluster",
            "focus_entity": "expense_group",
            "composition_density": "high",
            "emotional_posture": "pressure",
            "framing": "tight",
            "transition_behavior": "compression_shift",
        },
        "balance_revealed": {
            "state_type": "isolate_survivor",
            "focus_entity": "remaining_balance",
            "composition_density": "minimal",
            "emotional_posture": "reflection",
            "framing": "isolated",
            "transition_behavior": "slow_hold",
        },
        "contribution_starts": {
            "state_type": "optimistic_seed",
            "focus_entity": "monthly_sip",
            "composition_density": "low",
            "emotional_posture": "optimistic",
            "framing": "wide",
            "transition_behavior": "seed_enter",
        },
        "return_rate_activates": {
            "state_type": "growth_acceleration",
            "focus_entity": "annual_return_rate",
            "composition_density": "medium",
            "emotional_posture": "momentum",
            "framing": "medium",
            "transition_behavior": "acceleration_shift",
        },
        "time_extends": {
            "state_type": "growth_acceleration",
            "focus_entity": "time_period",
            "composition_density": "medium",
            "emotional_posture": "anticipation",
            "framing": "wide",
            "transition_behavior": "timeline_expansion",
        },
        "contributions_accumulate": {
            "state_type": "layered_growth",
            "focus_entity": "total_contribution",
            "composition_density": "high",
            "emotional_posture": "building",
            "framing": "layered",
            "transition_behavior": "layer_stack",
        },
        "corpus_revealed": {
            "state_type": "awe_reveal",
            "focus_entity": "target_corpus",
            "composition_density": "minimal",
            "emotional_posture": "awe",
            "framing": "hero",
            "transition_behavior": "slow_reveal",
        },
        "debt_appears": {
            "state_type": "liability_focus",
            "focus_entity": "debt_principal",
            "composition_density": "medium",
            "emotional_posture": "concern",
            "framing": "medium",
            "transition_behavior": "weight_enter",
        },
        "interest_rate_attaches": {
            "state_type": "pressure_cluster",
            "focus_entity": "interest_pressure",
            "composition_density": "high",
            "emotional_posture": "pressure",
            "framing": "tight",
            "transition_behavior": "pressure_ring",
        },
        "interest_accumulates": {
            "state_type": "pressure_cluster",
            "focus_entity": "interest_pressure",
            "composition_density": "high",
            "emotional_posture": "pressure",
            "framing": "tight",
            "transition_behavior": "compounding_pressure",
        },
        "minimum_payment_fails": {
            "state_type": "trap_reveal",
            "focus_entity": "minimum_payment",
            "composition_density": "minimal",
            "emotional_posture": "alarm",
            "framing": "isolated",
            "transition_behavior": "trap_hold",
        },
        "inflation_erodes": {
            "state_type": "erosion_focus",
            "focus_entity": "inflation_rate",
            "composition_density": "medium",
            "emotional_posture": "unease",
            "framing": "tight",
            "transition_behavior": "value_decay",
        },
    }

    def build_sequence(self, timed_beats: list[dict[str, Any]], *, fps: int = 30) -> dict[str, Any] | None:
        candidates = [
            self._state_from_beat(beat, index, fps=fps)
            for index, beat in enumerate(timed_beats)
        ]
        states = self._merge_states([state for state in candidates if state])
        if not states:
            return None
        return {
            "source": SCHEMA_VERSION,
            "states": states,
            "state_count": len(states),
            "fps": fps,
        }

    def attach_to_beats(self, timed_beats: list[dict[str, Any]], visual_state_sequence: dict[str, Any] | None) -> list[dict[str, Any]]:
        states = list((visual_state_sequence or {}).get("states") or [])
        if not states:
            return timed_beats
        enriched: list[dict[str, Any]] = []
        for beat in timed_beats:
            next_beat = dict(beat)
            state = self._state_for_beat(next_beat, states)
            if state:
                next_beat["visual_state"] = state
                data = next_beat.get("data")
                if isinstance(data, dict):
                    next_beat["data"] = {**data, "visual_state": state}
            enriched.append(next_beat)
        return enriched

    def _state_from_beat(self, beat: dict[str, Any], beat_index: int, *, fps: int) -> dict[str, Any] | None:
        action = self._active_action(beat)
        if not action:
            return None
        action_name = str(action.get("action") or "")
        template = dict(self.ACTION_STATE_MAP.get(action_name) or self._fallback_state(action))
        overlap_group = self._overlap_group(beat)
        state = {
            **template,
            "frame_window": self._frame_window(beat, fps=fps),
            "derived_from_action": action_name,
            "semantic_role": str(action.get("semantic_role") or ""),
            "overlap_group": overlap_group,
            "source_beat_indices": [beat_index],
            "source_action_ids": [str(action.get("id") or "")] if action.get("id") else [],
        }
        return state

    def _fallback_state(self, action: dict[str, Any]) -> dict[str, str]:
        role = str(action.get("semantic_role") or "semantic_value")
        return {
            "state_type": "semantic_focus",
            "focus_entity": role,
            "composition_density": "medium",
            "emotional_posture": "neutral",
            "framing": "medium",
            "transition_behavior": "semantic_shift",
        }

    def _merge_states(self, states: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for state in states:
            if merged and self._mergeable(merged[-1], state):
                previous = dict(merged[-1])
                previous["frame_window"] = {
                    "start_frame": min(int(previous["frame_window"]["start_frame"]), int(state["frame_window"]["start_frame"])),
                    "end_frame": max(int(previous["frame_window"]["end_frame"]), int(state["frame_window"]["end_frame"])),
                }
                previous["source_beat_indices"] = [
                    *previous.get("source_beat_indices", []),
                    *state.get("source_beat_indices", []),
                ]
                previous["source_action_ids"] = [
                    action_id
                    for action_id in [
                        *previous.get("source_action_ids", []),
                        *state.get("source_action_ids", []),
                    ]
                    if action_id
                ]
                merged[-1] = previous
                continue
            merged.append(state)
        for index, state in enumerate(merged):
            state["state_index"] = index
        return merged

    def _mergeable(self, previous: dict[str, Any], current: dict[str, Any]) -> bool:
        if previous.get("state_type") != current.get("state_type"):
            return False
        if previous.get("state_type") not in {"pressure_cluster", "growth_acceleration"}:
            return False
        return str(previous.get("overlap_group") or "") == str(current.get("overlap_group") or "")

    def _state_for_beat(self, beat: dict[str, Any], states: list[dict[str, Any]]) -> dict[str, Any] | None:
        start_frame = int(round(float(beat.get("start_time") or 0.0) * 30))
        end_frame = int(round(float(beat.get("end_time") or 0.0) * 30))
        action = self._active_action(beat)
        action_name = str((action or {}).get("action") or "")
        for state in states:
            if action_name and state.get("derived_from_action") == action_name:
                source_indices = state.get("source_beat_indices") or []
                try:
                    beat_index = int((action or {}).get("sequence_index"))
                except (TypeError, ValueError):
                    beat_index = -1
                if not source_indices or beat_index in source_indices or self._overlaps(start_frame, end_frame, state):
                    return deepcopy(state)
        return next((deepcopy(state) for state in states if self._overlaps(start_frame, end_frame, state)), None)

    def _overlaps(self, start_frame: int, end_frame: int, state: dict[str, Any]) -> bool:
        window = state.get("frame_window") if isinstance(state.get("frame_window"), dict) else {}
        state_start = int(window.get("start_frame") or 0)
        state_end = int(window.get("end_frame") or 0)
        return start_frame < state_end and end_frame > state_start

    def _frame_window(self, beat: dict[str, Any], *, fps: int) -> dict[str, int]:
        try:
            start_frame = int(round(float(beat.get("start_time") or 0.0) * fps))
            end_frame = int(round(float(beat.get("end_time") or 0.0) * fps))
        except (TypeError, ValueError):
            start_frame = 0
            end_frame = 0
        if end_frame <= start_frame:
            timing = beat.get("semantic_timing") if isinstance(beat.get("semantic_timing"), dict) else {}
            relative = timing.get("relative_window") if isinstance(timing.get("relative_window"), dict) else {}
            start_frame = int(relative.get("start_frame") or start_frame)
            end_frame = int(relative.get("end_frame") or max(start_frame + 1, end_frame))
        return {"start_frame": start_frame, "end_frame": end_frame}

    def _active_action(self, beat: dict[str, Any]) -> dict[str, Any] | None:
        data = beat.get("data") if isinstance(beat.get("data"), dict) else {}
        action = data.get("active_action") if isinstance(data.get("active_action"), dict) else None
        return dict(action) if action else None

    def _overlap_group(self, beat: dict[str, Any]) -> str:
        timing = beat.get("semantic_timing") if isinstance(beat.get("semantic_timing"), dict) else {}
        if timing.get("overlap_group"):
            return str(timing.get("overlap_group") or "")
        data = beat.get("data") if isinstance(beat.get("data"), dict) else {}
        choreography = data.get("action_choreography") if isinstance(data.get("action_choreography"), dict) else {}
        return str(choreography.get("overlap_group") or "")
