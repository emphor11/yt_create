from __future__ import annotations

from typing import Any


class StoryPlanningValidationMixin:
    def safe_visual_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        if self._is_valid_visual_item(item):
            return item
        return None

    def _is_valid_visual_item(self, item: dict[str, Any] | None) -> bool:
        if not item:
            return False
        visual = item.get("visual") or {}
        pattern = str(visual.get("pattern") or "").strip()
        data = visual.get("data") or {}
        if not pattern:
            return False
        if not isinstance(data, dict) or not data:
            return False
        if "title" in data and not str(data.get("title", "")).strip():
            return False
        if "values" in data and not [value for value in data.get("values") or [] if str(value).strip()]:
            return False
        beats = (item.get("beats") or {}).get("beats") or []
        if not beats:
            return False
        if any(not self._is_valid_beat(beat) for beat in beats):
            return False
        concept_text = str((item.get("concept") or {}).get("concept", "")).strip()
        if not concept_text:
            return False
        return True

    def _is_valid_beat(self, beat: dict[str, Any]) -> bool:
        if not isinstance(beat, dict):
            return False
        component = str(beat.get("component") or "").strip()
        beat_text = str(beat.get("text") or "").strip()
        steps = beat.get("steps") or []
        if not component:
            return False
        if component == "CalculationStrip" and self._valid_calculation_steps(steps):
            return True
        if not beat_text:
            return False
        lowered = beat_text.lower()
        fragment_starters = (
            "as soon",
            "we love",
            "the fact",
            "it is",
            "this is",
            "there are",
            "we have",
            "you know",
            "for the",
            "in the",
            "of the",
            "and the",
            "because",
            "which",
        )
        if any(lowered.startswith(fragment) for fragment in fragment_starters):
            return False
        if len(beat_text.split()) > 5:
            return False
        return True

    def _valid_calculation_steps(self, steps: Any) -> bool:
        if not isinstance(steps, list) or len(steps) < 2:
            return False
        for step in steps:
            if not isinstance(step, dict):
                return False
            if not str(step.get("label") or "").strip():
                return False
            if not str(step.get("value") or "").strip():
                return False
        return True
