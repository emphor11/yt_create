from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import current_app

from ..infrastructure.ffmpeg import FfmpegExecutor
from ..infrastructure.filesystem.storage import FileStorage
from ..models.repository import ProjectRepository
from ..pipelines.assembly.captions import CaptionWriter
from ..pipelines.assembly.ffmpeg_commands import AssemblyEncodingProfile, AssemblyFfmpegCommands
from ..pipelines.assembly.manifest import TimelineManifestBuilder
from ..pipelines.assembly.quality import MasterQualityGate
from .remotion_service import RemotionService, RemotionUnavailableError
from .render_spec_service import RenderSpecService
from .run_log import RunLogger


class AssemblyService:
    FINAL_CRF = "18"
    FINAL_PRESET = "veryfast"
    TARGET_LOUDNESS = "-16"
    TRUE_PEAK = "-1.5"
    LOUDNESS_RANGE = "11"
    FINAL_FPS = "30"
    FINAL_VIDEO_BITRATE = "8M"
    FINAL_MAXRATE = "10M"
    FINAL_BUFSIZE = "16M"

    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.logger = RunLogger()
        self.render_specs = RenderSpecService()
        self.remotion = RemotionService()
        self.ffmpeg = FfmpegExecutor()
        self.commands = AssemblyFfmpegCommands(
            AssemblyEncodingProfile(
                final_crf=self.FINAL_CRF,
                final_preset=self.FINAL_PRESET,
                target_loudness=self.TARGET_LOUDNESS,
                true_peak=self.TRUE_PEAK,
                loudness_range=self.LOUDNESS_RANGE,
                final_fps=self.FINAL_FPS,
                final_video_bitrate=self.FINAL_VIDEO_BITRATE,
                final_maxrate=self.FINAL_MAXRATE,
                final_bufsize=self.FINAL_BUFSIZE,
            )
        )
        self.caption_writer = CaptionWriter()
        self.manifest_builder = TimelineManifestBuilder()
        self.quality_gate = MasterQualityGate(self.ffmpeg)

    def assemble_project(self, project_id: int) -> str:
        project = self.repo.get_project(project_id)
        scenes = self.repo.list_scenes(project_id)
        output_dir = FileStorage(Path(current_app.config["STORAGE_ROOT"])).project_video_dir(project_id)
        ffmpeg_bin = self.ffmpeg.which("ffmpeg")
        if not ffmpeg_bin:
            summary_path = output_dir / "assembly_manifest.txt"
            summary_path.write_text(self.manifest_builder.text_manifest(project, scenes))
            self.repo.update_project(project_id, final_video_path=str(summary_path))
            self.logger.log(
                "assembly",
                "completed",
                "Created assembly manifest. Replace with ffmpeg assembly once ffmpeg is installed.",
                project_id,
            )
            return str(summary_path)

        segment_paths: list[Path] = []
        concat_manifest = output_dir / "segments.txt"

        include_intro = bool(current_app.config.get("ASSEMBLY_INCLUDE_INTRO", False))
        include_transitions = bool(current_app.config.get("ASSEMBLY_INCLUDE_TRANSITIONS", False))
        include_end_card = bool(current_app.config.get("ASSEMBLY_INCLUDE_END_CARD", True))

        self.logger.log("assembly", "running", "Rendering ordered scene timeline and end card.", project_id)
        if include_intro:
            intro_title = project.get("selected_title") or project.get("working_title") or "YTCreate Finance"
            intro_path = output_dir / "intro.mp4"
            self._render_timeline_card(
                ffmpeg_bin,
                self.render_specs.intro_spec(intro_title),
                intro_path,
                label="intro",
            )
            segment_paths.append(intro_path)

        for scene in scenes:
            segment_path = output_dir / f"scene-{scene['scene_order']:02d}.mp4"
            segment_paths.append(segment_path)
            self._render_scene_video(ffmpeg_bin, self._visual_path_for_scene(project_id, scene), scene["audio_path"], segment_path)
            if include_transitions and scene != scenes[-1]:
                transition_path = output_dir / f"transition-{scene['scene_order']:02d}.mp4"
                self._render_timeline_card(
                    ffmpeg_bin,
                    self.render_specs.transition_spec(),
                    transition_path,
                    label="transition",
                )
                segment_paths.append(transition_path)

        if include_end_card:
            end_path = output_dir / "end-card.mp4"
            self._render_timeline_card(
                ffmpeg_bin,
                self.render_specs.end_card_spec(),
                end_path,
                label="end-card",
            )
            segment_paths.append(end_path)

        concat_manifest.write_text(self.manifest_builder.ffmpeg_concat_manifest(segment_paths))
        assembled_path = output_dir / "assembled_timeline.mp4"
        self._concat_segments(ffmpeg_bin, segment_paths, assembled_path, output_dir)

        self.logger.log("assembly", "running", "Applying music mix and burned captions when configured.", project_id)
        voice_srt = output_dir / "voice_captions.srt"
        intro_offset = 3.0 if include_intro else 0.0
        transition_sec = 0.5 if include_transitions else 0.0
        self._write_caption_srt(scenes, voice_srt, intro_offset=intro_offset, transition_sec=transition_sec)
        final_path = output_dir / "final_video.mp4"
        processed_path = self._apply_music_and_captions(ffmpeg_bin, assembled_path, voice_srt, final_path)
        self._assert_final_master_quality(processed_path)
        self.repo.update_project(project_id, final_video_path=str(processed_path))
        self.logger.log("assembly", "completed", "Rendered V2 pre-CapCut master MP4 with ffmpeg.", project_id)
        return str(processed_path)

    def _concat_segments(self, ffmpeg_bin: str, segment_paths: list[Path], output_path: Path, cwd: Path) -> None:
        if not segment_paths:
            raise RuntimeError("No rendered scene segments are available for assembly.")
        self._run_ffmpeg(
            self.commands.concat_segments(ffmpeg_bin, segment_paths, output_path),
            cwd=cwd,
            timeout=180,
        )

    def _visual_path_for_scene(self, project_id: int, scene: dict) -> str:
        storage_root = Path(current_app.config["STORAGE_ROOT"])
        timeline_path = storage_root / "images" / str(project_id) / f"scene-{int(scene['scene_order']):02d}_timeline.mp4"
        if timeline_path.exists():
            return str(timeline_path)
        return str(scene["visual_path"])

    def _render_scene_video(self, ffmpeg_bin: str, visual_path: str, audio_path: str, output_path: Path) -> None:
        self._run_ffmpeg(self.commands.render_scene_video(ffmpeg_bin, visual_path, audio_path, output_path))

    def _render_timeline_card(self, ffmpeg_bin: str, spec, output_path: Path, label: str) -> None:
        try:
            self.remotion.render_video(spec, output_path)
            if self._has_audio_stream(output_path):
                return
            with_audio = output_path.with_name(f"{output_path.stem}-audio.mp4")
            self._add_silent_audio(ffmpeg_bin, output_path, with_audio, spec.duration_sec)
            with_audio.replace(output_path)
        except (RemotionUnavailableError, RuntimeError):
            self._render_color_clip(ffmpeg_bin, output_path, spec.duration_sec, label)

    def _render_color_clip(self, ffmpeg_bin: str, output_path: Path, duration_sec: float, label: str) -> None:
        self._run_ffmpeg(self.commands.color_clip(ffmpeg_bin, output_path, duration_sec))

    def _add_silent_audio(self, ffmpeg_bin: str, input_path: Path, output_path: Path, duration_sec: float) -> None:
        self._run_ffmpeg(self.commands.silent_audio(ffmpeg_bin, input_path, output_path, duration_sec))

    def _has_audio_stream(self, path: Path) -> bool:
        return self.ffmpeg.has_audio_stream(path)

    def _write_caption_srt(
        self,
        scenes: list[dict],
        output_path: Path,
        intro_offset: float,
        transition_sec: float,
    ) -> None:
        self.caption_writer.write(
            scenes,
            output_path,
            intro_offset=intro_offset,
            transition_sec=transition_sec,
        )

    def _caption_chunks(self, text: str, words_per_line: int = 7) -> list[str]:
        return self.caption_writer.chunks(text, words_per_line=words_per_line)

    def _srt_time(self, seconds: float) -> str:
        return self.caption_writer.srt_time(seconds)

    def _apply_music_and_captions(
        self,
        ffmpeg_bin: str,
        input_path: Path,
        captions_path: Path,
        output_path: Path,
    ) -> Path:
        current_path = input_path
        music_path = current_app.config.get("BACKGROUND_MUSIC_PATH")
        if current_app.config.get("MUSIC_ENABLED") and music_path and Path(music_path).exists():
            music_output = output_path.with_name("timeline_with_music.mp4")
            self._mix_background_music(ffmpeg_bin, current_path, Path(music_path), music_output)
            current_path = music_output

        captioned_path = output_path.with_name("timeline_with_captions.mp4")
        if current_app.config.get("CAPTIONS_ENABLED") and captions_path.exists():
            try:
                self._burn_captions(ffmpeg_bin, current_path, captions_path, captioned_path)
                current_path = captioned_path
            except RuntimeError as exc:
                current_app.logger.warning(
                    "Caption burn failed; continuing final export without burned captions. SRT remains at %s. Error: %s",
                    captions_path,
                    exc,
                )

        self._final_export(ffmpeg_bin, current_path, output_path)
        return output_path

    def _mix_background_music(self, ffmpeg_bin: str, input_path: Path, music_path: Path, output_path: Path) -> None:
        duration = max(self._probe_duration(input_path), 0.1)
        volume = float(current_app.config.get("BACKGROUND_MUSIC_VOLUME", 0.08))
        fade_out_start = max(duration - 3.0, duration * 0.85)
        self._run_ffmpeg(
            self.commands.mix_background_music(
                ffmpeg_bin,
                input_path,
                music_path,
                output_path,
                duration=duration,
                volume=volume,
                fade_out_start=fade_out_start,
            )
        )

    def _burn_captions(self, ffmpeg_bin: str, input_path: Path, captions_path: Path, output_path: Path) -> None:
        self._run_ffmpeg(self.commands.burn_captions(ffmpeg_bin, input_path, captions_path, output_path))

    def _final_export(self, ffmpeg_bin: str, input_path: Path, output_path: Path) -> None:
        self._run_ffmpeg(
            self.commands.final_export(ffmpeg_bin, input_path, output_path),
            timeout=int(current_app.config.get("ASSEMBLY_FFMPEG_TIMEOUT", 600)),
        )

    def _assert_final_master_quality(self, path: Path) -> None:
        self.quality_gate.assert_final_master_quality(path)

    def _probe_duration(self, path: Path) -> float:
        return self.ffmpeg.probe_duration(path)

    def _run_ffmpeg(self, command: list[str], cwd: Path | None = None, timeout: int | None = None) -> Any:
        timeout_sec = int(timeout or current_app.config.get("ASSEMBLY_FFMPEG_TIMEOUT", 600))
        return self.ffmpeg.run(command, cwd=cwd, timeout=timeout_sec)
