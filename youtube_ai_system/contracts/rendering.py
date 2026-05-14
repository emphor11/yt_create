"""Render specification contract wrappers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import ContractValidationResult, ValidationIssue


@dataclass(frozen=True)
class RenderSpecContract:
    composition: str = ""
    props: dict[str, Any] = field(default_factory=dict)
    duration_frames: int | None = None
    fps: int | None = None
    output_path: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RenderSpecContract":
        return cls(
            composition=str(payload.get("composition") or payload.get("composition_id") or ""),
            props=dict(payload.get("props") or payload.get("input_props") or {}),
            duration_frames=payload.get("duration_frames"),
            fps=payload.get("fps"),
            output_path=str(payload.get("output_path") or ""),
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data.update(
            {
                "composition": self.composition,
                "props": dict(self.props),
                "duration_frames": self.duration_frames,
                "fps": self.fps,
                "output_path": self.output_path,
            }
        )
        return data

    def validate(self) -> ContractValidationResult:
        result = ContractValidationResult()
        if not self.composition:
            result = result.with_issue(
                ValidationIssue("missing_composition", "Render composition is missing.", "composition")
            )
        return result

