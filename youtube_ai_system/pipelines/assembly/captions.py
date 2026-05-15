"""Caption timeline helpers for final assembly."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class CaptionWriter:
    def write(
        self,
        scenes: list[dict[str, Any]],
        output_path: Path,
        *,
        intro_offset: float,
        transition_sec: float,
    ) -> None:
        lines: list[str] = []
        cursor = intro_offset
        index = 1
        for scene_number, scene in enumerate(scenes):
            duration = float(scene.get("audio_duration_sec") or 0) or 2.5
            chunks = self.chunks(str(scene.get("narration_text") or ""))
            chunk_duration = duration / max(len(chunks), 1)
            scene_start = cursor
            for chunk_index, chunk in enumerate(chunks):
                start = scene_start + (chunk_index * chunk_duration)
                end = min(start + chunk_duration, scene_start + duration)
                lines.extend([str(index), f"{self.srt_time(start)} --> {self.srt_time(end)}", chunk, ""])
                index += 1
            cursor = scene_start + duration
            if scene_number != len(scenes) - 1:
                cursor += transition_sec
        output_path.write_text("\n".join(lines), encoding="utf-8")

    def chunks(self, text: str, words_per_line: int = 7) -> list[str]:
        words = text.split()
        if not words:
            return ["YTCreate Finance"]
        return [" ".join(words[i : i + words_per_line]) for i in range(0, len(words), words_per_line)]

    def srt_time(self, seconds: float) -> str:
        millis = int(round(seconds * 1000))
        hours, millis = divmod(millis, 3_600_000)
        minutes, millis = divmod(millis, 60_000)
        secs, millis = divmod(millis, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

