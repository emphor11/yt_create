from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import tempfile
import subprocess
import wave
from pathlib import Path

from flask import current_app
from PIL import Image, ImageDraw, ImageFont
import requests

from ..models.repository import ProjectRepository
from .run_log import RunLogger


class MediaService:
    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.logger = RunLogger()

    def generate_voice_and_visuals(self, project_id: int) -> None:
        project = self.repo.get_project(project_id)
        scenes = self.repo.list_scenes(project_id)
        audio_root = Path(current_app.config["STORAGE_ROOT"]) / "audio" / str(project_id)
        image_root = Path(current_app.config["STORAGE_ROOT"]) / "images" / str(project_id)
        audio_root.mkdir(parents=True, exist_ok=True)
        image_root.mkdir(parents=True, exist_ok=True)
        self.logger.log("media_generation", "running", "Generating scene media.", project_id)

        for scene in scenes:
            audio_path, subtitle_path, duration, audio_source = self._generate_audio(
                audio_root,
                scene["scene_order"],
                scene["narration_text"],
            )
            visual_path, visual_source = self._generate_visual(
                project_id,
                image_root,
                scene["scene_order"],
                scene["narration_text"],
                scene["visual_type"],
                scene.get("visual_instruction"),
                duration,
            )
            self.repo.update_scene(
                scene["id"],
                audio_path=str(audio_path),
                audio_duration_sec=duration,
                subtitle_path=str(subtitle_path) if subtitle_path else None,
                visual_path=str(visual_path),
                audio_source=audio_source,
                visual_source=visual_source,
                status="generated",
            )

        live_audio_count = sum(
            1 for scene in self.repo.list_scenes(project_id) if scene.get("audio_source") == "edge_tts"
        )
        self.logger.log(
            "media_generation",
            "completed",
            (
                f"Generated media assets for {len(scenes)} scenes in project '{project['working_title']}'. "
                f"Live voice used on {live_audio_count} scene(s)."
            ),
            project_id,
        )

    def compute_dynamic_visual_ratio(self, project_id: int) -> tuple[float, list[dict]]:
        dynamic_types = set(current_app.config["ALLOWED_VISUAL_TYPES"])
        scenes = self.repo.list_scenes(project_id)
        if not scenes:
            return 0.0, []
        dynamic_count = sum(1 for scene in scenes if scene.get("visual_type") in dynamic_types)
        return dynamic_count / len(scenes), scenes

    def project_media_summary(self, project_id: int) -> dict[str, object]:
        scenes = self.repo.list_scenes(project_id)
        audio_counts: dict[str, int] = {}
        visual_counts: dict[str, int] = {}
        generated_visuals = 0

        for scene in scenes:
            audio_source = scene.get("audio_source") or "unknown"
            visual_source = scene.get("visual_source") or "unknown"
            audio_counts[audio_source] = audio_counts.get(audio_source, 0) + 1
            visual_counts[visual_source] = visual_counts.get(visual_source, 0) + 1
            if scene.get("visual_path"):
                generated_visuals += 1

        total = len(scenes)
        if not total:
            voice_status = "not_run"
            voice_message = "Voice generation has not run yet."
            visual_status = "not_run"
            visual_message = "Visual generation has not run yet."
        else:
            if audio_counts.get("edge_tts") == total:
                voice_status = "live"
                voice_message = "All scenes used live Edge TTS."
            elif audio_counts.get("edge_tts", 0) > 0:
                voice_status = "mixed"
                voice_message = "Some scenes used live Edge TTS and some used demo fallback audio."
            elif audio_counts.get("demo_silent") == total:
                voice_status = "demo"
                voice_message = "All scenes used demo fallback audio."
            else:
                voice_status = "unknown"
                voice_message = "Voice sources are mixed or unavailable."

            if generated_visuals == total:
                visual_status = "generated"
                visual_message = "Every scene has a generated visual asset."
            elif generated_visuals > 0:
                visual_status = "partial"
                visual_message = "Some scenes have generated visual assets."
            else:
                visual_status = "missing"
                visual_message = "No generated visual assets were found."

        return {
            "total_scenes": total,
            "voice_status": voice_status,
            "voice_message": voice_message,
            "audio_counts": audio_counts,
            "visual_status": visual_status,
            "visual_message": visual_message,
            "visual_counts": visual_counts,
        }

    def project_voice_summary(self, project_id: int) -> dict[str, object]:
        scenes = self.repo.list_scenes(project_id)
        counts: dict[str, int] = {}
        for scene in scenes:
            source = scene.get("audio_source") or "unknown"
            counts[source] = counts.get(source, 0) + 1

        total = len(scenes)
        if not total:
            status = "not_run"
            message = "Voice generation has not run yet for this project."
        elif counts.get("edge_tts") == total:
            status = "live"
            message = "All scene audio was generated with live Edge TTS."
        elif counts.get("edge_tts", 0) > 0:
            status = "mixed"
            message = "Some scenes used live Edge TTS and some fell back to demo silent audio."
        elif counts.get("demo_silent") == total:
            status = "demo"
            message = "All scenes used demo silent audio."
        else:
            status = "unknown"
            message = "Audio sources are mixed or unavailable."

        return {
            "mode": current_app.config.get("VOICE_MODE", "demo"),
            "status": status,
            "message": message,
            "counts": counts,
            "total_scenes": total,
        }

    def run_voice_check(self) -> dict[str, object]:
        voice_mode = current_app.config.get("VOICE_MODE", "demo")
        audio_root = Path(current_app.config["STORAGE_ROOT"]) / "audio" / "voice-check"
        audio_root.mkdir(parents=True, exist_ok=True)

        if voice_mode != "auto":
            sample_path = audio_root / "scene-01.wav"
            duration = self._estimate_duration("Voice mode is set to demo, so this check uses silent fallback audio.")
            self._create_silent_wav(sample_path, duration)
            return {
                "mode": voice_mode,
                "status": "demo",
                "audio_source": "demo_silent",
                "audio_path": str(sample_path),
                "subtitle_path": None,
                "duration": duration,
                "message": "VOICE_MODE is not set to auto, so the app is currently using demo silent audio.",
            }

        sample_text = (
            "This is a live voice check for YTCreate. If you can hear natural speech, Edge TTS is working."
        )
        try:
            audio_path, subtitle_path, duration, audio_source = self._edge_tts_audio(audio_root, 1, sample_text)
        except Exception as exc:
            friendly_error = self._summarize_tts_error(exc)
            self.logger.log("voice_check", "failed", f"Live Edge TTS check failed ({friendly_error}).")
            return {
                "mode": voice_mode,
                "status": "failed",
                "audio_source": "edge_tts_failed",
                "audio_path": None,
                "subtitle_path": None,
                "duration": None,
                "message": f"Live Edge TTS check failed: {friendly_error}",
            }

        self.logger.log("voice_check", "completed", "Live Edge TTS check succeeded.")
        return {
            "mode": voice_mode,
            "status": "live",
            "audio_source": audio_source,
            "audio_path": str(audio_path),
            "subtitle_path": str(subtitle_path) if subtitle_path else None,
            "duration": duration,
            "message": "Live Edge TTS check succeeded.",
        }

    def _estimate_duration(self, narration: str) -> float:
        words = max(len(narration.split()), 1)
        return round(max(words / 2.4, 2.5), 2)

    def _generate_visual(
        self,
        project_id: int,
        image_root: Path,
        scene_order: int,
        narration: str,
        visual_type: str | None,
        visual_instruction: str | None,
        target_duration: float,
    ) -> tuple[Path, str]:
        if visual_type == "broll" and current_app.config.get("PEXELS_API_KEY"):
            try:
                return self._pexels_broll(
                    project_id,
                    image_root,
                    scene_order,
                    visual_instruction or narration,
                    target_duration,
                )
            except Exception as exc:
                self.logger.log(
                    "visual_generation",
                    "failed",
                    f"Pexels b-roll failed for scene {scene_order} ({exc}). Falling back to generated image.",
                )

        if visual_type == "motion_text":
            try:
                return self._render_motion_text_video(
                    image_root,
                    scene_order,
                    visual_instruction or narration,
                    target_duration,
                )
            except Exception as exc:
                self.logger.log(
                    "visual_generation",
                    "failed",
                    f"Motion text video failed for scene {scene_order} ({exc}). Falling back to generated image.",
                )

        if visual_type == "graph":
            try:
                return self._render_graph_video(
                    image_root,
                    scene_order,
                    visual_instruction or narration,
                    target_duration,
                )
            except Exception as exc:
                self.logger.log(
                    "visual_generation",
                    "failed",
                    f"Graph video failed for scene {scene_order} ({exc}). Falling back to generated image.",
                )

        visual_path = image_root / f"scene-{scene_order:02d}.png"
        self._render_image(visual_path, narration, visual_type)
        return visual_path, "generated_image"

    def _generate_audio(self, audio_root: Path, scene_order: int, narration: str) -> tuple[Path, Path | None, float, str]:
        if current_app.config.get("VOICE_MODE", "demo") == "auto":
            try:
                return self._edge_tts_audio(audio_root, scene_order, narration)
            except Exception as exc:
                friendly_error = self._summarize_tts_error(exc)
                self.logger.log(
                    "voice_generation",
                    "failed",
                    f"Edge TTS failed for scene {scene_order} ({friendly_error}). Falling back to demo audio.",
                )

        duration = self._estimate_duration(narration)
        audio_path = audio_root / f"scene-{scene_order:02d}.wav"
        self._create_silent_wav(audio_path, duration)
        return audio_path, None, duration, "demo_silent"

    def _edge_tts_audio(
        self, audio_root: Path, scene_order: int, narration: str
    ) -> tuple[Path, Path | None, float, str]:
        audio_path = audio_root / f"scene-{scene_order:02d}.mp3"
        subtitle_path = audio_root / f"scene-{scene_order:02d}.vtt"
        command = [
            str(Path(current_app.root_path).parent / ".venv" / "bin" / "edge-tts"),
            "--text",
            narration,
            "--voice",
            current_app.config["EDGE_TTS_VOICE"],
            "--rate",
            current_app.config["EDGE_TTS_RATE"],
            "--write-media",
            str(audio_path),
            "--write-subtitles",
            str(subtitle_path),
        ]
        timeout_sec = int(current_app.config.get("EDGE_TTS_CLI_TIMEOUT", 20))
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Edge TTS timed out after {timeout_sec}s") from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            detail = stderr or stdout or "unknown edge-tts CLI failure"
            raise RuntimeError(detail) from exc

        if not audio_path.exists():
            raise RuntimeError("Edge TTS did not produce an audio file.")
        if subtitle_path.exists() and subtitle_path.stat().st_size == 0:
            subtitle_path.unlink(missing_ok=True)
            subtitle_path = None
        duration = self._probe_duration(audio_path)
        return audio_path, subtitle_path, duration, "edge_tts"

    def _pexels_broll(
        self,
        project_id: int,
        image_root: Path,
        scene_order: int,
        query: str,
        target_duration: float,
    ) -> tuple[Path, str]:
        cache_root = Path(current_app.config["STORAGE_ROOT"]) / "cache" / "pexels"
        cache_root.mkdir(parents=True, exist_ok=True)
        normalized_query = " ".join((query or "").split()).strip() or "personal finance"
        cache_key = hashlib.sha1(normalized_query.lower().encode("utf-8")).hexdigest()
        cache_path = cache_root / f"{cache_key}.json"
        result = self._load_pexels_cache(cache_path)
        if result is None:
            result = self._fetch_pexels_result(normalized_query, target_duration)
            cache_path.write_text(json.dumps(result), encoding="utf-8")

        download_url = result["download_url"]
        output_path = image_root / f"scene-{scene_order:02d}.mp4"
        if not output_path.exists():
            response = requests.get(
                download_url,
                timeout=current_app.config["PEXELS_API_TIMEOUT"],
                stream=True,
            )
            response.raise_for_status()
            with output_path.open("wb") as output_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        output_file.write(chunk)
        return output_path, "pexels_video"

    def _load_pexels_cache(self, cache_path: Path) -> dict[str, str] | None:
        if not cache_path.exists():
            return None
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if payload.get("download_url"):
            return payload
        return None

    def _fetch_pexels_result(self, query: str, target_duration: float) -> dict[str, str]:
        response = requests.get(
            "https://api.pexels.com/videos/search",
            params={
                "query": query,
                "per_page": current_app.config.get("PEXELS_SEARCH_LIMIT", 5),
                "orientation": "landscape",
            },
            headers={"Authorization": current_app.config["PEXELS_API_KEY"]},
            timeout=current_app.config["PEXELS_API_TIMEOUT"],
        )
        response.raise_for_status()
        payload = response.json()
        videos = payload.get("videos", [])
        if not videos:
            raise RuntimeError("Pexels returned no videos for this query.")

        matching_video = None
        for video in videos:
            if float(video.get("duration") or 0) >= target_duration:
                matching_video = video
                break
        if matching_video is None:
            matching_video = videos[0]

        video_files = matching_video.get("video_files", [])
        if not video_files:
            raise RuntimeError("Pexels did not include downloadable files.")

        best_file = next(
            (
                file_info
                for file_info in video_files
                if file_info.get("quality") == "sd" and file_info.get("link")
            ),
            None,
        )
        if best_file is None:
            best_file = next(
                (file_info for file_info in video_files if file_info.get("link")),
                None,
            )
        if best_file is None:
            raise RuntimeError("Pexels did not include a usable download link.")

        return {
            "query": query,
            "video_id": str(matching_video.get("id", "")),
            "duration": str(matching_video.get("duration", "")),
            "download_url": best_file["link"],
        }

    def _render_motion_text_video(
        self,
        image_root: Path,
        scene_order: int,
        text: str,
        target_duration: float,
    ) -> tuple[Path, str]:
        ffmpeg_bin = self._require_ffmpeg()
        output_path = image_root / f"scene-{scene_order:02d}.mp4"
        fps = 24
        frame_count = max(int(target_duration * fps), fps * 2)
        safe_text = self._short_motion_text(text)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            for frame_index in range(frame_count):
                progress = (frame_index + 1) / frame_count
                frame_path = temp_root / f"frame-{frame_index:04d}.png"
                self._draw_motion_text_frame(frame_path, safe_text, progress)
            self._encode_frame_sequence(ffmpeg_bin, temp_root, fps, output_path)

        return output_path, "motion_text_video"

    def _render_graph_video(
        self,
        image_root: Path,
        scene_order: int,
        instruction: str,
        target_duration: float,
    ) -> tuple[Path, str]:
        ffmpeg_bin = self._require_ffmpeg()
        output_path = image_root / f"scene-{scene_order:02d}.mp4"
        fps = 24
        frame_count = max(int(target_duration * fps), fps * 2)
        graph_spec = self._graph_spec_from_instruction(instruction)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            for frame_index in range(frame_count):
                progress = (frame_index + 1) / frame_count
                frame_path = temp_root / f"frame-{frame_index:04d}.png"
                self._draw_graph_frame(frame_path, graph_spec, progress)
            self._encode_frame_sequence(ffmpeg_bin, temp_root, fps, output_path)

        return output_path, "graph_video"

    def _draw_motion_text_frame(self, path: Path, text: str, progress: float) -> None:
        width, height = 1280, 720
        image = Image.new("RGB", (width, height), color="#0f172a")
        draw = ImageDraw.Draw(image)
        accent_height = int(height * 0.18)
        draw.rectangle((0, 0, width, accent_height), fill="#1e293b")
        draw.rectangle((0, accent_height, width, height), fill="#111827")
        font = ImageFont.load_default(size=48)
        sub_font = ImageFont.load_default(size=22)
        alpha_progress = min(max((progress - 0.08) / 0.35, 0), 1)
        offset_x = int((1 - min(progress / 0.55, 1)) * 180)
        x = 96 + offset_x
        y = 270
        max_width = width - 180
        wrapped = self._wrap_text(text, line_length=18)
        fill = self._fade_color((255, 255, 255), alpha_progress)
        shadow_fill = self._fade_color((15, 23, 42), alpha_progress)
        draw.multiline_text((x + 4, y + 4), wrapped, font=font, fill=shadow_fill, spacing=14)
        draw.multiline_text((x, y), wrapped, font=font, fill=fill, spacing=14)
        draw.text((96, 120), "KEY IDEA", font=sub_font, fill="#94a3b8")
        bar_width = int(max_width * min(progress / 0.5, 1))
        draw.rounded_rectangle((96, 620, 96 + bar_width, 636), radius=8, fill="#f97316")
        image.save(path)

    def _draw_graph_frame(self, path: Path, spec: dict[str, object], progress: float) -> None:
        width, height = 1280, 720
        image = Image.new("RGB", (width, height), color="#0f172a")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=20)
        title_font = ImageFont.load_default(size=30)
        draw.text((80, 56), str(spec["title"]), font=title_font, fill="white")
        chart_left, chart_top, chart_right, chart_bottom = 110, 150, 1180, 590
        draw.line((chart_left, chart_bottom, chart_right, chart_bottom), fill="#475569", width=3)
        draw.line((chart_left, chart_top, chart_left, chart_bottom), fill="#475569", width=3)

        values = spec["values"]
        labels = spec["labels"]
        max_value = max(values) if values else 1
        chart_type = spec["chart_type"]

        if chart_type == "line":
            points = []
            step_x = (chart_right - chart_left) / max(len(values) - 1, 1)
            for index, value in enumerate(values):
                animated_value = value * min(progress / 0.75, 1)
                x = chart_left + step_x * index
                y = chart_bottom - ((chart_bottom - chart_top) * (animated_value / max_value))
                points.append((x, y))
                draw.text((x - 18, chart_bottom + 18), labels[index], font=font, fill="#94a3b8")
            if len(points) > 1:
                visible_points = max(2, int(len(points) * min(progress / 0.95, 1)))
                draw.line(points[:visible_points], fill="#38bdf8", width=6)
                for point in points[:visible_points]:
                    draw.ellipse((point[0] - 6, point[1] - 6, point[0] + 6, point[1] + 6), fill="#38bdf8")
        else:
            step_x = (chart_right - chart_left) / max(len(values), 1)
            bar_width = step_x * 0.56
            for index, value in enumerate(values):
                animated_value = value * min(progress / 0.75, 1)
                x1 = chart_left + step_x * index + (step_x - bar_width) / 2
                x2 = x1 + bar_width
                y1 = chart_bottom - ((chart_bottom - chart_top) * (animated_value / max_value))
                accent = "#38bdf8" if index != len(values) - 1 else "#f97316"
                draw.rounded_rectangle((x1, y1, x2, chart_bottom), radius=10, fill=accent)
                draw.text((x1, chart_bottom + 18), labels[index], font=font, fill="#94a3b8")
                draw.text((x1, y1 - 26), self._format_number(value), font=font, fill="white")

        image.save(path)

    def _graph_spec_from_instruction(self, instruction: str) -> dict[str, object]:
        text = " ".join((instruction or "").split())
        numbers = [
            float(match)
            for match in re.findall(r"(?<![\w.])\d+(?:\.\d+)?", text)
        ]
        if len(numbers) < 3:
            numbers = [10.0, 12.0, 15.0, 18.0]
        values = numbers[:6]
        labels = [f"P{i + 1}" for i in range(len(values))]
        lowered = text.lower()
        chart_type = "line" if "line" in lowered else "bar"
        title = text[:70] or "Finance trend comparison"
        return {
            "title": title,
            "values": values,
            "labels": labels,
            "chart_type": chart_type,
        }

    def _encode_frame_sequence(self, ffmpeg_bin: str, frame_root: Path, fps: int, output_path: Path) -> None:
        subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-framerate",
                str(fps),
                "-i",
                str(frame_root / "frame-%04d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )

    def _require_ffmpeg(self) -> str:
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise RuntimeError("ffmpeg is required to render animated visual videos.")
        return ffmpeg_bin

    def _summarize_tts_error(self, exc: Exception) -> str:
        message = str(exc).strip()
        lowered = message.lower()
        if "403" in lowered or "invalid response status" in lowered:
            return "Edge TTS was rejected by the provider (403). The app will use demo fallback audio instead."
        if "timed out" in lowered:
            return "Edge TTS timed out. The app will use demo fallback audio instead."
        if "did not produce an audio file" in lowered:
            return "Edge TTS did not return usable audio. The app will use demo fallback audio instead."
        if len(message) > 220:
            message = message[:217].rstrip() + "..."
        return message or "Live Edge TTS failed. The app will use demo fallback audio instead."

    def _format_number(self, value: float) -> str:
        if value >= 1000:
            return f"{value:,.0f}"
        if value.is_integer():
            return f"{int(value)}"
        return f"{value:.1f}"

    def _fade_color(self, color: tuple[int, int, int], progress: float) -> tuple[int, int, int]:
        return tuple(int(channel * max(0.15, progress)) for channel in color)

    def _short_motion_text(self, text: str) -> str:
        words = re.findall(r"\b[\w']+\b", text.upper())
        trimmed = " ".join(words[:6]).strip()
        return trimmed[:48] or "MONEY LEAK"

    def _create_silent_wav(self, path: Path, duration_sec: float) -> None:
        frame_rate = 16000
        frame_count = int(math.ceil(duration_sec * frame_rate))
        with wave.open(str(path), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(frame_rate)
            silence = b"\x00\x00" * frame_count
            wav_file.writeframes(silence)

    def _probe_duration(self, path: Path) -> float:
        result = subprocess.run(
            [
                "ffprobe",
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
        )
        payload = json.loads(result.stdout)
        duration = float(payload["format"]["duration"])
        return round(duration, 2)

    def _render_image(self, path: Path, text: str, visual_type: str | None) -> None:
        title = (visual_type or "scene").replace("_", " ").title()
        image = Image.new("RGB", (1280, 720), color="#0f172a")
        draw = ImageDraw.Draw(image)
        font_large = ImageFont.load_default(size=44)
        font_body = ImageFont.load_default(size=32)
        draw.rectangle((0, 0, 1280, 720), fill="#0f172a")
        draw.text((70, 70), title, fill="#94a3b8", font=font_large)
        wrapped = self._wrap_text(text, line_length=32)
        draw.multiline_text((70, 180), wrapped, fill="white", font=font_body, spacing=16)
        accent = {"graph": "#38bdf8", "broll": "#22c55e", "motion_text": "#f97316"}.get(
            visual_type or "", "#a855f7"
        )
        draw.rounded_rectangle((60, 60, 1220, 660), outline=accent, width=4, radius=24)
        image.save(path)

    def _wrap_text(self, text: str, line_length: int) -> str:
        words = text.split()
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            candidate = " ".join(current + [word])
            if len(candidate) > line_length and current:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            lines.append(" ".join(current))
        return "\n".join(lines)
