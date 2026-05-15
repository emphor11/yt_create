from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SCHEMA_VERSION = "semantic_scene_contract_v1"


@dataclass(frozen=True)
class SemanticEntity:
    id: str
    label: str
    kind: str
    role: str
    value: float | None = None
    display_value: str = ""
    unit: str = ""
    direction: str = ""
    source_text: str = ""
    sentence_index: int | None = None
    confidence: float = 1.0
    provenance: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticRelationship:
    id: str
    type: str
    source_entity_id: str
    target_entity_id: str
    label: str
    confidence: float = 1.0
    provenance: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticDerivedValue:
    id: str
    label: str
    value: float | None
    display_value: str
    unit: str
    source_entity_ids: list[str]
    derivation_method: str
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticSceneContract:
    scene_id: str
    narration: str
    primary_concept: dict[str, Any]
    entities: list[SemanticEntity]
    relationships: list[SemanticRelationship]
    derived_values: list[SemanticDerivedValue]
    spoken_values: list[str]
    warnings: list[dict[str, Any]]
    confidence: float
    source: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "scene_id": self.scene_id,
            "narration": self.narration,
            "primary_concept": dict(self.primary_concept),
            "entities": [entity.to_dict() for entity in self.entities],
            "relationships": [relationship.to_dict() for relationship in self.relationships],
            "derived_values": [value.to_dict() for value in self.derived_values],
            "spoken_values": list(self.spoken_values),
            "warnings": list(self.warnings),
            "confidence": self.confidence,
        }
