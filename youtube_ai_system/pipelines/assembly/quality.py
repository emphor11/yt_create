"""Quality gate for assembled master files."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ...infrastructure.ffmpeg import FfmpegExecutor


class MasterQualityGate:
    def __init__(self, ffmpeg: FfmpegExecutor | None = None) -> None:
        self.ffmpeg = ffmpeg or FfmpegExecutor()

    def assert_final_master_quality(self, path: Path) -> None:
        ffprobe_bin = self.ffmpeg.which("ffprobe")
        if not ffprobe_bin:
            return
        try:
            result = self.ffmpeg.run_raw(
                [
                    ffprobe_bin,
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-count_frames",
                    "-show_entries",
                    "stream=nb_read_frames,avg_frame_rate,duration,bit_rate",
                    "-of",
                    "json",
                    str(path),
                ],
                text=True,
                timeout=60,
            )
            stream = (json.loads(result.stdout or "{}").get("streams") or [{}])[0]
            duration = float(stream.get("duration") or 0)
            frames = int(stream.get("nb_read_frames") or 0)
            bitrate = int(stream.get("bit_rate") or 0)
            avg_rate = str(stream.get("avg_frame_rate") or "0/1")
            numerator, denominator = avg_rate.split("/", 1)
            fps = float(numerator) / max(float(denominator), 1.0)
        except (subprocess.SubprocessError, ValueError, json.JSONDecodeError, IndexError):
            return

        if duration >= 10 and fps < 24:
            raise RuntimeError(f"Final master failed quality gate: expected 30fps video, got {fps:.2f}fps.")
        if duration >= 10 and frames and frames < duration * 24:
            raise RuntimeError(
                f"Final master failed quality gate: expected at least {int(duration * 24)} frames, got {frames}."
            )
        if duration >= 60 and bitrate and bitrate < 50_000:
            raise RuntimeError(
                f"Final master failed quality gate: video bitrate is too low for upload ({bitrate} bps)."
            )
