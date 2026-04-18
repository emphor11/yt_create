from __future__ import annotations

from pathlib import Path

from flask import current_app
from PIL import Image, ImageDraw, ImageFont

from ..models.repository import ProjectRepository


class ThumbnailService:
    def __init__(self) -> None:
        self.repo = ProjectRepository()

    def ensure_thumbnails(self, project_id: int, titles: list[str]) -> list[str]:
        image_root = Path(current_app.config["STORAGE_ROOT"]) / "images" / str(project_id) / "thumbnails"
        image_root.mkdir(parents=True, exist_ok=True)
        paths: list[str] = []
        for index, title in enumerate(titles[:3], start=1):
            path = image_root / f"thumb-{index}.jpg"
            self._render_thumbnail(path, title)
            paths.append(str(path))
        return paths

    def _render_thumbnail(self, path: Path, title: str) -> None:
        image = Image.new("RGB", (1280, 720), color="#111827")
        draw = ImageDraw.Draw(image)
        font_title = ImageFont.load_default(size=56)
        font_sub = ImageFont.load_default(size=26)
        draw.rectangle((0, 0, 1280, 720), fill="#111827")
        draw.rounded_rectangle((60, 60, 1220, 660), fill="#1f2937", outline="#38bdf8", width=6, radius=28)
        draw.text((90, 90), "YTCreate", fill="#38bdf8", font=font_sub)
        wrapped = self._wrap_text(title, 18)
        draw.multiline_text((90, 210), wrapped, fill="white", font=font_title, spacing=18)
        draw.text((90, 600), "Personal finance breakdown", fill="#cbd5e1", font=font_sub)
        image.save(path, quality=92)

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
