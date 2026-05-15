"""Map normalized script payloads to current scene row dicts."""

from __future__ import annotations

import json
from typing import Any


class ScriptSceneRowMapper:
    def scene_rows_from_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        scene_rows = [
            {
                "scene_order": 0,
                "kind": "hook",
                "narration_text": payload["hook"]["narration"],
            }
        ]
        for index, scene in enumerate(payload["scenes"], start=1):
            row = {
                "scene_order": index,
                "kind": scene.get("kind", "body"),
                "narration_text": scene["narration"],
            }
            visual_scene = self.visual_scene_for_row(payload, scene, index)
            if visual_scene:
                row["visual_scene_json"] = json.dumps(visual_scene, ensure_ascii=False)
            scene_rows.append(row)
        scene_rows.append(
            {
                "scene_order": len(scene_rows),
                "kind": "outro",
                "narration_text": payload["outro"]["narration"],
            }
        )
        return scene_rows

    def visual_scene_for_row(self, payload: dict[str, Any], scene: dict[str, Any], index: int) -> dict[str, Any]:
        source = self.visual_scene_from_raw_scene(scene, str(scene.get("narration") or ""))
        if source:
            return source
        story_sections = ((payload.get("story_plan") or {}).get("sections") or [])
        scene_text = " ".join(str(scene.get("narration") or "").split())
        for section in story_sections:
            section_text = " ".join(str(section.get("text") or "").split())
            visual_scene = section.get("visual_scene")
            if isinstance(visual_scene, dict) and section_text and section_text == scene_text:
                return dict(visual_scene)
        section_index = index - 1
        if 0 <= section_index < len(story_sections):
            visual_scene = story_sections[section_index].get("visual_scene")
            if isinstance(visual_scene, dict):
                return dict(visual_scene)
        return {}

    def visual_scene_from_raw_scene(self, scene: dict[str, Any], narration: str) -> dict[str, Any]:
        source = scene.get("visual_scene") if isinstance(scene.get("visual_scene"), dict) else scene
        visual_scene: dict[str, Any] = {"narration": narration}
        for key in ("visual_intent", "visual_beats", "numbers", "emotion", "mechanism"):
            if key in source:
                visual_scene[key] = source[key]
        return visual_scene if len(visual_scene) > 1 else {}
