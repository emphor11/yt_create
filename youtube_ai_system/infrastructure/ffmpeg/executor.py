"""Subprocess adapter for FFmpeg-style command execution."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
import os


class FfmpegExecutor:
    def which(self, binary_name: str = "ffmpeg") -> str | None:
        return shutil.which(binary_name)

    def find_binary(self, binary_name: str = "ffmpeg", fallback_paths: tuple[str, ...] = ()) -> str | None:
        binary = self.which(binary_name)
        if binary:
            return binary
        for candidate in fallback_paths:
            path = Path(candidate)
            if path.is_file() and os.access(path, os.X_OK):
                return str(path)
        return None

    def encode_frame_sequence(self, ffmpeg_bin: str, frame_root: Path, fps: int, output_path: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-framerate",
                str(fps),
                "-i",
                str(frame_root / "frame-%04d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )

    def run_raw(
        self,
        command: list[str],
        *,
        text: bool = False,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=text,
            timeout=timeout,
        )

    def run_silent(self, command: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        timeout: int = 600,
    ) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                command,
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"FFmpeg assembly step timed out after {timeout}s.") from exc
        except subprocess.CalledProcessError as exc:
            detail = self.error_detail(exc)
            raise RuntimeError(f"FFmpeg assembly step failed: {detail}") from exc

    def has_audio_stream(self, path: Path) -> bool:
        if not path.exists() or path.stat().st_size == 0:
            return False
        ffprobe_bin = self.which("ffprobe")
        if not ffprobe_bin:
            return False
        try:
            result = self.run_raw(
                [
                    ffprobe_bin,
                    "-v",
                    "error",
                    "-select_streams",
                    "a",
                    "-show_entries",
                    "stream=index",
                    "-of",
                    "json",
                    str(path),
                ],
                text=True,
                timeout=30,
            )
            payload = json.loads(result.stdout or "{}")
        except (subprocess.SubprocessError, ValueError, json.JSONDecodeError):
            return False
        return bool(payload.get("streams"))

    def probe_duration(self, path: Path) -> float:
        ffprobe_bin = self.which("ffprobe")
        if not ffprobe_bin:
            return 0.0
        try:
            result = self.run_raw(
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
                timeout=30,
            )
            payload = json.loads(result.stdout or "{}")
            return float((payload.get("format") or {}).get("duration") or 0.0)
        except (subprocess.SubprocessError, ValueError, json.JSONDecodeError):
            return 0.0

    def extract_frame(
        self,
        video_path: Path,
        seconds: float,
        output_path: Path,
        *,
        scale: str = "96:54",
        timeout: int = 10,
    ) -> bool:
        ffmpeg_bin = self.which("ffmpeg")
        if not ffmpeg_bin:
            return False
        try:
            self.run_silent(
                [
                    ffmpeg_bin,
                    "-y",
                    "-ss",
                    f"{seconds:.3f}",
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    "-vf",
                    f"scale={scale}",
                    str(output_path),
                ],
                timeout=timeout,
            )
        except (subprocess.SubprocessError, OSError):
            return False
        return True

    def error_detail(self, exc: subprocess.CalledProcessError) -> str:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        if len(detail) > 800:
            detail = detail[:800].rstrip() + "...[truncated]"
        return detail
