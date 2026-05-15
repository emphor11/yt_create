from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


class StaticSceneImageRenderer:
    """Legacy static fallback image renderer."""

    def render_image(self, path: Path, text: str, visual_type: str | None) -> None:
        title = (visual_type or "scene").replace("_", " ").title()
        image = Image.new("RGB", (1280, 720), color="#0f172a")
        draw = ImageDraw.Draw(image)
        font_large = ImageFont.load_default(size=44)
        font_body = ImageFont.load_default(size=32)
        draw.rectangle((0, 0, 1280, 720), fill="#0f172a")
        draw.text((70, 70), title, fill="#94a3b8", font=font_large)
        wrapped = self.wrap_text(text, line_length=32)
        draw.multiline_text((70, 180), wrapped, fill="white", font=font_body, spacing=16)
        accent = {"graph": "#38bdf8", "broll": "#22c55e", "motion_text": "#f97316"}.get(
            visual_type or "", "#a855f7"
        )
        draw.rounded_rectangle((60, 60, 1220, 660), outline=accent, width=4, radius=24)
        image.save(path)

    def wrap_text(self, text: str, line_length: int) -> str:
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
