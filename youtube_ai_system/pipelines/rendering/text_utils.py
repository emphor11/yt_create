from __future__ import annotations

import re
from typing import Any


class RenderTextUtils:
    """Small text utilities used while building Remotion render specs."""

    def dominant_phrase(self, text: str) -> str:
        money_match = re.search(r"(₹\s?[\d,.]+(?:\s?(?:lakhs?|crores?|k|m)\b)?)", text, re.I)
        pct_match = re.search(r"(\d+(?:\.\d+)?%)", text)
        if money_match:
            return money_match.group(1).replace(" ", "")
        if pct_match:
            return pct_match.group(1)
        words = re.findall(r"[A-Za-z0-9₹%]+", text)
        return " ".join(words[:4]).upper() if words else "KEY STAT"

    def short_overlay(self, text: str, max_words: int) -> str:
        words = re.findall(r"[A-Za-z0-9₹%.,]+", text)
        return " ".join(words[:max_words]).strip()

    def sentiment(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ("debt", "broke", "loss", "lose", "risk", "mistake", "negative")):
            return "negative"
        if any(word in lowered for word in ("save", "profit", "growth", "invest", "positive", "wealth")):
            return "positive"
        return "neutral"

    def looks_like_line_chart(self, text: str) -> bool:
        lowered = text.lower()
        return any(word in lowered for word in ("line", "trend", "growth", "over time", "from 20"))

    def chart_color(self, text: str) -> str:
        sentiment = self.sentiment(text)
        if sentiment == "negative":
            return "red"
        if sentiment == "positive":
            return "teal"
        return "orange"

    def kicker(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ("debt", "broke", "loss", "mistake")):
            return "Risk signal"
        if any(word in lowered for word in ("save", "invest", "wealth", "growth")):
            return "Money move"
        return "Finance insight"

    def unit_label(self, text: str) -> str:
        if "%" in text:
            return "%"
        if "₹" in text or "rupee" in text.lower():
            return "₹"
        return ""

    def extract_named_field(self, text: str, field: str) -> str:
        match = re.search(rf"{field}\s*:\s*([^,;]+)", text, re.I)
        return match.group(1).strip() if match else ""

    def extract_color(self, text: str) -> str:
        color = self.extract_named_field(text, "color").lower()
        return color if color in {"red", "teal", "orange"} else ""

    def beat_color(self, value: Any) -> str:
        color = str(value or "orange").lower()
        return color if color in {"red", "orange", "teal", "navy", "white"} else "orange"

    def parse_split(self, content: str, caption: str) -> tuple[str, str, str, str]:
        text = content or caption
        parts = re.split(r"\s+vs\.?\s+|\s+\|\s+", text, maxsplit=1, flags=re.I)
        left = parts[0].strip() if parts else "What you think"
        right = parts[1].strip() if len(parts) > 1 else (caption or "Reality")
        return self.extract_split_label(left), left, self.extract_split_label(right), right

    def extract_split_label(self, content: str) -> str:
        cleaned = re.sub(r"₹\s?[\d,.]+(?:\s?(?:lakhs?|crores?|k|m)\b)?|\d+(?:\.\d+)?%", "", content, flags=re.I)
        words = [
            word
            for word in re.findall(r"[A-Za-z]+", cleaned)
            if word.lower() not in {"cannot", "cant", "less", "than", "left", "goes", "to"}
        ]
        return " ".join(words[:3]).title() or "Amount"
