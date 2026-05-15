from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


THEME = {
    "background": "#0A0A14",
    "surface": "#12121F",
    "text_primary": "#FFFFFF",
    "text_secondary": "rgba(255,255,255,0.6)",
    "accent_positive": "#2EC4B6",
    "accent_warning": "#FF9F1C",
    "accent_danger": "#E63946",
    "accent_neutral": "#4361EE",
}


@dataclass(frozen=True)
class VisualDirectorInput:
    concept_type: str
    concept_name: str
    primary_entity: str
    action: str
    start_value: str | None
    end_value: str | None
    percentage: float | None
    time_period: str | None
    confidence: float
    narration_text: str
    idea_type: str
    has_numbers: bool
    section_position: str
    preceding_concept_type: str | None
    visual_story: dict[str, Any] = field(default_factory=dict)
    story_state: dict[str, Any] = field(default_factory=dict)
    semantic_scene: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DirectedBeat:
    component: str
    text: str
    emphasis: str = "normal"
    subtext: str | None = None
    data: dict[str, Any] | None = None
    props: dict[str, Any] | None = None
    source_text: str | None = None
    sentence_index: int | None = None
    beat_phase: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "component": self.component,
            "text": self.text,
            "emphasis": self.emphasis,
        }
        if self.subtext:
            payload["subtext"] = self.subtext
        if self.data is not None:
            payload["data"] = self.data
        if self.props is not None:
            payload["props"] = self.props
        if self.source_text is not None:
            payload["source_text"] = self.source_text
        if self.sentence_index is not None:
            payload["sentence_index"] = self.sentence_index
        if self.beat_phase:
            payload["beat_phase"] = self.beat_phase
        return payload


@dataclass(frozen=True)
class SceneDirection:
    opening: str
    closing: str
    scene_position: str
    accent: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "emotional_arc": {"opening": self.opening, "closing": self.closing},
            "scene_position": self.scene_position,
            "accent": self.accent,
        }


@dataclass(frozen=True)
class CinematicIntent:
    visual_mode: str
    human_action: str
    metaphor: str
    overlay_text: str
    motion_treatment: str
    asset_query: str
    texture: str = "dark_documentary"

    def to_dict(self) -> dict[str, str]:
        return {
            "visual_mode": self.visual_mode,
            "human_action": self.human_action,
            "metaphor": self.metaphor,
            "overlay_text": self.overlay_text,
            "motion_treatment": self.motion_treatment,
            "asset_query": self.asset_query,
            "texture": self.texture,
        }


@dataclass(frozen=True)
class DirectedPlan:
    concept_type: str
    concept_name: str
    pattern: str
    data: dict[str, Any]
    beats: list[DirectedBeat]
    direction: SceneDirection
    theme: dict[str, str]
    fallback_reason: str | None = None
    visual_mode: str = "finance_mechanism"
    cinematic_intent: dict[str, str] = field(default_factory=dict)

    def is_valid(self) -> bool:
        return len(self.beats) >= 2 and all(beat.component and beat.text for beat in self.beats)

    def to_visual_plan_item(self) -> dict[str, Any]:
        return {
            "concept": {"concept": self.concept_name, "type": self.concept_type},
            "visual": {
                "pattern": self.pattern,
                "data": self.data,
                "visual_mode": self.visual_mode,
                "cinematic_intent": self.cinematic_intent,
            },
            "beats": {"beats": [beat.to_dict() for beat in self.beats]},
        }

