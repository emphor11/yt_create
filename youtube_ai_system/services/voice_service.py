from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from flask import current_app

from ..infrastructure.voice import VoiceAudioTools


@dataclass(frozen=True)
class VoiceResult:
    audio_path: Path
    subtitle_path: Path | None
    duration_sec: float
    source: str


class VoiceService:
    """Provider-neutral narration generation for the V2 media pipeline."""

    def __init__(self) -> None:
        self.audio_tools = VoiceAudioTools()

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

        ffmpeg_bin = self.audio_tools.require_ffmpeg_for_gtts()
        output_path = audio_root / f"scene-{scene_order:02d}.wav"
        lang = current_app.config.get("GTTS_LANG", "en")
        with tempfile.TemporaryDirectory() as temp_dir:
            mp3_path = Path(temp_dir) / "voice.mp3"
            gTTS(text=narration, lang=lang).save(str(mp3_path))
            self.audio_tools.convert_mp3_to_wav(ffmpeg_bin, mp3_path, output_path)
        output_path.with_suffix(".error.txt").unlink(missing_ok=True)
        return VoiceResult(output_path, None, self.probe_duration(output_path), "gtts")

    def _silent_audio(self, audio_root: Path, scene_order: int, narration: str, source: str) -> VoiceResult:
        output_path = audio_root / f"scene-{scene_order:02d}.wav"
        duration = self.estimate_duration(narration)
        self.audio_tools.write_silent_wav(output_path, duration)
        return VoiceResult(output_path, None, duration, source)

    def estimate_duration(self, narration: str) -> float:
        return self.audio_tools.estimate_duration(narration)

    def probe_duration(self, path: Path) -> float:
        probed_duration = self.audio_tools.probe_duration(path)
        if probed_duration is not None:
            return probed_duration
        soundfile_duration = self.audio_tools.soundfile_duration(path)
        if soundfile_duration is not None:
            return soundfile_duration
        return self.estimate_duration(path.stem)
