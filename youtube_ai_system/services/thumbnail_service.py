from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from flask import current_app
from PIL import Image, ImageDraw, ImageFont

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

    def ensure_creator_thumbnails(
        self,
        project_id: int,
        titles: list[str],
        scenes: list[dict[str, Any]] | None = None,
        force: bool = False,
    ) -> list[dict[str, str]]:
        image_root = Path(current_app.config["STORAGE_ROOT"]) / "images" / str(project_id) / "thumbnails"
        image_root.mkdir(parents=True, exist_ok=True)
        manifest_path = image_root / "creator_manifest.json"
        if manifest_path.exists() and not force:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                variants = manifest.get("variants", [])
                if variants and all(Path(variant["path"]).exists() for variant in variants):
                    return variants
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        phrases = self._thumbnail_phrases(titles, scenes or [])
        variants: list[dict[str, str]] = []
        for index, phrase in enumerate(phrases[:3], start=1):
            path = image_root / f"creator-thumb-{index}.jpg"
            self._render_creator_thumbnail(path, phrase, index)
            variants.append(
                {
                    "path": str(path),
                    "headline": phrase["headline"],
                    "supporting": phrase["supporting"],
                    "style": phrase["style"],
                }
            )
        manifest_path.write_text(json.dumps({"variants": variants}, indent=2), encoding="utf-8")
        return variants

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

    def _render_creator_thumbnail(self, path: Path, phrase: dict[str, str], variant: int) -> None:
        width, height = 1280, 720
        palettes = [
            {"bg": "#101820", "accent": "#ffcc33", "hot": "#f04f3a", "text": "#ffffff", "sub": "#d7e4ef"},
            {"bg": "#19161f", "accent": "#31d0aa", "hot": "#ff4d7d", "text": "#ffffff", "sub": "#e5dff0"},
            {"bg": "#071f2a", "accent": "#f8f871", "hot": "#45b7ff", "text": "#ffffff", "sub": "#d8edf5"},
        ]
        palette = palettes[(variant - 1) % len(palettes)]
        image = Image.new("RGB", (width, height), palette["bg"])
        draw = ImageDraw.Draw(image)

        for y in range(height):
            blend = y / height
            color = self._blend_hex(palette["bg"], "#000000", blend * 0.35)
            draw.line([(0, y), (width, y)], fill=color)

        self._draw_creator_shapes(draw, width, height, palette, variant)

        headline = phrase["headline"].upper()
        supporting = phrase["supporting"].upper()
        headline_font = self._font(104 if len(headline) < 18 else 88, bold=True)
        support_font = self._font(42, bold=True)
        tag_font = self._font(30, bold=True)

        headline_lines = self._fit_lines(draw, headline, headline_font, 760)
        support_lines = self._fit_lines(draw, supporting, support_font, 660)
        x = 80
        y = 112
        for line in headline_lines:
            draw.text((x + 6, y + 8), line, fill="#000000", font=headline_font)
            draw.text((x, y), line, fill=palette["text"], font=headline_font)
            y += int(headline_font.size * 1.05)

        draw.rounded_rectangle((80, y + 18, 650, y + 92), radius=14, fill=palette["accent"])
        draw.text((108, y + 32), "PERSONAL FINANCE", fill="#08111a", font=tag_font)

        y = 540
        for line in support_lines[:2]:
            draw.text((82, y + 3), line, fill="#000000", font=support_font)
            draw.text((80, y), line, fill=palette["sub"], font=support_font)
            y += 48

        draw.text((1042, 648), "YTCreate", fill=palette["sub"], font=tag_font)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, quality=94, subsampling=0)

    def _draw_creator_shapes(self, draw: ImageDraw.ImageDraw, width: int, height: int, palette: dict[str, str], variant: int) -> None:
        center = (980, 350)
        draw.ellipse((740, 98, 1215, 573), fill=self._with_alpha_mix(palette["accent"], palette["bg"], 0.22), outline=palette["accent"], width=8)
        draw.ellipse((824, 182, 1132, 490), fill=self._with_alpha_mix(palette["hot"], palette["bg"], 0.38), outline=palette["hot"], width=10)
        symbol_font = self._font(122, bold=True)
        main_symbol = "₹" if variant != 3 else "%"
        draw.text((center[0] - 50, center[1] - 72), main_symbol, fill="#ffffff", font=symbol_font)
        for index in range(8):
            angle = (index / 8) * math.tau + (variant * 0.2)
            radius = 230 + (index % 2) * 42
            x = center[0] + math.cos(angle) * radius
            y = center[1] + math.sin(angle) * radius
            size = 44 if index % 2 == 0 else 30
            draw.rounded_rectangle((x - size, y - size / 2, x + size, y + size / 2), radius=10, fill=palette["hot"])
        draw.line((770, 586, 1210, 200), fill=palette["accent"], width=14)

    def _thumbnail_phrases(self, titles: list[str], scenes: list[dict[str, Any]]) -> list[dict[str, str]]:
        corpus = " ".join([*titles, *(str(scene.get("narration_text") or "") for scene in scenes)]).lower()
        if "salary" in corpus or "leftover" in corpus or "month" in corpus:
            return [
                {"headline": "Salary Gone?", "supporting": "Where the money disappears", "style": "salary_leak"},
                {"headline": "Broke by Day 20", "supporting": "The hidden spending pattern", "style": "month_end"},
                {"headline": "₹50K Trap", "supporting": "Looks stable, feels impossible", "style": "salary_trap"},
            ]
        if "debt" in corpus or "emi" in corpus or "loan" in corpus:
            return [
                {"headline": "EMI Trap", "supporting": "One payment becomes five", "style": "emi"},
                {"headline": "Debt Spiral", "supporting": "The mistake starts small", "style": "debt"},
                {"headline": "Salary Squeezed", "supporting": "Why cash flow collapses", "style": "squeeze"},
            ]
        dominant = self._dominant_title(titles)
        return [
            {"headline": dominant, "supporting": "The money lesson nobody explains", "style": "generic_1"},
            {"headline": "Fix This First", "supporting": dominant, "style": "generic_2"},
            {"headline": "Money Leak", "supporting": dominant, "style": "generic_3"},
        ]

    def _dominant_title(self, titles: list[str]) -> str:
        title = next((candidate for candidate in titles if candidate.strip()), "Money Mistake")
        cleaned = re.sub(r"[^\w\s₹%]", " ", title)
        words = [word for word in cleaned.split() if len(word) > 2][:4]
        return " ".join(words) or "Money Mistake"

    def _fit_lines(self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            candidate = " ".join([*current, word])
            if draw.textlength(candidate, font=font) > max_width and current:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            lines.append(" ".join(current))
        return lines[:3]

    def _font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        font_name = "NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf"
        font_path = Path(current_app.root_path) / "static" / "fonts" / font_name
        return ImageFont.truetype(str(font_path), size=size)

    def _blend_hex(self, a: str, b: str, ratio: float) -> str:
        ratio = max(0.0, min(1.0, ratio))
        aa = tuple(int(a[index : index + 2], 16) for index in (1, 3, 5))
        bb = tuple(int(b[index : index + 2], 16) for index in (1, 3, 5))
        mixed = tuple(int(aa[i] * (1 - ratio) + bb[i] * ratio) for i in range(3))
        return "#%02x%02x%02x" % mixed

    def _with_alpha_mix(self, fg: str, bg: str, alpha: float) -> str:
        return self._blend_hex(bg, fg, alpha)
