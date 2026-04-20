from __future__ import annotations

from pathlib import Path

from flask import current_app

from ..models.repository import ProjectRepository
from .remotion_service import RemotionService
from .render_spec_service import RenderSpecService


class ThumbnailService:
    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.render_specs = RenderSpecService()
        self.remotion = RemotionService()

    def ensure_thumbnails(self, project_id: int, titles: list[str]) -> list[str]:
        image_root = Path(current_app.config["STORAGE_ROOT"]) / "images" / str(project_id) / "thumbnails"
        image_root.mkdir(parents=True, exist_ok=True)
        paths: list[str] = []
        for index, title in enumerate(titles[:3], start=1):
            path = image_root / f"thumb-{index}.jpg"
            self._render_thumbnail(path, title, index)
            paths.append(str(path))
        return paths

    def _render_thumbnail(self, path: Path, title: str, variant: int = 1) -> None:
        if not current_app.config.get("REMOTION_ENABLED", True):
            raise RuntimeError("Remotion thumbnails are required, but REMOTION_ENABLED=false.")
        spec = self.render_specs.thumbnail_spec(title, variant)
        self.remotion.render_still(spec, path)

    def _wrap_text(self, text: str, line_length: int) -> str:
        words = text.split()
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            candidate = " ".join(current + [word])
            if len(candidate) > line_length and current:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            lines.append(" ".join(current))
        return "\n".join(lines)
