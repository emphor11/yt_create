"""Base contract primitives used across the refactor boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    field: str = ""
    severity: str = "error"


@dataclass(frozen=True)
class ContractValidationResult:
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.errors

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    def with_issue(self, issue: ValidationIssue) -> "ContractValidationResult":
        return ContractValidationResult(self.issues + (issue,))


@dataclass(frozen=True)
class DictBackedContract:
    """Compatibility wrapper for current dict/JSON payloads.

    This keeps old payload shapes available while allowing new code to add
    validation and named accessors around them.
    """

    data: dict[str, Any] = field(default_factory=dict)

    required_fields: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DictBackedContract":
        return cls(dict(payload))

    def to_dict(self) -> dict[str, Any]:
        return dict(self.data)

    def validate(self) -> ContractValidationResult:
        result = ContractValidationResult()
        for field_name in self.required_fields:
            if field_name not in self.data or self.data.get(field_name) in (None, ""):
                result = result.with_issue(
                    ValidationIssue(
                        code="missing_required_field",
                        message=f"Required field '{field_name}' is missing.",
                        field=field_name,
                    )
                )
        return result


@dataclass(frozen=True)
class ArtifactReference:
    path: str
    kind: str = "file"
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def exists(self) -> bool:
        return Path(self.path).exists()

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "source": self.source,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ArtifactReference":
        return cls(
            path=str(payload.get("path", "")),
            kind=str(payload.get("kind", "file")),
            source=str(payload.get("source", "")),
            metadata=dict(payload.get("metadata") or {}),
        )
