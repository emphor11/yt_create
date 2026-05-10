from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from flask import current_app

from .scene_mapper import map_pattern_to_component
from .scene_debug import SceneDebugTrace, renderer_sequence
from .semantic_timing_engine import SemanticTimingEngine
from .visual_state_engine import VisualStateEngine
from .voice_service import VoiceService

MIN_BEAT_DURATION = 1.2
DIRECTED_MIN_BEAT_DURATION = 1.5
COMPONENT_DURATION_WEIGHTS = {
    "StatCard": 1.0,
    "HighlightText": 0.9,
    "ConceptCard": 1.0,
    "ConceptCardScene": 1.0,
    "RiskCard": 1.1,
    "RiskCardScene": 1.1,
    "FlowBar": 1.4,
    "FlowDiagram": 1.6,
    "BalanceBar": 1.5,
    "CalculationStrip": 1.6,
    "SplitComparison": 1.3,
    "SplitComparisonScene": 1.3,
    "GrowthChart": 1.5,
    "GrowthChartScene": 1.5,
    "InflationErosionVisualizer": 2.8,
    "LifestyleCreepVisualizer": 2.4,
    "EMIStackVisualizer": 2.5,
    "FOMOPriceCrashVisualizer": 2.4,
    "PortfolioDiversificationVisualizer": 2.4,
    "SmallLeaksAccumulator": 2.3,
    "StepFlow": 1.4,
    "StepFlowScene": 1.4,
    "MoneyFlowDiagram": 1.8,
    "DebtSpiralVisualizer": 1.8,
    "SIPGrowthEngine": 1.9,
}
PATTERN_PRIORITY = {
    "MoneyFlowDiagram": 7,
    "DebtSpiralVisualizer": 7,
    "SIPGrowthEngine": 7,
    "InflationErosionVisualizer": 7,
    "LifestyleCreepVisualizer": 7,
    "EMIStackVisualizer": 7,
    "FOMOPriceCrashVisualizer": 7,
    "PortfolioDiversificationVisualizer": 7,
    "SmallLeaksAccumulator": 7,
    "GrowthChart": 6,
    "SplitComparison": 6,
    "FlowDiagram": 6,
    "BalanceBar": 6,
    "NumericComparison": 5,
    "RiskCard": 3,
    "StepFlow": 2,
    "ConceptCard": 1,
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
DOMINANT_COMPONENTS = {
    "MoneyFlowDiagram",
    "DebtSpiralVisualizer",
    "SIPGrowthEngine",
    "InflationErosionVisualizer",
    "LifestyleCreepVisualizer",
    "EMIStackVisualizer",
    "FOMOPriceCrashVisualizer",
    "PortfolioDiversificationVisualizer",
    "SmallLeaksAccumulator",
    "GrowthChart",
    "FlowDiagram",
    "SplitComparison",
}
DOMINANT_SHARE = 0.64
TEXT_COMPONENTS = {"StatCard", "HighlightText", "ConceptCard", "ConceptCardScene", "RiskCard", "RiskCardScene"}
PHASE_WEIGHT_MULTIPLIERS = {
    "drain": 1.4,
    "spiral": 1.4,
    "growth": 1.4,
    "erosion": 1.4,
    "intro": 0.75,
    "principal": 0.75,
    "contribution": 0.75,
    "today": 0.75,
    "remainder": 0.95,
    "consequence": 0.95,
    "corpus": 0.95,
    "future": 0.95,
    "income_base": 0.75,
    "raise_arrives": 1.1,
    "expenses_follow": 1.45,
    "gap_revealed": 1.0,
    "first_emi": 0.75,
    "stacking": 1.45,
    "pressure": 1.0,
    "rise": 0.9,
    "crash": 1.55,
    "loss": 1.0,
    "concentrated": 0.8,
    "spread": 1.35,
    "impact": 1.05,
    "first_leak": 0.8,
    "repeat": 1.45,
    "month_end": 1.0,
}


class SceneBuilder:
    def __init__(self) -> None:
        self.voice_service = VoiceService()
        self.semantic_timing_engine = SemanticTimingEngine()
        self.visual_state_engine = VisualStateEngine()

    def build_scenes(self, sections: list[dict[str, Any]], debug_trace: SceneDebugTrace | None = None) -> dict[str, list[dict[str, Any]]]:
        scenes: list[dict[str, Any]] = []
        audio_root = self._audio_root()

        for index, section in enumerate(sections, start=1):
            narration = str(section.get("text") or "").strip()
            if not narration:
                continue

            audio_file = str(section.get("audio_file") or "").strip()
            supplied_duration = section.get("audio_duration")
            if audio_file and supplied_duration:
                resolved_audio_file = str(Path(audio_file).expanduser().resolve())
                resolved_duration = float(supplied_duration)
            else:
                voice_result = self.voice_service.generate_scene_audio(audio_root, index, narration)
                resolved_audio_file = str(Path(voice_result.audio_path).expanduser().resolve())
                resolved_duration = float(voice_result.duration_sec)

            audio_duration = round(max(resolved_duration, 0.0), 2)
            scene_duration = self._scene_duration(audio_duration, section)
            beats = self._section_beats(section, debug_trace=debug_trace)
            timed_beats = self._timeline_from_beats(beats, audio_duration, section, debug_trace=debug_trace)
            self._extend_last_beat_to_scene_duration(timed_beats, scene_duration)
            visual_state_sequence = None
            if debug_trace:
                debug_trace.snapshot("visual_state_engine_pre", {"timed_beats": timed_beats}, owner="scene_builder")
            visual_state_sequence = self.visual_state_engine.build_sequence(timed_beats)
            if visual_state_sequence:
                timed_beats = self.visual_state_engine.attach_to_beats(timed_beats, visual_state_sequence)
            if debug_trace:
                debug_trace.snapshot(
                    "visual_state_engine_post",
                    {"visual_state_sequence": visual_state_sequence or {}, "timed_beats": timed_beats},
                    owner="visual_state_engine",
                )
                if visual_state_sequence:
                    debug_trace.ownership("visual_state_sequence", "visual_state_engine", visual_state_sequence, "composition state sequence derived from timed semantic actions")
            data_warnings = self._validate_beat_data(timed_beats)
            for warning in data_warnings:
                current_app.logger.warning("SceneBuilder data warning for scene %s: %s", index, warning)
                if debug_trace:
                    debug_trace.warning("scene_builder", warning, {"scene_index": index})
            dominance_warning = self._text_dominance_warning(timed_beats, str(section.get("kind") or section.get("type") or ""))
            if dominance_warning:
                current_app.logger.warning("SceneBuilder visual warning for scene %s: %s", index, dominance_warning)
                if debug_trace:
                    debug_trace.warning("scene_builder", dominance_warning, {"scene_index": index})
            pattern, data, concept = self._scene_visual_contract(section)
            map_pattern_to_component(pattern)

            scene_result = {
                    "scene_id": f"scene_{index}",
                    "narration": narration,
                    "text": narration,
                    "concept": concept,
                    "concept_type": str(section.get("concept_type") or concept or "").strip(),
                    "pattern": pattern,
                    "data": data,
                    "direction": section.get("direction"),
                    "visual_mode": section.get("visual_mode") or self._visual_field(section, "visual_mode"),
                    "cinematic_intent": section.get("cinematic_intent") or self._visual_field(section, "cinematic_intent") or {},
                    "visual_story": section.get("visual_story") or {},
                    "story_state": section.get("story_state") or {},
                    "visual_state_sequence": visual_state_sequence or {},
                    "theme": section.get("theme") or {},
                    "beats": timed_beats,
                    "warnings": data_warnings,
                    "duration": round(scene_duration, 2),
                    "total_duration": round(scene_duration, 2),
                    "audio_duration": round(audio_duration, 2),
                    "audio_file": resolved_audio_file,
            }
            if debug_trace:
                debug_trace.snapshot("scene_builder_timeline", scene_result, owner="scene_builder")
                debug_trace.ownership("timed_beats", "scene_builder", timed_beats, "timeline constructed from expanded beats")
                debug_trace.ownership("pattern", "scene_builder", pattern, "scene visual contract selected for render")
                debug_trace.ownership("data", "scene_builder", data, "scene visual contract data enriched")
                debug_trace.determinism("scene_builder", section, scene_result)
                debug_trace.snapshot("renderer_sequence", renderer_sequence(scene_result), owner="scene_renderer")
                for beat_index, beat in enumerate(timed_beats):
                    beat_id = f"timed_beat:{beat_index}:{str(beat.get('component') or 'component')}"
                    source_id = f"beat:{beat_index}:{str(beat.get('component') or 'component')}"
                    frame_id = f"frame_range:{beat_index}:{int(float(beat.get('start_time') or 0) * 30)}-{int(float(beat.get('end_time') or 0) * 30)}"
                    component_id = f"component:{beat_index}:{str(beat.get('component') or 'component')}"
                    debug_trace.lineage_node(beat_id, "timed_beat", "scene_builder", str(beat.get("text") or ""), beat, owner="scene_builder", source_ids=[source_id])
                    debug_trace.lineage_node(frame_id, "frame_range", "scene_builder", f"{beat.get('start_time')}s-{beat.get('end_time')}s", beat, owner="scene_builder", source_ids=[beat_id])
                    debug_trace.lineage_node(component_id, "component", "scene_renderer", str(beat.get("component") or ""), beat.get("component"), owner="scene_renderer", source_ids=[frame_id])
                    debug_trace.lineage_edge(source_id, beat_id, "timed_beat_from_expanded_beat")
                    debug_trace.lineage_edge(beat_id, frame_id, "frame_range_from_scene_builder_timing")
                    debug_trace.lineage_edge(frame_id, component_id, "component_selected_for_frame_range")
                for probe_frame in self._sample_probe_frames(scene_result):
                    probe = debug_trace.frame_probe(scene_result, probe_frame)
                    if probe.get("fallback_component"):
                        debug_trace.fallback(
                            "scene_renderer",
                            "COMPONENT_MAP",
                            "unsupported component fallback",
                            probe.get("active_component"),
                            probe.get("fallback_component"),
                        )
                debug_trace.validate_scene(scene_result)
            scenes.append(scene_result)

        return {"scenes": scenes}

    def _visual_field(self, section: dict[str, Any], key: str) -> Any:
        visual_plan = section.get("visual_plan") or []
        if not visual_plan:
            return None
        visual = visual_plan[0].get("visual") or {}
        return visual.get(key)

    def _section_beats(self, section: dict[str, Any], debug_trace: SceneDebugTrace | None = None) -> list[dict[str, Any]]:
        visual_plan = section.get("visual_plan") or []
        beats: list[dict[str, Any]] = []
        for item in visual_plan:
            beats.extend((item.get("beats") or {}).get("beats") or [])

        cleaned = self._clean_and_dedupe_beats(beats, str(section.get("text") or ""))
        if len(cleaned) >= 2:
            result = self._force_escalation(cleaned, str(section.get("text") or ""))
            if debug_trace:
                debug_trace.snapshot("scene_builder_section_beats", {"raw": beats, "cleaned": cleaned, "result": result}, owner="scene_builder")
            return result
        if cleaned:
            result = self._force_escalation(self._expand_minimum_beats(cleaned, str(section.get("text") or "")), str(section.get("text") or ""))
            if debug_trace:
                debug_trace.fallback("scene_builder", "expand_minimum_beats", "only one cleaned beat", cleaned, result)
                debug_trace.snapshot("scene_builder_section_beats", {"raw": beats, "cleaned": cleaned, "result": result}, owner="scene_builder")
            return result

        fallback_text = self._fallback_text(str(section.get("text") or ""))
        result = self._force_escalation(
            self._expand_minimum_beats([{"component": "ConceptCard", "text": fallback_text}], str(section.get("text") or "")),
            str(section.get("text") or ""),
        )
        if debug_trace:
            debug_trace.fallback("scene_builder", "ConceptCard minimum beats", "no usable visual beats", beats, result)
            debug_trace.snapshot("scene_builder_section_beats", {"raw": beats, "cleaned": cleaned, "result": result}, owner="scene_builder")
        return result

    def _timeline_from_beats(
        self,
        beats: list[dict[str, Any]],
        audio_duration: float,
        section: dict[str, Any],
        debug_trace: SceneDebugTrace | None = None,
    ) -> list[dict[str, Any]]:
        min_duration = DIRECTED_MIN_BEAT_DURATION if section.get("direction") else MIN_BEAT_DURATION
        beats = self._merge_for_min_duration(beats, audio_duration, min_duration)
        if not beats:
            return []
        semantic_timing = self.semantic_timing_engine.allocate(beats, audio_duration, min_duration=min_duration)
        if semantic_timing is not None:
            timed_input = self._beats_with_semantic_timing(beats, semantic_timing.metadata)
            timeline = self._timeline_from_spans(timed_input, semantic_timing.spans)
            if debug_trace:
                debug_trace.snapshot("scene_builder_timeline_decision", semantic_timing.to_debug_dict() | {"timeline": timeline}, owner="semantic_timing_engine")
                debug_trace.ownership("timed_beats", "semantic_timing_engine", timeline, "audio-aware semantic timeline allocation from action micro-beats")
            return timeline
        dominant_component = self._dominant_component(section, beats)
        if dominant_component:
            durations = self._dominant_component_durations(beats, audio_duration, dominant_component, min_duration)
            timeline = self._timeline_from_durations(beats, durations, audio_duration)
            if debug_trace:
                debug_trace.snapshot("scene_builder_timeline_decision", {"strategy": "dominant_component", "dominant_component": dominant_component, "durations": durations, "timeline": timeline}, owner="scene_builder")
            return timeline
        aligned_spans = self._sentence_aligned_spans(beats, audio_duration, section)
        if aligned_spans is not None:
            timeline = self._timeline_from_spans(beats, aligned_spans)
            if debug_trace:
                debug_trace.snapshot("scene_builder_timeline_decision", {"strategy": "sentence_aligned", "spans": aligned_spans, "timeline": timeline}, owner="scene_builder")
            return timeline
        durations = self._component_weighted_durations(beats, audio_duration, min_duration)
        timeline = self._timeline_from_durations(beats, durations, audio_duration)
        if debug_trace:
            debug_trace.snapshot("scene_builder_timeline_decision", {"strategy": "component_weighted", "durations": durations, "timeline": timeline}, owner="scene_builder")
        return timeline

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

    def _audio_root(self) -> Path:
        storage_root = Path(current_app.config["STORAGE_ROOT"]).expanduser().resolve()
        audio_root = storage_root / "audio" / "scene_builder"
        audio_root.mkdir(parents=True, exist_ok=True)
        return audio_root

    def _scene_visual_contract(self, section: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
        visual_plan = section.get("visual_plan") or []
        best_pattern = ""
        best_data: dict[str, Any] = {}
        best_concept = ""
        best_score = -1

        if visual_plan:
            for item in visual_plan:
                visual = item.get("visual") or {}
                pattern = str(visual.get("pattern") or "").strip()
                data = self._normalize_data_dict(visual.get("data"))
                if not data:
                    data = self._data_from_matching_beat(item, pattern)
                concept = str((item.get("concept") or {}).get("concept") or "").strip()
                score = PATTERN_PRIORITY.get(pattern, 0)
                if pattern and data and concept and score > best_score:
                    best_pattern = pattern
                    best_data = data
                    best_concept = concept
                    best_score = score

            if best_pattern:
                return best_pattern, self._enrich_data_with_section(best_pattern, best_data, section), best_concept

            inferred = self._infer_contract_from_visual_plan(visual_plan)
            if inferred is not None:
                pattern, data, concept = inferred
                return pattern, self._enrich_data_with_section(pattern, data, section), concept
        fallback_text = self._fallback_text(str(section.get("text") or ""))
        return "ConceptCard", {"title": fallback_text.upper()}, fallback_text

    def _infer_contract_from_visual_plan(self, visual_plan: list[dict[str, Any]]) -> tuple[str, dict[str, Any], str] | None:
        best: tuple[str, dict[str, Any], str] | None = None
        best_score = -1
        for item in visual_plan:
            inferred = self._infer_contract_from_beats(item)
            if inferred is None:
                continue
            pattern, _, _ = inferred
            score = PATTERN_PRIORITY.get(pattern, 0)
            if score > best_score:
                best = inferred
                best_score = score
        return best

    def _infer_contract_from_beats(self, item: dict[str, Any]) -> tuple[str, dict[str, Any], str] | None:
        beats = ((item.get("beats") or {}).get("beats") or [])
        if not beats:
            return None
        last_beat = beats[-1]
        component = str(last_beat.get("component") or "").strip()
        concept = str(last_beat.get("text") or "").strip()
        if not component or not concept:
            return None
        if component == "RiskCard":
            return "RiskCard", {"title": concept.upper()}, concept
        if component == "SplitComparison":
            return "SplitComparison", {"headline": concept}, concept
        if component == "StepFlow":
            return "StepFlow", {"steps": [concept]}, concept
        if component == "GrowthChart":
            return "GrowthChart", {"end": concept, "curve": "up"}, concept
        values = [str(beat.get("text") or "").strip() for beat in beats if str(beat.get("text") or "").strip()]
        if component == "CalculationStrip":
            flat_steps: list[Any] = []
            for beat in beats:
                data = self._normalize_data_dict(beat.get("data"))
                steps = data.get("steps") or beat.get("steps") or []
                if isinstance(steps, list):
                    flat_steps.extend(steps)
            if flat_steps:
                return "CalculationStrip", {"steps": flat_steps}, concept
            return "CalculationStrip", {"values": values}, concept
        if component == "StatCard":
            return "NumericComparison", {"values": values}, concept
        return "ConceptCard", {"title": concept.upper()}, concept

    def _enrich_data_with_section(self, pattern: str, data: dict[str, Any], section: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(data)
        finance_concept = section.get("finance_concept") or {}
        narrative_arc = section.get("narrative_arc") or {}
        state = section.get("state") or {}

        start_value = self._first_text_value(
            finance_concept.get("start_value"),
            narrative_arc.get("start_state"),
            state.get("money_in"),
        )
        end_value = self._first_text_value(
            finance_concept.get("end_value"),
            narrative_arc.get("end_state"),
            state.get("balance_change"),
        )
        rate = self._first_text_value(
            narrative_arc.get("rate"),
            state.get("money_out"),
            self._percentage_text(finance_concept.get("percentage")),
        )

        if pattern == "NumericComparison":
            values = [str(value).strip() for value in enriched.get("values") or [] if str(value).strip()]
            values = self._append_unique_values(values, [start_value, rate, end_value])
            if values:
                enriched["values"] = values[:3]
            if start_value and not enriched.get("start"):
                enriched["start"] = start_value
            if rate and not enriched.get("rate"):
                enriched["rate"] = rate
            if end_value and not enriched.get("end"):
                enriched["end"] = end_value
        elif pattern == "GrowthChart":
            if start_value and not enriched.get("start"):
                enriched["start"] = start_value
            if end_value and not enriched.get("end"):
                enriched["end"] = end_value
            if rate and not enriched.get("rate"):
                enriched["rate"] = rate
        elif pattern in {"RiskCard", "ConceptCard"}:
            if rate and not enriched.get("subtitle"):
                enriched["subtitle"] = f"{rate} impact"
            if end_value and not enriched.get("value"):
                enriched["value"] = end_value
            if state and not enriched.get("state"):
                enriched["state"] = dict(state)
        elif pattern == "SplitComparison":
            if start_value and not enriched.get("left"):
                enriched["left"] = {"label": start_value}
            if end_value and not enriched.get("right"):
                enriched["right"] = {"label": end_value}
            if rate and not enriched.get("rate"):
                enriched["rate"] = rate
        elif pattern == "StepFlow":
            steps = [str(step).strip() for step in enriched.get("steps") or [] if str(step).strip()]
            if not enriched.get("steps"):
                enriched["steps"] = self._append_unique_values(steps, [start_value, rate, end_value]) or steps

        visual_type = str(section.get("visual_type") or narrative_arc.get("visual_type") or "").strip()
        if visual_type and not enriched.get("visual_type"):
            enriched["visual_type"] = visual_type
        return enriched

    def _clean_and_dedupe_beats(self, beats: list[dict[str, Any]], section_text: str) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        seen_texts: set[str] = set()
        for beat in beats:
            text = self._clean_beat_text(str(beat.get("text") or "").strip(), section_text)
            if not text:
                continue
            key = text.lower()
            if key in seen_texts:
                continue
            seen_texts.add(key)
            cleaned_beat: dict[str, Any] = {
                "component": str(beat.get("component") or "").strip() or "ConceptCard",
                "text": text,
            }
            for extra_key in ("subtext", "steps", "props", "source_text", "sentence_index", "beat_role", "beat_phase", "emphasis"):
                if extra_key in beat:
                    cleaned_beat[extra_key] = beat[extra_key]
            data = self._normalize_data_dict(beat.get("data"))
            if data:
                cleaned_beat["data"] = data
            cleaned.append(cleaned_beat)
        return cleaned

    def _normalize_data_dict(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError, json.JSONDecodeError):
                return {}
            return dict(parsed) if isinstance(parsed, dict) else {}
        return {}

    def _data_from_matching_beat(self, item: dict[str, Any], pattern: str) -> dict[str, Any]:
        if not pattern:
            return {}
        beats = (item.get("beats") or {}).get("beats") or []
        for beat in beats:
            if str(beat.get("component") or "").strip() == pattern:
                data = self._normalize_data_dict(beat.get("data"))
                if data:
                    return data
        return {}

    def _validate_beat_data(self, beats: list[dict[str, Any]]) -> list[str]:
        warnings: list[str] = []
        for index, beat in enumerate(beats):
            component = str(beat.get("component") or "").strip()
            required_fields = REQUIRED_BEAT_DATA.get(component)
            if not required_fields:
                continue
            data = self._normalize_data_dict(beat.get("data"))
            if not data:
                warnings.append(f"beat {index}: {component} has no data dict")
                continue
            for field in required_fields:
                if field not in data:
                    warnings.append(f"beat {index}: {component} missing required data field '{field}'")
        return warnings

    def _text_dominance_warning(self, beats: list[dict[str, Any]], scene_kind: str) -> str:
        if scene_kind.lower() in {"hook", "outro"} or not beats:
            return ""
        total_duration = sum(max(float(beat.get("end_time") or 0.0) - float(beat.get("start_time") or 0.0), 0.0) for beat in beats)
        if total_duration <= 0:
            return ""
        text_duration = sum(
            max(float(beat.get("end_time") or 0.0) - float(beat.get("start_time") or 0.0), 0.0)
            for beat in beats
            if str(beat.get("component") or "") in TEXT_COMPONENTS
        )
        text_ratio = text_duration / total_duration
        if text_ratio <= 0.40:
            return ""
        components = [str(beat.get("component") or "") for beat in beats]
        return f"text components occupy {text_ratio:.0%} of scene duration; beats={components}"

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
        word_counts = {
            index: max(len(sentence_text_by_index[index].split()), 1)
            for index in ordered_sentence_indices
        }
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

    def _component_weighted_durations(self, beats: list[dict[str, Any]], audio_duration: float, min_duration: float = MIN_BEAT_DURATION) -> list[float]:
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
            "CalculationStrip",
            "GrowthChart",
            "FlowDiagram",
            "FlowBar",
            "SplitComparison",
        }:
            return "process"
        return "change"

    def _append_unique_values(self, current: list[str], candidates: list[str]) -> list[str]:
        values = list(current)
        seen = {value.lower() for value in values}
        for candidate in candidates:
            value = str(candidate or "").strip()
            if not value or value.lower() in seen:
                continue
            seen.add(value.lower())
            values.append(value)
        return values

    def _first_text_value(self, *values: Any) -> str:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return ""

    def _percentage_text(self, value: Any) -> str:
        if value is None:
            return ""
        try:
            return f"{float(value):g}%"
        except (TypeError, ValueError):
            return str(value).strip()

    def _fallback_text(self, section_text: str) -> str:
        lowered = section_text.lower()
        if "salary" in lowered and any(token in lowered for token in ("vanish", "vanishes", "disappear", "disappears")):
            return "Salary disappears early"
        if "fix the system" in lowered or ("automate" in lowered and "spend" in lowered):
            return "Automate before you spend"
        words = section_text.split()
        if not words:
            return "Core message"
        phrase = " ".join(words[: min(len(words), 3)]).strip(" ,.-")
        if not re.search(r"[A-Za-z0-9₹]", phrase):
            return "Core message"
        return phrase or "Core message"

    def _merge_for_min_duration(self, beats: list[dict[str, Any]], audio_duration: float, min_duration: float = MIN_BEAT_DURATION) -> list[dict[str, Any]]:
        merged = [dict(beat) for beat in beats]
        while len(merged) > 1 and audio_duration > 0 and (audio_duration / len(merged)) < min_duration:
            last = merged.pop()
            merged[-1]["text"] = self._clean_beat_text(f"{merged[-1]['text']} {last['text']}", merged[-1]["text"])
            merged[-1]["component"] = last["component"] or merged[-1]["component"]
        return merged

    def _expand_minimum_beats(self, beats: list[dict[str, Any]], section_text: str) -> list[dict[str, Any]]:
        if len(beats) >= 2:
            return beats
        first, second = self._split_section_ideas(section_text)
        base_component = beats[0]["component"] if beats else "ConceptCard"
        primary_text = beats[0]["text"] if beats else first
        if not second or second.lower() == primary_text.lower():
            second = self._consequence_phrase(section_text, primary_text)
        if primary_text.lower() == second.lower():
            words = second.split()
            if len(words) > 1:
                second = " ".join(words[-2:])
        primary_beat = dict(beats[0]) if beats else {"component": base_component}
        primary_beat["component"] = base_component
        primary_beat["text"] = primary_text
        return [
            primary_beat,
            {"component": "ConceptCard", "text": self._clean_beat_text(second, section_text)},
        ]

    def _split_section_ideas(self, section_text: str) -> tuple[str, str]:
        parts = [part.strip(" ,.-") for part in re.split(r",| and | but | so | because ", section_text, maxsplit=1, flags=re.IGNORECASE) if part.strip()]
        if len(parts) >= 2:
            return self._short_phrase(parts[0]), self._short_phrase(parts[1])
        words = section_text.split()
        midpoint = max(len(words) // 2, 1)
        return self._short_phrase(" ".join(words[:midpoint])), self._short_phrase(" ".join(words[midpoint:]))

    def _short_phrase(self, text: str) -> str:
        words = text.split()
        phrase = " ".join(words[:4]).strip() or self._fallback_text(text)
        return self._clean_beat_text(phrase, text)

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
        } else 0.4
        return round(max(float(audio_duration or 0), 0.0) + tail, 2)

    def _clean_beat_text(self, text: str, section_text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip(" ,.-")
        cleaned = re.sub(r"\b(by|and|the|is)$", "", cleaned, flags=re.IGNORECASE).strip(" ,.-")
        lowered = cleaned.lower()
        if lowered == "salary can vanish":
            return "Salary vanishes early"
        if lowered == "salary can vanish by":
            return "Salary vanishes early"
        if lowered == "fix the system":
            return "Automate before you spend"
        if lowered.startswith("automate the") and "₹5,000" in cleaned:
            return "Automate savings"
        if not cleaned:
            return self._fallback_text(section_text)
        return cleaned[:1].upper() + cleaned[1:]

    def _force_escalation(self, beats: list[dict[str, str]], section_text: str) -> list[dict[str, str]]:
        if len(beats) < 2:
            return beats
        first = beats[0]["text"].lower()
        second = beats[1]["text"].lower()
        if first == second or first in second or second in first or self._ideas_overlap(first, second):
            beats[1]["text"] = self._consequence_phrase(section_text, beats[0]["text"])
        return beats

    def _consequence_phrase(self, section_text: str, primary_text: str) -> str:
        lowered = section_text.lower()
        if "salary" in lowered and any(token in lowered for token in ("month feel broken", "month breaks", "feel broken")):
            return "Month feels broken"
        if "salary" in lowered and any(token in lowered for token in ("vanish", "disappear")):
            return "Month feels broken"
        if "fix the system" in lowered or ("automate" in lowered and "spend" in lowered):
            return "Automate savings"
        if "leak" in lowered:
            return "Money leaks away"
        if "debt" in lowered and "trap" in lowered:
            return "Debt keeps growing"
        fallback = self._fallback_text(section_text)
        if fallback.lower() != primary_text.lower():
            return fallback
        words = [word for word in re.findall(r"[A-Za-z0-9₹%,']+", section_text) if word]
        if len(words) >= 2:
            return self._clean_beat_text(" ".join(words[-2:]), section_text)
        return self._clean_beat_text(section_text, section_text)

    def _ideas_overlap(self, first: str, second: str) -> bool:
        stopwords = {"the", "and", "a", "an", "to", "you", "your", "before"}
        first_words = {word for word in re.findall(r"[a-z]+", first) if word not in stopwords}
        second_words = {word for word in re.findall(r"[a-z]+", second) if word not in stopwords}
        return len(first_words.intersection(second_words)) >= 1


def build_scenes(sections: list[dict[str, Any]], debug_trace: SceneDebugTrace | None = None) -> dict[str, list[dict[str, Any]]]:
    return SceneBuilder().build_scenes(sections, debug_trace=debug_trace)
