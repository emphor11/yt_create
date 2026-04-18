from __future__ import annotations

import json
import math
import subprocess
import wave
from pathlib import Path

import edge_tts
from flask import current_app
from PIL import Image, ImageDraw, ImageFont

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
            visual_path = image_root / f"scene-{scene['scene_order']:02d}.png"
            self._render_image(visual_path, scene["narration_text"], scene["visual_type"])
            self.repo.update_scene(
                scene["id"],
                audio_path=str(audio_path),
                audio_duration_sec=duration,
                subtitle_path=str(subtitle_path) if subtitle_path else None,
                visual_path=str(visual_path),
                audio_source=audio_source,
                visual_source="generated_image",
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

    def _estimate_duration(self, narration: str) -> float:
        words = max(len(narration.split()), 1)
        return round(max(words / 2.4, 2.5), 2)

    def _generate_audio(self, audio_root: Path, scene_order: int, narration: str) -> tuple[Path, Path | None, float, str]:
        if current_app.config.get("VOICE_MODE", "demo") == "auto":
            try:
                return self._edge_tts_audio(audio_root, scene_order, narration)
            except Exception as exc:
                self.logger.log(
                    "voice_generation",
                    "failed",
                    f"Edge TTS failed for scene {scene_order} ({exc}). Falling back to demo audio.",
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
        communicate = edge_tts.Communicate(
            narration,
            voice=current_app.config["EDGE_TTS_VOICE"],
            rate=current_app.config["EDGE_TTS_RATE"],
            connect_timeout=current_app.config["EDGE_TTS_CONNECT_TIMEOUT"],
            receive_timeout=current_app.config["EDGE_TTS_RECEIVE_TIMEOUT"],
        )
        sub_maker = edge_tts.SubMaker()
        with audio_path.open("wb") as audio_file:
            for chunk in communicate.stream_sync():
                if chunk["type"] == "audio":
                    audio_file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    offset = chunk["offset"] / 10_000_000
                    duration = chunk["duration"] / 10_000_000
                    sub_maker.create_sub((offset, duration), chunk["text"])
        subtitle_text = sub_maker.generate_subs()
        subtitle_path.write_text(subtitle_text, encoding="utf-8")
        duration = self._probe_duration(audio_path)
        return audio_path, subtitle_path, duration, "edge_tts"

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
