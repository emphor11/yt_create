from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from flask import current_app

from ..models.repository import ProjectRepository
from .run_log import RunLogger


class AssemblyService:
    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.logger = RunLogger()

    def assemble_project(self, project_id: int) -> str:
        project = self.repo.get_project(project_id)
        scenes = self.repo.list_scenes(project_id)
        output_dir = Path(current_app.config["STORAGE_ROOT"]) / "video" / str(project_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            summary_path = output_dir / "assembly_manifest.txt"
            lines = [f"Project: {project['working_title']}", ""]
            for scene in scenes:
                lines.append(
                    f"{scene['scene_order']:02d} | {scene['kind']} | {scene['audio_path']} | {scene['visual_path']}"
                )
            summary_path.write_text("\n".join(lines))
            self.repo.update_project(project_id, final_video_path=str(summary_path))
            self.logger.log(
                "assembly",
                "completed",
                "Created assembly manifest. Replace with ffmpeg assembly once ffmpeg is installed.",
                project_id,
            )
            return str(summary_path)

        segment_paths: list[Path] = []
        concat_manifest = output_dir / "segments.txt"
        for scene in scenes:
            segment_path = output_dir / f"scene-{scene['scene_order']:02d}.mp4"
            segment_paths.append(segment_path)
            self._render_scene_video(ffmpeg_bin, scene["visual_path"], scene["audio_path"], segment_path)

        concat_manifest.write_text(
            "\n".join(f"file '{segment_path.name}'" for segment_path in segment_paths)
        )
        final_path = output_dir / "final_video.mp4"
        subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_manifest),
                "-c",
                "copy",
                str(final_path),
            ],
            cwd=output_dir,
            check=True,
            capture_output=True,
        )
        self.repo.update_project(project_id, final_video_path=str(final_path))
        self.logger.log("assembly", "completed", "Rendered final MP4 with ffmpeg.", project_id)
        return str(final_path)

    def _render_scene_video(self, ffmpeg_bin: str, visual_path: str, audio_path: str, output_path: Path) -> None:
        visual_suffix = Path(visual_path).suffix.lower()
        if visual_suffix in {".mp4", ".mov", ".mkv", ".webm"}:
            command = [
                ffmpeg_bin,
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                visual_path,
                "-i",
                audio_path,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                str(output_path),
            ]
        else:
            command = [
                ffmpeg_bin,
                "-y",
                "-loop",
                "1",
                "-i",
                visual_path,
                "-i",
                audio_path,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                str(output_path),
            ]
        subprocess.run(command, check=True, capture_output=True)
