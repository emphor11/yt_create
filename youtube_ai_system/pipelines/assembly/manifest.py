"""Assembly manifest helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class TimelineManifestBuilder:
    def text_manifest(self, project: dict[str, Any], scenes: list[dict[str, Any]]) -> str:
        lines = [f"Project: {project['working_title']}", ""]
        for scene in scenes:
            lines.append(
                f"{scene['scene_order']:02d} | {scene['kind']} | {scene['audio_path']} | {scene['visual_path']}"
            )
        return "\n".join(lines)

    def ffmpeg_concat_manifest(self, segment_paths: list[Path]) -> str:
        return "\n".join(f"file '{segment_path.name}'" for segment_path in segment_paths)

