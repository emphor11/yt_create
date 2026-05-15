from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from ...infrastructure.ffmpeg import FfmpegExecutor


class BeatTimelineBuilder:
    """Builds legacy beat timelines without changing clip ordering or timing."""

    def __init__(self, ffmpeg: FfmpegExecutor | None = None) -> None:
        self.ffmpeg = ffmpeg or FfmpegExecutor()

    def load_scene_beats(self, scene: dict, scene_duration: float) -> list[dict]:
        raw = scene.get("visual_plan_json")
        beats: list[dict] = []
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    beats = [beat for beat in parsed if isinstance(beat, dict)]
            except json.JSONDecodeError:
                beats = []
        if not beats:
            beats = [
                {
                    "beat_index": 0,
                    "beat_type": self.fallback_beat_type(scene.get("visual_type")),
                    "content": scene.get("visual_instruction") or scene.get("narration_text") or "Money reality",
                    "caption": "",
                    "color": "orange",
                    "estimated_start_sec": 0,
                    "estimated_duration_sec": min(max(scene_duration, 2.5), 4.0),
                }
            ]
        return beats

    def normalize_beat_durations(self, beats: list[dict], scene_duration: float) -> list[dict]:
        if not beats or scene_duration <= 0:
            return beats
        durations = [max(float(beat.get("estimated_duration_sec") or 3.0), 0.1) for beat in beats]
        total = sum(durations)
        if total <= 0:
            return beats
        scale = scene_duration / total
        normalized: list[dict] = []
        for beat, duration in zip(beats, durations):
            next_beat = dict(beat)
            next_beat["estimated_duration_sec"] = round(duration * scale, 2)
            normalized.append(next_beat)
        actual_total = round(sum(float(beat.get("estimated_duration_sec") or 0) for beat in normalized), 2)
        if normalized:
            normalized[-1]["estimated_duration_sec"] = round(
                float(normalized[-1].get("estimated_duration_sec") or 0) + (scene_duration - actual_total),
                2,
            )
        return normalized

    def fallback_beat_type(self, visual_type: str | None) -> str:
        if visual_type == "graph":
            return "chart"
        if visual_type == "broll":
            return "broll_caption"
        if visual_type in {"flow_diagram", "stat_explosion", "text_burst", "chart", "split_comparison", "broll_caption", "reaction_card"}:
            return visual_type
        return "text_burst"

    def concat_beat_clips(
        self,
        beat_paths: list[Path],
        output_path: Path,
        target_duration: float,
        *,
        probe_duration,
    ) -> None:
        ffmpeg_bin = self.ffmpeg.find_binary("ffmpeg")
        if not ffmpeg_bin:
            shutil.copy2(beat_paths[0], output_path)
            return
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            manifest = temp_root / "beats.txt"
            concat_path = temp_root / "beats_concat.mp4"
            manifest.write_text(
                "\n".join(f"file '{path.resolve()}'" for path in beat_paths),
                encoding="utf-8",
            )
            self.ffmpeg.run_raw(
                [
                    ffmpeg_bin,
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(manifest),
                    "-c",
                    "copy",
                    str(concat_path),
                ]
            )
            duration = probe_duration(concat_path)
            if duration < target_duration - 0.1:
                pad = round(target_duration - duration, 2)
                self.ffmpeg.run_raw(
                    [
                        ffmpeg_bin,
                        "-y",
                        "-i",
                        str(concat_path),
                        "-vf",
                        f"tpad=stop_mode=clone:stop_duration={pad}",
                        "-t",
                        str(round(target_duration, 2)),
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        "18",
                        "-pix_fmt",
                        "yuv420p",
                        str(output_path),
                    ]
                )
            elif duration > target_duration + 0.1:
                self.ffmpeg.run_raw(
                    [
                        ffmpeg_bin,
                        "-y",
                        "-i",
                        str(concat_path),
                        "-t",
                        str(round(target_duration, 2)),
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        "18",
                        "-pix_fmt",
                        "yuv420p",
                        str(output_path),
                    ]
                )
            else:
                shutil.copy2(concat_path, output_path)
