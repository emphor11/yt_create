from __future__ import annotations

import math
import re
import tempfile
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont


SENTIMENT_COLORS = {
    "negative": "#E63946",
    "positive": "#2EC4B6",
    "neutral": "#FF9F1C",
}

CHART_COLORS = {
    "red": "#E63946",
    "green": "#2EC4B6",
    "orange": "#FF9F1C",
    "blue": "#4361EE",
    "teal": "#4CC9F0",
}

PIE_PALETTE = ["#4361EE", "#E63946", "#2EC4B6", "#FF9F1C", "#7209B7"]

_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def fade_rgb(color: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    return tuple(int(c * max(0.0, min(1.0, alpha))) for c in color)


def get_font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    key = ("bold" if bold else "regular", size)
    if key not in _FONT_CACHE:
        fonts_dir = Path(__file__).resolve().parents[2] / "static" / "fonts"
        filename = "NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf"
        font_path = fonts_dir / filename
        if font_path.exists():
            _FONT_CACHE[key] = ImageFont.truetype(str(font_path), size)
        else:
            _FONT_CACHE[key] = ImageFont.load_default(size=size)
    return _FONT_CACHE[key]


class LegacyVisualVideoRenderer:
    """Legacy PIL/ffmpeg visual renderers kept behavior-compatible."""

    def __init__(
        self,
        *,
        groq_json: Callable[[str, str, str], dict],
        require_ffmpeg: Callable[[], str],
        encode_frame_sequence: Callable[[str, Path, int, Path], None],
        format_number: Callable[[float], str],
    ) -> None:
        self.groq_json = groq_json
        self.require_ffmpeg = require_ffmpeg
        self.encode_frame_sequence = encode_frame_sequence
        self.format_number = format_number

    def parse_motion_text(self, visual_instruction: str) -> dict:
        try:
            return self.groq_json(
                "You are a parsing assistant. Return valid JSON only.",
                (
                    "Parse this visual instruction for a YouTube finance video motion graphics "
                    "frame. Return valid JSON only, no markdown, no explanation.\n"
                    "Fields required:\n"
                    "- headline: main text to display large, maximum 4 words, can include "
                    "numbers and ₹ symbol\n"
                    "- subtext: supporting label displayed smaller below headline, "
                    "maximum 6 words, can be empty string\n"
                    "- sentiment: positive | negative | neutral\n\n"
                    f"Instruction: {visual_instruction}"
                ),
                "motion_text_parsing",
            )
        except RuntimeError:
            words = visual_instruction.split()
            headline = " ".join(words[:4]).upper() if words else "KEY STAT"
            subtext = " ".join(words[4:10]) if len(words) > 4 else ""
            return {"headline": headline, "subtext": subtext, "sentiment": "neutral"}

    def render_motion_text_video(
        self,
        image_root: Path,
        scene_order: int,
        text: str,
        target_duration: float,
    ) -> tuple[Path, str]:
        ffmpeg_bin = self.require_ffmpeg()
        output_path = image_root / f"scene-{scene_order:02d}.mp4"
        fps = 30
        frame_count = max(int(target_duration * fps), fps * 2)

        parsed = self.parse_motion_text(text)
        headline = str(parsed.get("headline", "")).strip() or "KEY STAT"
        subtext = str(parsed.get("subtext", "")).strip()
        sentiment = str(parsed.get("sentiment", "neutral")).strip().lower()
        if sentiment not in SENTIMENT_COLORS:
            sentiment = "neutral"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            for frame_index in range(frame_count):
                frame_path = temp_root / f"frame-{frame_index:04d}.png"
                self.draw_motion_text_frame(
                    frame_path,
                    headline,
                    subtext,
                    sentiment,
                    frame_index,
                    frame_count,
                )
            self.encode_frame_sequence(ffmpeg_bin, temp_root, fps, output_path)

        return output_path, "motion_text_video"

    def draw_motion_text_frame(
        self,
        path: Path,
        headline: str,
        subtext: str,
        sentiment: str,
        frame_index: int,
        frame_count: int,
    ) -> None:
        width, height = 1920, 1080
        bg_color = hex_to_rgb("#0A0A14")
        image = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(image)

        accent_color = SENTIMENT_COLORS.get(sentiment, SENTIMENT_COLORS["neutral"])
        draw.rectangle((0, 0, 8, height), fill=accent_color)

        gradient_start_y = int(height * 0.75)
        for y in range(gradient_start_y, height):
            progress = (y - gradient_start_y) / (height - gradient_start_y)
            darkened = tuple(max(0, bg_color[c] - int(progress * 0.4 * bg_color[c])) for c in range(3))
            draw.line([(0, y), (width, y)], fill=darkened)

        headline_font = get_font(bold=True, size=96)
        subtext_font = get_font(bold=False, size=42)

        headline_alpha = min(1.0, (frame_index + 1) / 8.0)
        subtext_alpha = max(0.0, min(1.0, (frame_index - 7) / 8.0)) if frame_index >= 7 else 0.0

        headline_bbox = headline_font.getbbox(headline)
        headline_w = headline_bbox[2] - headline_bbox[0]
        headline_h = headline_bbox[3] - headline_bbox[1]
        headline_x = (width - headline_w) // 2
        headline_y = (height // 2) - headline_h - 20

        headline_color = fade_rgb((255, 255, 255), headline_alpha)
        draw.text((headline_x, headline_y), headline, font=headline_font, fill=headline_color)

        if subtext:
            subtext_bbox = subtext_font.getbbox(subtext)
            subtext_w = subtext_bbox[2] - subtext_bbox[0]
            subtext_x = (width - subtext_w) // 2
            subtext_y = headline_y + headline_h + 32
            subtext_color = fade_rgb((166, 166, 166), subtext_alpha)
            draw.text((subtext_x, subtext_y), subtext, font=subtext_font, fill=subtext_color)

        image.save(path)

    def parse_graph_data(self, instruction: str) -> dict:
        try:
            return self.groq_json(
                "You are a data parsing assistant. Return valid JSON only.",
                (
                    "Parse this graph visual instruction for a YouTube finance video. "
                    "Return valid JSON only, no markdown, no explanation.\n"
                    "Fields required:\n"
                    "- chart_type: bar | line | pie | number_reveal\n"
                    "- title: string, max 8 words, the chart heading\n"
                    "- x_label: string, label for x axis (empty string for pie and number_reveal)\n"
                    "- y_label: string, label for y axis (empty string for pie and number_reveal)\n"
                    "- color: red | green | orange | blue | teal\n"
                    "- background: dark\n"
                    "- data: array format depends on chart_type:\n"
                    '    for bar: [{"label": "string", "value": number}, ...]\n'
                    '    for line: [{"label": "string", "value": number}, ...] '
                    "where label is the x-axis point (year, month, etc)\n"
                    '    for pie: [{"label": "string", "percentage": number}, ...] '
                    "percentages must sum to 100\n"
                    '    for number_reveal: {"number": "string", "unit": "string", "label": "string"}\n'
                    '                       example: {"number": "40%", "unit": "", '
                    '"label": "Credit Card Interest Rate"}\n\n'
                    "If the instruction does not contain explicit data, infer realistic "
                    "approximate data that matches the narrative context and is consistent "
                    "with publicly known Indian financial statistics.\n\n"
                    f"Instruction: {instruction}"
                ),
                "graph_data_parsing",
            )
        except RuntimeError:
            return {
                "chart_type": "bar",
                "title": instruction[:60] if instruction else "Financial Overview",
                "x_label": "",
                "y_label": "",
                "color": "blue",
                "data": [
                    {"label": "2020", "value": 45},
                    {"label": "2021", "value": 52},
                    {"label": "2022", "value": 61},
                    {"label": "2023", "value": 58},
                    {"label": "2024", "value": 73},
                ],
            }

    def render_graph_video(
        self,
        image_root: Path,
        scene_order: int,
        instruction: str,
        target_duration: float,
    ) -> tuple[Path, str]:
        ffmpeg_bin = self.require_ffmpeg()
        output_path = image_root / f"scene-{scene_order:02d}.mp4"
        fps = 30
        frame_count = max(int(target_duration * fps), fps * 2)

        graph_spec = self.parse_graph_data(instruction)
        chart_type = str(graph_spec.get("chart_type", "bar")).lower()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            for frame_index in range(frame_count):
                progress = (frame_index + 1) / frame_count
                frame_path = temp_root / f"frame-{frame_index:04d}.png"

                if chart_type == "pie":
                    self.draw_pie_frame(frame_path, graph_spec, progress)
                elif chart_type == "number_reveal":
                    self.draw_number_reveal_frame(frame_path, graph_spec, progress)
                elif chart_type == "line":
                    self.draw_line_frame(frame_path, graph_spec, progress)
                else:
                    self.draw_bar_frame(frame_path, graph_spec, progress)

            self.encode_frame_sequence(ffmpeg_bin, temp_root, fps, output_path)

        return output_path, "graph_video"

    def resolve_chart_color(self, color_name: str) -> str:
        return CHART_COLORS.get(color_name.lower(), CHART_COLORS["blue"])

    def draw_bar_frame(self, path: Path, spec: dict, progress: float) -> None:
        width, height = 1920, 1080
        bg = hex_to_rgb("#0D1117")
        image = Image.new("RGB", (width, height), color=bg)
        draw = ImageDraw.Draw(image)

        title_font = get_font(bold=True, size=28)
        label_font = get_font(bold=False, size=20)
        value_font = get_font(bold=True, size=20)

        title = str(spec.get("title", "Chart"))
        color_hex = self.resolve_chart_color(str(spec.get("color", "blue")))
        bar_color = hex_to_rgb(color_hex)
        data = spec.get("data", [])
        if not isinstance(data, list) or len(data) < 2:
            data = [
                {"label": "Start", "value": 40},
                {"label": "Middle", "value": 60},
                {"label": "End", "value": 80},
            ]

        t_bbox = title_font.getbbox(title)
        t_w = t_bbox[2] - t_bbox[0]
        draw.text(((width - t_w) // 2, 40), title, font=title_font, fill="white")

        chart_left, chart_top, chart_right, chart_bottom = 160, 120, 1760, 920

        draw.line((chart_left, chart_bottom, chart_right, chart_bottom), fill=(255, 255, 255), width=1)
        draw.line((chart_left, chart_top, chart_left, chart_bottom), fill=(255, 255, 255), width=1)

        for i in range(1, 5):
            gy = chart_bottom - int((chart_bottom - chart_top) * (i / 5))
            draw.line((chart_left, gy, chart_right, gy), fill=(38, 42, 48), width=1)

        values = [float(d.get("value", 0)) for d in data]
        labels = [str(d.get("label", "")) for d in data]
        max_value = max(values) if values and max(values) > 0 else 1

        for i in range(6):
            val = int(max_value * i / 5)
            gy = chart_bottom - int((chart_bottom - chart_top) * (i / 5))
            draw.text((chart_left - 60, gy - 10), str(val), font=label_font, fill=(148, 163, 184))

        step_x = (chart_right - chart_left) / max(len(values), 1)
        bar_width = step_x * 0.55
        anim_progress = min(progress / 0.6, 1.0)

        for idx, value in enumerate(values):
            animated_value = value * anim_progress
            x1 = chart_left + step_x * idx + (step_x - bar_width) / 2
            x2 = x1 + bar_width
            bar_h = (chart_bottom - chart_top) * (animated_value / max_value)
            y1 = chart_bottom - bar_h

            draw.rounded_rectangle((x1, y1, x2, chart_bottom), radius=6, fill=bar_color)
            draw.text((x1, chart_bottom + 12), labels[idx], font=label_font, fill=(148, 163, 184))
            if anim_progress >= 1.0:
                val_str = self.format_number(value)
                draw.text((x1, y1 - 28), val_str, font=value_font, fill="white")

        x_label = str(spec.get("x_label", ""))
        if x_label:
            xl_bbox = label_font.getbbox(x_label)
            draw.text(((width - (xl_bbox[2] - xl_bbox[0])) // 2, chart_bottom + 50), x_label, font=label_font, fill=(148, 163, 184))

        image.save(path)

    def draw_line_frame(self, path: Path, spec: dict, progress: float) -> None:
        width, height = 1920, 1080
        bg = hex_to_rgb("#0D1117")
        image = Image.new("RGB", (width, height), color=bg)
        draw = ImageDraw.Draw(image)

        title_font = get_font(bold=True, size=28)
        label_font = get_font(bold=False, size=20)
        value_font = get_font(bold=True, size=18)

        title = str(spec.get("title", "Trend"))
        color_hex = self.resolve_chart_color(str(spec.get("color", "blue")))
        line_color = hex_to_rgb(color_hex)
        fill_color = fade_rgb(line_color, 0.15)
        data = spec.get("data", [])
        if not isinstance(data, list) or len(data) < 2:
            data = [
                {"label": "Start", "value": 40},
                {"label": "Middle", "value": 60},
                {"label": "End", "value": 80},
            ]

        t_bbox = title_font.getbbox(title)
        t_w = t_bbox[2] - t_bbox[0]
        draw.text(((width - t_w) // 2, 40), title, font=title_font, fill="white")

        chart_left, chart_top, chart_right, chart_bottom = 160, 120, 1760, 920

        draw.line((chart_left, chart_bottom, chart_right, chart_bottom), fill=(255, 255, 255), width=1)
        draw.line((chart_left, chart_top, chart_left, chart_bottom), fill=(255, 255, 255), width=1)

        for i in range(1, 5):
            gy = chart_bottom - int((chart_bottom - chart_top) * (i / 5))
            draw.line((chart_left, gy, chart_right, gy), fill=(38, 42, 48), width=1)

        values = [float(d.get("value", 0)) for d in data]
        labels = [str(d.get("label", "")) for d in data]
        max_value = max(values) if values and max(values) > 0 else 1

        step_x = (chart_right - chart_left) / max(len(values) - 1, 1)
        all_points = []
        for idx, value in enumerate(values):
            x = chart_left + step_x * idx
            y = chart_bottom - ((chart_bottom - chart_top) * (value / max_value))
            all_points.append((x, y))

        line_progress = min(progress / 0.7, 1.0)
        visible_count = max(2, int(len(all_points) * line_progress))
        visible_points = all_points[:visible_count]

        if len(visible_points) >= 2:
            fill_polygon = list(visible_points) + [(visible_points[-1][0], chart_bottom), (visible_points[0][0], chart_bottom)]
            draw.polygon(fill_polygon, fill=fill_color)
            draw.line(visible_points, fill=line_color, width=3)

        for idx, point in enumerate(visible_points):
            draw.ellipse((point[0] - 5, point[1] - 5, point[0] + 5, point[1] + 5), fill=line_color)
            if idx < len(labels):
                draw.text((point[0] - 15, chart_bottom + 12), labels[idx], font=label_font, fill=(148, 163, 184))
            if line_progress >= 1.0 and idx < len(values):
                val_str = self.format_number(values[idx])
                draw.text((point[0] - 15, point[1] - 28), val_str, font=value_font, fill="white")

        image.save(path)

    def draw_pie_frame(self, path: Path, spec: dict, progress: float) -> None:
        width, height = 1920, 1080
        bg = hex_to_rgb("#0D1117")
        image = Image.new("RGB", (width, height), color=bg)
        draw = ImageDraw.Draw(image)

        title_font = get_font(bold=True, size=28)
        label_font = get_font(bold=False, size=22)
        pct_font = get_font(bold=True, size=24)

        title = str(spec.get("title", "Distribution"))
        data = spec.get("data", [])
        if not isinstance(data, list) or not data:
            data = [{"label": "N/A", "percentage": 100}]

        t_bbox = title_font.getbbox(title)
        t_w = t_bbox[2] - t_bbox[0]
        draw.text(((width - t_w) // 2, 40), title, font=title_font, fill="white")

        pie_cx, pie_cy, pie_r = 800, 540, 320
        pie_box = (pie_cx - pie_r, pie_cy - pie_r, pie_cx + pie_r, pie_cy + pie_r)

        anim_progress = min(progress / 0.6, 1.0)
        total_angle = 360 * anim_progress
        start_angle = -90

        percentages = [float(d.get("percentage", 0)) for d in data]
        labels_list = [str(d.get("label", "")) for d in data]

        for idx, pct in enumerate(percentages):
            segment_angle = (pct / 100) * total_angle
            if segment_angle <= 0:
                continue
            end_angle = start_angle + segment_angle
            color = PIE_PALETTE[idx % len(PIE_PALETTE)]
            draw.pieslice(pie_box, start_angle, end_angle, fill=color)

            if anim_progress >= 1.0 and pct >= 5:
                mid_angle = math.radians(start_angle + segment_angle / 2)
                lx = pie_cx + int(pie_r * 0.6 * math.cos(mid_angle))
                ly = pie_cy + int(pie_r * 0.6 * math.sin(mid_angle))
                draw.text((lx - 15, ly - 10), f"{pct:.0f}%", font=pct_font, fill="white")

            start_angle = end_angle

        legend_x = pie_cx + pie_r + 80
        legend_y = 200
        for idx, label in enumerate(labels_list):
            color = PIE_PALETTE[idx % len(PIE_PALETTE)]
            draw.rectangle((legend_x, legend_y, legend_x + 20, legend_y + 20), fill=color)
            draw.text((legend_x + 30, legend_y - 2), f"{label} ({percentages[idx]:.0f}%)", font=label_font, fill=(200, 200, 200))
            legend_y += 40

        image.save(path)

    def draw_number_reveal_frame(self, path: Path, spec: dict, progress: float) -> None:
        width, height = 1920, 1080
        bg = hex_to_rgb("#0D1117")
        image = Image.new("RGB", (width, height), color=bg)
        draw = ImageDraw.Draw(image)

        accent_color = self.resolve_chart_color(str(spec.get("color", "teal")))
        draw.rectangle((0, 0, 8, height), fill=accent_color)

        number_font = get_font(bold=True, size=120)
        label_font = get_font(bold=False, size=36)

        data = spec.get("data", {})
        if isinstance(data, list):
            data = data[0] if data else {}
        number_str = str(data.get("number", "0"))
        unit = str(data.get("unit", ""))
        label = str(data.get("label", ""))

        count_progress = min(progress / 0.7, 1.0)

        numeric_part = re.sub(r"[^\d.]", "", number_str)
        suffix = number_str.replace(numeric_part, "") if numeric_part else ""
        try:
            target_value = float(numeric_part) if numeric_part else 0
        except ValueError:
            target_value = 0

        current_value = target_value * count_progress
        if "." in numeric_part:
            display_number = f"{current_value:.1f}{suffix}"
        else:
            display_number = f"{int(current_value)}{suffix}"

        full_display = f"{display_number} {unit}".strip() if unit else display_number
        n_bbox = number_font.getbbox(full_display)
        n_w = n_bbox[2] - n_bbox[0]
        n_x = (width - n_w) // 2
        n_y = (height // 2) - 80
        draw.text((n_x, n_y), full_display, font=number_font, fill="white")

        if label:
            l_bbox = label_font.getbbox(label)
            l_w = l_bbox[2] - l_bbox[0]
            l_x = (width - l_w) // 2
            l_y = n_y + 140
            draw.text((l_x, l_y), label, font=label_font, fill=(179, 179, 179))

        image.save(path)
