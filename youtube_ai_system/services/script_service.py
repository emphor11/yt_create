from __future__ import annotations

import json
import re
import ssl
from typing import Any
from urllib import error, request

import certifi
from flask import current_app
import requests

from ..models.repository import ProjectRepository, utcnow
from .beat_planner import generate_beats
from .concept_extractor import extract as extract_concept
from .narration_refiner import refine as refine_narration
from .run_log import RunLogger
from .story_intelligence_engine import StoryIntelligenceEngine
from .visual_logic_engine import map_concept_to_visual

TENSION_KEYWORDS = {
    "?",
    "why",
    "how",
    "never",
    "secret",
    "mistake",
    "truth",
    "wrong",
    "actually",
    "shocking",
    "reveal",
    "hidden",
    "nobody",
    "most people",
    "what happens",
    "find out",
    "you think",
    "real reason",
}

PEOPLE_GROUP_WORDS = {
    "indians",
    "people",
    "salary",
    "workers",
    "families",
    "earners",
    "graduates",
    "investors",
}

NEGATIVE_IMPLICATION_WORDS = {
    "lose",
    "lost",
    "losing",
    "paying",
    "gone",
    "spent",
    "debt",
    "broke",
    "savings",
    "interest",
    "leak",
    "drain",
    "cost",
}

DEFAULT_TARGET_DURATION_MINUTES = 8
DEFAULT_CHANNEL_NICHE = "personal finance India"
DEFAULT_SCRIPT_TONE = "confident, direct, slightly provocative"
VALID_TENSION_TYPES = {
    "curiosity_gap",
    "shocking_statistic",
    "contrarian_claim",
    "common_mistake_reveal",
    "before_after",
}

CONCEPT_PRIORITY = {
    "numeric": 5,
    "risk": 4,
    "comparison": 3,
    "growth": 2,
    "definition": 1,
}


class ScriptService:
    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.logger = RunLogger()
        self.story_intelligence = StoryIntelligenceEngine()

    def generate_script(
        self,
        project_id: int,
        topic: str,
        angle: str,
        target_duration_minutes: int | None = None,
        niche: str | None = None,
        tone: str | None = None,
    ) -> int:
        prompt = self._build_prompt(topic, angle, target_duration_minutes, niche, tone)
        payload, source = self._generate_payload(topic, angle, prompt)
        script_version_id = self.repo.create_script_version(
            project_id=project_id,
            hook_json=payload["hook"],
            outro_json=payload["outro"],
            titles_json=payload.get("titles", []),
            description_text=payload.get("description", ""),
            tags_json=payload.get("tags", []),
            full_script_json=payload,
            source_prompt=prompt,
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
        normalized = self._normalize_payload(payload, "", "")
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
        errors: list[str] = []
        if float(hook.get("duration", hook.get("estimated_duration_sec", 0)) or 0) > 7:
            errors.append("Hook must be 7 seconds or under.")

        narration = str(hook.get("narration", "")).strip()
        narration_lower = narration.lower()
        word_count = len(narration.split())

        condition_a = any(keyword in narration_lower for keyword in TENSION_KEYWORDS)

        condition_b = False
        has_pct = "%" in narration
        large_numbers = [int(m) for m in re.findall(r"\d+", narration) if int(m) > 1000]
        has_large_number = len(large_numbers) > 0
        has_people_group = any(pg in narration_lower for pg in PEOPLE_GROUP_WORDS)
        if (has_pct or has_large_number) and word_count <= 25 and has_people_group:
            condition_b = True

        condition_c = False
        has_rupee = "₹" in narration
        has_negative = any(nw in narration_lower for nw in NEGATIVE_IMPLICATION_WORDS)
        if has_rupee and has_negative:
            condition_c = True

        if not (condition_a or condition_b or condition_c):
            guidance_lines = [
                "Hook must include a tension signal. Satisfy ANY ONE of these:",
                "  A) Include a tension keyword or question mark: " + ", ".join(sorted(TENSION_KEYWORDS)),
                "  B) Include a percentage or number > 1000 AND a people group word "
                + f"({', '.join(sorted(PEOPLE_GROUP_WORDS))}) in under 25 words",
                "  C) Include ₹ symbol AND a negative implication word "
                + f"({', '.join(sorted(NEGATIVE_IMPLICATION_WORDS))})",
            ]
            errors.append(" | ".join(guidance_lines))
        return errors

    def approval_ready(self, script_version: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any]]:
        payload = self.load_script_payload(script_version)
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
        return (not errors, errors, payload)

    def scene_rows_from_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        scene_rows = [
            {
                "scene_order": 0,
                "kind": "hook",
                "narration_text": payload["hook"]["narration"],
            }
        ]
        for index, scene in enumerate(payload["scenes"], start=1):
            scene_rows.append(
                {
                    "scene_order": index,
                    "kind": scene.get("kind", "body"),
                    "narration_text": scene["narration"],
                }
            )
        scene_rows.append(
            {
                "scene_order": len(scene_rows),
                "kind": "outro",
                "narration_text": payload["outro"]["narration"],
            }
        )
        return scene_rows

    def _generate_payload(self, topic: str, angle: str, prompt: str) -> tuple[dict[str, Any], str]:
        provider = current_app.config.get("LLM_PROVIDER", "auto")
        self.logger.log(
            "script_generation",
            "running",
            (
                f"Script generation provider selection: provider={provider}, "
                f"groq_key={'yes' if bool(current_app.config.get('GROQ_API_KEY')) else 'no'}, "
                f"claude_key={'yes' if bool(current_app.config.get('CLAUDE_API_KEY')) else 'no'}."
            ),
        )

        if provider in {"auto", "groq"} and current_app.config.get("GROQ_API_KEY"):
            try:
                payload = self._groq_script(topic, angle, prompt, current_app.config["GROQ_API_KEY"])
                payload = self._normalize_payload(payload, topic, angle)
                payload.setdefault("meta", {})["source"] = "live_groq"
                self.logger.log("script_generation", "completed", "Script source selected: live_groq.")
                return payload, "live Groq API"
            except (error.URLError, ValueError, KeyError, json.JSONDecodeError) as exc:
                self.logger.log(
                    "script_generation",
                    "failed",
                    f"Groq generation failed ({exc}). Falling back to the next provider.",
                )

        if provider in {"auto", "anthropic", "claude"} and current_app.config.get("CLAUDE_API_KEY"):
            try:
                payload = self._claude_script(topic, angle, prompt, current_app.config["CLAUDE_API_KEY"])
                payload = self._normalize_payload(payload, topic, angle)
                payload.setdefault("meta", {})["source"] = "live_claude"
                self.logger.log("script_generation", "completed", "Script source selected: live_claude.")
                return payload, "live Claude API"
            except (error.URLError, ValueError, KeyError, json.JSONDecodeError) as exc:
                self.logger.log(
                    "script_generation",
                    "failed",
                    f"Claude generation failed ({exc}). Falling back to demo script.",
                )

        payload = self._demo_script(topic, angle)
        payload = self._normalize_payload(payload, topic, angle)
        payload.setdefault("meta", {})["source"] = "demo"
        self.logger.log("script_generation", "completed", "Script source selected: demo_fallback.")
        return payload, "demo fallback"

    def _build_prompt(
        self,
        topic: str,
        angle: str,
        target_duration_minutes: int | None = None,
        niche: str | None = None,
        tone: str | None = None,
    ) -> str:
        target_duration_minutes = target_duration_minutes or current_app.config.get(
            "TARGET_DURATION_MINUTES",
            DEFAULT_TARGET_DURATION_MINUTES,
        )
        niche = niche or current_app.config.get("CHANNEL_NICHE", DEFAULT_CHANNEL_NICHE)
        tone = tone or current_app.config.get("SCRIPT_TONE", DEFAULT_SCRIPT_TONE)
        if self._ten_minute_finance_enabled():
            return self._build_ten_minute_finance_prompt(topic, angle)
        return (
            "You are a world-class YouTube script writer for a finance-explanation channel in the style of 20 Minute University-style videos (e.g. “All of Economics in 20 minutes”).\n\n"
            "Your only job is to generate raw spoken-style narration that will be processed by a deterministic system later.\n\n"
            "---\n\n"
            "OUTPUT REQUIREMENTS:\n\n"
            "* Output only narration content inside the required JSON format\n"
            "* No markdown, no bullet points, no extra text\n"
            "* No section labels like \"Hook\", \"Body\"\n\n"
            "---\n\n"
            "TONE & STYLE:\n\n"
            "* Direct, slightly sarcastic, warm, knowledgeable\n"
            "* Conversational (talk to the viewer, not at them)\n"
            "* Light humor + relatable analogies\n"
            "* Use Indian finance context naturally (salary, EMI, SIP, inflation, debt trap, etc.)\n"
            "* Keep language simple and spoken-friendly\n\n"
            "---\n\n"
            "CORE WRITING RULES:\n\n"
            "1. ONE IDEA PER SENTENCE\n"
            "Each sentence must express only ONE clear idea.\n"
            "Do NOT combine multiple ideas using \"and\", \"because\", \"which\", etc.\n\n"
            "2. SHORT SENTENCES\n"
            "Keep sentences short (ideally under 20 words).\n"
            "Split complex thoughts into multiple sentences.\n\n"
            "3. CONCEPT GROUPING\n"
            "Each concept should be expressed using 1–3 consecutive sentences.\n"
            "Do NOT mix multiple concepts together.\n\n"
            "4. EXPLICIT CONCEPT VISIBILITY\n"
            "The core concept must be clearly visible.\n"
            "Avoid vague phrases like “this situation”.\n"
            "Use clear terms like:\n\n"
            "* emergency fund\n"
            "* debt trap\n"
            "* inflation\n"
            "* lifestyle inflation\n"
            "* compound interest\n\n"
            "---\n\n"
            "STRUCTURE (NATURAL FLOW ONLY):\n\n"
            "HOOK:\n\n"
            "* First 2–5 sentences\n"
            "* Strong curiosity or tension\n"
            "* No greetings or filler\n\n"
            "BODY:\n\n"
            "* Continuous flow of ideas\n"
            "* Each concept explained clearly\n"
            "* Use relatable examples and analogies\n\n"
            "OUTRO:\n\n"
            "* Last 3–6 sentences\n"
            "* Quick recap\n"
            "* One practical takeaway\n"
            "* End with a strong line\n\n"
            "---\n\n"
            "CONSTRAINTS:\n\n"
            "* Do NOT generate visuals\n"
            "* Do NOT add extra fields\n"
            "* Do NOT enforce structure labels\n"
            "* Do NOT invent fake numbers\n\n"
            "---\n\n"
            "INPUT VARIABLES (already passed by system):\n\n"
            "* CHANNEL_DESCRIPTION\n"
            "* TOPIC\n"
            "* AUDIENCE\n"
            "* DURATION_APPROX\n\n"
            "Use them naturally in writing.\n\n"
            f"CHANNEL_DESCRIPTION: {niche}\n"
            f"TOPIC: {topic}\n"
            f"AUDIENCE: {angle}\n"
            f"DURATION_APPROX: {target_duration_minutes} minutes\n"
            f"TONE_HINT: {tone}\n\n"
            "OUTPUT FORMAT:\n"
            "Return one valid JSON object only.\n"
            "{\n"
            '  "hook": {"narration": "string", "duration": 6, "tension_type": "curiosity_gap"},\n'
            '  "scenes": [{"scene_index": 1, "kind": "body", "narration": "string", "duration": 45}],\n'
            '  "outro": {"narration": "string", "duration": 18},\n'
            '  "suggested_titles": ["title option 1", "title option 2"],\n'
            '  "suggested_description": "string",\n'
            '  "tags": ["tag1", "tag2"],\n'
            '  "tension_type_used": "curiosity_gap"\n'
            "}\n"
            f"The total duration across hook + scenes + outro should be about {target_duration_minutes * 60} seconds.\n"
            "Return only JSON.\n"
        )

    def _ten_minute_finance_enabled(self) -> bool:
        return str(current_app.config.get("CHANNEL_STYLE", "")).lower() == "ten_minute_finance"

    def _build_ten_minute_finance_prompt(self, topic: str, angle: str) -> str:
        return (
            "You are writing a script for \"10 Minute Finance\".\n\n"
            "TONE RULES:\n"
            "- Write like a smart friend roasting bad financial decisions with love.\n"
            "- Use specific rupee amounts and percentages for claims.\n"
            "- Use real Indian finance context where relevant.\n"
            "- No jargon without plain-English explanation.\n\n"
            "SCRIPT STRUCTURE:\n"
            "- Hook: 5-7 seconds, unresolved tension.\n"
            "- Body: 8-12 scenes, one idea per scene.\n"
            "- Outro: 15-20 seconds with forward hook.\n"
            "- Total narration: about 1400-1600 words.\n\n"
            "OUTPUT FORMAT:\n"
            "Return valid JSON only.\n"
            "{\n"
            '  "hook": {"narration": "string", "duration": 6, "tension_type": "shocking_statistic|curiosity_gap|contrarian_claim"},\n'
            '  "scenes": [{"scene_index": 1, "kind": "body", "narration": "string", "duration": 60}],\n'
            '  "outro": {"narration": "string", "duration": 18},\n'
            '  "suggested_titles": ["title1", "title2", "title3"],\n'
            '  "suggested_description": "string",\n'
            '  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]\n'
            "}\n\n"
            f"Topic: {topic}\n"
            f"Angle: {angle}\n"
        )

    def _groq_script(self, topic: str, angle: str, prompt: str, api_key: str) -> dict[str, Any]:
        body = {
            "model": current_app.config["GROQ_MODEL"],
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a professional YouTube scriptwriter. "
                        "You always return valid JSON only. "
                        "You never add explanations, apologies, markdown formatting, or code fences."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 5200 if self._ten_minute_finance_enabled() else 1800,
            "response_format": {"type": "json_object"},
        }
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "YTCreate/1.0",
                },
                timeout=45,
            )
            response.raise_for_status()
            response_json = response.json()
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            error_body = exc.response.text if exc.response is not None else str(exc)
            raise ValueError(f"Groq API error {status_code}: {error_body}") from exc
        except requests.RequestException as exc:
            raise error.URLError(str(exc)) from exc

        text = response_json["choices"][0]["message"]["content"]
        self.logger.log("script_generation", "running", f"Raw Groq response before parsing: {text}")
        return self._extract_json_payload(text)

    def _claude_script(self, topic: str, angle: str, prompt: str, api_key: str) -> dict[str, Any]:
        body = {
            "model": current_app.config["CLAUDE_MODEL"],
            "max_tokens": 1400,
            "messages": [{"role": "user", "content": prompt}],
        }
        req = request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        try:
            with request.urlopen(req, timeout=45, context=ssl_context) as response:
                response_json = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="ignore")
            raise ValueError(f"Anthropic API error {exc.code}: {error_body}") from exc
        text = "".join(block.get("text", "") for block in response_json.get("content", []) if block.get("type") == "text")
        self.logger.log("script_generation", "running", f"Raw Claude response before parsing: {text}")
        return self._extract_json_payload(text)

    def _extract_json_payload(self, raw_text: str) -> dict[str, Any]:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json", "", 1).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Model did not return a JSON object.")
        return json.loads(cleaned[start : end + 1])

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

    def _normalize_payload(self, payload: dict[str, Any], topic: str, angle: str) -> dict[str, Any]:
        hook = payload.get("hook") or {}
        scenes = payload.get("scenes") or []
        outro = payload.get("outro") or {}

        if isinstance(hook, str):
            hook = {"narration": hook}
        if isinstance(outro, str):
            outro = {"narration": outro}

        normalized = {
            "hook": {
                "narration": self._refined_narration(
                    str(hook.get("narration") or hook.get("text") or f"The hidden truth about {topic.lower()}")
                ),
                "duration": self._coerce_duration(hook.get("duration", hook.get("estimated_duration_sec")), 6),
            },
            "scenes": [],
            "outro": {
                "narration": self._refined_narration(
                    str(outro.get("narration") or outro.get("text") or f"Fix {angle.lower()} before it costs you another year.")
                ),
                "duration": self._coerce_duration(outro.get("duration", outro.get("estimated_duration_sec")), 18),
            },
            "meta": dict(payload.get("meta") or {}),
        }

        for index, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                continue
            normalized["scenes"].append(
                {
                    "kind": scene.get("kind", "body"),
                    "scene_index": int(scene.get("scene_index") or index),
                    "narration": self._refined_narration(
                        str(
                            scene.get("narration")
                            or scene.get("narration_text")
                            or scene.get("content")
                            or f"Scene {index} expands the main idea around {topic.lower()}."
                        )
                    ),
                    "duration": self._coerce_duration(scene.get("duration", scene.get("estimated_duration_sec")), 35),
                }
            )

        if not normalized["scenes"]:
            normalized["scenes"] = self._demo_script(topic, angle)["scenes"]

        planning_payload = self._group_payload_for_story_plan(normalized)
        normalized["story_plan"] = self.story_intelligence.plan_from_script_payload(planning_payload)
        normalized["story_plan"] = self._attach_section_concepts(normalized["story_plan"])
        normalized["story_plan"] = self._attach_section_visual_plan(normalized["story_plan"])
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

    def group_sentences_into_sections(self, sentences: list[str]) -> list[str]:
        cleaned = [self._normalize_text(sentence) for sentence in sentences if self._normalize_text(sentence)]
        if not cleaned:
            return []

        groups: list[list[str]] = []
        index = 0

        while index < len(cleaned):
            current = [cleaned[index]]
            index += 1

            if index < len(cleaned):
                current.append(cleaned[index])
                index += 1

            if index < len(cleaned):
                next_sentence = cleaned[index]
                if (
                    len(current) < 3
                    and self._section_word_count(current) < 8
                    and not self._sentence_starts_new_section(next_sentence)
                    and self._shares_topic_with_current(current, next_sentence)
                    and self._section_word_count(current + [next_sentence]) <= 20
                ):
                    current.append(next_sentence)
                    index += 1

            groups.append(current)

        groups = self._merge_short_sections(groups)
        return [" ".join(group) for group in groups if group]

    def _group_payload_for_story_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        hook = dict(payload.get("hook") or {})
        raw_sentences: list[str] = []
        for scene in payload.get("scenes") or []:
            raw_sentences.extend(self._split_story_sentences(str(scene.get("narration") or "")))
        outro = payload.get("outro") or {}
        raw_sentences.extend(self._split_story_sentences(str(outro.get("narration") or "")))
        body_sentences = [sentence for sentence in raw_sentences if self._keep_story_sentence(sentence)]
        if len(body_sentences) < 2:
            body_sentences = [sentence for sentence in raw_sentences if self._keep_story_sentence(sentence, allow_short=True)]

        grouped_sections = self.group_sentences_into_sections(body_sentences)
        grouped_scenes = [{"narration": section_text} for section_text in grouped_sections]

        return {
            "hook": hook,
            "scenes": grouped_scenes,
            "outro": {"narration": ""},
        }

    def _attach_section_concepts(self, story_plan: dict[str, Any]) -> dict[str, Any]:
        sections = story_plan.get("sections") or []
        for section in sections:
            concepts: list[dict[str, str]] = []
            seen: set[tuple[str, str]] = set()
            for sentence in self._split_story_sentences(str(section.get("text") or "")):
                extracted = extract_concept(sentence)
                concept = extracted.get("concept")
                concept_type = extracted.get("type")
                if not concept or concept_type == "unknown":
                    continue
                key = (str(concept), str(concept_type))
                if key in seen:
                    continue
                seen.add(key)
                concepts.append({"concept": str(concept), "type": str(concept_type)})
            concepts.sort(
                key=lambda item: (
                    CONCEPT_PRIORITY.get(item.get("type", ""), 0),
                    len(str(item.get("concept") or "").split()),
                ),
                reverse=True,
            )
            section["concepts"] = concepts
        story_plan["agenda"] = self._agenda_from_top_concepts(sections)
        return story_plan

    def _attach_section_visual_plan(self, story_plan: dict[str, Any]) -> dict[str, Any]:
        sections = story_plan.get("sections") or []
        for section in sections:
            text = str(section.get("text") or "")
            visual_plan: list[dict[str, Any]] = []
            for concept in section.get("concepts") or []:
                candidate = {
                    "concept": dict(concept),
                    "visual": map_concept_to_visual(concept),
                    "beats": generate_beats(
                        {**concept, "weight_level": section.get("weight", {}).get("level", "medium")},
                        text,
                    ),
                }
                visual_plan.append(self._safe_visual_item(candidate, text))
            numeric_plan = self._numeric_visual_plan(text)
            if self._is_valid_visual_item(numeric_plan):
                section["visual_plan"] = [numeric_plan]
                continue
            if visual_plan:
                section["visual_plan"] = visual_plan
                continue
            if text.strip():
                section["visual_plan"] = [self._fallback_visual_item(text)]
            else:
                section["visual_plan"] = []
        return story_plan

    def _split_story_sentences(self, text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
        return [part.strip() for part in parts if part.strip()]

    def _sentence_starts_new_section(self, sentence: str) -> bool:
        lowered = sentence.lower().strip()
        if any(lowered.startswith(token) for token in ("but", "however", "so", "now", "because", "this means")):
            return True
        return len(sentence.split()) > 15

    def _keep_story_sentence(self, sentence: str, allow_short: bool = False) -> bool:
        lowered = sentence.lower().strip()
        if len(sentence.split()) < 6 and not allow_short:
            return False
        if any(phrase in lowered for phrase in ("for instance", "let's", "we've all", "you know")):
            return False
        return True

    def _normalize_text(self, text: str) -> str:
        return " ".join(str(text or "").strip().split())

    def _shares_topic_with_current(self, current: list[str], next_sentence: str) -> bool:
        if not next_sentence:
            return False
        current_terms = self._topic_terms(" ".join(current))
        next_terms = self._topic_terms(next_sentence)
        return bool(current_terms.intersection(next_terms))

    def _topic_terms(self, text: str) -> set[str]:
        keywords = {
            "debt",
            "credit",
            "payment",
            "minimum",
            "interest",
            "inflation",
            "savings",
            "investment",
            "returns",
            "budget",
            "budgeting",
            "income",
            "fund",
            "loan",
            "emi",
            "sip",
            "trap",
            "risk",
        }
        return {word for word in re.findall(r"[a-z]+", text.lower()) if word in keywords}

    def _section_word_count(self, section: list[str]) -> int:
        return len(" ".join(section).split())

    def _merge_short_sections(self, groups: list[list[str]]) -> list[list[str]]:
        merged: list[list[str]] = []
        index = 0
        while index < len(groups):
            current = list(groups[index])
            next_group = groups[index + 1] if index + 1 < len(groups) else None
            if (
                self._section_word_count(current) < 8
                and next_group is not None
                and self._can_merge_short_sections(current, next_group)
            ):
                current.extend(groups[index + 1])
                index += 1
            merged.append(current)
            index += 1
        return merged

    def _can_merge_short_sections(self, current: list[str], next_group: list[str]) -> bool:
        current_text = " ".join(current)
        next_text = " ".join(next_group)
        current_terms = self._topic_terms(current_text)
        next_terms = self._topic_terms(next_text)
        if current_terms and next_terms:
            return True
        return bool(current_terms.intersection(next_terms))

    def _agenda_from_top_concepts(self, sections: list[dict[str, Any]]) -> list[str]:
        ranked: list[tuple[float, int, str]] = []
        for section in sections:
            score = float((section.get("weight") or {}).get("score") or 0.0)
            for concept in section.get("concepts") or []:
                concept_text = str(concept.get("concept") or "").strip()
                if concept_text:
                    concept_type = str(concept.get("type") or "")
                    ranked.append((score, CONCEPT_PRIORITY.get(concept_type, 0), concept_text))
        ranked.sort(key=lambda item: (item[1], item[0], len(item[2].split())), reverse=True)
        agenda: list[str] = []
        seen: set[str] = set()
        for _, _, concept_text in ranked:
            key = concept_text.lower()
            if key in seen:
                continue
            seen.add(key)
            agenda.append(concept_text)
            if len(agenda) == 3:
                break
        return agenda

    def _numeric_visual_plan(self, text: str) -> dict[str, Any] | None:
        numeric_phrases = self._numeric_phrases(text)
        if not self._numeric_visual_allowed(text, numeric_phrases):
            return None
        if len(numeric_phrases) >= 2:
            strongest = numeric_phrases[-1]
            return {
                "concept": {"concept": strongest, "type": "numeric"},
                "visual": {
                    "component": "CalculationStrip",
                    "props": {"values": numeric_phrases[:3]},
                },
                "beats": {
                    "beats": self._numeric_beats(numeric_phrases[:3], strongest),
                },
            }
        strongest = numeric_phrases[0]
        return {
            "concept": {"concept": strongest, "type": "numeric"},
            "visual": {
                "component": "StatCard",
                "props": {"title": strongest},
            },
            "beats": {
                "beats": [{"component": "StatCard", "text": strongest}],
            },
        }

    def _unique_beat_values(self, values: list[str], strongest: str) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(value)
        if strongest.lower() not in seen:
            unique.append(strongest)
        return unique[:3]

    def _numeric_phrases(self, text: str) -> list[str]:
        if not re.search(r"(₹|Rs\.?\s*|\d|%)", text, flags=re.IGNORECASE):
            return []
        pattern = r"(?:₹\s*|Rs\.?\s*)?\d[\d,]*(?:\.\d+)?\s*(?:%|years?|months?|lakhs?)?"
        matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
        phrases: list[str] = []
        for match in matches:
            token = " ".join(match.group(0).strip().split())
            if not token or not re.search(r"\d", token):
                continue
            label = self._numeric_label(text, match.start(), match.end())
            phrase = f"{token} {label}".strip() if label else token
            phrases.append(" ".join(phrase.split()))
        return self._unique_beat_values(phrases, phrases[-1] if phrases else "")

    def _numeric_label(self, text: str, start: int, end: int) -> str:
        before_words = re.findall(r"[a-z]+", text[max(0, start - 28) : start].lower())
        after_words = re.findall(r"[a-z]+", text[end : min(len(text), end + 28)].lower())
        keywords = {
            "interest": "interest",
            "bill": "bill",
            "balance": "balance",
            "debt": "debt",
            "payment": "payment",
            "salary": "salary",
            "return": "return",
            "returns": "returns",
            "cost": "cost",
            "emi": "emi",
            "principal": "principal",
            "minimum": "payment",
            "due": "payment",
        }
        for word in after_words[:3]:
            if word in keywords:
                return keywords[word]
        for word in reversed(before_words[-3:]):
            if word in keywords:
                return keywords[word]
        return ""

    def _numeric_beats(self, numeric_phrases: list[str], strongest: str) -> list[dict[str, str]]:
        values = self._unique_beat_values(numeric_phrases, strongest)
        if len(values) >= 3:
            return [
                {"component": "StatCard", "text": values[0]},
                {"component": "CalculationStrip", "text": values[1]},
                {"component": "StatCard", "text": values[2]},
            ]
        if len(values) == 2:
            return [
                {"component": "StatCard", "text": values[0]},
                {"component": "CalculationStrip", "text": values[1]},
            ]
        return [{"component": "StatCard", "text": values[0]}] if values else [{"component": "StatCard", "text": strongest}]

    def _numeric_visual_allowed(self, text: str, numeric_phrases: list[str]) -> bool:
        if not numeric_phrases:
            return False
        lowered = text.lower()
        has_comparison = any(word in lowered for word in (" more ", " less ", " vs ", " versus "))
        has_transformation = any(word in lowered for word in (" increase", " increases", " reduce", " reduces", " grow", " grows "))
        if len(numeric_phrases) >= 2:
            return True
        return has_comparison or has_transformation

    def _is_valid_visual_item(self, item: dict[str, Any] | None) -> bool:
        if not item:
            return False
        visual = item.get("visual") or {}
        props = visual.get("props") or {}
        title = str(props.get("title", "")).strip()
        if "title" in props and not title:
            return False
        beats = (item.get("beats") or {}).get("beats") or []
        if not beats:
            return False
        if any(not str(beat.get("text", "")).strip() for beat in beats):
            return False
        concept_text = str((item.get("concept") or {}).get("concept", "")).strip()
        if not concept_text:
            return False
        return True

    def _safe_visual_item(self, item: dict[str, Any], section_text: str) -> dict[str, Any]:
        if self._is_valid_visual_item(item):
            return item
        return self._fallback_visual_item(section_text)

    def _fallback_visual_item(self, section_text: str) -> dict[str, Any]:
        fallback_text = self._fallback_text(section_text)
        return {
            "concept": {"concept": fallback_text, "type": "fallback"},
            "visual": {
                "component": "ConceptCard",
                "props": {"title": fallback_text.upper()},
            },
            "beats": {
                "beats": [{"component": "ConceptCard", "text": fallback_text}],
            },
        }

    def _fallback_text(self, section_text: str) -> str:
        words = [word for word in re.findall(r"[A-Za-z0-9₹%]+", section_text) if word]
        text = " ".join(words[:3]).strip()
        return text or "Key Idea"

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
