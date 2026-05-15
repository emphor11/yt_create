from __future__ import annotations

import math
import os
import shutil
import subprocess
import wave
from pathlib import Path


class VoiceAudioTools:
    """Filesystem and subprocess helpers for generated narration audio."""

    def estimate_duration(self, narration: str) -> float:
        words = max(len(narration.split()), 1)
        return round(max(words / 2.4, 2.5), 2)

    def write_silent_wav(self, path: Path, duration_sec: float) -> None:
        frame_rate = 16000
        frame_count = int(math.ceil(duration_sec * frame_rate))
        with wave.open(str(path), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(frame_rate)
            wav_file.writeframes(b"\x00\x00" * frame_count)

    def require_ffmpeg_for_gtts(self) -> str:
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise RuntimeError("gTTS fallback needs ffmpeg to convert MP3 to WAV.")
        return ffmpeg_bin

    def convert_mp3_to_wav(self, ffmpeg_bin: str, mp3_path: Path, output_path: Path) -> None:
        subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-i",
                str(mp3_path),
                "-ar",
                "24000",
                "-ac",
                "1",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )

    def probe_duration(self, path: Path) -> float | None:
        ffprobe_bin = shutil.which("ffprobe")
        if not ffprobe_bin:
            for candidate in ("/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe"):
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    ffprobe_bin = candidate
                    break
        if not ffprobe_bin:
            return None
        result = subprocess.run(
            [
                ffprobe_bin,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return round(float(result.stdout.strip()), 2)

    def soundfile_duration(self, path: Path) -> float | None:
        try:
            import soundfile as sf

            info = sf.info(str(path))
            return round(info.frames / float(info.samplerate), 2)
        except Exception:
            return None
