from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SCHEMA_VERSION = "visual_action_graph_v1"


@dataclass(frozen=True)
class VisualAction:
    id: str
    action: str
    label: str
    motion: str
    intent: str
    semantic_role: str = ""
    source_entity_id: str = ""
    target_entity_id: str = ""
    relationship_id: str = ""
    sentence_index: int | None = None
    value: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    sequence_index: int = 0
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualActionEdge:
    id: str
    type: str
    source_action_id: str
    target_action_id: str
    label: str
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualActionGraph:
    scene_id: str
    primary_concept: dict[str, Any]
    actions: list[VisualAction]
    edges: list[VisualActionEdge]
    warnings: list[dict[str, Any]]
    confidence: float
    source: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "scene_id": self.scene_id,
            "primary_concept": dict(self.primary_concept),
            "actions": [action.to_dict() for action in self.actions],
            "edges": [edge.to_dict() for edge in self.edges],
            "warnings": list(self.warnings),
            "confidence": self.confidence,
        }
