from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SCHEMA_VERSION = "visual_event_sequence_v1"


@dataclass(frozen=True)
class VisualEvent:
    id: str
    sequence_index: int
    active_entity: str
    world_object: str
    primitive_type: str
    perceptual_world: str
    emotional_direction: str
    narration_anchor: str
    suppression_target: str
    visual_purpose: str
    source_action_id: str = ""
    source_motion: str = ""
    semantic_role: str = ""
    value: dict[str, Any] = field(default_factory=dict)
    timing: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualEventSequence:
    scene_id: str
    primary_concept: dict[str, Any]
    events: list[VisualEvent]
    warnings: list[dict[str, Any]]
    confidence: float
    allowed_world_objects: list[str] = field(default_factory=list)
    forbidden_world_objects: list[str] = field(default_factory=list)
    recurring_example: dict[str, Any] = field(default_factory=dict)
    fidelity: dict[str, Any] = field(default_factory=dict)
    source: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "scene_id": self.scene_id,
            "primary_concept": dict(self.primary_concept),
            "events": [event.to_dict() for event in self.events],
            "allowed_world_objects": list(self.allowed_world_objects),
            "forbidden_world_objects": list(self.forbidden_world_objects),
            "recurring_example": dict(self.recurring_example),
            "fidelity": dict(self.fidelity),
            "warnings": list(self.warnings),
            "confidence": self.confidence,
        }
