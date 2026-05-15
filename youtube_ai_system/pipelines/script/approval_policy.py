"""Script approval policy extracted from the legacy script service."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from ...models.repository import ProjectRepository
from ...services.financial_governance import narrative_progression_report, repetition_report
from ...services.visual_scene_normalizer import KNOWN_MECHANISMS
from .constants import (
    BODY_MIN_WORDS,
    DEFAULT_TARGET_DURATION_MINUTES,
    DUPLICATE_SCENE_SIMILARITY,
    HOOK_MIN_WORDS,
    MIN_BODY_SCENES_FOR_LONG_FORM,
    OUTRO_MIN_WORDS,
    TOTAL_WORD_APPROVAL_TOLERANCE_MIN_WORDS,
    TOTAL_WORD_APPROVAL_TOLERANCE_RATIO,
)
from .hook_validation import HookValidator
from .scene_rows import ScriptSceneRowMapper


class ScriptApprovalPolicy:
    def __init__(
        self,
        *,
        repo: ProjectRepository,
        hook_validator: HookValidator,
        scene_row_mapper: ScriptSceneRowMapper,
    ) -> None:
        self.repo = repo
        self.hook_validator = hook_validator
        self.scene_row_mapper = scene_row_mapper

    def validate_hook(self, hook: dict[str, Any]) -> list[str]:
        return self.hook_validator.validate(hook)

    def approval_errors(self, script_version: dict[str, Any], payload: dict[str, Any]) -> list[str]:
        errors = self.validate_hook(payload["hook"])
        ai_generated_at = script_version.get("ai_generated_at")
        user_edited_at = script_version.get("user_edited_at")
        if not user_edited_at:
            errors.append("You must edit the script before approval.")
        elif user_edited_at <= ai_generated_at:
            errors.append("User edits must happen after the AI draft is generated.")
        body_scenes = [scene for scene in payload["scenes"] if scene.get("kind", "body") == "body"]
        if not body_scenes:
            errors.append("At least one body scene is required.")
        errors.extend(self.validate_body_scene_count(script_version, body_scenes))
        errors.extend(self.validate_long_form_depth(script_version, payload, body_scenes))
        errors.extend(self.validate_visual_scene_contract(payload, body_scenes))
        errors.extend(self.validate_duplicate_body_scenes(body_scenes))
        errors.extend(self.validate_script_governance(body_scenes))
        return errors

    def validate_body_scene_count(
        self,
        script_version: dict[str, Any],
        body_scenes: list[dict[str, Any]],
    ) -> list[str]:
        project_id = script_version.get("video_project_id")
        if not project_id:
            return []
        project = self.repo.get_project(int(project_id))
        target_minutes = int(project.get("target_duration_minutes") or DEFAULT_TARGET_DURATION_MINUTES)
        if target_minutes >= DEFAULT_TARGET_DURATION_MINUTES and len(body_scenes) < MIN_BODY_SCENES_FOR_LONG_FORM:
            return [
                (
                    f"Target duration is {target_minutes} minutes, but the script has only "
                    f"{len(body_scenes)} body scenes. Add at least {MIN_BODY_SCENES_FOR_LONG_FORM} body scenes before approval."
                )
            ]
        return []

    def validate_long_form_depth(
        self,
        script_version: dict[str, Any],
        payload: dict[str, Any],
        body_scenes: list[dict[str, Any]],
    ) -> list[str]:
        project_id = script_version.get("video_project_id")
        if not project_id:
            return []
        project = self.repo.get_project(int(project_id))
        target_minutes = int(project.get("target_duration_minutes") or DEFAULT_TARGET_DURATION_MINUTES)
        if target_minutes < DEFAULT_TARGET_DURATION_MINUTES:
            return []

        errors: list[str] = []
        for index, scene in enumerate(body_scenes, start=1):
            word_count = self.word_count(str(scene.get("narration") or ""))
            if word_count < BODY_MIN_WORDS:
                errors.append(
                    (
                        f"Body scene {index} is too short for a professional {target_minutes}-minute video: "
                        f"{word_count} words. Minimum: {BODY_MIN_WORDS} words."
                    )
                )
            sentence_count = self.sentence_count(str(scene.get("narration") or ""))
            if sentence_count < 8:
                errors.append(
                    (
                        f"Body scene {index} has only {sentence_count} spoken sentences. "
                        "Use 8-12 short sentences with setup, example, mechanism, consequence, and transition."
                    )
                )

        total_words = self.payload_word_count(payload)
        minimum_total = self.minimum_total_words_for_target(target_minutes)
        minimum_total_for_approval = self.minimum_total_words_for_approval(target_minutes)
        if total_words < minimum_total_for_approval:
            errors.append(
                (
                    f"Target duration is {target_minutes} minutes, but the script has only "
                    f"{total_words} spoken words. Minimum for approval: {minimum_total} words."
                )
            )
        return errors

    def validate_visual_scene_contract(
        self,
        payload: dict[str, Any],
        body_scenes: list[dict[str, Any]],
    ) -> list[str]:
        errors: list[str] = []
        for index, scene in enumerate(body_scenes, start=1):
            narration = str(scene.get("narration") or "")
            visual_scene = self.visual_scene_for_row(payload, scene, index)
            if not visual_scene:
                errors.append(f"Body scene {index} is missing visual planning fields.")
                continue

            mechanism = str(visual_scene.get("mechanism") or "").strip()
            if mechanism not in KNOWN_MECHANISMS:
                errors.append(
                    (
                        f"Body scene {index} has invalid visual mechanism {mechanism!r}. "
                        "Choose one supported finance mechanism."
                    )
                )

            visual_intent = str(visual_scene.get("visual_intent") or "").strip()
            if not visual_intent:
                errors.append(f"Body scene {index} is missing visual_intent.")

            visual_beats = visual_scene.get("visual_beats") or []
            if not isinstance(visual_beats, list) or len([beat for beat in visual_beats if str(beat).strip()]) < 2:
                errors.append(f"Body scene {index} needs at least 2 visual_beats.")

            spoken_numbers = self.number_tokens(narration)
            for raw_number in visual_scene.get("numbers") or []:
                requested_tokens = self.number_tokens(str(raw_number))
                if requested_tokens and not requested_tokens.issubset(spoken_numbers):
                    errors.append(
                        (
                            f"Body scene {index} visual numbers include {raw_number!r}, "
                            "but that number is not spoken in the narration."
                        )
                    )
        return errors

    def payload_word_count(self, payload: dict[str, Any]) -> int:
        texts = [
            str((payload.get("hook") or {}).get("narration") or ""),
            *[str(scene.get("narration") or "") for scene in payload.get("scenes") or []],
            str((payload.get("outro") or {}).get("narration") or ""),
        ]
        return sum(self.word_count(text) for text in texts)

    def minimum_total_words_for_target(self, target_minutes: int) -> int:
        body_scene_count = max(MIN_BODY_SCENES_FOR_LONG_FORM, int(target_minutes))
        return body_scene_count * BODY_MIN_WORDS + HOOK_MIN_WORDS + OUTRO_MIN_WORDS

    def minimum_total_words_for_approval(self, target_minutes: int) -> int:
        target = self.minimum_total_words_for_target(target_minutes)
        tolerance = max(
            TOTAL_WORD_APPROVAL_TOLERANCE_MIN_WORDS,
            round(target * TOTAL_WORD_APPROVAL_TOLERANCE_RATIO),
        )
        return max(0, target - tolerance)

    def word_count(self, text: str) -> int:
        return len(re.findall(r"[A-Za-z0-9₹%]+(?:[.,][A-Za-z0-9]+)*", text))

    def sentence_count(self, text: str) -> int:
        return len([part for part in re.split(r"(?<=[.!?])\s+", str(text or "").strip()) if part.strip()])

    def number_tokens(self, text: str) -> set[str]:
        tokens: set[str] = set()
        for match in re.finditer(r"\d[\d,]*(?:\.\d+)?", str(text or "")):
            token = match.group(0).replace(",", "")
            if token.endswith(".0"):
                token = token[:-2]
            if token:
                tokens.add(token)
        return tokens

    def validate_duplicate_body_scenes(self, body_scenes: list[dict[str, Any]]) -> list[str]:
        errors: list[str] = []
        normalized = [self.duplicate_signature(str(scene.get("narration") or "")) for scene in body_scenes]
        for left_index, left_text in enumerate(normalized):
            if not left_text:
                continue
            for right_index in range(left_index + 1, len(normalized)):
                right_text = normalized[right_index]
                if not right_text:
                    continue
                similarity = SequenceMatcher(None, left_text, right_text).ratio()
                if similarity >= DUPLICATE_SCENE_SIMILARITY:
                    errors.append(
                        (
                            f"Body scene {left_index + 1} and body scene {right_index + 1} are too similar "
                            f"({similarity:.0%} match). Rewrite or remove the duplicate before approval."
                        )
                    )
        return errors

    def validate_script_governance(self, body_scenes: list[dict[str, Any]]) -> list[str]:
        report = repetition_report(body_scenes)
        errors: list[str] = []
        for item in report.get("repeated_phrases") or []:
            if int(item.get("count") or 0) >= 3:
                errors.append(
                    (
                        f"Repeated narration theme {item.get('phrase')!r} appears in "
                        f"{item.get('count')} body scenes. Rewrite repeated philosophy before approval."
                    )
                )
        for leak in report.get("meta_visual_leaks") or []:
            errors.append(
                (
                    f"Body scene {leak.get('scene_index')} contains meta-visual narration "
                    f"{leak.get('phrase')!r}. Keep narration spoken-only."
                )
            )
        return errors

    def duplicate_signature(self, narration: str) -> str:
        text = narration.lower()
        text = re.sub(r"₹\s*", "rs ", text)
        text = re.sub(r"[^\w\s%]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def visual_scene_for_row(self, payload: dict[str, Any], scene: dict[str, Any], index: int) -> dict[str, Any]:
        return self.scene_row_mapper.visual_scene_for_row(payload, scene, index)
