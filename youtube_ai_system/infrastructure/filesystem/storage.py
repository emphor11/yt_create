"""Filesystem path helpers for project artifacts."""

from __future__ import annotations

from pathlib import Path


class FileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def project_video_dir(self, project_id: int) -> Path:
        return self.ensure_dir(self.root / "video" / str(project_id))

    def project_audio_dir(self, project_id: int) -> Path:
        return self.ensure_dir(self.root / "audio" / str(project_id))

    def project_image_dir(self, project_id: int) -> Path:
        return self.ensure_dir(self.root / "images" / str(project_id))

    def ensure_dir(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

