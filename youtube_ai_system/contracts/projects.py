"""Project contract wrappers compatible with existing project dicts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import ContractValidationResult, ValidationIssue


@dataclass(frozen=True)
class ProjectContract:
    id: int | None = None
    working_title: str = ""
    topic: str = ""
    angle: str = ""
    state: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProjectContract":
        return cls(
            id=payload.get("id"),
            working_title=str(payload.get("working_title") or ""),
            topic=str(payload.get("topic") or ""),
            angle=str(payload.get("angle") or ""),
            state=str(payload.get("state") or ""),
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data.update(
            {
                "id": self.id,
                "working_title": self.working_title,
                "topic": self.topic,
                "angle": self.angle,
                "state": self.state,
            }
        )
        return data

    def validate(self) -> ContractValidationResult:
        result = ContractValidationResult()
        if not self.working_title:
            result = result.with_issue(
                ValidationIssue("missing_working_title", "Project title is missing.", "working_title")
            )
        if not self.state:
            result = result.with_issue(
                ValidationIssue("missing_state", "Project state is missing.", "state")
            )
        return result

