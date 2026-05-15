from __future__ import annotations

import json
from pathlib import Path

from flask import current_app

from ..contracts.rendering import RenderSpec
from ..infrastructure.ffmpeg import FfmpegExecutor
from ..infrastructure.filesystem.storage import FileStorage
from ..models.repository import ProjectRepository
from ..pipelines.media import (
    BeatClipGenerator,
    BeatTimelineBuilder,
    BrollAssetProvider,
    DynamicVisualCoverageCalculator,
    generate_edge_tts_audio,
    IndianNumberFormatter,
    LegacyVisualVideoRenderer,
    MediaAudioFallbacks,
    MediaGroqJsonClient,
    MediaSummaryBuilder,
    MediaVisualDebugPrinter,
    OutroSectionBuilder,
    SceneRenderSectionBuilder,
    SceneTextSignalResolver,
    StaticSceneImageRenderer,
    VoiceCheckResultBuilder,
)
from .cinematic_event_compiler import CinematicEventCompiler
from .concept_service import ConceptService
from .remotion_service import RemotionService
from .render_spec_service import RenderSpecService
from .run_log import RunLogger
from .scene_builder import build_scenes
from .scene_debug import SceneDebugStore, SceneDebugTrace, debug_video_pipeline_enabled, elapsed_ms, new_trace_for_scene, stable_hash, stage_timer
from .story_pipeline import StoryPipeline
from .voice_service import VoiceService


class MediaService:
    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.logger = RunLogger()
        self.voice_service = VoiceService()
        self.render_specs = RenderSpecService()
        self.remotion = RemotionService()
        self.concepts = ConceptService()
        self.story_pipeline = StoryPipeline(logger=self.logger)
        self.cinematic_event_compiler = CinematicEventCompiler()
        self.coverage_calculator = DynamicVisualCoverageCalculator()
        self.summary_builder = MediaSummaryBuilder()
        self.groq_json = MediaGroqJsonClient(self.logger)
        self.text_signals = SceneTextSignalResolver()
        self.outro_builder = OutroSectionBuilder(self.text_signals)
        self.scene_section_builder = SceneRenderSectionBuilder(
            text_signals=self.text_signals,
            outro_builder=self.outro_builder,
            story_pipeline=self.story_pipeline,
            cinematic_event_compiler=self.cinematic_event_compiler,
        )
        self.voice_check_results = VoiceCheckResultBuilder()
        self.number_formatter = IndianNumberFormatter()
        self.ffmpeg = FfmpegExecutor()
        self.audio_fallbacks = MediaAudioFallbacks(self.ffmpeg)
        self.beat_timeline = BeatTimelineBuilder(self.ffmpeg)
        self.broll_provider = BrollAssetProvider(groq_json=self._call_groq_api, logger=self.logger)
        self.static_image_renderer = StaticSceneImageRenderer()
        self.legacy_visual_renderer = LegacyVisualVideoRenderer(
            groq_json=self._call_groq_api,
            require_ffmpeg=self._require_ffmpeg,
            encode_frame_sequence=self._encode_frame_sequence,
            format_number=self._format_number,
        )
        self.visual_debug_printer = MediaVisualDebugPrinter(
            render_specs=self.render_specs,
            estimate_duration=self._estimate_duration,
            ten_minute_finance_enabled=self._ten_minute_finance_enabled,
            load_scene_beats=self._load_scene_beats,
        )
        self.beat_clip_generator = BeatClipGenerator(
            concepts=self.concepts,
            repo=self.repo,
            render_specs=self.render_specs,
            remotion=self.remotion,
            logger=self.logger,
            ten_minute_finance_enabled=self._ten_minute_finance_enabled,
            load_scene_beats=self._load_scene_beats,
            normalize_beat_durations=self._normalize_beat_durations,
            regenerated_beat_from_scene=self._regenerated_beat_from_scene,
            visual_debug_enabled=self._visual_debug_enabled,
            validated_beat_for_debug=self._validated_beat_for_debug,
            debug_entry=self._debug_entry,
            print_visual_debug=self._print_visual_debug,
            pexels_broll=self._pexels_broll,
            concat_beat_clips=self._concat_beat_clips,
        )

    # -----------------------------------------------------------------------
    # Public entry points
    # -----------------------------------------------------------------------
    def generate_voice_and_visuals(self, project_id: int) -> None:
        project = self.repo.get_project(project_id)
        scenes = self.repo.list_scenes(project_id)
        storage = FileStorage(Path(current_app.config["STORAGE_ROOT"]))
        audio_root = storage.project_audio_dir(project_id)
        image_root = storage.project_image_dir(project_id)
        self.logger.log("media_generation", "running", "Generating scene media.", project_id)

        for scene in scenes:
            self._generate_scene_media(project_id, scene, audio_root, image_root)

        live_audio_count = sum(
            1
            for scene in self.repo.list_scenes(project_id)
            if str(scene.get("audio_source") or "").startswith(("kokoro", "gtts", "edge_tts"))
        )
        self.logger.log(
            "media_generation",
            "completed",
            (
                f"Generated media assets for {len(scenes)} scenes in project '{project['working_title']}'. "
                f"Narration voice used on {live_audio_count} scene(s)."
            ),
            project_id,
        )

    def generate_scene_media(self, project_id: int, scene_id: int) -> None:
        scene = self.repo.get_scene(scene_id)
        if not scene or int(scene["video_project_id"]) != int(project_id):
            raise ValueError(f"Scene {scene_id} does not belong to project {project_id}.")
        storage = FileStorage(Path(current_app.config["STORAGE_ROOT"]))
        audio_root = storage.project_audio_dir(project_id)
        image_root = storage.project_image_dir(project_id)
        self._generate_scene_media(project_id, scene, audio_root, image_root, force=True)

    def _generate_scene_media(
        self,
        project_id: int,
        scene: dict,
        audio_root: Path,
        image_root: Path,
        force: bool = False,
    ) -> None:
        if not force and self._scene_media_complete(scene):
            if self._visual_debug_enabled():
                self._print_existing_scene_debug(scene)
            self.logger.log(
                "media_generation",
                "completed",
                f"Skipping scene {scene['scene_order']} because media already exists.",
                project_id,
            )
            return

        self.logger.log(
            "voice_generation", "running",
            f"Starting voice generation for scene {scene['scene_order']}.",
            project_id,
        )
        try:
            voice_result = self._generate_audio(audio_root, scene["scene_order"], scene["narration_text"])
            audio_path = voice_result.audio_path
            subtitle_path = voice_result.subtitle_path
            duration = voice_result.duration_sec
            audio_source = voice_result.source
            audio_status = "completed"
        except Exception as exc:
            self.logger.log(
                "voice_generation", "failed",
                f"Voice generation failed for scene {scene['scene_order']}: {exc}",
                project_id,
            )
            duration = self._estimate_duration(scene["narration_text"])
            audio_path = audio_root / f"scene-{scene['scene_order']:02d}.wav"
            self._create_silent_wav(audio_path, duration)
            subtitle_path = None
            audio_source = "demo_silent"
            audio_status = "failed"

        self.logger.log(
            "voice_generation", audio_status,
            f"Voice generation {audio_status} for scene {scene['scene_order']} (source={audio_source}, duration={duration}s).",
            project_id,
        )

        self.logger.log(
            "visual_generation", "running",
            f"Starting visual generation for scene {scene['scene_order']} using scene renderer.",
            project_id,
        )
        visual_pattern = str(scene.get("visual_type") or "")
        visual_concept = str(scene.get("visual_instruction") or "")
        scene_section: dict[str, object] = {"visual_plan": self._scene_visual_plan(scene)}
        debug_trace = new_trace_for_scene(project_id, scene)
        try:
            started = stage_timer()
            scene_section = self._section_for_scene_render(scene, duration, audio_path, debug_trace=debug_trace)
            if debug_trace:
                debug_trace.event("story_pipeline", "completed", {"output_hash": stable_hash(scene_section)}, duration_ms=elapsed_ms(started))
            visual_path, visual_source, visual_pattern, visual_concept = self._render_scene_with_scene_builder(
                image_root,
                scene["scene_order"],
                scene_section,
                debug_trace=debug_trace,
            )
            visual_status = "completed"
            self.logger.log(
                "visual_generation", "completed",
                f"Visual generation completed for scene {scene['scene_order']} (source={visual_source}).",
                project_id,
            )
        except Exception as exc:
            self.logger.log(
                "visual_generation", "failed",
                f"Visual generation failed for scene {scene['scene_order']}: {exc}",
                project_id,
            )
            if debug_trace:
                debug_trace.error("visual_generation", str(exc), {"scene_order": scene["scene_order"]})
            visual_path = None
            visual_source = "remotion_failed"
            visual_status = "failed"
        finally:
            if debug_trace:
                SceneDebugStore().save(debug_trace)

        scene_status = "generated" if (audio_status == "completed" and visual_status == "completed") else "failed"
        self.repo.update_scene(
            scene["id"],
            audio_path=str(Path(audio_path).expanduser().resolve()),
            audio_duration_sec=duration,
            subtitle_path=str(subtitle_path) if subtitle_path else None,
            visual_path=str(visual_path) if visual_path else None,
            audio_source=audio_source,
            visual_source=visual_source,
            visual_type=visual_pattern,
            visual_instruction=visual_concept,
            visual_plan_json=json.dumps(scene_section.get("visual_plan") or [], ensure_ascii=False),
            status=scene_status,
        )

    def compute_dynamic_visual_ratio(self, project_id: int) -> tuple[float, list[dict]]:
        scenes = self.repo.list_scenes(project_id)
        return self.coverage_calculator.compute(scenes)

    def _section_for_scene_render(
        self,
        scene: dict,
        audio_duration: float,
        audio_path: Path,
        debug_trace: SceneDebugTrace | None = None,
    ) -> dict:
        return self.scene_section_builder.section_for_scene_render(
            scene,
            audio_duration,
            audio_path,
            debug_trace=debug_trace,
        )


    def _scene_visual_plan(self, scene: dict) -> list[dict]:
        return self.scene_section_builder.scene_visual_plan(scene)

    def _derived_visual_plan_from_narration(self, narration: str, kind: str) -> list[dict]:
        return self.scene_section_builder.derived_visual_plan_from_narration(narration, kind)

    def _section_intelligence_from_narration(
        self,
        narration: str,
        kind: str,
        visual_scene: dict | None = None,
        debug_trace: SceneDebugTrace | None = None,
    ) -> dict:
        return self.scene_section_builder.section_intelligence_from_narration(
            narration,
            kind,
            visual_scene=visual_scene,
            debug_trace=debug_trace,
        )

    def _outro_section_intelligence(self, narration: str) -> dict:
        return self.scene_section_builder.outro_section_intelligence(narration)

    def _outro_actions(self, narration: str) -> list[dict[str, object]]:
        return self.scene_section_builder.outro_actions(narration)

    def _outro_punchline(self, narration: str) -> str:
        return self.scene_section_builder.outro_punchline(narration)

    def _scene_text_signals(self, narration: str) -> dict[str, object]:
        return self.scene_section_builder.scene_text_signals(narration)

    def _dominant_entity_from_text(self, narration: str) -> str:
        return self.scene_section_builder.dominant_entity_from_text(narration)

    def _idea_type_from_text(self, narration: str) -> str:
        return self.scene_section_builder.idea_type_from_text(narration)

    def _json_dict_from_scene_field(self, value: object) -> dict:
        return self.scene_section_builder.json_dict_from_scene_field(value)

    def _weight_for_scene_kind(self, kind: str) -> dict[str, object]:
        return self.scene_section_builder.weight_for_scene_kind(kind)

    def _render_scene_with_scene_builder(
        self,
        image_root: Path,
        scene_order: int,
        section: dict,
        debug_trace: SceneDebugTrace | None = None,
    ) -> tuple[Path, str, str, str]:
        scene_result = build_scenes([section], debug_trace=debug_trace)["scenes"][0]
        output_path = image_root / f"scene-{scene_order:02d}.mp4"
        spec = RenderSpec(
            composition="VideoRenderer",
            props={"scenes": [scene_result]},
            duration_sec=float(scene_result.get("duration") or 0),
            source="remotion_scene_builder",
        )
        if debug_trace:
            debug_trace.snapshot(
                "render_spec_pre",
                {"composition": spec.composition, "props": spec.props, "duration_sec": spec.duration_sec, "source": spec.source, "output_path": output_path},
                owner="render_spec_service",
            )
            debug_trace.ownership("component", "render_spec_service", spec.composition, "VideoRenderer RenderSpec selected")
            debug_trace.determinism("render_spec", scene_result, {"composition": spec.composition, "duration_sec": spec.duration_sec, "source": spec.source})
        self.remotion.render_video(spec, output_path)
        return (
            output_path,
            "remotion_scene_builder",
            str(scene_result.get("pattern") or ""),
            str(scene_result.get("concept") or ""),
        )

    def project_media_summary(self, project_id: int) -> dict[str, object]:
        scenes = self.repo.list_scenes(project_id)
        return self.summary_builder.project_media_summary(scenes)

    def project_voice_summary(self, project_id: int) -> dict[str, object]:
        scenes = self.repo.list_scenes(project_id)
        mode = current_app.config.get("VOICE_PROVIDER", current_app.config.get("VOICE_MODE", "demo"))
        return self.summary_builder.project_voice_summary(scenes, mode)

    def run_voice_check(self) -> dict[str, object]:
        audio_root = Path(current_app.config["STORAGE_ROOT"]) / "audio" / "voice-check"
        audio_root.mkdir(parents=True, exist_ok=True)
        mode = current_app.config.get("VOICE_PROVIDER", "kokoro")
        try:
            result = self.voice_service.run_voice_check(audio_root)
        except Exception as exc:
            friendly_error = self._summarize_tts_error(exc)
            self.logger.log("voice_check", "failed", f"Voice check failed ({friendly_error}).")
            return self.voice_check_results.failure(exc, mode)

        self.logger.log("voice_check", "completed", f"Voice check completed with {result.source}.")
        return self.voice_check_results.success(result, mode)

    def _estimate_duration(self, narration: str) -> float:
        return self.audio_fallbacks.estimate_duration(narration)

    def _generate_audio(self, audio_root: Path, scene_order: int, narration: str):
        return self.voice_service.generate_scene_audio(audio_root, scene_order, narration)

    def _edge_tts_audio(self, audio_root: Path, scene_order: int, narration: str) -> tuple[Path, Path | None, float, str]:
        return generate_edge_tts_audio(
            audio_root,
            scene_order,
            narration,
            current_app.config,
            probe_duration=self._probe_duration,
            cleanup_empty_file=self._cleanup_empty_file,
        )

    def _cleanup_empty_file(self, path: Path) -> None:
        self.audio_fallbacks.cleanup_empty_file(path)

    # -----------------------------------------------------------------------
    # Visual generation — dispatcher
    # -----------------------------------------------------------------------
    def _generate_visual(
        self,
        project_id: int,
        image_root: Path,
        scene: dict,
        scene_order: int,
        narration: str,
        visual_type: str | None,
        visual_instruction: str | None,
        target_duration: float,
    ) -> tuple[Path, str]:
        source_asset_path = None
        if visual_type == "broll":
            source_asset_path = None

        if not current_app.config.get("REMOTION_ENABLED", True):
            raise RuntimeError("Remotion visuals are required, but REMOTION_ENABLED=false.")

        spec = self.render_specs.scene_spec(
            {**scene, "visual_type": visual_type},
            target_duration,
            source_asset_path=source_asset_path,
        )
        if self._visual_debug_enabled():
            validated_scene = {
                "visual_type": visual_type,
                "visual_instruction": visual_instruction,
                "narration_text": narration,
            }
            self._print_visual_debug(
                {**scene, "scene_order": scene_order, "narration_text": narration},
                [
                    {
                        "visual_logic": {"type": "scene", "content": visual_instruction or narration},
                        "validated_beat": validated_scene,
                        "render_spec": {"component": spec.composition, "props": spec.props},
                    }
                ],
            )
        output_path = image_root / f"scene-{scene_order:02d}.mp4"
        self.remotion.render_video(spec, output_path)
        return output_path, spec.source

    def _scene_media_complete(self, scene: dict) -> bool:
        audio_path = scene.get("audio_path")
        visual_path = scene.get("visual_path")
        return (
            scene.get("status") == "generated"
            and bool(audio_path)
            and bool(visual_path)
            and Path(str(audio_path)).exists()
            and Path(str(visual_path)).exists()
        )

    def generate_beat_clips(
        self,
        project_id: int,
        image_root: Path,
        scene: dict,
        scene_duration: float,
    ) -> tuple[Path, str]:
        return self.beat_clip_generator.generate(
            config=current_app.config,
            project_id=project_id,
            image_root=image_root,
            scene=scene,
            scene_duration=scene_duration,
        )

    def _regenerated_beat_from_scene(self, scene: dict, original: dict, beat_index: int) -> dict:
        narration = str(scene.get("narration_text") or scene.get("visual_instruction") or "")
        classified_intent = self.render_specs.classifyIntent(narration)
        logic = self.render_specs.deriveFromNarration(narration, classified_intent=classified_intent)
        pattern = self.render_specs.LOGIC_TYPE_TO_PATTERN.get(str(logic.get("type") or ""), "MONEY_FLOW")
        return {
            "beat_index": beat_index,
            "intent": "COMPARISON" if logic.get("type") == "comparison" else "EXPLANATION",
            "pattern": pattern,
            "visual_logic": logic,
            "classified_intent": classified_intent,
            "narration": narration,
            "estimated_start_sec": original.get("estimated_start_sec", 0),
            "estimated_duration_sec": original.get("estimated_duration_sec", 3),
        }

    def _visual_debug_enabled(self) -> bool:
        return bool(current_app.config.get("VISUAL_DEBUG", False))

    def _print_existing_scene_debug(self, scene: dict) -> None:
        self.visual_debug_printer.print_existing_scene_debug(scene)

    def _validated_beat_for_debug(self, beat: dict) -> dict:
        return self.visual_debug_printer.validated_beat_for_debug(beat)

    def _debug_entry(self, validated_beat: dict, spec) -> dict:
        return self.visual_debug_printer.debug_entry(validated_beat, spec)

    def _print_visual_debug(self, scene: dict, entries: list[dict]) -> None:
        self.visual_debug_printer.print_visual_debug(scene, entries)

    def _load_scene_beats(self, scene: dict, scene_duration: float) -> list[dict]:
        return self.beat_timeline.load_scene_beats(scene, scene_duration)

    def _normalize_beat_durations(self, beats: list[dict], scene_duration: float) -> list[dict]:
        return self.beat_timeline.normalize_beat_durations(beats, scene_duration)

    def _fallback_beat_type(self, visual_type: str | None) -> str:
        return self.beat_timeline.fallback_beat_type(visual_type)

    def _concat_beat_clips(self, beat_paths: list[Path], output_path: Path, target_duration: float) -> None:
        self.beat_timeline.concat_beat_clips(
            beat_paths,
            output_path,
            target_duration,
            probe_duration=self._probe_duration,
        )

    def _ten_minute_finance_enabled(self) -> bool:
        return str(current_app.config.get("CHANNEL_STYLE", "")).lower() == "ten_minute_finance"

    # -----------------------------------------------------------------------
    # Groq API helper (shared by motion_text, graph, broll micro-calls)
    # -----------------------------------------------------------------------
    def _call_groq_api(self, system_prompt: str, user_prompt: str, purpose: str) -> dict:
        """Call Groq API with retries. Returns parsed JSON dict."""
        api_key = current_app.config.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not configured.")
        model = current_app.config.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        return self.groq_json.call_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            purpose=purpose,
            api_key=api_key,
            model=model,
        )

    def _extract_json_from_text(self, raw_text: str) -> dict:
        return self.groq_json.extract_json_from_text(raw_text)

    # -----------------------------------------------------------------------
    # B-roll: Pexels + query simplification
    # -----------------------------------------------------------------------
    def _simplify_broll_query(self, visual_instruction: str) -> str:
        return self.broll_provider.simplify_query(visual_instruction)

    def _pexels_broll(
        self,
        project_id: int,
        image_root: Path,
        scene_order: int,
        query: str,
        target_duration: float,
    ) -> tuple[Path, str]:
        return self.broll_provider.pexels_broll(
            current_app.config,
            project_id,
            scene_order,
            query,
            target_duration,
        )

    def _load_pexels_cache(self, cache_path: Path) -> dict[str, str] | None:
        return self.broll_provider.load_pexels_cache(cache_path)

    def _fetch_pexels_result(self, query: str, target_duration: float) -> dict[str, str]:
        return self.broll_provider.fetch_pexels_result(current_app.config, query, target_duration)

    # -----------------------------------------------------------------------
    # B-roll: Pixabay fallback
    # -----------------------------------------------------------------------
    def _pixabay_broll(
        self,
        project_id: int,
        image_root: Path,
        scene_order: int,
        query: str,
        target_duration: float,
    ) -> tuple[Path, str]:
        return self.broll_provider.pixabay_broll(
            current_app.config,
            project_id,
            scene_order,
            query,
            target_duration,
        )

    def _broll_source_path(self, project_id: int, provider: str, scene_order: int) -> Path:
        return self.broll_provider.broll_source_path(current_app.config, project_id, provider, scene_order)

    # -----------------------------------------------------------------------
    # Motion text: Groq parsing + rendering
    # -----------------------------------------------------------------------
    def _parse_motion_text(self, visual_instruction: str) -> dict:
        return self.legacy_visual_renderer.parse_motion_text(visual_instruction)

    def _render_motion_text_video(
        self,
        image_root: Path,
        scene_order: int,
        text: str,
        target_duration: float,
    ) -> tuple[Path, str]:
        return self.legacy_visual_renderer.render_motion_text_video(
            image_root,
            scene_order,
            text,
            target_duration,
        )

    def _draw_motion_text_frame_v2(
        self, path: Path, headline: str, subtext: str,
        sentiment: str, frame_index: int, frame_count: int,
    ) -> None:
        self.legacy_visual_renderer.draw_motion_text_frame(
            path,
            headline,
            subtext,
            sentiment,
            frame_index,
            frame_count,
        )

    # -----------------------------------------------------------------------
    # Graph: Groq parsing + 4 renderers
    # -----------------------------------------------------------------------
    def _parse_graph_data(self, instruction: str) -> dict:
        return self.legacy_visual_renderer.parse_graph_data(instruction)

    def _render_graph_video(
        self,
        image_root: Path,
        scene_order: int,
        instruction: str,
        target_duration: float,
    ) -> tuple[Path, str]:
        return self.legacy_visual_renderer.render_graph_video(
            image_root,
            scene_order,
            instruction,
            target_duration,
        )

    def _resolve_chart_color(self, color_name: str) -> str:
        return self.legacy_visual_renderer.resolve_chart_color(color_name)

    def _draw_bar_frame(self, path: Path, spec: dict, progress: float) -> None:
        self.legacy_visual_renderer.draw_bar_frame(path, spec, progress)

    def _draw_line_frame(self, path: Path, spec: dict, progress: float) -> None:
        self.legacy_visual_renderer.draw_line_frame(path, spec, progress)

    def _draw_pie_frame(self, path: Path, spec: dict, progress: float) -> None:
        self.legacy_visual_renderer.draw_pie_frame(path, spec, progress)

    def _draw_number_reveal_frame(self, path: Path, spec: dict, progress: float) -> None:
        self.legacy_visual_renderer.draw_number_reveal_frame(path, spec, progress)

    # -----------------------------------------------------------------------
    # FFmpeg / utility helpers
    # -----------------------------------------------------------------------
    def _encode_frame_sequence(self, ffmpeg_bin: str, frame_root: Path, fps: int, output_path: Path) -> None:
        self.ffmpeg.encode_frame_sequence(ffmpeg_bin, frame_root, fps, output_path)

    def _require_ffmpeg(self) -> str:
        ffmpeg_bin = self.ffmpeg.find_binary("ffmpeg", ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"))
        if not ffmpeg_bin:
            raise RuntimeError("ffmpeg is required to render animated visual videos.")
        return ffmpeg_bin

    def _summarize_tts_error(self, exc: Exception) -> str:
        return self.voice_check_results.summarize_tts_error(exc)

    def _format_number(self, value: float) -> str:
        return self.number_formatter.format_number(value)

    def _format_indian_grouped_number(self, value: int) -> str:
        return self.number_formatter.format_indian_grouped_number(value)

    def _create_silent_wav(self, path: Path, duration_sec: float) -> None:
        self.audio_fallbacks.create_silent_wav(path, duration_sec)

    def _probe_duration(self, path: Path) -> float:
        return self.audio_fallbacks.probe_duration(path)

    def _render_image(self, path: Path, text: str, visual_type: str | None) -> None:
        self.static_image_renderer.render_image(path, text, visual_type)

    def _wrap_text(self, text: str, line_length: int) -> str:
        return self.static_image_renderer.wrap_text(text, line_length)
