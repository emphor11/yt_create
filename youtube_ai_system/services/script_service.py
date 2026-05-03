from __future__ import annotations

import json
import re
from typing import Any
from urllib import error

from flask import current_app
import requests

from ..models.repository import ProjectRepository, utcnow
from .narration_refiner import refine as refine_narration
from .run_log import RunLogger
from .script_scene_refiner import ScriptSceneRefiner
from .story_pipeline import StoryPipeline
from .visual_scene_normalizer import visual_script_prompt_contract

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


class ScriptService:
    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.logger = RunLogger()
        self.story_pipeline = StoryPipeline(logger=self.logger)
        self.scene_refiner = ScriptSceneRefiner()

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
        if float(hook.get("duration", hook.get("estimated_duration_sec", 0)) or 0) > 30:
            errors.append("Hook must be 30 seconds or under.")

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
                f"groq_key={'yes' if bool(current_app.config.get('GROQ_API_KEY')) else 'no'}."
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
        return (
            "You are a world-class YouTube script writer for a finance-explanation channel in the style of 20 Minute University-style videos (e.g. “All of Economics in 20 minutes”).\n\n"
            "Your only job is to generate raw spoken-style narration that will be processed by a deterministic system later.\n\n"
            "---\n\n"
            "OUTPUT REQUIREMENTS:\n\n"
            "* Output only the required JSON object\n"
            "* Narration fields must contain spoken narration only\n"
            "* No markdown, no bullet points, no extra text\n"
            "* No section labels like \"Hook\", \"Body\", or \"Outro\" inside narration text\n\n"
            "---\n\n"
            "TONE & STYLE:\n\n"
            "* Direct, slightly sarcastic, warm, knowledgeable\n"
            "* Conversational (talk to the viewer, not at them)\n"
            "* Light humor + relatable analogies\n"
            "* Use Indian finance context naturally (salary, EMI, SIP, inflation, debt trap, lifestyle inflation, compound interest, risk-vs-return, diversification, FOMO, etc.)\n"
            "* Keep language simple and spoken-friendly\n\n"
            "---\n\n"
            "CORE WRITING RULES:\n\n"
            "1. ONE IDEA PER SENTENCE\n"
            "Each sentence must express only ONE clear idea.\n"
            "Do NOT combine multiple ideas using \"and\", \"because\", \"which\", etc.\n\n"
            "2. SHORT SENTENCES\n"
            "Keep sentences short (ideally under 20 words).\n"
            "Split complex thoughts into multiple short sentences.\n\n"
            "3. CONCEPT GROUPING\n"
            "Each concept should be expressed using 1–3 consecutive sentences.\n"
            "Do NOT mix multiple concepts together in the same group of sentences.\n\n"
            "4. EXPLICIT CONCEPT VISIBILITY\n"
            "The core concept must be clearly visible from the sentence itself.\n"
            "Avoid vague phrases like “this situation”, “this thing”, “this example”.\n"
            "Use clear, concrete terms like:\n\n"
            "* emergency fund\n"
            "* debt trap\n"
            "* inflation\n"
            "* lifestyle inflation\n"
            "* compound interest\n"
            "* risk-vs-return\n"
            "* diversification\n"
            "* FOMO\n"
            "* panic-selling\n"
            "* behavioral bias\n\n"
            "---\n\n"
            "STRUCTURE (NATURAL FLOW ONLY):\n\n"
            "HOOK:\n\n"
            "* First 2–5 sentences\n"
            "* Start with strong curiosity or tension\n"
            "* Must pass this hook contract: under 25 words, and include either a question mark/\"why\", or a ₹ amount with a negative finance word like gone/leak/drain/debt/cost, or a percentage/big number with a people group\n"
            "* Prefer hooks like: \"Why does your ₹50,000 salary feel gone by day 20?\"\n"
            "* Avoid validator-weak hooks like: \"You work hard but still struggle to save.\"\n"
            "* No greetings, no \"hey guys\", no \"welcome back\"\n"
            "* Make the viewer feel like they are already in the problem (salary, EMIs, lack of savings, debt, inflation, investing confusion)\n\n"
            "BODY:\n\n"
            "* Continuous flow of ideas with no labels, markdown, or bullet points inside narration\n"
            "* Each body scene should focus on one concept group\n"
            "* Each body scene must be 70–110 words across 5–8 short sentences\n"
            "* Each scene must include a concrete example, a mechanism, and a consequence\n"
            "* Each concept should be explained in a complete visual sequence, not compressed into 1–3 tiny sentences\n"
            "* For 8–12 minute scripts, prefer 8–12 body scenes\n"
            "* Create enough body scenes for the requested duration\n"
            "* Use relatable Indian-finance examples: salary, rent, EMI, SIP, FD, mutual funds, loans, crypto, etc.\n"
            "* Prefer light, slightly irreverent humor and analogies\n\n"
            "OUTRO:\n\n"
            "* Last 3–6 sentences\n"
            "* Quick recap of the main idea in 1–2 lines\n"
            "* One clear, practical, non-guarantee takeaway (track EMIs, build an emergency fund, diversify, reduce debt, avoid panic-selling, etc.)\n"
            "* End with one strong, memorable line that sticks in the viewer’s mind\n\n"
            "---\n\n"
            "CONSTRAINTS:\n\n"
            "* Generate visual planning fields for body scenes, but keep narration fields spoken-only\n"
            "* Do NOT add extra fields in the JSON apart from the exact ones listed in the OUTPUT FORMAT below\n"
            "* Do NOT invent fake factual claims, guaranteed returns, or predictions (no \"guaranteed 25% returns\", no \"XYZ stock will go to 1000\")\n"
            "* You may use simple hypothetical numbers only when clearly framed as examples\n"
            "* Duration fields are rough estimates only, but body scenes must still contain enough narration for the target duration\n"
            "* Do NOT output section labels like \"Hook\", \"Body\", or \"Outro\" inside the narration text\n\n"
            "---\n\n"
            "INPUT VARIABLES (already passed by system):\n\n"
            "* CHANNEL_DESCRIPTION\n"
            "* TOPIC\n"
            "* AUDIENCE\n"
            "* DURATION_APPROX\n\n"
            "Use them naturally in writing, but do NOT expose them as separate JSON keys.\n\n"
            f"CHANNEL_DESCRIPTION: {niche}\n"
            f"TOPIC: {topic}\n"
            f"AUDIENCE: {angle}\n"
            f"DURATION_APPROX: {target_duration_minutes} minutes\n"
            f"TONE_HINT: {tone}\n\n"
            f"{visual_script_prompt_contract()}\n"
            "OUTPUT FORMAT:\n"
            "Return one valid JSON object only.\n"
            "{\n"
            '  "hook": {"narration": "string", "duration": 6, "tension_type": "curiosity_gap"},\n'
            '  "scenes": [{"scene_index": 1, "kind": "body", "narration": "string", "duration": 45, "visual_intent": "what the viewer sees", "visual_beats": ["beat 1", "beat 2", "beat 3"], "numbers": ["only numbers spoken in narration"], "emotion": "anxiety", "mechanism": "lifestyle_inflation"}],\n'
            '  "outro": {"narration": "string", "duration": 18},\n'
            '  "suggested_titles": ["title option 1", "title option 2"],\n'
            '  "suggested_description": "string",\n'
            '  "tags": ["tag1", "tag2"],\n'
            '  "tension_type_used": "curiosity_gap"\n'
            "}\n"
            f"The total duration across hook + scenes + outro should be approximately {target_duration_minutes * 60} seconds, but this is soft guidance; focus on natural flow, not exact timing.\n"
            "Return only JSON.\n"
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
        self.logger.log("script_generation", "running", f"Raw Groq response before parsing: {text}")
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
            narration = self._refined_narration(
                str(
                    scene.get("narration")
                    or scene.get("narration_text")
                    or scene.get("content")
                    or self._fallback_scene(index, topic)
                )
            )
            refined_scene = self.scene_refiner.refine_scene(
                scene,
                narration,
                index=index,
                topic=topic,
                angle=angle,
            )
            narration = str(refined_scene["narration"])
            normalized_scene = {
                "kind": "body",
                "scene_index": index,
                "narration": narration,
                "duration": self._coerce_duration(scene.get("duration", scene.get("estimated_duration_sec")), 45),
            }
            normalized["scenes"].append(normalized_scene)
            planning_scene = dict(normalized_scene)
            visual_scene = dict(refined_scene.get("visual_scene") or self._visual_scene_from_raw_scene(scene, narration))
            raw_visual_scene = self._visual_scene_from_raw_scene(scene, narration)
            if visual_scene and not refined_scene.get("allow_grouping"):
                planning_scene["visual_scene"] = visual_scene
            planning_scenes.append(planning_scene)

        if not normalized["scenes"]:
            normalized["scenes"] = self._demo_script(topic, angle)["scenes"]

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
        source = scene.get("visual_scene") if isinstance(scene.get("visual_scene"), dict) else scene
        visual_scene: dict[str, Any] = {"narration": narration}
        for key in ("visual_intent", "visual_beats", "numbers", "emotion", "mechanism"):
            if key in source:
                visual_scene[key] = source[key]
        return visual_scene if len(visual_scene) > 1 else {}

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
