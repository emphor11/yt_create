from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib import error

from flask import current_app

from ..contracts.scripts import ScriptBriefContract
from ..models.repository import ProjectRepository, utcnow
from ..pipelines.script import (
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
                f"groq_key={'yes' if bool(current_app.config.get('GROQ_API_KEY')) else 'no'}."
            ),
        )

        if provider not in {"auto", "groq"}:
            raise ValueError(f"Script generation requires Groq. Unsupported LLM_PROVIDER={provider!r}.")
        if not current_app.config.get("GROQ_API_KEY"):
            raise ValueError("Script generation requires Groq, but GROQ_API_KEY is not configured.")

        try:
            payload = self._groq_script(topic, angle, prompt, current_app.config["GROQ_API_KEY"])
            if script_brief:
                payload.setdefault("meta", {})["script_brief"] = script_brief
            payload = self._normalize_payload(payload, topic, angle, project_id=project_id)
            if script_brief:
                self._validate_script_against_brief(payload, script_brief)
                payload.setdefault("meta", {})["script_brief"] = script_brief
            payload.setdefault("meta", {})["source"] = "live_groq"
            self.logger.log("script_generation", "completed", "Script source selected: live_groq.")
            return payload, "live Groq API"
        except (error.URLError, ValueError, KeyError, json.JSONDecodeError) as exc:
            self.logger.log(
                "script_generation",
                "failed",
                f"Groq generation failed ({exc}).",
            )
            raise

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
                f"groq_key={'yes' if bool(current_app.config.get('GROQ_API_KEY')) else 'no'}."
            ),
        )
        if provider not in {"auto", "groq"}:
            raise ValueError(f"ScriptBrief generation requires Groq. Unsupported LLM_PROVIDER={provider!r}.")
        if not current_app.config.get("GROQ_API_KEY"):
            raise ValueError("ScriptBrief generation requires Groq, but GROQ_API_KEY is not configured.")
        payload = self._groq_script_brief(prompt, current_app.config["GROQ_API_KEY"])
        brief = ScriptBriefContract.from_dict(payload)
        validation = brief.validate()
        if not validation.passed:
            messages = "; ".join(issue.message for issue in validation.errors)
            raise ValueError(f"ScriptBrief generation failed validation: {messages}")
        self.logger.log("script_brief_generation", "completed", "Generated ScriptBrief contract.")
        return brief.to_dict()

    def _groq_script(self, topic: str, angle: str, prompt: str, api_key: str) -> dict[str, Any]:
        return self.groq_generator.generate(
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

    def _validate_script_against_brief(self, payload: dict[str, Any], script_brief: dict[str, Any]) -> None:
        errors: list[str] = []
        brief = ScriptBriefContract.from_dict(script_brief)
        validation = brief.validate()
        if not validation.passed:
            messages = "; ".join(issue.message for issue in validation.errors)
            raise ValueError(f"ScriptBrief validation failed before script validation: {messages}")
        body_scenes = [scene for scene in payload.get("scenes") or [] if scene.get("kind", "body") == "body"]
        scene_map = [item.to_dict() for item in brief.scene_function_map]
        if len(body_scenes) != len(scene_map):
            errors.append(
                f"generated {len(body_scenes)} body scenes, but ScriptBrief requires {len(scene_map)} scene function entries"
            )

        for index, (scene, map_item) in enumerate(zip(body_scenes, scene_map), start=1):
            expected = str(map_item.get("mechanism") or "").strip()
            actual = str(scene.get("mechanism") or "").strip()
            if expected and actual != expected:
                errors.append(f"scene {index} mechanism {actual!r} does not match ScriptBrief mechanism {expected!r}")

        recurring_terms = self._recurring_example_terms(str(script_brief.get("recurring_example") or ""))
        if recurring_terms and body_scenes:
            hit_count = 0
            for scene in body_scenes:
                narration = str(scene.get("narration") or "").lower()
                if any(term in narration for term in recurring_terms):
                    hit_count += 1
            minimum_hits = min(len(body_scenes), 2)
            if hit_count < minimum_hits:
                errors.append(
                    f"recurring example appears in {hit_count} body scenes; expected at least {minimum_hits}"
                )

        if errors:
            raise ValueError("Script does not satisfy ScriptBrief: " + "; ".join(errors))

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
            if refined_scene.get("allow_grouping"):
                planning_scene = {
                    "kind": "body",
                    "scene_index": index,
                    "narration": original_narration,
                    "duration": normalized_scene["duration"],
                }
            else:
                planning_scene = dict(normalized_scene)
            if visual_scene and not refined_scene.get("allow_grouping"):
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

    
