"""Story planning compatibility contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import ContractValidationResult, ValidationIssue


@dataclass(frozen=True)
class StoryPlanContract:
    thesis: str = ""
    format_name: str = ""
    hook_type: str = ""
    scenes: tuple[dict[str, Any], ...] = ()
    sections: tuple[dict[str, Any], ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StoryPlanContract":
        return cls(
            thesis=str(payload.get("thesis") or payload.get("core_thesis") or ""),
            format_name=str(payload.get("format") or payload.get("format_name") or ""),
            hook_type=str(payload.get("hook_type") or ""),
            scenes=tuple(scene for scene in payload.get("scenes", []) if isinstance(scene, dict)),
            sections=tuple(section for section in payload.get("sections", []) if isinstance(section, dict)),
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data.update(
            {
                "thesis": self.thesis,
                "format_name": self.format_name,
                "hook_type": self.hook_type,
                "scenes": list(self.scenes),
                "sections": list(self.sections),
            }
        )
        return data

    def validate(self) -> ContractValidationResult:
        result = ContractValidationResult()
        if not (self.scenes or self.sections):
            result = result.with_issue(ValidationIssue("missing_story_units", "Story plan has no scenes or sections.", "scenes"))
        return result
