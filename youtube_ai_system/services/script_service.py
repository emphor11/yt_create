from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib import error

from flask import current_app

from ..contracts.scripts import SCRIPT_BRIEF_EMOTIONAL_DIRECTIONS, SCRIPT_BRIEF_MECHANISMS, ScriptBriefContract
from ..models.repository import ProjectRepository, utcnow
from ..pipelines.script import (
    GeminiScriptGenerator,
    GroqScriptGenerator,
    HookValidator,
    NEGATIVE_IMPLICATION_WORDS,
    PEOPLE_GROUP_WORDS,
    ScriptApprovalPolicy,
    ScriptPromptBuilder,
    ScriptSceneRowMapper,
    TENSION_KEYWORDS,
    VALID_TENSION_TYPES,
)
from .narration_refiner import refine as refine_narration
from .run_log import RunLogger
from .script_scene_refiner import ScriptSceneRefiner
from .scene_debug import SceneDebugStore, SceneDebugTrace, debug_video_pipeline_enabled
from .financial_governance import narrative_progression_report, repetition_report
from .story_pipeline import StoryPipeline
from .visual_scene_normalizer import visual_script_prompt_contract

class ScriptService:
    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.logger = RunLogger()
        self.story_pipeline = StoryPipeline(logger=self.logger)
        self.scene_refiner = ScriptSceneRefiner()
        self.hook_validator = HookValidator(
            tension_keywords=TENSION_KEYWORDS,
            people_group_words=PEOPLE_GROUP_WORDS,
            negative_implication_words=NEGATIVE_IMPLICATION_WORDS,
        )
        self.scene_row_mapper = ScriptSceneRowMapper()
        self.approval_policy = ScriptApprovalPolicy(
            repo=self.repo,
            hook_validator=self.hook_validator,
            scene_row_mapper=self.scene_row_mapper,
        )
        self.groq_generator = GroqScriptGenerator(self.logger)
        self.gemini_generator = GeminiScriptGenerator(self.logger)
        self.prompt_builder = ScriptPromptBuilder(visual_script_prompt_contract)

    def generate_script(
        self,
        project_id: int,
        topic: str,
        angle: str,
        target_duration_minutes: int | None = None,
        niche: str | None = None,
        tone: str | None = None,
    ) -> int:
        brief_prompt = self._build_brief_prompt(topic, angle, target_duration_minutes, niche, tone)
        script_brief = self._generate_script_brief(topic, angle, brief_prompt)
        prompt = self._build_prompt(topic, angle, target_duration_minutes, niche, tone, script_brief)
        payload, source = self._generate_payload(project_id, topic, angle, prompt, script_brief=script_brief)
        source_prompt = f"{brief_prompt}\n\n--- FULL SCRIPT PROMPT ---\n\n{prompt}"
        script_version_id = self.repo.create_script_version(
            project_id=project_id,
            hook_json=payload["hook"],
            outro_json=payload["outro"],
            titles_json=payload.get("titles", []),
            description_text=payload.get("description", ""),
            tags_json=payload.get("tags", []),
            full_script_json=payload,
            source_prompt=source_prompt,
        )
        self.logger.log(
            "script_generation",
            "completed",
            f"Generated script draft using {source}.",
            project_id,
        )
        return script_version_id

    def save_script_edits(
        self,
        script_version_id: int,
        payload: dict[str, Any],
    ) -> None:
        project_id = self.repo.get_script_version(script_version_id)["video_project_id"]
        project = self.repo.get_project(project_id)
        normalized = self._normalize_payload(
            payload,
            str(project.get("topic") or ""),
            str(project.get("angle") or ""),
            project_id=project_id,
        )
        script_brief = normalized.get("meta", {}).get("script_brief")
        if isinstance(script_brief, dict) and script_brief:
            normalized = self._apply_script_brief_repairs(
                normalized,
                script_brief,
                topic=str(project.get("topic") or ""),
                angle=str(project.get("angle") or ""),
                validate=False,
            )
        self.repo.update_script_version(
            script_version_id,
            hook_json=json.dumps(normalized["hook"]),
            outro_json=json.dumps(normalized["outro"]),
            titles_json=json.dumps(normalized.get("titles", [])),
            description_text=normalized.get("description", ""),
            tags_json=json.dumps(normalized.get("tags", [])),
            full_script_json=json.dumps(normalized),
            user_edited_at=utcnow(),
        )
        self.logger.log("script_edit", "completed", "Saved manual script edits.", project_id)

    def load_script_payload(self, script_version: dict[str, Any]) -> dict[str, Any]:
        raw = script_version["full_script_json"]
        return json.loads(raw) if isinstance(raw, str) else raw

    def validate_hook(self, hook: dict[str, Any]) -> list[str]:
        return self.approval_policy.validate_hook(hook)

    def approval_ready(self, script_version: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any]]:
        payload = self.load_script_payload(script_version)
        errors = self.approval_policy.approval_errors(script_version, payload)
        return (not errors, errors, payload)

    def _validate_body_scene_count(self, script_version: dict[str, Any], body_scenes: list[dict[str, Any]]) -> list[str]:
        return self.approval_policy.validate_body_scene_count(script_version, body_scenes)

    def _validate_long_form_depth(
        self,
        script_version: dict[str, Any],
        payload: dict[str, Any],
        body_scenes: list[dict[str, Any]],
    ) -> list[str]:
        return self.approval_policy.validate_long_form_depth(script_version, payload, body_scenes)

    def _validate_visual_scene_contract(
        self,
        payload: dict[str, Any],
        body_scenes: list[dict[str, Any]],
    ) -> list[str]:
        return self.approval_policy.validate_visual_scene_contract(payload, body_scenes)

    def _payload_word_count(self, payload: dict[str, Any]) -> int:
        return self.approval_policy.payload_word_count(payload)

    def _minimum_total_words_for_target(self, target_minutes: int) -> int:
        return self.approval_policy.minimum_total_words_for_target(target_minutes)

    def _minimum_total_words_for_approval(self, target_minutes: int) -> int:
        return self.approval_policy.minimum_total_words_for_approval(target_minutes)

    def _word_count(self, text: str) -> int:
        return self.approval_policy.word_count(text)

    def _sentence_count(self, text: str) -> int:
        return self.approval_policy.sentence_count(text)

    def _number_tokens(self, text: str) -> set[str]:
        return self.approval_policy.number_tokens(text)

    def _validate_duplicate_body_scenes(self, body_scenes: list[dict[str, Any]]) -> list[str]:
        return self.approval_policy.validate_duplicate_body_scenes(body_scenes)

    def _validate_script_governance(self, body_scenes: list[dict[str, Any]]) -> list[str]:
        return self.approval_policy.validate_script_governance(body_scenes)

    def _duplicate_signature(self, narration: str) -> str:
        return self.approval_policy.duplicate_signature(narration)

    def scene_rows_from_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return self.scene_row_mapper.scene_rows_from_payload(payload)

    def _visual_scene_for_row(self, payload: dict[str, Any], scene: dict[str, Any], index: int) -> dict[str, Any]:
        return self.scene_row_mapper.visual_scene_for_row(payload, scene, index)

    def _generate_payload(
        self,
        project_id_or_topic: int | str | None,
        topic_or_angle: str,
        angle_or_prompt: str,
        prompt: str | None = None,
        script_brief: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str]:
        if prompt is None:
            project_id = None
            topic = str(project_id_or_topic or "")
            angle = topic_or_angle
            prompt = angle_or_prompt
        else:
            project_id = int(project_id_or_topic) if project_id_or_topic is not None else None
            topic = topic_or_angle
            angle = angle_or_prompt
        provider = current_app.config.get("LLM_PROVIDER", "auto")
        self.logger.log(
            "script_generation",
            "running",
            (
                f"Script generation provider selection: provider={provider}, "
                f"groq_key={'yes' if bool(current_app.config.get('GROQ_API_KEY')) else 'no'}, "
                f"gemini_key={'yes' if bool(current_app.config.get('GEMINI_API_KEY')) else 'no'}."
            ),
        )

        if provider == "demo":
            payload = self._demo_script(topic, angle)
            if script_brief:
                payload.setdefault("meta", {})["script_brief"] = script_brief
            payload = self._normalize_payload(payload, topic, angle, project_id=project_id)
            payload.setdefault("meta", {})["source"] = "demo"
            if script_brief:
                payload.setdefault("meta", {})["script_brief"] = script_brief
                payload.setdefault("meta", {})["script_brief_compliance"] = self._script_brief_compliance_report(
                    payload,
                    script_brief,
                    topic=topic,
                    angle=angle,
                )
            self.logger.log("script_generation", "completed", "Script source selected: demo.")
            return payload, "demo"

        providers = self._script_provider_order(provider)
        if not providers:
            raise ValueError("Script generation requires Groq or Gemini, but no live LLM API key is configured.")
        last_exc: Exception | None = None
        for provider_name in providers:
            try:
                api_key = self._api_key_for_provider(provider_name)
                payload = self._call_script_provider(provider_name, topic, angle, prompt, api_key)
                if script_brief:
                    payload.setdefault("meta", {})["script_brief"] = script_brief
                payload = self._normalize_payload(payload, topic, angle, project_id=project_id)
                if script_brief:
                    payload = self._apply_script_brief_repairs(
                        payload,
                        script_brief,
                        topic=topic,
                        angle=angle,
                        validate=True,
                    )
                source = self._source_for_provider(provider_name)
                payload.setdefault("meta", {})["source"] = source
                self.logger.log("script_generation", "completed", f"Script source selected: {source}.")
                return payload, self._source_label_for_provider(provider_name)
            except (error.URLError, ValueError, KeyError, json.JSONDecodeError) as exc:
                last_exc = exc
                self.logger.log(
                    "script_generation",
                    "failed",
                    f"{provider_name.title()} generation failed ({exc}).",
                )
                if provider == "auto" and provider_name == "groq" and self._is_rate_limit_error(exc):
                    self.logger.log(
                        "script_generation",
                        "running",
                        "Groq rate limit reached; trying Gemini fallback.",
                    )
                    continue
                raise
        if last_exc:
            self.logger.log(
                "script_generation",
                "failed",
                f"Live script generation failed ({last_exc}).",
            )
            raise last_exc
        raise ValueError("Script generation requires Groq or Gemini, but no live LLM API key is configured.")

    def _build_prompt(
        self,
        topic: str,
        angle: str,
        target_duration_minutes: int | None = None,
        niche: str | None = None,
        tone: str | None = None,
        script_brief: dict[str, Any] | None = None,
    ) -> str:
        return self.prompt_builder.build(
            config=current_app.config,
            topic=topic,
            angle=angle,
            target_duration_minutes=target_duration_minutes,
            niche=niche,
            tone=tone,
            script_brief=script_brief,
        )

    def _build_brief_prompt(
        self,
        topic: str,
        angle: str,
        target_duration_minutes: int | None = None,
        niche: str | None = None,
        tone: str | None = None,
    ) -> str:
        return self.prompt_builder.build_brief_prompt(
            config=current_app.config,
            topic=topic,
            angle=angle,
            target_duration_minutes=target_duration_minutes,
            niche=niche,
            tone=tone,
        )

    def _generate_script_brief(self, topic: str, angle: str, prompt: str) -> dict[str, Any]:
        provider = current_app.config.get("LLM_PROVIDER", "auto")
        self.logger.log(
            "script_brief_generation",
            "running",
            (
                f"ScriptBrief provider selection: provider={provider}, "
                f"groq_key={'yes' if bool(current_app.config.get('GROQ_API_KEY')) else 'no'}, "
                f"gemini_key={'yes' if bool(current_app.config.get('GEMINI_API_KEY')) else 'no'}."
            ),
        )
        if provider == "demo":
            brief = self._demo_script_brief(topic, angle)
            self.logger.log("script_brief_generation", "completed", "Generated demo ScriptBrief contract.")
            return brief
        providers = self._script_provider_order(provider)
        if not providers:
            raise ValueError("ScriptBrief generation requires Groq or Gemini, but no live LLM API key is configured.")
        last_exc: Exception | None = None
        for provider_name in providers:
            try:
                payload = self._call_script_brief_provider(provider_name, prompt, self._api_key_for_provider(provider_name))
                payload = self._repair_script_brief_contract(payload)
                brief = ScriptBriefContract.from_dict(payload)
                validation = brief.validate()
                if not validation.passed:
                    messages = "; ".join(issue.message for issue in validation.errors)
                    raise ValueError(f"ScriptBrief generation failed validation: {messages}")
                topic_errors = self._validate_script_brief_topic_alignment(topic, angle, brief.to_dict())
                if topic_errors:
                    raise ValueError(f"ScriptBrief topic alignment failed: {'; '.join(topic_errors)}")
                self.logger.log(
                    "script_brief_generation",
                    "completed",
                    f"Generated ScriptBrief contract with {provider_name}.",
                )
                return brief.to_dict()
            except (error.URLError, ValueError, KeyError, json.JSONDecodeError) as exc:
                last_exc = exc
                self.logger.log(
                    "script_brief_generation",
                    "failed",
                    f"{provider_name.title()} ScriptBrief generation failed ({exc}).",
                )
                if provider == "auto" and provider_name == "groq" and self._is_rate_limit_error(exc):
                    self.logger.log(
                        "script_brief_generation",
                        "running",
                        "Groq rate limit reached; trying Gemini fallback.",
                    )
                    continue
                raise
        if last_exc:
            raise last_exc
        raise ValueError("ScriptBrief generation requires Groq or Gemini, but no live LLM API key is configured.")

    def _repair_script_brief_contract(self, payload: dict[str, Any]) -> dict[str, Any]:
        repaired = dict(payload or {})
        selected_format = str(repaired.get("selected_format") or "")
        recurring_example = str(repaired.get("recurring_example") or "the recurring money example")
        forbids_budgeting = self._brief_forbids_budgeting(repaired)
        changed = False
        allowed_mechanisms = [
            mechanism
            for mechanism in (
                self._normalize_script_brief_mechanism_value(str(item))
                for item in (repaired.get("allowed_mechanisms") or [])
            )
            if mechanism in SCRIPT_BRIEF_MECHANISMS
        ]
        if allowed_mechanisms and allowed_mechanisms != list(repaired.get("allowed_mechanisms") or []):
            repaired["allowed_mechanisms"] = allowed_mechanisms
            changed = True
        scene_map: list[dict[str, Any]] = []
        for scene_offset, item in enumerate(repaired.get("scene_function_map") or []):
            if not isinstance(item, dict):
                continue
            updated = dict(item)
            mechanism = self._normalize_script_brief_mechanism_value(str(updated.get("mechanism") or ""))
            if mechanism != str(updated.get("mechanism") or "") and mechanism in SCRIPT_BRIEF_MECHANISMS:
                updated["mechanism"] = mechanism
                changed = True
            if mechanism not in SCRIPT_BRIEF_MECHANISMS:
                if mechanism in SCRIPT_BRIEF_EMOTIONAL_DIRECTIONS and str(updated.get("emotional_direction") or "") not in SCRIPT_BRIEF_EMOTIONAL_DIRECTIONS:
                    updated["emotional_direction"] = mechanism
                inferred = self._infer_scene_mechanism_from_brief_entry(updated, allowed_mechanisms, scene_offset)
                if inferred:
                    updated["mechanism"] = inferred
                    changed = True
            function = self._normalized_phrase(str(updated.get("function") or ""))
            should_repair = selected_format != "action_plan" and self._is_generic_body_advice_function(function)
            should_repair = should_repair or (forbids_budgeting and self._function_has_budgeting_drift(function))
            if should_repair:
                mechanism = str(updated.get("mechanism") or "the selected mechanism").replace("_", " ")
                updated["function"] = (
                    f"Expose the {mechanism} consequence through the recurring example: {recurring_example}."
                )
                changed = True
            scene_map.append(updated)
        if scene_map:
            repaired["scene_function_map"] = scene_map
        if changed:
            self.logger.log(
                "script_brief_generation",
                "running",
                "Repaired generic ScriptBrief body scene functions before validation.",
            )
        return repaired

    def _normalize_script_brief_mechanism_value(self, value: str) -> str:
        normalized = self._normalized_phrase(value).replace(" ", "_")
        aliases = {
            "anchor": "anchoring",
            "anchoring_bias": "anchoring",
            "price_anchor": "price_anchoring",
            "payment_pain": "payment_pain_reduction",
            "monthly_payment_pain": "payment_pain_reduction",
            "affordability": "affordability_illusion",
            "illusion_of_affordability": "affordability_illusion",
            "cashflow_squeeze": "cash_flow_squeeze",
            "cash_flow": "cash_flow_squeeze",
            "future_obligation": "delayed_consequence",
            "lockin": "lock_in",
            "subscription_lockin": "subscription_lock_in",
        }
        return aliases.get(normalized, normalized)

    def _infer_scene_mechanism_from_brief_entry(
        self,
        scene_entry: dict[str, Any],
        allowed_mechanisms: list[str],
        scene_offset: int,
    ) -> str:
        if not allowed_mechanisms:
            return ""
        haystack = " ".join(
            self._normalized_phrase(str(scene_entry.get(field) or ""))
            for field in ("function", "visual_intent", "description")
        )
        for mechanism in allowed_mechanisms:
            mechanism_phrase = mechanism.replace("_", " ")
            if mechanism_phrase in haystack:
                return mechanism
        if scene_offset < len(allowed_mechanisms):
            return allowed_mechanisms[scene_offset]
        return allowed_mechanisms[-1]

    def _brief_forbids_budgeting(self, script_brief: dict[str, Any]) -> bool:
        forbidden = " ".join(self._normalized_phrase(str(item)) for item in script_brief.get("forbidden_drift") or [])
        return "general budgeting advice" in forbidden or self._function_has_budgeting_drift(forbidden)

    def _is_generic_body_advice_function(self, normalized_function: str) -> bool:
        tokens = set(normalized_function.split())
        if tokens.intersection({"advice", "budgeting", "conclusion", "guidance", "reassess", "summarize", "summary", "takeaway", "takeaways"}):
            return True
        return any(
            phrase in normalized_function
            for phrase in (
                "avoid pitfalls",
                "call to action",
                "make informed decision",
                "make informed financial decision",
                "provide strategies",
                "discuss strategies",
            )
        )

    def _function_has_budgeting_drift(self, normalized_function: str) -> bool:
        return any(
            marker in normalized_function
            for marker in (
                "50 30 20",
                "budgeting",
                "set a budget",
                "spend less",
                "track expenses",
                "tracking expenses",
            )
        )

    def _script_provider_order(self, provider: str) -> list[str]:
        provider = str(provider or "auto").lower()
        if provider == "auto":
            providers: list[str] = []
            if current_app.config.get("GROQ_API_KEY"):
                providers.append("groq")
            if current_app.config.get("GEMINI_API_KEY"):
                providers.append("gemini")
            return providers
        if provider in {"groq", "gemini"}:
            api_key_name = "GROQ_API_KEY" if provider == "groq" else "GEMINI_API_KEY"
            if not current_app.config.get(api_key_name):
                raise ValueError(
                    f"{provider.title()} generation requires {api_key_name}, but it is not configured."
                )
            return [provider]
        raise ValueError(f"Unsupported LLM_PROVIDER={provider!r}. Use 'auto', 'groq', 'gemini', or 'demo'.")

    def _api_key_for_provider(self, provider: str) -> str:
        key_name = "GROQ_API_KEY" if provider == "groq" else "GEMINI_API_KEY"
        return str(current_app.config.get(key_name) or "")

    def _source_for_provider(self, provider: str) -> str:
        return "live_groq" if provider == "groq" else "live_gemini"

    def _source_label_for_provider(self, provider: str) -> str:
        return "live Groq API" if provider == "groq" else "live Gemini API"

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return "429" in message or "rate_limit" in message or "rate limit" in message or "too many requests" in message

    def _call_script_provider(
        self,
        provider: str,
        topic: str,
        angle: str,
        prompt: str,
        api_key: str,
    ) -> dict[str, Any]:
        if provider == "groq":
            return self._groq_script(topic, angle, prompt, api_key)
        if provider == "gemini":
            return self._gemini_script(topic, angle, prompt, api_key)
        raise ValueError(f"Unsupported script provider: {provider}")

    def _call_script_brief_provider(self, provider: str, prompt: str, api_key: str) -> dict[str, Any]:
        if provider == "groq":
            return self._groq_script_brief(prompt, api_key)
        if provider == "gemini":
            return self._gemini_script_brief(prompt, api_key)
        raise ValueError(f"Unsupported script provider: {provider}")

    def _groq_script(self, topic: str, angle: str, prompt: str, api_key: str) -> dict[str, Any]:
        return self.groq_generator.generate(
            topic=topic,
            angle=angle,
            prompt=prompt,
            api_key=api_key,
            config=current_app.config,
            sleep_func=time.sleep,
        )

    def _gemini_script(self, topic: str, angle: str, prompt: str, api_key: str) -> dict[str, Any]:
        return self.gemini_generator.generate(
            topic=topic,
            angle=angle,
            prompt=prompt,
            api_key=api_key,
            config=current_app.config,
            sleep_func=time.sleep,
        )

    def _groq_script_brief(self, prompt: str, api_key: str) -> dict[str, Any]:
        return self.groq_generator.generate_brief(
            prompt=prompt,
            api_key=api_key,
            config=current_app.config,
            sleep_func=time.sleep,
        )

    def _gemini_script_brief(self, prompt: str, api_key: str) -> dict[str, Any]:
        return self.gemini_generator.generate_brief(
            prompt=prompt,
            api_key=api_key,
            config=current_app.config,
            sleep_func=time.sleep,
        )

    def _groq_retry_wait_seconds(self, response: Any | None) -> float:
        return self.groq_generator.retry_wait_seconds(response)

    def _extract_json_payload(self, raw_text: str) -> dict[str, Any]:
        return self.groq_generator.extract_json_payload(raw_text)

    def _validate_payload_shape(self, payload: dict[str, Any]) -> None:
        required_top = {"hook", "scenes", "outro", "story_plan"}
        missing = required_top - set(payload)
        if missing:
            raise ValueError(f"Missing script fields: {sorted(missing)}")
        if not isinstance(payload["scenes"], list) or not payload["scenes"]:
            raise ValueError("Script must include at least one scene.")
        if not isinstance(payload["hook"], dict) or not payload["hook"].get("narration"):
            raise ValueError("Hook must be an object with narration.")
        if not isinstance(payload["outro"], dict) or not payload["outro"].get("narration"):
            raise ValueError("Outro must be an object with narration.")

    def _validate_script_against_brief(
        self,
        payload: dict[str, Any],
        script_brief: dict[str, Any],
        compliance: dict[str, Any] | None = None,
    ) -> None:
        brief = ScriptBriefContract.from_dict(script_brief)
        validation = brief.validate()
        if not validation.passed:
            messages = "; ".join(issue.message for issue in validation.errors)
            raise ValueError(f"ScriptBrief validation failed before script validation: {messages}")
        compliance = compliance or self._script_brief_compliance_report(payload, script_brief)
        errors = list(compliance.get("errors") or [])
        if errors:
            raise ValueError("Script does not satisfy ScriptBrief: " + "; ".join(errors))

    def _apply_script_brief_repairs(
        self,
        payload: dict[str, Any],
        script_brief: dict[str, Any],
        *,
        topic: str = "",
        angle: str = "",
        validate: bool = False,
    ) -> dict[str, Any]:
        payload.setdefault("meta", {})["script_brief"] = script_brief
        payload = self._repair_payload_for_script_brief(payload, script_brief)
        payload = self._refresh_derived_script_outputs(payload)
        compliance = self._script_brief_compliance_report(payload, script_brief, topic=topic, angle=angle)
        payload.setdefault("meta", {})["script_brief_compliance"] = compliance
        payload.setdefault("meta", {})["script_brief"] = script_brief
        if validate:
            self._validate_script_against_brief(payload, script_brief, compliance)
        return payload

    def _script_brief_compliance_report(
        self,
        payload: dict[str, Any],
        script_brief: dict[str, Any],
        *,
        topic: str = "",
        angle: str = "",
    ) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        brief = ScriptBriefContract.from_dict(script_brief)
        body_scenes = [scene for scene in payload.get("scenes") or [] if scene.get("kind", "body") == "body"]
        scene_map = [item.to_dict() for item in brief.scene_function_map]
        scene_count = {
            "expected": len(scene_map),
            "actual": len(body_scenes),
            "passed": len(body_scenes) == len(scene_map),
        }
        if len(body_scenes) != len(scene_map):
            errors.append(
                f"generated {len(body_scenes)} body scenes, but ScriptBrief requires {len(scene_map)} scene function entries"
            )

        mechanism_matches: list[dict[str, Any]] = []
        for index, (scene, map_item) in enumerate(zip(body_scenes, scene_map), start=1):
            expected = str(map_item.get("mechanism") or "").strip()
            actual = str(scene.get("mechanism") or "").strip()
            passed = bool(expected and actual == expected)
            mechanism_matches.append(
                {
                    "scene_index": index,
                    "expected": expected,
                    "actual": actual,
                    "passed": passed,
                }
            )
            if expected and actual != expected:
                errors.append(f"scene {index} mechanism {actual!r} does not match ScriptBrief mechanism {expected!r}")

        recurring_terms = self._recurring_example_terms(str(script_brief.get("recurring_example") or ""))
        hit_count = 0
        minimum_hits = min(len(body_scenes), 2) if body_scenes else 0
        if recurring_terms and body_scenes:
            for scene in body_scenes:
                narration = str(scene.get("narration") or "").lower()
                if any(term in narration for term in recurring_terms):
                    hit_count += 1
            if hit_count < minimum_hits:
                errors.append(
                    f"recurring example appears in {hit_count} body scenes; expected at least {minimum_hits}"
                )

        forbidden_hits = self._forbidden_drift_hits(payload, script_brief)
        for hit in forbidden_hits:
            errors.append(f"forbidden drift phrase appears in {hit['location']}: {hit['phrase']!r}")

        topic_alignment_errors = self._validate_script_brief_topic_alignment(topic, angle, script_brief) if topic or angle else []
        errors.extend(topic_alignment_errors)

        return {
            "passed": not errors,
            "errors": errors,
            "warnings": warnings,
            "scene_count": scene_count,
            "mechanism_matches": mechanism_matches,
            "recurring_example": {
                "terms": recurring_terms,
                "hit_count": hit_count,
                "minimum_hits": minimum_hits,
                "passed": hit_count >= minimum_hits,
            },
            "forbidden_drift": {
                "hits": forbidden_hits,
                "passed": not forbidden_hits,
            },
            "topic_alignment": {
                "passed": not topic_alignment_errors,
                "errors": topic_alignment_errors,
            },
        }

    def _repair_payload_for_script_brief(self, payload: dict[str, Any], script_brief: dict[str, Any]) -> dict[str, Any]:
        forbidden_hits = self._forbidden_drift_hits(payload, script_brief)
        if not forbidden_hits:
            return self._repair_weak_advisory_language(payload)
        repaired = dict(payload)
        scenes = [dict(scene) for scene in payload.get("scenes") or []]
        repaired["scenes"] = scenes
        hook = dict(payload.get("hook") or {})
        outro = dict(payload.get("outro") or {})
        repaired["hook"] = hook
        repaired["outro"] = outro
        replacement = self._script_brief_replacement_phrase(script_brief)
        by_location: dict[str, list[dict[str, str]]] = {}
        for hit in forbidden_hits:
            by_location.setdefault(str(hit.get("location") or ""), []).append(hit)
        for location, hits in by_location.items():
            target: dict[str, Any] | None = None
            if location == "hook":
                target = hook
            elif location == "outro":
                target = outro
            elif location.startswith("scene_"):
                try:
                    scene_index = int(location.split("_", 1)[1]) - 1
                except (IndexError, ValueError):
                    scene_index = -1
                if 0 <= scene_index < len(scenes):
                    target = scenes[scene_index]
            if not target:
                continue
            narration = str(target.get("narration") or "")
            for hit in hits:
                phrase = str(hit.get("phrase") or "")
                marker = str(hit.get("marker") or "")
                if phrase:
                    narration = self._replace_forbidden_phrase(narration, phrase, replacement)
                if marker:
                    narration = self._replace_forbidden_semantic_marker(narration, marker)
            target["narration"] = " ".join(narration.split())
        repaired.setdefault("meta", {}).setdefault("script_brief_repairs", []).append(
            {
                "kind": "forbidden_drift_replacement",
                "locations": sorted(by_location),
            }
        )
        return self._repair_weak_advisory_language(repaired)

    def _repair_weak_advisory_language(self, payload: dict[str, Any]) -> dict[str, Any]:
        replacements = (
            (r"\bmake informed financial decisions\b", "judge the full payment before saying yes"),
            (r"\bmake informed decisions\b", "judge the full cost before saying yes"),
            (r"\bachieve (?:your|our|their) financial goals\b", "keep the real cost visible"),
            (r"\buse them wisely\b", "make the full cost answer first"),
            (r"\bbe mindful of (?:your|our|their) finances\b", "notice what the payment locks up"),
            (r"\bbudget and plan (?:your|our|their) finances more effectively\b", "keep cash free for a specific reason"),
            (r"\bmake the most of (?:your|our|their) money\b", "keep liquidity available today"),
            (r"\blive a life of luxury and freedom\b", "buy comfort without pretending the obligation disappeared"),
            (r"\bliving a life of luxury and freedom\b", "buying comfort while the obligation keeps running"),
            (r"\bpeople must be careful\b", "the payment has to survive the full term"),
            (r"\bthey must consider the true cost\b", "the full cost has to stay visible"),
            (r"\bpeople must be aware of this mechanism\b", "the mechanism has to be visible before the EMI feels small"),
            (r"\bthey must not fool themselves\b", "the EMI cannot be allowed to become the whole decision"),
            (r"\bmonthly payments are just a mechanism\b", "monthly payments are a framing device"),
            (r"\bthey are not a substitute for financial discipline\b", "they are not a substitute for a full-cost check"),
            (r"\bdo not just look at the monthly payment\b", "do not stop at the monthly payment"),
            (r"\blook at the total cost\b", "make the total cost visible"),
            (r"\bdo not let the affordability illusion trap you\b", "do not let the smaller number hide the obligation"),
        )
        repaired = dict(payload)
        changed_locations: list[str] = []

        def repair_text(text: str) -> tuple[str, bool]:
            updated = str(text or "")
            changed = False
            for pattern, replacement in replacements:
                updated_next = re.sub(pattern, replacement, updated, flags=re.IGNORECASE)
                if updated_next != updated:
                    changed = True
                    updated = updated_next
            return " ".join(updated.split()), changed

        hook = dict(payload.get("hook") or {})
        hook_text, hook_changed = repair_text(str(hook.get("narration") or ""))
        if hook_changed:
            hook["narration"] = hook_text
            repaired["hook"] = hook
            changed_locations.append("hook")

        scenes: list[dict[str, Any]] = []
        for index, scene in enumerate(payload.get("scenes") or [], start=1):
            if not isinstance(scene, dict):
                continue
            updated_scene = dict(scene)
            narration, changed = repair_text(str(updated_scene.get("narration") or ""))
            if changed:
                updated_scene["narration"] = narration
                changed_locations.append(f"scene_{index}")
            scenes.append(updated_scene)
        if scenes:
            repaired["scenes"] = scenes

        outro = dict(payload.get("outro") or {})
        outro_text, outro_changed = repair_text(str(outro.get("narration") or ""))
        if outro_changed:
            outro["narration"] = outro_text
            repaired["outro"] = outro
            changed_locations.append("outro")

        if changed_locations:
            repaired.setdefault("meta", {}).setdefault("script_brief_repairs", []).append(
                {
                    "kind": "weak_advisory_language_replacement",
                    "locations": changed_locations,
                }
            )
        return repaired

    def _refresh_derived_script_outputs(self, payload: dict[str, Any]) -> dict[str, Any]:
        repaired = dict(payload)
        scenes = [dict(scene) for scene in payload.get("scenes") or [] if isinstance(scene, dict)]
        repaired["scenes"] = scenes
        repaired.setdefault("meta", {})
        repaired["meta"]["script_governance"] = repetition_report(scenes)
        repaired["meta"]["narrative_progression"] = narrative_progression_report([*scenes, dict(payload.get("outro") or {})])
        repaired["story_plan"] = self.story_pipeline.build_story_plan(repaired)
        return repaired

    def _script_brief_replacement_phrase(self, script_brief: dict[str, Any]) -> str:
        recurring = str(script_brief.get("recurring_example") or "").strip()
        if recurring:
            return recurring
        scene_map = script_brief.get("scene_function_map") or []
        if scene_map and isinstance(scene_map[0], dict):
            mechanism = str(scene_map[0].get("mechanism") or "").replace("_", " ").strip()
            if mechanism:
                return f"the {mechanism} decision"
        return "this money decision"

    def _replace_forbidden_phrase(self, narration: str, phrase: str, replacement: str) -> str:
        if not phrase:
            return narration
        pattern = re.compile(re.escape(phrase), flags=re.IGNORECASE)
        return pattern.sub(replacement, narration)

    def _replace_forbidden_semantic_marker(self, narration: str, marker: str) -> str:
        replacements = {
            "sip": "productive capital",
            "mutual fund": "productive opportunity",
            "stock picking": "another capital use",
            "asset allocation": "capital allocation",
            "rebalance portfolio": "move capital",
            "credit score": "payment record",
            "cibil": "payment record",
        }
        replacement = replacements.get(marker.lower())
        if not replacement:
            return narration
        pattern = re.compile(rf"\b(?:high-growth\s+|diversified\s+)?{re.escape(marker)}\b", flags=re.IGNORECASE)
        return pattern.sub(replacement, narration)

    def _recurring_example_terms(self, recurring_example: str) -> list[str]:
        stopwords = {
            "about",
            "after",
            "being",
            "from",
            "into",
            "that",
            "this",
            "where",
            "while",
            "with",
            "your",
            "looks",
            "feel",
            "feels",
        }
        terms = []
        for token in re.findall(r"[a-zA-Z][a-zA-Z-]{3,}", recurring_example.lower()):
            cleaned = token.replace("-", " ")
            if cleaned not in stopwords and cleaned not in terms:
                terms.append(cleaned)
        return terms[:8]

    def _forbidden_drift_hits(self, payload: dict[str, Any], script_brief: dict[str, Any]) -> list[dict[str, str]]:
        text_payloads = [("hook", payload.get("hook") or {})]
        text_payloads.extend((f"scene_{index}", scene) for index, scene in enumerate(payload.get("scenes") or [], start=1))
        text_payloads.append(("outro", payload.get("outro") or {}))
        hits: list[dict[str, str]] = []
        for phrase in script_brief.get("forbidden_drift") or []:
            normalized_phrase = self._normalized_phrase(str(phrase))
            semantic_markers = self._forbidden_drift_semantic_markers(normalized_phrase)
            for location, item in text_payloads:
                narration = item.get("narration") if isinstance(item, dict) else ""
                normalized_narration = self._normalized_phrase(str(narration or ""))
                if (
                    len(normalized_phrase.split()) >= 3
                    and normalized_phrase
                    and normalized_phrase in normalized_narration
                ):
                    hits.append({"phrase": str(phrase), "location": location})
                    continue
                for marker in semantic_markers:
                    if marker in normalized_narration:
                        hits.append({"phrase": str(phrase), "location": location, "marker": marker})
        return hits

    def _forbidden_drift_semantic_markers(self, normalized_phrase: str) -> tuple[str, ...]:
        if "general budgeting advice" in normalized_phrase or normalized_phrase == "budgeting":
            return (
                "50 30 20",
                "set a budget",
                "track your expenses",
                "track our expenses",
                "spend less",
                "cash for small purchases",
                "budget and track",
            )
        if "investment strategies" in normalized_phrase:
            return ("sip", "mutual fund", "stock picking", "asset allocation", "rebalance portfolio")
        if "credit score management" in normalized_phrase:
            return ("credit score", "cibil", "improve your score", "score management")
        if "generic financial literacy" in normalized_phrase:
            return (
                "make informed financial decisions",
                "make informed decisions",
                "achieve your financial goals",
                "achieve our financial goals",
                "achieve their financial goals",
                "use them wisely",
                "be mindful of our finances",
                "be mindful of your finances",
                "make the most of their money",
                "make the most of your money",
                "living a life of luxury and freedom",
                "live a life of luxury and freedom",
            )
        if "loan options" in normalized_phrase:
            return ("personal loan", "home loan", "loan option", "refinance")
        if "cash flow management for businesses" in normalized_phrase:
            return ("business cash flow", "working capital", "invoice cycle", "vendor payment")
        return ()

    def _validate_script_brief_topic_alignment(self, topic: str, angle: str, script_brief: dict[str, Any]) -> list[str]:
        topic_text = self._normalized_phrase(f"{topic} {angle}")
        if not topic_text:
            return []
        functions = " ".join(
            str(item.get("function") or "")
            for item in script_brief.get("scene_function_map") or []
            if isinstance(item, dict)
        )
        searchable = self._normalized_phrase(
            " ".join(
                [
                    str(script_brief.get("topic_interpretation") or ""),
                    str(script_brief.get("thesis") or ""),
                    str(script_brief.get("viewer_promise") or ""),
                    str(script_brief.get("recurring_example") or ""),
                    functions,
                ]
            )
        )
        errors: list[str] = []
        if not self._is_salary_topic(topic_text):
            for phrase in self._salary_drift_phrases():
                if phrase in searchable:
                    errors.append(f"non-salary topic drifted into salary/day-20 curriculum: {phrase!r}")
                    break

        topic_terms = [
            term
            for term in topic_text.split()
            if len(term) >= 5 and term not in {"about", "after", "before", "people", "money", "finance", "financial"}
        ]
        if topic_terms and not any(term in searchable for term in topic_terms[:6]):
            errors.append("ScriptBrief does not reflect the submitted topic strongly enough.")

        if self._is_rich_people_topic(topic_text):
            has_strategy = any(term in searchable for term in ("strategic", "strategy", "cash flow", "capital", "liquidity", "business", "investor", "wealthy"))
            has_consumer_risk = any(term in searchable for term in ("consumer", "trap", "misuse", "risk", "illusion", "danger", "overcommit"))
            if not (has_strategy and has_consumer_risk):
                errors.append("Rich-people/business topics must include both strategic-use and consumer-risk framing.")

        if self._is_monthly_payment_topic(topic_text):
            preferred = {
                "payment_pain_reduction",
                "affordability_illusion",
                "price_anchoring",
                "commitment_stacking",
                "subscription_lock_in",
                "lock_in",
                "cash_flow_squeeze",
            }
            mechanisms = {str(item) for item in script_brief.get("allowed_mechanisms") or []}
            if not mechanisms.intersection(preferred):
                errors.append("Monthly-payment topics need at least one payment-psychology or cash-flow mechanism.")
        return errors

    def _is_salary_topic(self, normalized_topic: str) -> bool:
        return any(token in normalized_topic for token in ("salary", "paycheck", "payday", "month end", "take home", "ctc", "raise", "increment"))

    def _is_rich_people_topic(self, normalized_topic: str) -> bool:
        return any(token in normalized_topic for token in ("rich people", "wealthy", "business", "founder", "investor"))

    def _is_monthly_payment_topic(self, normalized_topic: str) -> bool:
        return any(token in normalized_topic for token in ("monthly payment", "monthly payments", "subscription", "bnpl", "no cost emi"))

    def _salary_drift_phrases(self) -> tuple[str, ...]:
        return (
            "50000 salary",
            "50 000 salary",
            "₹50 000 salary",
            "day 20",
            "salary disappears",
            "salary vanish",
            "salary drain",
            "month end",
            "payday",
        )

    def _normalized_phrase(self, value: str) -> str:
        return " ".join(re.findall(r"[a-zA-Z0-9₹]+", str(value or "").lower()))

    def _normalize_payload(self, payload: dict[str, Any], topic: str, angle: str, project_id: int | None = None) -> dict[str, Any]:
        hook = payload.get("hook") or {}
        scenes = payload.get("scenes") or []
        outro = payload.get("outro") or {}

        if isinstance(hook, str):
            hook = {"narration": hook}
        if isinstance(outro, str):
            outro = {"narration": outro}

        normalized = {
            "hook": {
                "narration": self._refine_hook_narration(
                    self._refined_narration(
                        str(hook.get("narration") or hook.get("text") or self._fallback_hook(topic))
                    ),
                    topic,
                    angle,
                ),
                "duration": self._coerce_duration(hook.get("duration", hook.get("estimated_duration_sec")), 6),
            },
            "scenes": [],
            "outro": {
                "narration": self._refined_narration(
                    str(outro.get("narration") or outro.get("text") or self._fallback_outro())
                ),
                "duration": self._coerce_duration(outro.get("duration", outro.get("estimated_duration_sec")), 18),
            },
            "meta": dict(payload.get("meta") or {}),
        }

        planning_scenes: list[dict[str, Any]] = []
        for index, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                continue
            debug_trace = self._script_debug_trace(project_id, index, scene)
            narration = self._refined_narration(
                str(
                    scene.get("narration")
                    or scene.get("narration_text")
                    or scene.get("content")
                    or self._fallback_scene(index, topic)
                )
            )
            original_narration = narration
            if debug_trace:
                debug_trace.snapshot("groq_post_parse", scene, owner="groq")
                debug_trace.ownership("narration", "groq", scene.get("narration") or scene.get("narration_text") or scene.get("content"), "Groq generated narration")
                for key in ("mechanism", "visual_intent", "visual_beats", "numbers", "emotion"):
                    if key in scene:
                        debug_trace.ownership(key, "groq", scene.get(key), f"Groq generated {key}")
            refined_scene = self.scene_refiner.refine_scene(
                scene,
                narration,
                index=index,
                topic=topic,
                angle=angle,
                debug_trace=debug_trace,
            )
            narration = str(refined_scene["narration"])
            normalized_scene = {
                "kind": "body",
                "scene_index": index,
                "narration": narration,
                "duration": self._coerce_duration(scene.get("duration", scene.get("estimated_duration_sec")), 45),
            }
            visual_scene = dict(refined_scene.get("visual_scene") or self._visual_scene_from_raw_scene(scene, narration))
            for key in ("visual_intent", "visual_beats", "numbers", "emotion", "mechanism"):
                if key in visual_scene:
                    normalized_scene[key] = visual_scene[key]
                elif key in scene:
                    normalized_scene[key] = scene[key]
            normalized["scenes"].append(normalized_scene)
            force_scene_contract = bool(
                normalized["meta"].get("script_brief")
                or scene.get("mechanism")
                or scene.get("visual_scene")
            )
            allow_grouping = bool(refined_scene.get("allow_grouping")) and not force_scene_contract
            if allow_grouping:
                planning_scene = {
                    "kind": "body",
                    "scene_index": index,
                    "narration": original_narration,
                    "duration": normalized_scene["duration"],
                }
            else:
                planning_scene = dict(normalized_scene)
            if visual_scene and not allow_grouping:
                planning_scene["visual_scene"] = visual_scene
            planning_scenes.append(planning_scene)
            if debug_trace:
                debug_trace.snapshot("script_normalized_scene", planning_scene, owner="script_service")
                SceneDebugStore().save(debug_trace)

        if not normalized["scenes"]:
            normalized["scenes"] = self._demo_script(topic, angle)["scenes"]

        normalized["meta"]["script_governance"] = repetition_report(normalized["scenes"])
        normalized["meta"]["narrative_progression"] = narrative_progression_report(
            [*normalized["scenes"], normalized["outro"]]
        )

        planning_payload = dict(normalized)
        planning_payload["scenes"] = planning_scenes or list(normalized["scenes"])
        normalized["story_plan"] = self.story_pipeline.build_story_plan(planning_payload)
        normalized["meta"]["story_engine"] = "story_intelligence_v1"
        normalized["titles"] = self._normalize_titles(payload.get("suggested_titles") or payload.get("titles"), topic, angle)
        normalized["description"] = str(
            payload.get("suggested_description")
            or payload.get("description")
            or f"A practical breakdown of {topic.lower()} with a focus on {angle.lower()}."
        )
        normalized["tags"] = self._normalize_tags(payload.get("tags"), topic, angle)

        self._validate_payload_shape(normalized)
        return normalized

    def _script_debug_trace(self, project_id: int | None, index: int, scene: dict[str, Any]) -> SceneDebugTrace | None:
        if project_id is None or not debug_video_pipeline_enabled():
            return None
        return SceneDebugTrace(
            scene_id=f"scene_{index}",
            project_id=int(project_id),
            scene_order=index,
            narration=str(scene.get("narration") or scene.get("narration_text") or scene.get("content") or ""),
        )

    def _normalize_titles(self, titles: Any, topic: str, angle: str) -> list[str]:
        if isinstance(titles, str):
            titles = [titles]
        if not isinstance(titles, list):
            titles = []
        cleaned = [str(title).strip() for title in titles if str(title).strip()]
        return cleaned[:5] or self._demo_script(topic, angle)["titles"]

    def _normalize_tags(self, tags: Any, topic: str, angle: str) -> list[str]:
        if isinstance(tags, str):
            tags = [item.strip() for item in tags.split(",")]
        if not isinstance(tags, list):
            tags = []
        cleaned = [str(tag).strip() for tag in tags if str(tag).strip()]
        return cleaned[:8] or [topic, angle, "personal finance", "money habits"]

    def _visual_scene_from_raw_scene(self, scene: dict[str, Any], narration: str) -> dict[str, Any]:
        return self.scene_row_mapper.visual_scene_from_raw_scene(scene, narration)

    def _normalize_tension_type(self, value: Any) -> str:
        tension_type = str(value or "").strip().lower()
        return tension_type if tension_type in VALID_TENSION_TYPES else "curiosity_gap"

    def _coerce_duration(self, value: Any, default: int) -> int:
        try:
            duration = int(round(float(value)))
            return duration if duration > 0 else default
        except (TypeError, ValueError):
            return default

    def _refined_narration(self, narration: str) -> str:
        refined = refine_narration(narration)
        return " ".join(refined) if refined else str(narration or "").strip()

    def _refine_hook_narration(self, narration: str, topic: str, angle: str) -> str:
        hook_text = " ".join(str(narration or "").split()).strip()
        if not self.validate_hook({"narration": hook_text}):
            return hook_text

        context = f"{hook_text} {topic} {angle}".lower()
        rupee_match = re.search(r"(?:₹\s*|Rs\.?\s*)\d[\d,]*(?:\.\d+)?", hook_text, re.IGNORECASE)
        amount = rupee_match.group(0).replace("Rs.", "₹").replace("Rs", "₹") if rupee_match else ""

        if "salary" in context or "paycheck" in context or "income" in context:
            subject = f"your {amount} salary" if amount else "your salary"
            return f"Why does {subject} feel gone by day 20?"
        if "debt" in context or "credit card" in context or "loan" in context or "emi" in context:
            return "Why does one debt payment keep your money leaking every month?"
        if "inflation" in context or "fd" in context or "fixed deposit" in context:
            return "Why does safe money still lose buying power every year?"
        if "emergency" in context or "savings" in context or "save" in context:
            return "Why do most savings vanish when one emergency hits?"
        if "invest" in context or "fomo" in context or "risk" in context or "return" in context:
            return "Why do smart investors still lose money chasing returns?"
        return "Why does your money disappear even when you are doing everything right?"

    def _fallback_hook(self, topic: str) -> str:
        topic_text = str(topic or "money").strip().lower()
        return f"The hidden truth about {topic_text}."

    def _fallback_scene(self, index: int, topic: str) -> str:
        topic_text = str(topic or "").strip().lower()
        if topic_text:
            return f"Scene {index} explains one clear idea about {topic_text}."
        return f"Scene {index} explains one clear finance idea."

    def _fallback_outro(self) -> str:
        return "Recap the key takeaways and choose one clear next step."

    def _demo_script(self, topic: str, angle: str) -> dict[str, Any]:
        return {
            "hook": {
                "narration": "80% of Indians have less than ₹5,000 saved, and the real reason is not what most people think.",
                "duration": 6,
                "tension_type": "shocking_statistic",
            },
            "scenes": [
                {
                    "kind": "body",
                    "narration": "In your 20s, salary can vanish by day 12, and one card bill can make the whole month feel broken.",
                    "duration": 35,
                },
                {
                    "kind": "body",
                    "narration": "The real issue is invisible defaults: a ₹8,00,000 salary can still leak ₹1,60,000 before you notice.",
                    "duration": 35,
                },
                {
                    "kind": "body",
                    "narration": "The fix is simple: automate ₹5,000 before emotion gets a vote, so manual spending cannot turn savings into ₹0.",
                    "duration": 35,
                },
            ],
            "outro": {
                "narration": "Fix the system now, automate the ₹5,000, and next year stops feeling expensive.",
                "duration": 18,
            },
            "titles": [
                f"The hidden {topic} mistake in your 20s",
                f"Why most people get {topic} wrong",
                f"The truth about {angle} and money",
            ],
            "description": f"A practical breakdown of {topic.lower()} through the lens of {angle.lower()}.",
            "tags": [topic, angle, "personal finance", "money habits"],
            "meta": {"source": "demo"},
        }

    def _demo_script_brief(self, topic: str, angle: str) -> dict[str, Any]:
        return {
            "topic_interpretation": f"A demo finance script about {topic or 'money habits'} through the angle of {angle or 'practical behavior'}.",
            "thesis": "Small default money decisions quietly shape cash flow unless the viewer makes the system explicit.",
            "viewer_promise": "The viewer will understand the core money leak and one practical way to control it.",
            "selected_format": "mechanism_explainer",
            "format_rationale": "The demo script uses a compact mechanism explanation so local app flow remains deterministic.",
            "recurring_example": "a salaried Indian household where salary leaks through monthly spending defaults",
            "allowed_mechanisms": ["salary_drain", "expense_leakage"],
            "forbidden_drift": ["generic SIP advice", "unrelated stock prediction", "platform-specific investing advice"],
            "scene_function_map": [
                {
                    "scene_index": 1,
                    "function": "Show the salary leak appearing early in the month.",
                    "mechanism": "salary_drain",
                    "emotional_direction": "building",
                },
                {
                    "scene_index": 2,
                    "function": "Show invisible defaults turning income into leakage.",
                    "mechanism": "expense_leakage",
                    "emotional_direction": "revealing",
                },
                {
                    "scene_index": 3,
                    "function": "Show one automated action protecting savings before spending emotion takes over.",
                    "mechanism": "expense_leakage",
                    "emotional_direction": "clarity",
                },
            ],
            "tone_directive": "Confident, direct, and practical.",
        }

    
