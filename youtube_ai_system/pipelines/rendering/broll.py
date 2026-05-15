from __future__ import annotations

from collections.abc import Callable
from typing import Any


class RenderBrollResolver:
    """B-roll source asset requirements and search query extraction."""

    def beat_requires_source_asset(
        self,
        beat: dict[str, Any],
        *,
        is_structured_beat: Callable[[dict[str, Any]], bool],
        normalize_structured_beat: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> bool:
        if is_structured_beat(beat):
            return normalize_structured_beat(beat)["component"] == "BrollOverlay"
        return False

    def broll_query_for_beat(
        self,
        beat: dict[str, Any],
        *,
        is_structured_beat: Callable[[dict[str, Any]], bool],
        normalize_structured_beat: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> str:
        if is_structured_beat(beat):
            normalized = normalize_structured_beat(beat)
            props = normalized.get("props") or {}
            return str(
                props.get("query")
                or props.get("searchQuery")
                or normalized.get("visual_logic")
                or normalized.get("caption")
                or "finance stress"
            )
        return str(beat.get("content") or beat.get("caption") or "finance stress")
