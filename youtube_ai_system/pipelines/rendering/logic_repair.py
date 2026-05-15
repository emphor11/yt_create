from __future__ import annotations

from collections.abc import Callable
from typing import Any


class RenderLogicRepair:
    """Repairs visual logic text from structured beat props."""

    def repair_visual_logic(
        self,
        visual_logic_text: str,
        beat: dict[str, Any],
        context: str,
        *,
        numbers_respect_context: Callable[[str, str], bool],
        is_concrete_visual_logic: Callable[[str], bool],
        has_visual_structure: Callable[[str], bool],
        contextual_visual_logic: Callable[[str, dict[str, Any]], str],
        beat_context: Callable[[dict[str, Any]], str],
    ) -> str:
        for candidate in self.repair_candidates(visual_logic_text, beat):
            cleaned = " ".join(str(candidate or "").split())
            if not numbers_respect_context(cleaned, context):
                continue
            if is_concrete_visual_logic(cleaned) and has_visual_structure(cleaned):
                return cleaned
        return contextual_visual_logic(context or beat_context(beat), beat)

    def repair_candidates(self, visual_logic_text: str, beat: dict[str, Any]) -> list[str]:
        candidates = [visual_logic_text]
        props = beat.get("props") if isinstance(beat.get("props"), dict) else {}
        combined = " ".join(
            str(props.get(key) or "")
            for key in ("headline", "subtext", "leftContent", "rightContent", "content", "caption")
            if props.get(key)
        )
        if combined:
            candidates.append(combined)
        if props.get("leftContent") and props.get("rightContent"):
            candidates.append(f"{props.get('leftContent')} vs {props.get('rightContent')}")
        for key in ("headline", "subtext", "leftContent", "rightContent", "content", "caption", "query", "title"):
            value = props.get(key)
            if value:
                candidates.append(str(value))
        raw_data = props.get("data")
        if isinstance(raw_data, list):
            data_parts = []
            for point in raw_data[:4]:
                if isinstance(point, dict):
                    label = point.get("label")
                    value = point.get("value")
                    if label is not None and value is not None:
                        data_parts.append(f"{label}={value}")
            if data_parts:
                candidates.append("data: " + ", ".join(data_parts))
        raw_nodes = props.get("nodes")
        if isinstance(raw_nodes, list):
            labels = [
                str(node.get("label") if isinstance(node, dict) else node)
                for node in raw_nodes
                if str(node.get("label") if isinstance(node, dict) else node).strip()
            ]
            if labels:
                candidates.append(" -> ".join(labels))
        return candidates
