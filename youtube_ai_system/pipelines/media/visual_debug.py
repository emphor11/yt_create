from __future__ import annotations

import json
from typing import Callable


class MediaVisualDebugPrinter:
    """Formats VISUAL_DEBUG output for media rendering."""

    def __init__(
        self,
        *,
        render_specs,
        estimate_duration: Callable[[str], float],
        ten_minute_finance_enabled: Callable[[], bool],
        load_scene_beats: Callable[[dict, float], list[dict]],
    ) -> None:
        self.render_specs = render_specs
        self.estimate_duration = estimate_duration
        self.ten_minute_finance_enabled = ten_minute_finance_enabled
        self.load_scene_beats = load_scene_beats

    def print_existing_scene_debug(self, scene: dict) -> None:
        try:
            duration = self.estimate_duration(str(scene.get("narration_text") or ""))
            if self.ten_minute_finance_enabled():
                entries = []
                for beat in self.load_scene_beats(scene, duration):
                    validated_beat = self.validated_beat_for_debug(beat)
                    try:
                        spec = self.render_specs.beat_spec(beat)
                        entries.append(self.debug_entry(validated_beat, spec))
                    except Exception as exc:
                        entries.append(
                            {
                                "visual_logic": validated_beat.get("visual_logic") or {"type": str(validated_beat.get("beat_type") or "legacy")},
                                "validated_beat": validated_beat,
                                "render_spec": {"error": str(exc)},
                            }
                        )
                self.print_visual_debug(scene, entries)
                return

            try:
                spec = self.render_specs.scene_spec(scene, duration)
                render_spec = {"component": spec.composition, "props": spec.props}
            except Exception as exc:
                render_spec = {"error": str(exc)}
            self.print_visual_debug(
                scene,
                [
                    {
                        "visual_logic": {"type": "scene", "content": scene.get("visual_instruction") or scene.get("narration_text") or ""},
                        "validated_beat": {
                            "visual_type": scene.get("visual_type"),
                            "visual_instruction": scene.get("visual_instruction"),
                            "narration_text": scene.get("narration_text"),
                        },
                        "render_spec": render_spec,
                    }
                ],
            )
        except Exception as exc:
            print(f"\n--- SCENE {scene.get('scene_order', '?')} DEBUG ---\n")
            print("DEBUG_ERROR:")
            print(json.dumps(str(exc), ensure_ascii=False, indent=2))
            print("\n---\n")

    def validated_beat_for_debug(self, beat: dict) -> dict:
        if self.render_specs._is_structured_beat(beat):
            return self.render_specs.normalize_structured_beat(beat)
        return dict(beat)

    def debug_entry(self, validated_beat: dict, spec) -> dict:
        visual_logic = validated_beat.get("visual_logic")
        if visual_logic is None:
            visual_logic = {
                "type": str(validated_beat.get("beat_type") or "legacy"),
                "content": str(validated_beat.get("content") or ""),
                "caption": str(validated_beat.get("caption") or ""),
            }
        return {
            "visual_logic": visual_logic,
            "validated_beat": validated_beat,
            "render_spec": {
                "component": spec.composition,
                "props": spec.props,
            },
        }

    def print_visual_debug(self, scene: dict, entries: list[dict]) -> None:
        scene_order = int(scene.get("scene_order") or scene.get("scene_index") or 0)
        narration = str(scene.get("narration_text") or scene.get("narration") or "")
        visual_logic = [entry["visual_logic"] for entry in entries]
        validated_beats = [entry["validated_beat"] for entry in entries]
        render_specs = [entry["render_spec"] for entry in entries]
        print(f"\n--- SCENE {scene_order} DEBUG ---\n")
        print("NARRATION:")
        print(json.dumps(narration, ensure_ascii=False, indent=2))
        print("\nVISUAL_LOGIC:")
        print(json.dumps(visual_logic[0] if len(visual_logic) == 1 else visual_logic, ensure_ascii=False, indent=2, default=str))
        print("\nVALIDATED_BEAT:")
        print(json.dumps(validated_beats[0] if len(validated_beats) == 1 else validated_beats, ensure_ascii=False, indent=2, default=str))
        print("\nRENDER_SPEC:")
        print(json.dumps(render_specs[0] if len(render_specs) == 1 else render_specs, ensure_ascii=False, indent=2, default=str))
        print("\n---\n")
