from __future__ import annotations

from dataclasses import dataclass

from .base import ContractValidationResult, DictBackedContract, ValidationIssue


@dataclass(frozen=True)
class AssemblyManifestContract(DictBackedContract):
    required_fields = ("segments", "output_path")

    @property
    def segments(self) -> list[str]:
        segments = self.data.get("segments") or []
        return [str(segment) for segment in segments] if isinstance(segments, list) else []

    @property
    def output_path(self) -> str:
        return str(self.data.get("output_path") or "")

    def validate(self) -> ContractValidationResult:
        result = super().validate()
        if not isinstance(self.data.get("segments"), list):
            result = result.with_issue(
                ValidationIssue("invalid_segments", "Assembly segments must be a list.", "segments")
            )
        return result
