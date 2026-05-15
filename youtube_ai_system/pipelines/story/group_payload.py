from __future__ import annotations

import re
from typing import Any


class StoryGroupPayloadHelper:
    """Build story-group records from existing scene text without owning orchestration."""

    def visual_scene_source(self, scene: dict[str, Any]) -> dict[str, Any]:
        visual_scene = scene.get("visual_scene")
        if isinstance(visual_scene, dict):
            return dict(visual_scene)

        source: dict[str, Any] = {}
        for key in ("visual_intent", "visual_beats", "numbers", "emotion", "mechanism"):
            if key in scene:
                source[key] = scene[key]
        if source:
            source.setdefault("narration", scene.get("narration") or scene.get("text") or "")
        return source

    def has_numbers(self, text: str) -> bool:
        return bool(re.search(r"₹|%|\d+", text))

    def has_comparison(self, text: str) -> bool:
        return bool(re.search(r"\bvs\b|\bversus\b|\bbut\b|\bhowever\b|\binstead\b", text, re.IGNORECASE))

    def has_causation(self, text: str) -> bool:
        return bool(
            re.search(
                r"\bbecause\b|\bso\b|\btherefore\b|\bleads to\b|\bresults in\b",
                text,
                re.IGNORECASE,
            )
        )

    def group_record(
        self,
        narration: str,
        *,
        idea_group_id: str,
        dominant_entity: str = "money",
        idea_type: str = "emphasis",
        visual_scene: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "narration": narration,
            "idea_group_id": idea_group_id,
            "dominant_entity": dominant_entity,
            "idea_type": idea_type,
            "has_numbers": self.has_numbers(narration),
            "has_comparison": self.has_comparison(narration),
            "has_causation": self.has_causation(narration),
        }
        if visual_scene is not None:
            record["visual_scene"] = visual_scene
        return record
