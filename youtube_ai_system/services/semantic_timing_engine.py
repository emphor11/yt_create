from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SemanticTimingPlan:
    spans: list[tuple[float, float]]
    metadata: list[dict[str, Any]]
    durations: list[float]
    strategy: str = "semantic_timing"

    def to_debug_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "durations": [round(duration, 3) for duration in self.durations],
            "spans": [(round(start, 3), round(end, 3)) for start, end in self.spans],
            "metadata": self.metadata,
        }


class SemanticTimingEngine:
    """Allocates audio time from semantic action intent, not component weight alone."""

    INTENT_WEIGHTS = {
        "establish_source": 0.86,
        "establish_contribution": 0.88,
        "establish_liability": 0.92,
        "establish_starting_value": 0.9,
        "show_outflow": 0.68,
        "show_fixed_payment_pressure": 0.7,
        "show_growth_force": 0.92,
        "show_duration": 0.78,
        "show_principal_base": 0.96,
        "show_growth_result": 1.38,
        "show_consequence": 1.32,
        "show_trap": 1.35,
        "show_cost_pressure": 1.05,
        "show_debt_growth": 1.2,
        "show_erosion_force": 1.12,
        "show_long_term_effect": 1.25,
        "show_raise": 1.02,
        "show_lifestyle_capture": 1.2,
        "show_spending_expansion": 0.82,
    }

    MOTION_WEIGHTS = {
        "credit_in": 0.88,
        "repeat_deposit": 0.86,
        "collision_drain": 0.66,
        "notification_stack": 0.68,
        "reveal_survivor": 1.34,
        "compound_reveal": 1.45,
        "growth_curve_pull": 0.96,
        "timeline_expand": 0.82,
        "stacking_accumulation": 1.0,
        "balance_weight": 0.95,
        "pressure_ring": 1.02,
        "compounding_pressure": 1.2,
        "partial_payback": 1.18,
        "value_decay": 1.16,
        "timeline_decay": 1.25,
        "upward_step": 0.98,
        "absorption_pull": 1.16,
        "shadow_follow": 0.82,
    }

    PHASE_WEIGHTS = {
        "intro": 0.88,
        "contribution": 0.88,
        "principal": 0.9,
        "today": 0.9,
        "drain": 0.72,
        "stacking": 0.76,
        "growth": 1.0,
        "spiral": 1.12,
        "erosion": 1.12,
        "expenses_follow": 0.82,
        "raise_arrives": 1.0,
        "remainder": 1.26,
        "corpus": 1.34,
        "consequence": 1.3,
        "future": 1.28,
        "pressure": 1.18,
        "gap_revealed": 1.25,
    }

    def allocate(
        self,
        beats: list[dict[str, Any]],
        audio_duration: float,
        *,
        min_duration: float,
    ) -> SemanticTimingPlan | None:
        if audio_duration <= 0 or len(beats) < 2:
            return None
        actions = [self._active_action(beat) for beat in beats]
        if not any(actions):
            return None
        durations = self._durations(beats, actions, audio_duration, min_duration)
        spans = self._spans_from_durations(durations, audio_duration)
        metadata = [
            self._metadata_for_beat(beat, action, span, duration, index, len(beats))
            for index, (beat, action, span, duration) in enumerate(zip(beats, actions, spans, durations))
        ]
        return SemanticTimingPlan(spans=spans, metadata=metadata, durations=durations)

    def _durations(
        self,
        beats: list[dict[str, Any]],
        actions: list[dict[str, Any] | None],
        audio_duration: float,
        min_duration: float,
    ) -> list[float]:
        count = len(beats)
        if audio_duration <= min_duration * count:
            return [audio_duration / count for _ in beats]
        weights = [self._semantic_weight(beat, action, index, count) for index, (beat, action) in enumerate(zip(beats, actions))]
        durations = self._weighted_with_floor(weights, audio_duration, min_duration)
        durations = self._rebalance_reveals(durations, beats, actions, audio_duration, min_duration)
        return self._cap_extreme_durations(durations, beats, actions, audio_duration, min_duration)

    def _weighted_with_floor(self, weights: list[float], audio_duration: float, min_duration: float) -> list[float]:
        durations = [0.0 for _ in weights]
        remaining = set(range(len(weights)))
        remaining_duration = audio_duration
        while remaining:
            total_weight = sum(weights[index] for index in remaining) or float(len(remaining))
            below_floor = [
                index
                for index in remaining
                if (weights[index] / total_weight) * remaining_duration < min_duration
            ]
            if not below_floor:
                for index in remaining:
                    durations[index] = remaining_duration * (weights[index] / total_weight)
                break
            for index in below_floor:
                durations[index] = min_duration
                remaining.remove(index)
                remaining_duration -= min_duration
            if remaining_duration <= 0 and remaining:
                equal = audio_duration / len(weights)
                return [equal for _ in weights]
        return durations

    def _rebalance_reveals(
        self,
        durations: list[float],
        beats: list[dict[str, Any]],
        actions: list[dict[str, Any] | None],
        audio_duration: float,
        min_duration: float,
    ) -> list[float]:
        if len(durations) < 3:
            return durations
        reveal_indices = [
            index
            for index, (beat, action) in enumerate(zip(beats, actions))
            if self._is_reveal(beat, action)
        ]
        if not reveal_indices:
            return durations
        target_reveal = min(audio_duration * 0.22, max(min_duration * 1.25, audio_duration / len(durations) * 1.3))
        for index in reveal_indices:
            if durations[index] >= target_reveal:
                continue
            needed = target_reveal - durations[index]
            donor_indices = [
                donor
                for donor in range(len(durations))
                if donor != index and not self._is_reveal(beats[donor], actions[donor]) and durations[donor] > min_duration
            ]
            if not donor_indices:
                continue
            total_available = sum(max(durations[donor] - min_duration, 0.0) for donor in donor_indices)
            take = min(needed, total_available)
            if take <= 0:
                continue
            durations[index] += take
            for donor in donor_indices:
                available = max(durations[donor] - min_duration, 0.0)
                durations[donor] -= take * (available / total_available)
        drift = audio_duration - sum(durations)
        if durations:
            durations[-1] += drift
        return durations

    def _cap_extreme_durations(
        self,
        durations: list[float],
        beats: list[dict[str, Any]],
        actions: list[dict[str, Any] | None],
        audio_duration: float,
        min_duration: float,
    ) -> list[float]:
        if len(durations) < 3 or audio_duration <= 0:
            return durations
        caps = [
            audio_duration * (0.34 if self._is_reveal(beat, action) else 0.26)
            for beat, action in zip(beats, actions)
        ]
        excess = 0.0
        for index, cap in enumerate(caps):
            if durations[index] > cap:
                excess += durations[index] - cap
                durations[index] = cap
        if excess <= 0:
            return durations
        receivers = [index for index, duration in enumerate(durations) if duration < caps[index]]
        while excess > 0.001 and receivers:
            room = [max(caps[index] - durations[index], 0.0) for index in receivers]
            total_room = sum(room)
            if total_room <= 0:
                break
            distributed = 0.0
            for position, index in enumerate(receivers):
                add = min(excess * (room[position] / total_room), room[position])
                durations[index] += add
                distributed += add
            excess -= distributed
            receivers = [index for index in receivers if durations[index] < caps[index] - 0.001]
        if excess > 0.001:
            flexible = [index for index, duration in enumerate(durations) if duration > min_duration]
            if flexible:
                share = excess / len(flexible)
                for index in flexible:
                    durations[index] += share
        drift = audio_duration - sum(durations)
        if durations:
            durations[-1] += drift
        return durations

    def _semantic_weight(self, beat: dict[str, Any], action: dict[str, Any] | None, index: int, count: int) -> float:
        phase = str(beat.get("beat_phase") or ((beat.get("data") or {}).get("active_phase") if isinstance(beat.get("data"), dict) else "") or "")
        weight = self.PHASE_WEIGHTS.get(phase, 1.0)
        if action:
            intent = str(action.get("intent") or "")
            motion = str(action.get("motion") or "")
            weight *= self.INTENT_WEIGHTS.get(intent, 1.0)
            weight *= self.MOTION_WEIGHTS.get(motion, 1.0)
        emphasis = str(beat.get("emphasis") or "")
        if emphasis == "hero" or index == count - 1:
            weight *= 1.18
        if index == 0:
            weight *= 0.92
        return max(weight, 0.2)

    def _spans_from_durations(self, durations: list[float], audio_duration: float) -> list[tuple[float, float]]:
        spans: list[tuple[float, float]] = []
        cursor = 0.0
        for index, duration in enumerate(durations):
            start = cursor
            end = cursor + duration
            if index == len(durations) - 1:
                end = audio_duration
            spans.append((start, end))
            cursor = end
        return spans

    def _metadata_for_beat(
        self,
        beat: dict[str, Any],
        action: dict[str, Any] | None,
        span: tuple[float, float],
        duration: float,
        index: int,
        count: int,
    ) -> dict[str, Any]:
        data = beat.get("data") if isinstance(beat.get("data"), dict) else {}
        choreography = data.get("action_choreography") if isinstance(data.get("action_choreography"), dict) else {}
        overlap_group = str(choreography.get("overlap_group") or "")
        intent = str((action or {}).get("intent") or "")
        motion = str((action or {}).get("motion") or "")
        pacing = "compress"
        if self._is_reveal(beat, action):
            pacing = "reveal_hold"
        elif intent in {"show_growth_force", "show_debt_growth", "show_erosion_force"}:
            pacing = "pressure_build"
        elif overlap_group in {"overlapping_outflows", "compound_growth"}:
            pacing = "overlap_intensify"
        elif index == 0:
            pacing = "setup"
        return {
            "engine": "semantic_timing",
            "pacing": pacing,
            "intent": intent,
            "motion": motion,
            "overlap_group": overlap_group,
            "audio_span": {"start_time": round(span[0], 3), "end_time": round(span[1], 3), "duration": round(duration, 3)},
            "relative_window": choreography.get("window") or {},
            "emotional_emphasis": "landing" if index == count - 1 else ("pressure" if pacing in {"pressure_build", "overlap_intensify"} else "neutral"),
        }

    def _active_action(self, beat: dict[str, Any]) -> dict[str, Any] | None:
        data = beat.get("data") if isinstance(beat.get("data"), dict) else {}
        action = data.get("active_action") if isinstance(data.get("active_action"), dict) else None
        return dict(action) if action else None

    def _is_reveal(self, beat: dict[str, Any], action: dict[str, Any] | None) -> bool:
        action_name = str((action or {}).get("action") or "")
        intent = str((action or {}).get("intent") or "")
        phase = str(beat.get("beat_phase") or "")
        return (
            action_name.endswith("_revealed")
            or action_name in {"corpus_revealed", "balance_revealed", "minimum_payment_fails"}
            or intent in {"show_growth_result", "show_consequence", "show_trap"}
            or phase in {"remainder", "corpus", "future", "consequence", "gap_revealed", "pressure"}
        )
