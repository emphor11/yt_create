from __future__ import annotations

from pathlib import Path
from typing import Any

from ...contracts.adapters import load_json_array, load_json_object


class SceneRenderSectionBuilder:
    """Builds the scene-section payload consumed by the Remotion scene builder."""

    def __init__(self, *, text_signals: Any, outro_builder: Any, story_pipeline: Any, cinematic_event_compiler: Any) -> None:
        self.text_signals = text_signals
        self.outro_builder = outro_builder
        self.story_pipeline = story_pipeline
        self.cinematic_event_compiler = cinematic_event_compiler

    def section_for_scene_render(
        self,
        scene: dict,
        audio_duration: float,
        audio_path: Path,
        debug_trace: Any | None = None,
    ) -> dict:
        narration = str(scene.get("narration_text") or "")
        kind = str(scene.get("kind") or "body")
        stored_visual_scene = self.json_dict_from_scene_field(scene.get("visual_scene_json"))
        if debug_trace:
            debug_trace.snapshot("stored_visual_scene", stored_visual_scene, owner="scene_db")
            if stored_visual_scene:
                debug_trace.ownership("visual_scene", "scene_db", stored_visual_scene, "stored visual_scene_json")
        intelligence = self.section_intelligence_from_narration(
            narration,
            kind,
            visual_scene=stored_visual_scene,
            debug_trace=debug_trace,
        )
        stored_finance_concept = self.json_dict_from_scene_field(scene.get("finance_concept_json"))
        if stored_finance_concept:
            intelligence["finance_concept"] = stored_finance_concept

        visual_plan = list(intelligence.get("visual_plan") or []) or self.scene_visual_plan(scene)
        section = {
            "text": narration,
            "kind": kind,
            "weight": self.weight_for_scene_kind(kind),
            "visual_plan": visual_plan,
            "audio_file": str(audio_path),
            "audio_duration": float(audio_duration),
            "finance_concept": intelligence.get("finance_concept") or {},
            "semantic_scene": intelligence.get("semantic_scene") or {},
            "visual_action_graph": intelligence.get("visual_action_graph") or {},
            "visual_event_sequence": intelligence.get("visual_event_sequence") or {},
            "narrative_arc": intelligence.get("narrative_arc") or {},
            "visual_story": intelligence.get("visual_story") or {},
            "story_state": intelligence.get("story_state") or {},
            "direction": intelligence.get("direction"),
            "visual_mode": intelligence.get("visual_mode"),
            "cinematic_intent": intelligence.get("cinematic_intent") or {},
            "concept_type": str(intelligence.get("concept_type") or ""),
            "theme": intelligence.get("theme") or {},
            "state": intelligence.get("state") or {},
            "visual_type": str(intelligence.get("visual_type") or ""),
            "dominant_entity": str(intelligence.get("dominant_entity") or "money"),
            "idea_type": str(intelligence.get("idea_type") or "emphasis"),
            "has_numbers": bool(intelligence.get("has_numbers")),
            "has_comparison": bool(intelligence.get("has_comparison")),
            "has_causation": bool(intelligence.get("has_causation")),
            "visual_scene": stored_visual_scene or intelligence.get("visual_scene") or {},
        }
        section = self.cinematic_event_compiler.attach_to_section(section, duration_seconds=float(audio_duration))
        if debug_trace:
            debug_trace.snapshot("story_pipeline_section_for_render", section, owner="media_service")
            debug_trace.ownership("visual_plan", "media_service", visual_plan, "fresh intelligence visual plan preferred over stored plan")
            if section.get("cinematic_events"):
                debug_trace.ownership(
                    "cinematic_events",
                    "cinematic_event_compiler",
                    section.get("cinematic_events"),
                    "audio-duration-aware narration event timeline",
                )
        return section

    def scene_visual_plan(self, scene: dict) -> list[dict]:
        return load_json_array(scene.get("visual_plan_json"))

    def derived_visual_plan_from_narration(self, narration: str, kind: str) -> list[dict]:
        section = self.section_intelligence_from_narration(narration, kind)
        return list(section.get("visual_plan") or [])

    def section_intelligence_from_narration(
        self,
        narration: str,
        kind: str,
        visual_scene: dict | None = None,
        debug_trace: Any | None = None,
    ) -> dict:
        if kind == "outro":
            return self.outro_section_intelligence(narration)

        signals = self.scene_text_signals(narration)
        section: dict = {
            "type": "problem" if kind == "hook" else ("optimization" if kind == "outro" else "explanation"),
            "text": narration,
            "weight": self.weight_for_scene_kind(kind),
            **signals,
        }
        if visual_scene:
            section["visual_scene"] = visual_scene
        story_plan = {"hook": narration[:60], "agenda": [], "sections": [section]}
        if debug_trace:
            debug_trace.snapshot("story_pipeline_pre_visual_plan", story_plan, owner="media_service")
            self.story_pipeline.visual_scene_normalizer.normalize(section, 0, debug_trace=debug_trace)
        story_plan = self.story_pipeline.attach_section_concepts(story_plan, debug_trace=debug_trace)
        story_plan = self.story_pipeline.attach_section_narrative_arc(story_plan, debug_trace=debug_trace)
        sections_after_concepts = story_plan.get("sections") or [{}]
        if sections_after_concepts:
            concept_type = str(sections_after_concepts[0].get("concept_type") or "")
            if not concept_type:
                fc = sections_after_concepts[0].get("finance_concept") or {}
                concept_type = str(fc.get("concept_type") or "").lower()
            seed_objects = self.story_pipeline.visual_story_engine.CONCEPT_TO_OBJECTS.get(
                concept_type,
                ["money_decision"],
            )
            story_plan["visual_story"] = {
                "protagonist": {"role": "finance_decision_maker"},
                "recurring_objects": list(seed_objects),
            }
        story_plan = self.story_pipeline.attach_visual_story(story_plan)
        story_plan = self.story_pipeline.attach_section_visual_plan(story_plan, debug_trace=debug_trace)
        return dict((story_plan.get("sections") or [{}])[0])

    def outro_section_intelligence(self, narration: str) -> dict:
        return self.outro_builder.section_intelligence(narration)

    def outro_actions(self, narration: str) -> list[dict[str, object]]:
        return self.outro_builder.actions(narration)

    def outro_punchline(self, narration: str) -> str:
        return self.outro_builder.punchline(narration)

    def scene_text_signals(self, narration: str) -> dict[str, object]:
        return self.text_signals.scene_text_signals(narration)

    def dominant_entity_from_text(self, narration: str) -> str:
        return self.text_signals.dominant_entity_from_text(narration)

    def idea_type_from_text(self, narration: str) -> str:
        return self.text_signals.idea_type_from_text(narration)

    def json_dict_from_scene_field(self, value: object) -> dict:
        return load_json_object(value)

    def weight_for_scene_kind(self, kind: str) -> dict[str, object]:
        return self.text_signals.weight_for_scene_kind(kind)
