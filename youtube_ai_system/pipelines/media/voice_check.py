from __future__ import annotations

from typing import Any


class VoiceCheckResultBuilder:
    """Formats voice-check results for the existing route/UI contract."""

    def success(self, result: Any, mode: str) -> dict[str, object]:
        live = result.source not in {"demo_silent", "voice_fallback_silent"}
        return {
            "mode": mode,
            "status": "live" if live else "demo",
            "audio_source": result.source,
            "audio_path": str(result.audio_path),
            "subtitle_path": str(result.subtitle_path) if result.subtitle_path else None,
            "duration": result.duration_sec,
            "message": (
                f"Voice check completed with {result.source}."
                if live
                else "Voice check used silent fallback audio. Install/configure Kokoro for live narration."
            ),
        }

    def failure(self, exc: Exception, mode: str) -> dict[str, object]:
        friendly_error = self.summarize_tts_error(exc)
        return {
            "mode": mode,
            "status": "failed",
            "audio_source": "voice_failed",
            "audio_path": None,
            "subtitle_path": None,
            "duration": None,
            "message": f"Voice check failed: {friendly_error}",
        }

    def summarize_tts_error(self, exc: Exception) -> str:
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
