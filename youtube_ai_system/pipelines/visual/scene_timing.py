from __future__ import annotations

from typing import Any

from .scene_builder_constants import (
    COMPONENT_DURATION_WEIGHTS,
    DOMINANT_COMPONENTS,
    DOMINANT_SHARE,
    MIN_BEAT_DURATION,
    PHASE_WEIGHT_MULTIPLIERS,
)


class SceneBuilderTimingMixin:
    def _sample_probe_frames(self, scene: dict[str, Any]) -> list[int]:
        frames: list[int] = []
        for beat in scene.get("beats") or []:
            start = int(float(beat.get("start_time") or 0) * 30)
            end = int(float(beat.get("end_time") or 0) * 30)
            midpoint = start + max((end - start) // 2, 0)
            frames.extend([start, midpoint])
        return sorted(set(frame for frame in frames if frame >= 0))[:24]

    def _timeline_from_durations(
        self,
        beats: list[dict[str, Any]],
        durations: list[float],
        audio_duration: float,
    ) -> list[dict[str, Any]]:
        timeline: list[dict[str, Any]] = []
        cursor = 0.0
        for index, (beat, duration) in enumerate(zip(beats, durations)):
            start_time = cursor
            end_time = cursor + duration
            if index == len(beats) - 1:
                end_time = audio_duration if audio_duration > 0 else cursor + duration
            timed_beat = {
                "component": beat["component"],
                "text": beat["text"],
                "start_time": round(start_time, 2),
                "end_time": round(end_time, 2),
                "emphasis": str(beat.get("emphasis") or self._beat_emphasis(index, len(beats))),
                "beat_role": str(beat.get("beat_role") or self._beat_role(beat, index, len(beats))),
            }
            for key in ("subtext", "steps", "props", "data", "source_text", "sentence_index", "beat_phase", "semantic_timing"):
                if key in beat:
                    timed_beat[key] = beat[key]
            timeline.append(timed_beat)
            cursor = end_time
        return timeline

    def _extend_last_beat_to_scene_duration(self, beats: list[dict[str, Any]], scene_duration: float) -> None:
        if not beats:
            return
        beats[-1]["end_time"] = round(max(scene_duration, float(beats[-1].get("end_time") or 0.0)), 2)

    def _timeline_from_spans(
        self,
        beats: list[dict[str, Any]],
        spans: list[tuple[float, float]],
    ) -> list[dict[str, Any]]:
        timeline: list[dict[str, Any]] = []
        for index, (beat, (start_time, end_time)) in enumerate(zip(beats, spans)):
            timed_beat = {
                "component": beat["component"],
                "text": beat["text"],
                "start_time": round(start_time, 2),
                "end_time": round(end_time, 2),
                "emphasis": str(beat.get("emphasis") or self._beat_emphasis(index, len(beats))),
                "beat_role": str(beat.get("beat_role") or self._beat_role(beat, index, len(beats))),
            }
            for key in ("subtext", "steps", "props", "data", "source_text", "sentence_index", "beat_phase", "semantic_timing"):
                if key in beat:
                    timed_beat[key] = beat[key]
            timeline.append(timed_beat)
        return timeline

    def _beats_with_semantic_timing(self, beats: list[dict[str, Any]], metadata: list[dict[str, Any]]) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for beat, timing in zip(beats, metadata):
            next_beat = dict(beat)
            next_beat["semantic_timing"] = dict(timing)
            data = next_beat.get("data")
            if isinstance(data, dict):
                next_beat["data"] = {**data, "semantic_timing": dict(timing)}
            enriched.append(next_beat)
        return enriched

    def _sentence_aligned_spans(
        self,
        beats: list[dict[str, Any]],
        audio_duration: float,
        section: dict[str, Any],
    ) -> list[tuple[float, float]] | None:
        if audio_duration <= 0:
            return None
        if not beats or any("sentence_index" not in beat or not str(beat.get("source_text") or "").strip() for beat in beats):
            return None

        sentence_text_by_index: dict[int, str] = {}
        for beat in beats:
            try:
                sentence_index = int(beat.get("sentence_index"))
            except (TypeError, ValueError):
                return None
            sentence_text_by_index.setdefault(sentence_index, str(beat.get("source_text") or "").strip())

        ordered_sentence_indices = sorted(sentence_text_by_index)
        word_counts = {index: max(len(sentence_text_by_index[index].split()), 1) for index in ordered_sentence_indices}
        total_words = sum(word_counts.values())
        if total_words <= 0:
            return None

        sentence_ranges: dict[int, tuple[float, float]] = {}
        cursor = 0.0
        for position, sentence_index in enumerate(ordered_sentence_indices):
            duration = (word_counts[sentence_index] / total_words) * audio_duration
            start = cursor
            end = cursor + duration
            if position == len(ordered_sentence_indices) - 1:
                end = audio_duration
            sentence_ranges[sentence_index] = (start, end)
            cursor = end

        beat_indices_by_sentence: dict[int, list[int]] = {}
        for beat_index, beat in enumerate(beats):
            beat_indices_by_sentence.setdefault(int(beat.get("sentence_index")), []).append(beat_index)

        spans: list[tuple[float, float]] = [(0.0, 0.0) for _ in beats]
        for sentence_index, beat_indices in beat_indices_by_sentence.items():
            sentence_start, sentence_end = sentence_ranges[sentence_index]
            sentence_duration = max(sentence_end - sentence_start, 0.0)
            weights = [self._beat_weight(beats[index]) for index in beat_indices]
            total_weight = sum(weights) or float(len(beat_indices))
            local_cursor = sentence_start
            for position, (beat_index, weight) in enumerate(zip(beat_indices, weights)):
                duration = sentence_duration * (weight / total_weight)
                start = local_cursor
                end = local_cursor + duration
                if position == len(beat_indices) - 1:
                    end = sentence_end
                spans[beat_index] = (start, end)
                local_cursor = end
        return spans

    def _component_weighted_durations(
        self,
        beats: list[dict[str, Any]],
        audio_duration: float,
        min_duration: float = MIN_BEAT_DURATION,
    ) -> list[float]:
        if not beats:
            return []
        if audio_duration <= 0:
            return [min_duration for _ in beats]
        if audio_duration <= min_duration * len(beats):
            equal_duration = audio_duration / len(beats)
            return [equal_duration for _ in beats]

        weights = [self._beat_weight(beat) for beat in beats]
        durations = [0.0 for _ in beats]
        remaining_indices = set(range(len(beats)))
        remaining_duration = audio_duration

        while remaining_indices:
            total_weight = sum(weights[index] for index in remaining_indices)
            if total_weight <= 0:
                equal_duration = remaining_duration / len(remaining_indices)
                for index in remaining_indices:
                    durations[index] = equal_duration
                break

            below_minimum = [
                index
                for index in remaining_indices
                if (weights[index] / total_weight) * remaining_duration < min_duration
            ]
            if not below_minimum:
                for index in remaining_indices:
                    durations[index] = (weights[index] / total_weight) * remaining_duration
                break

            for index in below_minimum:
                durations[index] = min_duration
                remaining_duration -= min_duration
                remaining_indices.remove(index)

            if remaining_duration <= 0 and remaining_indices:
                equal_duration = audio_duration / len(beats)
                return [equal_duration for _ in beats]

        return durations

    def _dominant_component(self, section: dict[str, Any], beats: list[dict[str, Any]]) -> str:
        visual_plan = section.get("visual_plan") or []
        pattern = ""
        if visual_plan:
            pattern = str((visual_plan[0].get("visual") or {}).get("pattern") or "").strip()
        if pattern in DOMINANT_COMPONENTS and any(str(beat.get("component") or "").strip() == pattern for beat in beats):
            return pattern
        for component in DOMINANT_COMPONENTS:
            if any(str(beat.get("component") or "").strip() == component for beat in beats):
                return component
        return ""

    def _dominant_component_durations(
        self,
        beats: list[dict[str, Any]],
        audio_duration: float,
        dominant_component: str,
        min_duration: float = MIN_BEAT_DURATION,
    ) -> list[float]:
        if not beats:
            return []
        if audio_duration <= 0:
            return [min_duration for _ in beats]
        dominant_indices = [
            index for index, beat in enumerate(beats) if str(beat.get("component") or "").strip() == dominant_component
        ]
        if not dominant_indices:
            return self._component_weighted_durations(beats, audio_duration, min_duration)
        if len(beats) == 1:
            return [audio_duration]

        support_indices = [index for index in range(len(beats)) if index not in dominant_indices]
        if not support_indices:
            weights = [self._beat_weight(beat) for beat in beats]
            total_weight = sum(weights) or float(len(beats))
            return [audio_duration * (weight / total_weight) for weight in weights]

        support_count = len(support_indices)
        target_share = max(DOMINANT_SHARE, 0.78 if len(dominant_indices) > 1 else DOMINANT_SHARE)
        target_dominant = audio_duration * target_share
        support_floor = min(min_duration, max((audio_duration - target_dominant) / support_count, 0.35))
        max_dominant = max(audio_duration - support_floor * support_count, audio_duration / len(beats))
        dominant_duration = min(max(target_dominant, min_duration * len(dominant_indices)), max_dominant)
        remaining = max(audio_duration - dominant_duration, 0.0)
        dominant_weights = [self._beat_weight(beats[index]) for index in dominant_indices]
        total_dominant_weight = sum(dominant_weights) or float(len(dominant_indices))
        support_weights = [self._beat_weight(beats[index]) for index in support_indices]
        total_support_weight = sum(support_weights) or float(len(support_indices))
        durations = [0.0 for _ in beats]
        for index, weight in zip(dominant_indices, dominant_weights):
            durations[index] = dominant_duration * (weight / total_dominant_weight)
        for index, weight in zip(support_indices, support_weights):
            durations[index] = remaining * (weight / total_support_weight)
        return durations

    def _beat_weight(self, beat: dict[str, Any]) -> float:
        base = COMPONENT_DURATION_WEIGHTS.get(str(beat.get("component") or "ConceptCard"), 1.0)
        phase = str(beat.get("beat_phase") or "").strip()
        data = beat.get("data")
        if not phase and isinstance(data, dict):
            phase = str(data.get("active_phase") or "").strip()
        return base * PHASE_WEIGHT_MULTIPLIERS.get(phase, 1.0)

    def _beat_emphasis(self, index: int, total: int) -> str:
        if total <= 1 or index == total - 1:
            return "hero"
        if index == 0:
            return "normal"
        return "subtle"

    def _beat_role(self, beat: dict[str, Any], index: int, total: int) -> str:
        component = str(beat.get("component") or "").strip()
        if index == 0:
            return "introduce"
        if total <= 1 or index == total - 1:
            return "result"
        if component in {
            "MoneyFlowDiagram",
            "DebtSpiralVisualizer",
            "SIPGrowthEngine",
            "InflationErosionVisualizer",
            "LifestyleCreepVisualizer",
            "EMIStackVisualizer",
            "FOMOPriceCrashVisualizer",
            "PortfolioDiversificationVisualizer",
            "SmallLeaksAccumulator",
            "RiskReturnVisualizer",
            "EmergencyFundVisualizer",
            "OutroRecapVisualizer",
            "CalculationStrip",
            "GrowthChart",
            "FlowDiagram",
            "FlowBar",
            "SplitComparison",
        }:
            return "process"
        return "change"

    def _scene_duration(self, audio_duration: float, section: dict[str, Any]) -> float:
        visual_plan = section.get("visual_plan") or []
        pattern = ""
        if visual_plan:
            visual = visual_plan[0].get("visual") or {}
            pattern = str(visual.get("pattern") or "").strip()
        tail = 0.8 if pattern in {
            "MoneyFlowDiagram",
            "DebtSpiralVisualizer",
            "SIPGrowthEngine",
            "InflationErosionVisualizer",
            "LifestyleCreepVisualizer",
            "EMIStackVisualizer",
            "FOMOPriceCrashVisualizer",
            "PortfolioDiversificationVisualizer",
            "SmallLeaksAccumulator",
            "RiskReturnVisualizer",
            "EmergencyFundVisualizer",
            "OutroRecapVisualizer",
        } else 0.4
        return round(max(float(audio_duration or 0), 0.0) + tail, 2)
