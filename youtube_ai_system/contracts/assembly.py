from __future__ import annotations

from dataclasses import dataclass

from .base import DictBackedContract


@dataclass(frozen=True)
class AssemblyManifestContract(DictBackedContract):
    required_fields = ("segments", "output_path")

    @property
    def segments(self) -> list[str]:
        segments = self.data.get("segments") or []
        return [str(segment) for segment in segments] if isinstance(segments, list) else []

