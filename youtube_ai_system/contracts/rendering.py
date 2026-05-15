"""Render specification contract wrappers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import ContractValidationResult, ValidationIssue


@dataclass(frozen=True)
class RenderSpec:
    composition: str
    props: dict[str, Any]
    duration_sec: float
    source: str
    output_ext: str = ".mp4"
    source_asset_path: Path | None = None


@dataclass(frozen=True)
class RenderSpecContract:
    composition: str = ""
    props: dict[str, Any] = field(default_factory=dict)
    duration_frames: int | None = None
    duration_sec: float | None = None
    fps: int | None = None
    source: str = ""
    output_ext: str = ".mp4"
    source_asset_path: str = ""
    output_path: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RenderSpecContract":
        return cls(
            composition=str(payload.get("composition") or payload.get("composition_id") or ""),
            props=dict(payload.get("props") or payload.get("input_props") or {}),
            duration_frames=payload.get("duration_frames"),
            duration_sec=payload.get("duration_sec"),
            fps=payload.get("fps"),
            source=str(payload.get("source") or ""),
            output_ext=str(payload.get("output_ext") or ".mp4"),
            source_asset_path=str(payload.get("source_asset_path") or ""),
            output_path=str(payload.get("output_path") or ""),
            raw=dict(payload),
        )

    @classmethod
    def from_render_spec(cls, spec: Any) -> "RenderSpecContract":
        source_asset_path = getattr(spec, "source_asset_path", None)
        return cls(
            composition=str(getattr(spec, "composition", "")),
            props=dict(getattr(spec, "props", {}) or {}),
            duration_sec=getattr(spec, "duration_sec", None),
            source=str(getattr(spec, "source", "")),
            output_ext=str(getattr(spec, "output_ext", ".mp4")),
            source_asset_path=str(source_asset_path or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data.update(
            {
                "composition": self.composition,
                "props": dict(self.props),
                "duration_frames": self.duration_frames,
                "duration_sec": self.duration_sec,
                "fps": self.fps,
                "source": self.source,
                "output_ext": self.output_ext,
                "source_asset_path": self.source_asset_path,
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
        if self.duration_sec is not None and self.duration_sec <= 0:
            result = result.with_issue(
                ValidationIssue("invalid_duration", "Render duration must be positive.", "duration_sec")
            )
        if self.duration_frames is not None and self.duration_frames <= 0:
            result = result.with_issue(
                ValidationIssue("invalid_duration_frames", "Render frame duration must be positive.", "duration_frames")
            )
        return result
