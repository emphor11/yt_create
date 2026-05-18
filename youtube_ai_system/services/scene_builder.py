from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import current_app

from ..pipelines.visual import (
    COMPONENT_DURATION_WEIGHTS,
    DIRECTED_MIN_BEAT_DURATION,
    MIN_BEAT_DURATION,
    PATTERN_PRIORITY,
    SceneBuilderContractMixin,
    SceneBuilderTextMixin,
    SceneBuilderTimingMixin,
)
from .scene_mapper import map_pattern_to_component
from .scene_debug import SceneDebugTrace, renderer_sequence
from .semantic_timing_engine import SemanticTimingEngine
from .shot_director import ShotDirector
from .visual_state_engine import VisualStateEngine
from .voice_service import VoiceService


class SceneBuilder(SceneBuilderContractMixin, SceneBuilderTimingMixin, SceneBuilderTextMixin):
    def __init__(self) -> None:
        self.voice_service = VoiceService()
        self.semantic_timing_engine = SemanticTimingEngine()
        self.visual_state_engine = VisualStateEngine()
        self.shot_director = ShotDirector()

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
            shot_sequence = None
            if debug_trace:
                debug_trace.snapshot("shot_director_pre", {"timed_beats": timed_beats, "visual_state_sequence": visual_state_sequence or {}}, owner="scene_builder")
            shot_sequence = self.shot_director.build_sequence(timed_beats)
            if shot_sequence:
                timed_beats = self.shot_director.attach_to_beats(timed_beats, shot_sequence)
            if debug_trace:
                debug_trace.snapshot(
                    "shot_director_post",
                    {"shot_sequence": shot_sequence or {}, "timed_beats": timed_beats},
                    owner="shot_director",
                )
                if shot_sequence:
                    debug_trace.ownership("shot_sequence", "shot_director", shot_sequence, "intra-scene shot choreography derived from timed semantic beats")
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
                    "cinematic_events": section.get("cinematic_events") or [],
                    "visual_event_sequence": section.get("visual_event_sequence") or {},
                    "visual_state_sequence": visual_state_sequence or {},
                    "shot_sequence": shot_sequence or {},
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

    def _audio_root(self) -> Path:
        storage_root = Path(current_app.config["STORAGE_ROOT"]).expanduser().resolve()
        audio_root = storage_root / "audio" / "scene_builder"
        audio_root.mkdir(parents=True, exist_ok=True)
        return audio_root

def build_scenes(sections: list[dict[str, Any]], debug_trace: SceneDebugTrace | None = None) -> dict[str, list[dict[str, Any]]]:
    return SceneBuilder().build_scenes(sections, debug_trace=debug_trace)
