from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from flask import current_app


@dataclass(frozen=True)
class VoiceResult:
    audio_path: Path
    subtitle_path: Path | None
    duration_sec: float
    source: str


class VoiceService:
    """Provider-neutral narration generation for the V2 media pipeline."""

    def generate_scene_audio(self, audio_root: Path, scene_order: int, narration: str) -> VoiceResult:
        audio_root.mkdir(parents=True, exist_ok=True)
        if current_app.config.get("VOICE_MODE") == "demo":
            return self._silent_audio(audio_root, scene_order, narration, "demo_silent")

        primary = current_app.config.get("VOICE_PROVIDER", "kokoro")
        fallback = current_app.config.get("VOICE_FALLBACK_PROVIDER", "gtts")
        failures: list[str] = []
        for provider in (primary, fallback):
            provider = str(provider or "").lower().strip()
            if not provider or provider == "none":
                continue
            try:
                if provider == "kokoro":
                    return self._kokoro_audio(audio_root, scene_order, narration)
                if provider == "gtts":
                    return self._gtts_audio(audio_root, scene_order, narration)
                if provider == "silent":
                    return self._silent_audio(audio_root, scene_order, narration, "demo_silent")
            except Exception as exc:
                failures.append(f"{provider}: {exc}")

        result = self._silent_audio(audio_root, scene_order, narration, "voice_fallback_silent")
        if failures:
            result.audio_path.with_suffix(".error.txt").write_text("\n".join(failures), encoding="utf-8")
        return result

    def run_voice_check(self, audio_root: Path) -> VoiceResult:
        sample_text = (
            "This is a YTCreate V2 voice check. If this sounds natural, the Kokoro narration "
            "pipeline is ready for finance videos."
        )
        return self.generate_scene_audio(audio_root, 1, sample_text)

    def _kokoro_audio(self, audio_root: Path, scene_order: int, narration: str) -> VoiceResult:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline

        output_path = audio_root / f"scene-{scene_order:02d}.wav"
        lang_code = current_app.config.get("KOKORO_LANG_CODE", "a")
        narrator = current_app.config.get("KOKORO_NARRATOR", "male")
        voice = (
            current_app.config.get("KOKORO_VOICE_FEMALE")
            if narrator == "female"
            else current_app.config.get("KOKORO_VOICE_MALE")
        )
        pipeline = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M")
        chunks = []
        for item in pipeline(narration, voice=voice):
            audio = self._extract_kokoro_audio(item)
            chunks.append(np.asarray(audio, dtype="float32"))
        if not chunks:
            raise RuntimeError("Kokoro did not return audio chunks.")
        audio_data = np.concatenate(chunks)
        sf.write(str(output_path), audio_data, 24000)
        output_path.with_suffix(".error.txt").unlink(missing_ok=True)
        duration = self.probe_duration(output_path)
        return VoiceResult(output_path, None, duration, f"kokoro:{voice}")

    def _extract_kokoro_audio(self, item):
        if hasattr(item, "output") and hasattr(item.output, "audio"):
            audio = item.output.audio
        elif isinstance(item, tuple):
            audio = item[-1]
            if hasattr(audio, "audio"):
                audio = audio.audio
        else:
            audio = item

        if hasattr(audio, "detach"):
            audio = audio.detach().cpu().numpy()
        return audio

    def _gtts_audio(self, audio_root: Path, scene_order: int, narration: str) -> VoiceResult:
        from gtts import gTTS

        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise RuntimeError("gTTS fallback needs ffmpeg to convert MP3 to WAV.")

        output_path = audio_root / f"scene-{scene_order:02d}.wav"
        lang = current_app.config.get("GTTS_LANG", "en")
        with tempfile.TemporaryDirectory() as temp_dir:
            mp3_path = Path(temp_dir) / "voice.mp3"
            gTTS(text=narration, lang=lang).save(str(mp3_path))
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
        output_path.with_suffix(".error.txt").unlink(missing_ok=True)
        return VoiceResult(output_path, None, self.probe_duration(output_path), "gtts")

    def _silent_audio(self, audio_root: Path, scene_order: int, narration: str, source: str) -> VoiceResult:
        output_path = audio_root / f"scene-{scene_order:02d}.wav"
        duration = self.estimate_duration(narration)
        frame_rate = 16000
        frame_count = int(math.ceil(duration * frame_rate))
        with wave.open(str(output_path), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(frame_rate)
            wav_file.writeframes(b"\x00\x00" * frame_count)
        return VoiceResult(output_path, None, duration, source)

    def estimate_duration(self, narration: str) -> float:
        words = max(len(narration.split()), 1)
        return round(max(words / 2.4, 2.5), 2)

    def probe_duration(self, path: Path) -> float:
        ffprobe_bin = shutil.which("ffprobe")
        if not ffprobe_bin:
            for candidate in ("/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe"):
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    ffprobe_bin = candidate
                    break
        if ffprobe_bin:
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

        try:
            import soundfile as sf

            info = sf.info(str(path))
            return round(info.frames / float(info.samplerate), 2)
        except Exception:
            return self.estimate_duration(path.stem)
