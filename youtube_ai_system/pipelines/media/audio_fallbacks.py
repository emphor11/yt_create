from __future__ import annotations

import json
import math
import wave
from pathlib import Path

from ...infrastructure.ffmpeg import FfmpegExecutor


class MediaAudioFallbacks:
    """Audio fallback utilities used by media generation.

    These methods intentionally mirror the legacy MediaService behavior so
    fallback timing and silent WAV generation remain stable during refactors.
    """

    def __init__(self, ffmpeg: FfmpegExecutor | None = None) -> None:
        self.ffmpeg = ffmpeg or FfmpegExecutor()

    def estimate_duration(self, narration: str) -> float:
        words = max(len(narration.split()), 1)
        return round(max(words / 2.4, 2.5), 2)

    def cleanup_empty_file(self, path: Path) -> None:
        try:
            if path.exists() and path.stat().st_size == 0:
                path.unlink(missing_ok=True)
        except OSError:
            pass

    def create_silent_wav(self, path: Path, duration_sec: float) -> None:
        frame_rate = 16000
        frame_count = int(math.ceil(duration_sec * frame_rate))
        with wave.open(str(path), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(frame_rate)
            silence = b"\x00\x00" * frame_count
            wav_file.writeframes(silence)

    def probe_duration(self, path: Path) -> float:
        ffprobe_bin = self.ffmpeg.find_binary("ffprobe", ("/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe"))
        if ffprobe_bin:
            result = self.ffmpeg.run_raw(
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
                text=True,
            )
            payload = json.loads(result.stdout)
            duration = float(payload["format"]["duration"])
            return round(duration, 2)

        try:
            from mutagen import File as MutagenFile

            audio = MutagenFile(str(path))
            if audio and audio.info:
                return round(audio.info.length, 2)
        except Exception:
            pass
        return round(max(path.stat().st_size / 2000, 2.5), 2)
