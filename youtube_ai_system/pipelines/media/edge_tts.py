from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable


def generate_edge_tts_audio(
    audio_root: Path,
    scene_order: int,
    narration: str,
    config: Any,
    *,
    probe_duration: Callable[[Path], float],
    cleanup_empty_file: Callable[[Path], None],
) -> tuple[Path, Path | None, float, str]:
    """Generate audio using the edge-tts async Python API."""
    import edge_tts

    audio_path = audio_root / f"scene-{scene_order:02d}.mp3"
    subtitle_path = audio_root / f"scene-{scene_order:02d}.vtt"

    voice = config["EDGE_TTS_VOICE"]
    rate = config["EDGE_TTS_RATE"]

    async def _generate() -> None:
        communicate = edge_tts.Communicate(narration, voice, rate=rate)
        submaker = edge_tts.SubMaker()
        with open(str(audio_path), "wb") as audio_file:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    submaker.feed(chunk)
        sub_content = submaker.generate_subs()
        if sub_content and sub_content.strip():
            subtitle_path.write_text(sub_content, encoding="utf-8")

    timeout_sec = int(config.get("EDGE_TTS_CLI_TIMEOUT", 30))
    try:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(asyncio.wait_for(_generate(), timeout=timeout_sec))
        finally:
            loop.close()
    except asyncio.TimeoutError as exc:
        cleanup_empty_file(audio_path)
        cleanup_empty_file(subtitle_path)
        raise RuntimeError(f"Edge TTS timed out after {timeout_sec}s") from exc
    except Exception:
        cleanup_empty_file(audio_path)
        cleanup_empty_file(subtitle_path)
        raise

    if not audio_path.exists() or audio_path.stat().st_size == 0:
        cleanup_empty_file(audio_path)
        raise RuntimeError("Edge TTS did not produce an audio file.")

    if subtitle_path.exists() and subtitle_path.stat().st_size == 0:
        subtitle_path.unlink(missing_ok=True)
        sub_out = None
    else:
        sub_out = subtitle_path if subtitle_path.exists() else None

    duration = probe_duration(audio_path)
    return audio_path, sub_out, duration, "edge_tts"
