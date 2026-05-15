"""Script contract wrappers compatible with stored script JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .adapters import narration_from_payload
from .base import ContractValidationResult, ValidationIssue


@dataclass(frozen=True)
class ScriptSceneContract:
    scene_index: int | None = None
    kind: str = "body"
    title: str = ""
    narration: str = ""
    visual: str = ""
    visual_intent: str = ""
    visual_beats: tuple[Any, ...] = ()
    numbers: tuple[str, ...] = ()
    emotion: str = ""
    mechanism: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScriptSceneContract":
        return cls(
            scene_index=payload.get("scene_index"),
            kind=str(payload.get("kind") or "body"),
            title=str(payload.get("title") or payload.get("heading") or ""),
            narration=str(payload.get("narration") or payload.get("voiceover") or payload.get("text") or ""),
            visual=str(payload.get("visual") or payload.get("visual_description") or ""),
            visual_intent=str(payload.get("visual_intent") or ""),
            visual_beats=tuple(payload.get("visual_beats") or ()),
            numbers=tuple(str(number) for number in (payload.get("numbers") or ())),
            emotion=str(payload.get("emotion") or ""),
            mechanism=str(payload.get("mechanism") or ""),
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data.update(
            {
                "kind": self.kind,
                "narration": self.narration,
            }
        )
        if self.scene_index is not None:
            data["scene_index"] = self.scene_index
        if self.title:
            data["title"] = self.title
        if self.visual:
            data["visual"] = self.visual
        if self.visual_intent:
            data["visual_intent"] = self.visual_intent
        if self.visual_beats:
            data["visual_beats"] = list(self.visual_beats)
        if self.numbers:
            data["numbers"] = list(self.numbers)
        if self.emotion:
            data["emotion"] = self.emotion
        if self.mechanism:
            data["mechanism"] = self.mechanism
        return data


@dataclass(frozen=True)
class ScriptDraftContract:
    hook: dict[str, Any] = field(default_factory=dict)
    scenes: tuple[ScriptSceneContract, ...] = ()
    outro: dict[str, Any] = field(default_factory=dict)
    titles: tuple[str, ...] = ()
    description: str = ""
    tags: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScriptDraftContract":
        raw_scenes = payload.get("scenes") or []
        hook = payload.get("hook") if isinstance(payload.get("hook"), dict) else {"narration": payload.get("hook") or ""}
        outro = payload.get("outro") if isinstance(payload.get("outro"), dict) else {"narration": payload.get("outro") or ""}
        return cls(
            hook=dict(hook),
            scenes=tuple(ScriptSceneContract.from_dict(scene) for scene in raw_scenes if isinstance(scene, dict)),
            outro=dict(outro),
            titles=tuple(str(title) for title in (payload.get("titles") or payload.get("suggested_titles") or ())),
            description=str(payload.get("description") or payload.get("suggested_description") or ""),
            tags=tuple(str(tag) for tag in (payload.get("tags") or ())),
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data.update(
            {
                "hook": dict(self.hook),
                "scenes": [scene.to_dict() for scene in self.scenes],
                "outro": dict(self.outro),
            }
        )
        if self.titles:
            data["titles"] = list(self.titles)
        if self.description:
            data["description"] = self.description
        if self.tags:
            data["tags"] = list(self.tags)
        return data

    @property
    def hook_narration(self) -> str:
        return narration_from_payload(self.hook)

    @property
    def outro_narration(self) -> str:
        return narration_from_payload(self.outro)

    def validate(self) -> ContractValidationResult:
        result = ContractValidationResult()
        if not self.hook_narration:
            result = result.with_issue(ValidationIssue("missing_hook", "Script hook is missing.", "hook"))
        if not self.scenes:
            result = result.with_issue(ValidationIssue("missing_scenes", "Script scenes are missing.", "scenes"))
        if not self.outro_narration:
            result = result.with_issue(ValidationIssue("missing_outro", "Script outro is missing.", "outro"))
        return result
