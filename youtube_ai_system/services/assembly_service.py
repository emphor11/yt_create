from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from flask import current_app

from ..models.repository import ProjectRepository
from .remotion_service import RemotionService, RemotionUnavailableError
from .render_spec_service import RenderSpecService
from .run_log import RunLogger


class AssemblyService:
    FINAL_CRF = "18"
    FINAL_PRESET = "veryfast"
    TARGET_LOUDNESS = "-16"
    TRUE_PEAK = "-1.5"
    LOUDNESS_RANGE = "11"

    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.logger = RunLogger()
        self.render_specs = RenderSpecService()
        self.remotion = RemotionService()

    def assemble_project(self, project_id: int) -> str:
        project = self.repo.get_project(project_id)
        scenes = self.repo.list_scenes(project_id)
        output_dir = Path(current_app.config["STORAGE_ROOT"]) / "video" / str(project_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            summary_path = output_dir / "assembly_manifest.txt"
            lines = [f"Project: {project['working_title']}", ""]
            for scene in scenes:
                lines.append(
                    f"{scene['scene_order']:02d} | {scene['kind']} | {scene['audio_path']} | {scene['visual_path']}"
                )
            summary_path.write_text("\n".join(lines))
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

        self.logger.log("assembly", "running", "Rendering intro, scene timeline, transitions, and end card.", project_id)
        intro_path = output_dir / "intro.mp4"
        self._render_timeline_card(
            ffmpeg_bin,
            self.render_specs.intro_spec(project["working_title"]),
            intro_path,
            label="intro",
        )
        segment_paths.append(intro_path)

        for scene in scenes:
            segment_path = output_dir / f"scene-{scene['scene_order']:02d}.mp4"
            segment_paths.append(segment_path)
            self._render_scene_video(ffmpeg_bin, self._visual_path_for_scene(project_id, scene), scene["audio_path"], segment_path)
            if scene != scenes[-1]:
                transition_path = output_dir / f"transition-{scene['scene_order']:02d}.mp4"
                self._render_timeline_card(
                    ffmpeg_bin,
                    self.render_specs.transition_spec(),
                    transition_path,
                    label="transition",
                )
                segment_paths.append(transition_path)

        end_path = output_dir / "end-card.mp4"
        self._render_timeline_card(
            ffmpeg_bin,
            self.render_specs.end_card_spec(),
            end_path,
            label="end-card",
        )
        segment_paths.append(end_path)

        concat_manifest.write_text(
            "\n".join(f"file '{segment_path.name}'" for segment_path in segment_paths)
        )
        assembled_path = output_dir / "assembled_timeline.mp4"
        self._run_ffmpeg(
            [
                ffmpeg_bin,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_manifest),
                "-c",
                "copy",
                str(assembled_path),
            ],
            cwd=output_dir,
            timeout=180,
        )

        self.logger.log("assembly", "running", "Applying music mix and burned captions when configured.", project_id)
        voice_srt = output_dir / "voice_captions.srt"
        self._write_caption_srt(scenes, voice_srt, intro_offset=3.0, transition_sec=0.5)
        final_path = output_dir / "final_video.mp4"
        processed_path = self._apply_music_and_captions(ffmpeg_bin, assembled_path, voice_srt, final_path)
        self.repo.update_project(project_id, final_video_path=str(processed_path))
        self.logger.log("assembly", "completed", "Rendered V2 pre-CapCut master MP4 with ffmpeg.", project_id)
        return str(processed_path)

    def _visual_path_for_scene(self, project_id: int, scene: dict) -> str:
        storage_root = Path(current_app.config["STORAGE_ROOT"])
        timeline_path = storage_root / "images" / str(project_id) / f"scene-{int(scene['scene_order']):02d}_timeline.mp4"
        if timeline_path.exists():
            return str(timeline_path)
        return str(scene["visual_path"])

    def _render_scene_video(self, ffmpeg_bin: str, visual_path: str, audio_path: str, output_path: Path) -> None:
        visual_suffix = Path(visual_path).suffix.lower()
        if visual_suffix in {".mp4", ".mov", ".mkv", ".webm"}:
            command = [
                ffmpeg_bin,
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                visual_path,
                "-i",
                audio_path,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",
                "-vf",
                "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                self.FINAL_CRF,
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        else:
            command = [
                ffmpeg_bin,
                "-y",
                "-loop",
                "1",
                "-i",
                visual_path,
                "-i",
                audio_path,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",
                "-vf",
                "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                self.FINAL_CRF,
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        self._run_ffmpeg(command)

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
        self._run_ffmpeg(
            [
                ffmpeg_bin,
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c=black:s=1920x1080:r=30:d={duration_sec}",
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=channel_layout=stereo:sample_rate=48000:d={duration_sec}",
                "-shortest",
                "-c:v",
                "libx264",
                "-preset",
                self.FINAL_PRESET,
                "-crf",
                self.FINAL_CRF,
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(output_path),
            ],
        )

    def _add_silent_audio(self, ffmpeg_bin: str, input_path: Path, output_path: Path, duration_sec: float) -> None:
        self._run_ffmpeg(
            [
                ffmpeg_bin,
                "-y",
                "-i",
                str(input_path),
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=channel_layout=stereo:sample_rate=48000:d={duration_sec}",
                "-shortest",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(output_path),
            ],
        )

    def _has_audio_stream(self, path: Path) -> bool:
        ffprobe_bin = shutil.which("ffprobe")
        if not ffprobe_bin:
            return False
        result = subprocess.run(
            [
                ffprobe_bin,
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(result.stdout or "{}")
        return bool(payload.get("streams"))

    def _write_caption_srt(
        self,
        scenes: list[dict],
        output_path: Path,
        intro_offset: float,
        transition_sec: float,
    ) -> None:
        lines: list[str] = []
        cursor = intro_offset
        index = 1
        for scene_number, scene in enumerate(scenes):
            duration = float(scene.get("audio_duration_sec") or 0) or 2.5
            chunks = self._caption_chunks(str(scene.get("narration_text") or ""))
            chunk_duration = duration / max(len(chunks), 1)
            scene_start = cursor
            for chunk_index, chunk in enumerate(chunks):
                start = scene_start + (chunk_index * chunk_duration)
                end = min(start + chunk_duration, scene_start + duration)
                lines.extend([str(index), f"{self._srt_time(start)} --> {self._srt_time(end)}", chunk, ""])
                index += 1
            cursor = scene_start + duration
            if scene_number != len(scenes) - 1:
                cursor += transition_sec
        output_path.write_text("\n".join(lines), encoding="utf-8")

    def _caption_chunks(self, text: str, words_per_line: int = 7) -> list[str]:
        words = text.split()
        if not words:
            return ["YTCreate Finance"]
        return [" ".join(words[i : i + words_per_line]) for i in range(0, len(words), words_per_line)]

    def _srt_time(self, seconds: float) -> str:
        millis = int(round(seconds * 1000))
        hours, millis = divmod(millis, 3_600_000)
        minutes, millis = divmod(millis, 60_000)
        secs, millis = divmod(millis, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

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
            self._burn_captions(ffmpeg_bin, current_path, captions_path, captioned_path)
            current_path = captioned_path

        self._final_export(ffmpeg_bin, current_path, output_path)
        return output_path

    def _mix_background_music(self, ffmpeg_bin: str, input_path: Path, music_path: Path, output_path: Path) -> None:
        duration = max(self._probe_duration(input_path), 0.1)
        volume = float(current_app.config.get("BACKGROUND_MUSIC_VOLUME", 0.08))
        fade_out_start = max(duration - 3.0, duration * 0.85)
        self._run_ffmpeg(
            [
                ffmpeg_bin,
                "-y",
                "-i",
                str(input_path),
                "-stream_loop",
                "-1",
                "-i",
                str(music_path),
                "-filter_complex",
                (
                    f"[1:a]atrim=0:{duration:.2f},afade=t=in:st=0:d=2,"
                    f"afade=t=out:st={fade_out_start:.2f}:d=3,volume={volume}[music];"
                    "[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
                ),
                "-map",
                "0:v",
                "-map",
                "[aout]",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(output_path),
            ]
        )

    def _burn_captions(self, ffmpeg_bin: str, input_path: Path, captions_path: Path, output_path: Path) -> None:
        safe_srt = str(captions_path).replace("'", "\\'")
        self._run_ffmpeg(
            [
                ffmpeg_bin,
                "-y",
                "-i",
                str(input_path),
                "-vf",
                f"subtitles='{safe_srt}':force_style='Fontsize=28,Outline=2,PrimaryColour=&HFFFFFF&,Alignment=2,MarginV=90'",
                "-c:v",
                "libx264",
                "-preset",
                self.FINAL_PRESET,
                "-crf",
                self.FINAL_CRF,
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )

    def _final_export(self, ffmpeg_bin: str, input_path: Path, output_path: Path) -> None:
        self._run_ffmpeg(
            [
                ffmpeg_bin,
                "-y",
                "-i",
                str(input_path),
                "-filter_complex",
                (
                    "[0:v]eq=contrast=1.05:saturation=0.94:brightness=-0.01[v];"
                    f"[0:a]loudnorm=I={self.TARGET_LOUDNESS}:TP={self.TRUE_PEAK}:LRA={self.LOUDNESS_RANGE}[a]"
                ),
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-c:v",
                "libx264",
                "-preset",
                self.FINAL_PRESET,
                "-crf",
                self.FINAL_CRF,
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(output_path),
            ],
            timeout=int(current_app.config.get("ASSEMBLY_FFMPEG_TIMEOUT", 600)),
        )

    def _probe_duration(self, path: Path) -> float:
        ffprobe_bin = shutil.which("ffprobe")
        if not ffprobe_bin:
            return 0.0
        try:
            result = subprocess.run(
                [
                    ffprobe_bin,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "json",
                    str(path),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            payload = json.loads(result.stdout or "{}")
            return float((payload.get("format") or {}).get("duration") or 0.0)
        except (subprocess.SubprocessError, ValueError, json.JSONDecodeError):
            return 0.0

    def _run_ffmpeg(self, command: list[str], cwd: Path | None = None, timeout: int | None = None) -> subprocess.CompletedProcess:
        timeout_sec = int(timeout or current_app.config.get("ASSEMBLY_FFMPEG_TIMEOUT", 600))
        try:
            return subprocess.run(
                command,
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"FFmpeg assembly step timed out after {timeout_sec}s.") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            if len(detail) > 800:
                detail = detail[:800].rstrip() + "...[truncated]"
            raise RuntimeError(f"FFmpeg assembly step failed: {detail}") from exc
