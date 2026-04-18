from __future__ import annotations

import json
import re
import ssl
from urllib import error, request
from typing import Any

import certifi
from flask import current_app
import requests

from ..models.repository import ProjectRepository, utcnow
from .run_log import RunLogger

TENSION_WORDS = {
    "why",
    "how",
    "never",
    "secret",
    "mistake",
    "truth",
    "wrong",
    "actually",
    "shocking",
    "hidden",
}

DEFAULT_TARGET_DURATION_MINUTES = 8
DEFAULT_CHANNEL_NICHE = "personal finance India"
DEFAULT_SCRIPT_TONE = "confident, direct, slightly provocative"
VALID_VISUAL_TYPES = {"graph", "broll", "motion_text"}
VALID_TENSION_TYPES = {
    "curiosity_gap",
    "shocking_statistic",
    "contrarian_claim",
    "common_mistake_reveal",
    "before_after",
}


class ScriptService:
    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.logger = RunLogger()

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
            titles_json=payload["titles"],
            description_text=payload["description"],
            tags_json=payload["tags"],
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
        self.repo.update_script_version(
            script_version_id,
            hook_json=json.dumps(payload["hook"]),
            outro_json=json.dumps(payload["outro"]),
            titles_json=json.dumps(payload["titles"]),
            description_text=payload["description"],
            tags_json=json.dumps(payload["tags"]),
            full_script_json=json.dumps(payload),
            user_edited_at=utcnow(),
        )
        self.logger.log("script_edit", "completed", "Saved manual script edits.", project_id)

    def load_script_payload(self, script_version: dict[str, Any]) -> dict[str, Any]:
        raw = script_version["full_script_json"]
        return json.loads(raw) if isinstance(raw, str) else raw

    def validate_hook(self, hook: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if float(hook.get("estimated_duration_sec", 0)) > 7:
            errors.append("Hook must be 7 seconds or under.")
        narration = str(hook.get("narration", "")).strip()
        narration_words = re.findall(r"\b[\w']+\b", narration.lower())
        has_tension_word = any(word in TENSION_WORDS for word in narration_words)
        has_question = "?" in narration
        if not (has_tension_word or has_question):
            errors.append("Hook must include a curiosity/tension signal.")
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
                "visual_instruction": payload["hook"]["visual_instruction"],
                "visual_type": payload["hook"]["visual_type"],
            }
        ]
        for index, scene in enumerate(payload["scenes"], start=1):
            scene_rows.append(
                {
                    "scene_order": index,
                    "kind": scene.get("kind", "body"),
                    "narration_text": scene["narration"],
                    "visual_instruction": scene["visual_instruction"],
                    "visual_type": scene["visual_type"],
                }
            )
        scene_rows.append(
            {
                "scene_order": len(scene_rows),
                "kind": "outro",
                "narration_text": payload["outro"]["narration"],
                "visual_instruction": payload["outro"]["visual_instruction"],
                "visual_type": payload["outro"]["visual_type"],
            }
        )
        return scene_rows

    def _generate_payload(self, topic: str, angle: str, prompt: str) -> tuple[dict[str, Any], str]:
        provider = current_app.config.get("LLM_PROVIDER", "auto")
        if provider in {"auto", "groq"} and current_app.config.get("GROQ_API_KEY"):
            try:
                payload = self._groq_script(topic, angle, prompt, current_app.config["GROQ_API_KEY"])
                payload = self._normalize_payload(payload, topic, angle)
                payload.setdefault("meta", {})["source"] = "live_groq"
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
                return payload, "live Claude API"
            except (error.URLError, ValueError, KeyError, json.JSONDecodeError) as exc:
                self.logger.log(
                    "script_generation",
                    "failed",
                    f"Claude generation failed ({exc}). Falling back to demo script.",
                )
        payload = self._demo_script(topic, angle)
        payload.setdefault("meta", {})["source"] = "demo"
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
        return (
            "You are an expert YouTube scriptwriter specializing in finance content.\n"
            "You have deep knowledge of what makes finance videos perform well — strong hooks, clear explanations, emotional engagement, and retention-driving structure.\n"
            "Your job is to write a complete, ready-to-edit YouTube video script based on the inputs provided below.\n\n"
            "INPUTS:\n"
            f"- Topic: {topic}\n"
            f"- Angle: {angle}\n"
            f"- Target duration: {target_duration_minutes} minutes\n"
            f"- Channel niche: {niche}\n"
            f"- Tone: {tone}\n\n"
            "SCRIPT RULES — follow every single one:\n\n"
            "HOOK (first 5–7 seconds):\n"
            "- Must create immediate tension, curiosity, or shock\n"
            "- Must NOT start with \"In this video\", \"Today we\", \"Welcome back\", or any greeting\n"
            "- Must NOT start with a question that the viewer can immediately answer with yes or no\n"
            "- Must end on an unresolved claim, a surprising statistic, or a tension point that makes the viewer need to keep watching\n"
            "- Must be under 7 seconds when read aloud at a natural pace (roughly 18–20 words max)\n"
            "- Must feel like the viewer walked into the middle of something important\n\n"
            "SCRIPT BODY:\n"
            "- Every scene must have ONE clear idea only — no cramming two points into one scene\n"
            "- Use simple language — explain like you are talking to a smart 25-year-old, not a finance professor\n"
            "- No jargon without immediate plain-English explanation right after\n"
            "- Vary sentence length — short punchy sentences after longer explanatory ones\n"
            "- Every 60–90 seconds of narration must have a retention anchor\n"
            "- Do NOT repeat the same point in different words across scenes\n"
            "- Do NOT use filler phrases like essentially, basically, at the end of the day, in conclusion, to summarize\n"
            "- Do NOT be preachy or moralize — present facts and let the viewer decide\n"
            "- Do NOT use passive voice — always active voice\n\n"
            "DATA REQUIREMENT — MANDATORY:\n"
            "- Every scene that makes a factual claim MUST include at least one specific number, percentage, date, or named example\n"
            "- WRONG: \"Unemployment rates fell significantly under Trump\"\n"
            "- RIGHT: \"US unemployment hit 3.5% in February 2020 — the lowest in 50 years\"\n"
            "- WRONG: \"India's exports were affected by the trade war\"\n"
            "- RIGHT: \"India's exports to the US dropped 8.3% in 2019 during peak tariff tensions\"\n"
            "- If you cannot include a specific data point for a claim, do not make that claim. Remove the scene entirely\n\n"
            "HOOK REWRITE RULE:\n"
            "- Before finalizing the hook, ask yourself: \"If someone heard only this sentence with no context, would they NEED to keep watching to resolve the tension?\"\n"
            "- If the answer is no, rewrite it\n"
            "- BAD HOOK EXAMPLES: \"Trump's economy soared\" | \"The US economy changed under Trump\" | \"What Trump did to the economy will shock you\"\n"
            "- GOOD HOOK EXAMPLES: \"The decision Trump made in 2018 quietly cost Indian IT companies $4 billion — and most Indians still don't know about it\" | \"While everyone was watching the stock market, Trump changed one rule that affects every Indian sending money abroad\" | \"Three Indian companies doubled their revenue because of Trump's economy — and they're not the ones you'd expect\"\n\n"
            "OUTRO (last 15–20 seconds):\n"
            "- Do NOT say smash the like button or hit subscribe as the first sentence\n"
            "- End with a forward hook — give the viewer a reason to watch the next video or think about something after they leave\n"
            "- Include one soft CTA buried naturally in the outro\n\n"
            "VISUAL INSTRUCTIONS:\n"
            "- For every scene, write a clear plain-English visual instruction\n"
            "- Choose one visual type per scene from these three only: graph, broll, motion_text\n"
            "- For graph: specify chart type, data to show, and animation style\n"
            "- For broll: write a specific 3–5 word search query for stock footage\n"
            "- For motion_text: write the exact text on screen, under 10 words\n\n"
            "WHAT GREAT FINANCE CONTENT SOUNDS LIKE:\n"
            "- urgent, useful, specific, number-driven, and respectful of the viewer's time\n"
            "- slightly smarter after each scene\n"
            "- clear villain and clear payoff\n\n"
            "OUTPUT FORMAT:\n"
            "Return a single valid JSON object. No markdown. No explanation before or after. No code fences. Just the raw JSON.\n"
            "Use exactly this structure:\n"
            "{\n"
            '  "hook": {\n'
            '    "narration": "the hook text here",\n'
            '    "estimated_duration_sec": 6,\n'
            '    "tension_type": "curiosity_gap"\n'
            "  },\n"
            '  "scenes": [\n'
            "    {\n"
            '      "scene_index": 1,\n'
            '      "narration_text": "the narration for this scene",\n'
            '      "visual_type": "graph",\n'
            '      "visual_instruction": "animated bar chart showing India GDP growth from 2015 to 2024, bars growing upward one by one, dark background, white bars",\n'
            '      "estimated_duration_sec": 45\n'
            "    }\n"
            "  ],\n"
            '  "outro": {\n'
            '    "narration": "the outro narration here",\n'
            '    "estimated_duration_sec": 18\n'
            "  },\n"
            '  "suggested_titles": ["title option 1", "title option 2", "title option 3"],\n'
            '  "suggested_description": "the full YouTube description here, 150-200 words, SEO optimized with natural keyword usage",\n'
            '  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],\n'
            '  "tension_type_used": "curiosity_gap"\n'
            "}\n"
            f"The total of all estimated_duration_sec across hook + all scenes + outro must equal approximately {target_duration_minutes * 60} seconds.\n"
            "Now write the complete script for the topic and angle provided above. Return only the JSON. Nothing else.\n"
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
                        "You never add explanations, apologies, markdown formatting, or code fences. "
                        "You follow every instruction in the prompt precisely. "
                        "You never break character or add commentary outside the JSON object."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 1800,
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
        required_top = {"hook", "scenes", "outro", "titles", "description", "tags"}
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
                "narration": str(hook.get("narration") or hook.get("text") or f"The hidden truth about {topic.lower()}"),
                "estimated_duration_sec": self._coerce_duration(hook.get("estimated_duration_sec"), 6),
                "tension_type": self._normalize_tension_type(
                    hook.get("tension_type") or payload.get("tension_type_used"),
                ),
                "visual_instruction": str(
                    hook.get("visual_instruction")
                    or f"{self._short_motion_text(topic)}"
                ),
                "visual_type": self._normalize_visual_type(hook.get("visual_type"), default="motion_text"),
            },
            "scenes": [],
            "outro": {
                "narration": str(outro.get("narration") or outro.get("text") or f"Fix {angle.lower()} before it costs you another year."),
                "visual_instruction": str(
                    outro.get("visual_instruction")
                    or "CALM SUMMARY"
                ),
                "visual_type": self._normalize_visual_type(outro.get("visual_type"), default="motion_text"),
            },
            "titles": self._normalize_titles(payload.get("suggested_titles") or payload.get("titles"), topic, angle),
            "description": str(
                payload.get("suggested_description")
                or payload.get("description")
                or f"A practical breakdown of {topic.lower()} with a focus on {angle.lower()}."
            ),
            "tags": self._normalize_tags(payload.get("tags"), topic, angle),
            "meta": payload.get("meta", {}),
        }

        for index, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                continue
            visual_type = self._normalize_visual_type(scene.get("visual_type"))
            normalized["scenes"].append(
                {
                    "kind": scene.get("kind", "body"),
                    "scene_index": int(scene.get("scene_index") or index),
                    "narration": str(
                        scene.get("narration")
                        or scene.get("narration_text")
                        or scene.get("content")
                        or f"Scene {index} expands the main idea around {topic.lower()}."
                    ),
                    "visual_instruction": str(
                        scene.get("visual_instruction")
                        or self._fallback_visual_instruction(visual_type, topic, angle, index)
                    ),
                    "visual_type": visual_type,
                    "estimated_duration_sec": self._coerce_duration(
                        scene.get("estimated_duration_sec"),
                        35,
                    ),
                }
            )

        if not normalized["scenes"]:
            normalized["scenes"] = self._demo_script(topic, angle)["scenes"]

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

    def _normalize_visual_type(self, value: Any, default: str = "broll") -> str:
        visual_type = str(value or "").strip().lower()
        return visual_type if visual_type in VALID_VISUAL_TYPES else default

    def _normalize_tension_type(self, value: Any) -> str:
        tension_type = str(value or "").strip().lower()
        return tension_type if tension_type in VALID_TENSION_TYPES else "curiosity_gap"

    def _coerce_duration(self, value: Any, default: int) -> int:
        try:
            duration = int(round(float(value)))
            return duration if duration > 0 else default
        except (TypeError, ValueError):
            return default

    def _short_motion_text(self, topic: str) -> str:
        words = re.findall(r"\b[\w']+\b", topic.upper())
        return " ".join(words[:4])[:40] or "HIDDEN MONEY TRUTH"

    def _fallback_visual_instruction(self, visual_type: str, topic: str, angle: str, index: int) -> str:
        if visual_type == "graph":
            return (
                f"animated bar chart comparing a bad {angle.lower()} outcome versus a better money system, "
                "bars growing upward one by one, dark background, white labels"
            )
        if visual_type == "motion_text":
            return self._short_motion_text(f"{topic} {index}")
        return f"{topic.lower()} {angle.lower()} person"

    def _demo_script(self, topic: str, angle: str) -> dict[str, Any]:
        return {
            "hook": {
                "narration": f"Why do smart people still get {topic.lower()} completely wrong?",
                "estimated_duration_sec": 6,
                "tension_type": "curiosity_gap",
                "visual_instruction": f"Bold motion text showing the hidden truth about {angle}",
                "visual_type": "motion_text",
            },
            "scenes": [
                {
                    "kind": "body",
                    "narration": f"Most people think {topic.lower()} is about discipline, but the real issue is invisible defaults.",
                    "visual_instruction": "Show a clean dark chart comparing salary growth versus savings rate over five years.",
                    "visual_type": "graph",
                },
                {
                    "kind": "body",
                    "narration": f"In your 20s, one repeated {angle.lower()} can quietly erase years of progress.",
                    "visual_instruction": "Find urban b-roll of young adults paying with cards, checking bills, and scrolling banking apps.",
                    "visual_type": "broll",
                },
                {
                    "kind": "body",
                    "narration": "The fix is simple: automate the right decision before emotion gets a vote.",
                    "visual_instruction": "Use bold kinetic text that highlights automate before emotion.",
                    "visual_type": "motion_text",
                },
            ],
            "outro": {
                "narration": "If you want money to feel easier, fix the system before you blame yourself.",
                "visual_instruction": "End with a calm motion text summary and subscribe prompt.",
                "visual_type": "motion_text",
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
