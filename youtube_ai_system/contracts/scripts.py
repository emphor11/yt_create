"""Script contract wrappers compatible with stored script JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import ContractValidationResult, ValidationIssue


@dataclass(frozen=True)
class ScriptSceneContract:
    title: str = ""
    narration: str = ""
    visual: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScriptSceneContract":
        return cls(
            title=str(payload.get("title") or payload.get("heading") or ""),
            narration=str(payload.get("narration") or payload.get("voiceover") or payload.get("text") or ""),
            visual=str(payload.get("visual") or payload.get("visual_description") or ""),
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data.update({"title": self.title, "narration": self.narration, "visual": self.visual})
        return data


@dataclass(frozen=True)
class ScriptDraftContract:
    hook: str = ""
    scenes: tuple[ScriptSceneContract, ...] = ()
    outro: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScriptDraftContract":
        raw_scenes = payload.get("scenes") or []
        return cls(
            hook=str(payload.get("hook") or ""),
            scenes=tuple(ScriptSceneContract.from_dict(scene) for scene in raw_scenes if isinstance(scene, dict)),
            outro=str(payload.get("outro") or ""),
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data.update(
            {
                "hook": self.hook,
                "scenes": [scene.to_dict() for scene in self.scenes],
                "outro": self.outro,
            }
        )
        return data

    def validate(self) -> ContractValidationResult:
        result = ContractValidationResult()
        if not self.hook:
            result = result.with_issue(ValidationIssue("missing_hook", "Script hook is missing.", "hook"))
        if not self.scenes:
            result = result.with_issue(ValidationIssue("missing_scenes", "Script scenes are missing.", "scenes"))
        return result

