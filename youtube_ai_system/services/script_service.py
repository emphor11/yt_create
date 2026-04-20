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
from .render_spec_service import RenderSpecService
from .run_log import RunLogger

TENSION_KEYWORDS = {
    "?", "why", "how", "never", "secret", "mistake", "truth", "wrong",
    "actually", "shocking", "reveal", "hidden", "nobody",
    "most people", "what happens", "find out", "you think",
    "real reason",
}

PEOPLE_GROUP_WORDS = {
    "indians", "people", "salary", "workers", "families",
    "earners", "graduates", "investors",
}

NEGATIVE_IMPLICATION_WORDS = {
    "lose", "lost", "losing", "paying", "gone", "spent", "debt",
    "broke", "savings", "interest", "leak", "drain", "cost",
}

DEFAULT_TARGET_DURATION_MINUTES = 8
DEFAULT_CHANNEL_NICHE = "personal finance India"
DEFAULT_SCRIPT_TONE = "confident, direct, slightly provocative"
BEAT_VISUAL_TYPES = {
    "stat_explosion",
    "text_burst",
    "chart",
    "split_comparison",
    "broll_caption",
    "reaction_card",
}
VALID_VISUAL_TYPES = {"graph", "broll", "motion_text", *BEAT_VISUAL_TYPES}
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
        self.render_specs = RenderSpecService()
        self._recent_visual_texts: list[str] = []
        self._used_visual_signatures: set[str] = set()
        self._generic_fallback_count = 0
        self._last_scene_component = ""
        self._last_scene_pattern = ""

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
        narration_lower = narration.lower()
        word_count = len(narration.split())

        # --- Condition A: tension keyword or question mark ---
        condition_a = False
        for keyword in TENSION_KEYWORDS:
            if keyword in narration_lower:
                condition_a = True
                break

        # --- Condition B: percentage/large number + people group ---
        condition_b = False
        has_pct = "%" in narration
        large_numbers = [int(m) for m in re.findall(r"\d+", narration) if int(m) > 1000]
        has_large_number = len(large_numbers) > 0
        has_people_group = any(pg in narration_lower for pg in PEOPLE_GROUP_WORDS)
        if (has_pct or has_large_number) and word_count <= 25 and has_people_group:
            condition_b = True

        # --- Condition C: rupee symbol + negative implication ---
        condition_c = False
        has_rupee = "₹" in narration
        has_negative = any(nw in narration_lower for nw in NEGATIVE_IMPLICATION_WORDS)
        if has_rupee and has_negative:
            condition_c = True

        if not (condition_a or condition_b or condition_c):
            guidance_lines = [
                "Hook must include a tension signal. Satisfy ANY ONE of these:",
                "  A) Include a tension keyword or question mark: "
                + ", ".join(sorted(TENSION_KEYWORDS)),
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
                "visual_instruction": payload["hook"]["visual_instruction"],
                "visual_type": payload["hook"]["visual_type"],
                "visual_plan_json": json.dumps(payload["hook"].get("visual_beats") or []),
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
                    "visual_plan_json": json.dumps(scene.get("visual_beats") or []),
                }
            )
        scene_rows.append(
            {
                "scene_order": len(scene_rows),
                "kind": "outro",
                "narration_text": payload["outro"]["narration"],
                "visual_instruction": payload["outro"]["visual_instruction"],
                "visual_type": payload["outro"]["visual_type"],
                "visual_plan_json": json.dumps(payload["outro"].get("visual_beats") or []),
            }
        )
        return scene_rows

    def _generate_payload(self, topic: str, angle: str, prompt: str) -> tuple[dict[str, Any], str]:
        provider = current_app.config.get("LLM_PROVIDER", "auto")
        if self._ten_minute_finance_enabled() and provider in {"auto", "groq"} and current_app.config.get("GROQ_API_KEY"):
            try:
                skeleton_prompt = self._build_ten_minute_finance_prompt(topic, angle, include_beats=False)
                payload = self._groq_script(topic, angle, skeleton_prompt, current_app.config["GROQ_API_KEY"])
                payload = self._normalize_payload(payload, topic, angle)
                payload = self._attach_visual_beats_with_groq(payload, current_app.config["GROQ_API_KEY"])
                payload = self._normalize_payload(payload, topic, angle)
                payload.setdefault("meta", {})["source"] = "live_groq_ten_minute_finance"
                return payload, "live Groq API with visual beats"
            except (error.URLError, ValueError, KeyError, json.JSONDecodeError) as exc:
                self.logger.log(
                    "script_generation",
                    "failed",
                    f"10 Minute Finance Groq generation failed ({exc}). Falling back to the next provider.",
                )

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
        payload = self._normalize_payload(payload, topic, angle)
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
        if self._ten_minute_finance_enabled():
            return self._build_ten_minute_finance_prompt(topic, angle, include_beats=True)
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
            "- These visuals are rendered in Remotion, so write instructions for a premium finance video package, not generic stock slides\n"
            "- For graph: specify chart type, exact data, title, unit, color, and the insight the viewer should notice\n"
            "- For broll: write a concrete footage/search idea plus the exact lower-third overlay text to burn into the Remotion template\n"
            "- For motion_text: write the exact headline and supporting fact on screen, using numbers wherever possible\n"
            "- Avoid vague phrases like 'show money' or 'financial animation'; every visual must reinforce a spoken claim\n\n"
            "GRAPH DATA RULE — MANDATORY:\n"
            "When visual_type is graph, the visual_instruction field MUST include "
            "actual data points in this exact format:\n\n"
            "For bar charts: \n"
            "'bar chart, data: Label1=Value1, Label2=Value2, Label3=Value3, "
            "title: Chart Title Here, unit: %, color: orange, insight: what changes fastest'\n\n"
            "For line charts:\n"
            "'line chart, data: Year1=Value1, Year2=Value2, Year3=Value3, "
            "title: Chart Title Here, unit: ₹, color: red, insight: where the trend becomes dangerous'\n\n"
            "For pie charts:\n"
            "'pie chart, data: Label1=Percentage1%, Label2=Percentage2%, "
            "title: Chart Title Here'\n\n"
            "For number reveals:\n"
            "'number reveal, value: 40%, label: Credit Card Interest Rate India'\n\n"
            "If you do not have exact data, use realistic approximate figures "
            "consistent with Indian financial statistics. Label them clearly.\n\n"
            "NEVER write a graph instruction without data. A graph instruction "
            "without data is invalid and will fail rendering.\n\n"
            "MOTION TEXT RULE:\n"
            "When visual_type is motion_text, the visual_instruction field must "
            "contain the key information to display, not a description of what to show.\n\n"
            "WRONG: 'show a bold statement about savings'\n"
            "RIGHT: 'SAVINGS RATE DROPPING — only 4% of income saved'\n\n"
            "WRONG: 'lifestyle inflation warning'\n"
            "RIGHT: 'LIFESTYLE INFLATION — 75% spend more as they earn more'\n\n"
            "The visual_instruction for motion_text should be the actual text "
            "content, structured as: HEADLINE — supporting fact or stat\n\n"
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

    def _ten_minute_finance_enabled(self) -> bool:
        return str(current_app.config.get("CHANNEL_STYLE", "")).lower() == "ten_minute_finance"

    def _build_ten_minute_finance_prompt(self, topic: str, angle: str, include_beats: bool = True) -> str:
        visual_section = (
            "VISUAL BEATS — MANDATORY:\n"
            "For each scene, provide a visual_beats array with 4-6 beat objects.\n"
            "Each beat covers a 3-4 second window within the scene's narration.\n"
            "Use this decision order for every beat: intent → visual_logic → pattern → props → animation_intent.\n\n"
            "CONCRETENESS RULE — MANDATORY:\n"
            "Every beat must describe a concrete visual object, not an abstract editing label.\n"
            "visual_logic MUST be an object, not a sentence. Valid schemas only:\n"
            '- decay: {"type":"decay","input":"₹1,00,000","factor":"6% inflation","output":"₹94,000 real value"}\n'
            '- flow: {"type":"flow","source":"₹25,000 Salary","process":"₹23,000 Expenses","result":"₹2,000 Left"}\n'
            '- comparison: {"type":"comparison","left":"₹50,000 Debt","right":"₹18,000 Interest/year"}\n'
            '- growth: {"type":"growth","input":"₹5,000 SIP","rate":"12% return","output":"₹60,000 invested"}\n'
            "Each visual must include a number AND complete structure. \"6% inflation exists\" is invalid.\n"
            "INVALID visual_logic or props words: \"static_image\", \"narrative\", \"contrast\", \"flow\", \"statistic\", \"concept\", \"idea\", \"thing\", \"split screen\", \"show comparison\", \"display data\".\n"
            "Use numbers from narration first. If no numbers exist, use a contextual finance fallback; never invent unrelated random numbers.\n"
            "HOOK beats must be numeric, loss/contrast/extreme-based, with the primary headline at 6 words max. The first hook beat must not be a diagram.\n\n"
            "INTENT SELECTION RULES:\n"
            "- HOOK: opening curiosity/question/tension only\n"
            "- COMPARISON: two values/states/options explicitly contrasted\n"
            "- DATA: numeric trend or stat without direct comparison\n"
            "- EXPLANATION: process, system, cause-effect, money movement\n"
            "- EMPHASIS: short punchline/shock without structure\n"
            "- CONTEXT: real-world situation/background\n"
            "Priority: COMPARISON > EXPLANATION > DATA > EMPHASIS. Never use EMPHASIS if COMPARISON or EXPLANATION applies.\n\n"
            "PATTERN COMPATIBILITY MATRIX:\n"
            "- HOOK: EMPHASIS or CONTEXT\n"
            "- COMPARISON: COMPARISON only\n"
            "- DATA: GROWTH or COMPARISON\n"
            "- EXPLANATION: MONEY_FLOW, VALUE_DECAY, LOOP, or GROWTH\n"
            "- EMPHASIS: EMPHASIS only\n"
            "- CONTEXT: CONTEXT only\n\n"
            "PATTERN RULES:\n"
            "- VALUE_DECAY: value decreases over time due to inflation, tax, fees, erosion\n"
            "- MONEY_FLOW: money moves between people, entities, accounts, or categories\n"
            "- LOOP: repeated debt, credit, or habit cycle\n"
            "- GROWTH: compounding, SIP, investing, or value increasing over time\n"
            "- COMPARISON: explicit contrast between two values/states/options\n"
            "- EMPHASIS: punchline or key statement only\n"
            "- CONTEXT: real-world visual background or situational b-roll\n"
            "Do not default to EMPHASIS unless no structure exists.\n\n"
            "STYLE PROFILE 20mu_finance:\n"
            "- max FlowDiagram nodes: 5\n"
            "- text density: medium\n"
            "- animation speed: moderate\n"
            "- colors: red, orange, teal, navy, white\n"
            "- do not use FlowDiagram for more than 60% of beats\n"
            "- include at least one COMPARISON and one EMPHASIS per video when possible\n\n"
            "CAPTION RULES:\n"
            "- max 10 words\n"
            "- restate the insight simply\n"
            "- do not repeat narration verbatim\n\n"
            "GRAPH DATA RULE — MANDATORY:\n"
            "Do not invent chart data. Use only numbers stated in the narration or simple derived values from those numbers.\n"
            "Use charts ONLY when at least two real numeric points exist. If no real data exists, do not choose DATA/GROWTH chart.\n"
            "When using chart data, put real data in props.data or this format:\n"
            '"bar_chart, data: FD=6.5, Inflation=6.7, title: FD loses after inflation, color: red"\n\n'
            "MEME RULE:\n"
            "Do NOT reference copyrighted meme images. Use reaction_card instead.\n"
            "reaction_card text should be short, punchy, internet-native phrases:\n"
            '"wait what", "me every payday", "no cap", "this hits different", "bruh"\n\n'
        ) if include_beats else (
            "VISUAL FIELDS:\n"
            "For every hook, body scene, and outro, include only the legacy visual_instruction and visual_type fields.\n"
            "Do not include visual_beats in this call.\n\n"
        )
        beat_schema = (
            ',\n'
            '    "visual_beats": [\n'
            "      {\n"
            '        "beat_index": 0,\n'
            '        "intent": "HOOK|COMPARISON|DATA|EXPLANATION|EMPHASIS|CONTEXT",\n'
            '        "visual_logic": {"type": "decay|flow|comparison|growth", "input": "₹1,00,000", "factor": "6% inflation", "output": "₹94,000"},\n'
            '        "pattern": "MONEY_FLOW|VALUE_DECAY|COMPARISON|LOOP|GROWTH|EMPHASIS|CONTEXT",\n'
            '        "props": {"caption": "max 10 words"},\n'
            '        "animation_intent": "reveal|progress|highlight|transform",\n'
            '        "context_ref": "",\n'
            '        "duration_locked": false,\n'
            '        "estimated_start_sec": 0,\n'
            '        "estimated_duration_sec": 3\n'
            "      }\n"
            "    ]"
        ) if include_beats else ""
        return (
            "You are writing a script for \"10 Minute Finance\" — a YouTube channel that "
            "explains Indian personal finance like a smart friend who has read all the "
            "books and lost patience with people being broke. Think Crash Course energy "
            "meets brutal finance honesty meets Indian middle-class reality.\n\n"
            "TONE RULES — NON-NEGOTIABLE:\n"
            "- Write like you are roasting bad financial decisions with love\n"
            "- Every 2-3 sentences must end with either a surprising fact OR a relatable failure moment OR a punchline\n"
            "- Use specific rupee amounts and percentages for every single claim\n"
            "- Use these phrases naturally: \"here's the thing\", \"nobody tells you this\", \"okay so\", \"and here's where it gets worse\", \"plot twist\"\n"
            "- Mention real Indian context: FDs, PPF, Zerodha, SIP, SEBI, Indian inflation rate, Indian salary averages\n"
            "- Allow mild humor: dry wit, self-aware jokes, rhetorical questions\n"
            "- No jargon without immediate plain-English translation right after\n"
            "- Never say \"it is important to note\" or \"in conclusion\" or \"essentially\"\n\n"
            "SCRIPT STRUCTURE:\n"
            "- Hook: 5-7 seconds. Do NOT start with \"in this video\" or \"today we\". Start with a shocking stat or a relatable failure. End on unresolved tension.\n"
            "- Body scenes: 8-12 scenes, each 45-90 seconds of narration when read aloud. Each scene covers exactly ONE idea.\n"
            "- Outro: 15-20 seconds. Forward hook + one soft CTA buried naturally.\n"
            "- Total narration: approximately 1400-1600 words for a 10-minute video.\n\n"
            f"{visual_section}"
            "OUTPUT FORMAT — RETURN ONLY VALID JSON, NO MARKDOWN:\n"
            "{\n"
            '  "hook": {\n'
            '    "narration": "string",\n'
            '    "estimated_duration_sec": 6,\n'
            '    "tension_type": "shocking_statistic|curiosity_gap|contrarian_claim",\n'
            '    "visual_instruction": "string",\n'
            '    "visual_type": "motion_text|graph|broll"'
            f"{beat_schema}\n"
            "  },\n"
            '  "scenes": [\n'
            "    {\n"
            '      "scene_index": 1,\n'
            '      "kind": "body",\n'
            '      "narration": "string",\n'
            '      "visual_instruction": "string",\n'
            '      "visual_type": "graph|broll|motion_text",\n'
            '      "estimated_duration_sec": 60'
            f"{beat_schema}\n"
            "    }\n"
            "  ],\n"
            '  "outro": {\n'
            '    "narration": "string",\n'
            '    "estimated_duration_sec": 18,\n'
            '    "visual_instruction": "string",\n'
            '    "visual_type": "motion_text"'
            f"{beat_schema}\n"
            "  },\n"
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
                        "You never add explanations, apologies, markdown formatting, or code fences. "
                        "You follow every instruction in the prompt precisely. "
                        "You never break character or add commentary outside the JSON object."
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
        return self._extract_json_payload(text)

    def _attach_visual_beats_with_groq(self, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
        sections: list[tuple[str, dict[str, Any]]] = [("hook", payload["hook"])]
        sections.extend((f"scene {scene.get('scene_index')}", scene) for scene in payload["scenes"])
        sections.append(("outro", payload["outro"]))
        for label, section in sections:
            narration = str(section.get("narration") or "")
            duration = self._coerce_duration(section.get("estimated_duration_sec"), 30)
            try:
                section["visual_beats"] = self._groq_visual_beats(narration, duration, api_key)
            except (error.URLError, ValueError, KeyError, json.JSONDecodeError) as exc:
                self.logger.log(
                    "script_generation",
                    "failed",
                    f"Visual beat generation failed for {label} ({exc}). Using fallback beats.",
                )
                section["visual_beats"] = self._fallback_visual_beats(
                    section.get("visual_type"),
                    section.get("visual_instruction") or narration,
                    duration,
                )
        return payload

    def _groq_visual_beats(self, narration: str, duration: int, api_key: str) -> list[dict[str, Any]]:
        body = {
            "model": current_app.config["GROQ_MODEL"],
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You generate visual beat plans for a fast-paced YouTube finance video. "
                        "Return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Given this scene narration for a 10 Minute Finance YouTube video, "
                        "generate a visual_beats array with 4-6 beat objects. Use this order: "
                        "intent → visual_logic → pattern → props → animation_intent. "
                        "visual_logic must be an object, not a sentence. Use only these complete schemas: "
                        "{\"type\":\"decay\",\"input\":\"₹1,00,000\",\"factor\":\"6% inflation\",\"output\":\"₹94,000 real value\"}; "
                        "{\"type\":\"flow\",\"source\":\"₹25,000 Salary\",\"process\":\"₹23,000 Expenses\",\"result\":\"₹2,000 Left\"}; "
                        "{\"type\":\"comparison\",\"left\":\"₹50,000 Debt\",\"right\":\"₹18,000 Interest/year\"}; "
                        "{\"type\":\"growth\",\"input\":\"₹5,000 SIP\",\"rate\":\"12% return\",\"output\":\"₹60,000 invested\"}. "
                        "Each visual must include a number plus complete structure. \"6% inflation exists\" is invalid. "
                        "Never output vague placeholders or banned words like "
                        "\"static_image\", \"narrative\", \"contrast\", \"flow\", \"concept\", \"idea\", \"thing\", "
                        "\"split screen\", \"statistic\", \"show comparison\", or \"display data\". "
                        "Do not invent chart data. Use only numbers stated in the narration or simple derived values. "
                        "Use charts only when at least two real numeric points exist; otherwise use EMPHASIS. "
                        "Hook beats must be numeric, high-impact, loss/contrast/extreme-based, and the first hook beat must not be a diagram. "
                        "Intent priority: COMPARISON > EXPLANATION > DATA > EMPHASIS. "
                        "Never use EMPHASIS if COMPARISON or EXPLANATION applies. "
                        "Intent-pattern compatibility: HOOK=[EMPHASIS,CONTEXT], "
                        "COMPARISON=[COMPARISON], DATA=[GROWTH,COMPARISON], "
                        "EXPLANATION=[MONEY_FLOW,VALUE_DECAY,LOOP,GROWTH], "
                        "EMPHASIS=[EMPHASIS], CONTEXT=[CONTEXT]. "
                        "Pattern rules: VALUE_DECAY means value decreases due to inflation/tax/fees; "
                        "MONEY_FLOW means money moves between entities/categories; LOOP means repeated cycle; "
                        "GROWTH means compounding/SIP/value increasing; COMPARISON means explicit contrast; "
                        "CONTEXT means b-roll/background. "
                        "Props must match the pattern. FlowDiagram props use nodes with id, label, role "
                        "(source, process, modifier, result, actor, sink), optional children, and connections. "
                        "Captions must be max 10 words, simpler than narration, and not copied from narration. "
                        "Do not use FlowDiagram for more than 60% of beats; include comparison and emphasis when possible. "
                        "Return only a JSON object shaped as {\"visual_beats\": [...]} with beat_index, "
                        "intent, visual_logic, pattern, props, animation_intent, context_ref, duration_locked, "
                        "estimated_start_sec, estimated_duration_sec. "
                        f"Scene duration target: {duration} seconds.\n\n"
                        f"Scene narration: {narration}"
                    ),
                },
            ],
            "temperature": 0.55,
            "max_tokens": 1400,
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
                timeout=30,
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
        payload = self._extract_json_payload(text)
        beats = payload.get("visual_beats") or payload.get("beats") or []
        return self._normalize_visual_beats(beats, "motion_text", narration, duration)

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
        self._recent_visual_texts = []
        self._used_visual_signatures = set()
        self._generic_fallback_count = 0
        self._last_scene_component = ""
        self._last_scene_pattern = ""
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
                "estimated_duration_sec": self._coerce_duration(outro.get("estimated_duration_sec"), 18),
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
        normalized["hook"]["visual_beats"] = self._normalize_visual_beats(
            hook.get("visual_beats"),
            normalized["hook"]["visual_type"],
            normalized["hook"]["visual_instruction"],
            normalized["hook"]["estimated_duration_sec"],
            enforce_hook=True,
            context_text=normalized["hook"]["narration"],
        )
        for index, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                continue
            visual_type = self._normalize_visual_type(scene.get("visual_type"))
            duration = self._coerce_duration(
                scene.get("estimated_duration_sec"),
                35,
            )
            instruction = str(
                scene.get("visual_instruction")
                or self._fallback_visual_instruction(visual_type, topic, angle, index)
            )
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
                    "visual_instruction": instruction,
                    "visual_type": visual_type,
                    "estimated_duration_sec": duration,
                    "visual_beats": self._normalize_visual_beats(
                        scene.get("visual_beats"),
                        visual_type,
                        instruction,
                        duration,
                        context_text=str(
                            scene.get("narration")
                            or scene.get("narration_text")
                            or scene.get("content")
                            or instruction
                        ),
                    ),
                }
            )

        if not normalized["scenes"]:
            normalized["scenes"] = self._demo_script(topic, angle)["scenes"]

        normalized["outro"]["visual_beats"] = self._normalize_visual_beats(
            outro.get("visual_beats"),
            normalized["outro"]["visual_type"],
            normalized["outro"]["visual_instruction"],
            normalized["outro"]["estimated_duration_sec"],
            context_text=normalized["outro"]["narration"],
            is_outro=True,
        )

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

    def _normalize_visual_beats(
        self,
        beats: Any,
        visual_type: Any,
        visual_instruction: str,
        scene_duration: int | float,
        enforce_hook: bool = False,
        context_text: str = "",
        is_outro: bool = False,
    ) -> list[dict[str, Any]]:
        if isinstance(beats, str):
            try:
                beats = json.loads(beats)
            except json.JSONDecodeError:
                beats = []
        if not isinstance(beats, list) or not beats:
            beats = self._fallback_visual_beats(visual_type, visual_instruction, scene_duration, context_text=context_text, is_outro=is_outro)

        min_sec = float(current_app.config.get("VISUAL_BEAT_MIN_SEC", 2.5))
        max_sec = float(current_app.config.get("VISUAL_BEAT_MAX_SEC", 4.0)) + 0.5
        normalized: list[dict[str, Any]] = []
        cursor = 0.0
        for index, beat in enumerate(beats):
            if not isinstance(beat, dict):
                continue
            if self._is_structured_visual_beat(beat):
                beat_context = {**beat}
                beat_context.setdefault("narration", context_text or visual_instruction)
                beat_context.setdefault("visual_instruction", visual_instruction)
                if is_outro:
                    beat_context["is_outro"] = True
                if not self.validateRelevance(beat_context, context_text or visual_instruction):
                    beat_context["visual_logic"] = self.deriveFromNarration(context_text or visual_instruction)
                structured = self.render_specs.normalize_structured_beat(
                    {
                        **beat_context,
                        "beat_index": beat.get("beat_index", index),
                        "estimated_start_sec": beat.get("estimated_start_sec", cursor),
                    }
                )
                structured["beat_index"] = int(structured.get("beat_index") or index)
                structured["estimated_start_sec"] = round(
                    self._coerce_float(structured.get("estimated_start_sec"), cursor),
                    2,
                )
                normalized.append(structured)
                cursor = structured["estimated_start_sec"] + float(structured.get("estimated_duration_sec") or 3)
                continue
            beat_type = str(beat.get("beat_type") or beat.get("type") or "text_burst").strip().lower()
            if beat_type not in BEAT_VISUAL_TYPES and beat_type not in {"graph", "broll", "motion_text"}:
                beat_type = "text_burst"
            duration = self._coerce_float(beat.get("estimated_duration_sec"), min(max(float(scene_duration), min_sec), max_sec))
            duration = max(min_sec, min(duration, max_sec))
            start = self._coerce_float(beat.get("estimated_start_sec"), cursor)
            content = str(beat.get("content") or beat.get("headline") or visual_instruction or "Money mistake")
            caption = str(beat.get("caption") or beat.get("subtext") or "")
            if self._legacy_beat_needs_safe_emphasis(beat_type, content, caption, context_text or visual_instruction):
                safe = self.render_specs.normalize_structured_beat(
                    {
                        "beat_index": int(beat.get("beat_index") or index),
                        "intent": "EMPHASIS",
                        "pattern": "EMPHASIS",
                        "visual_logic": self.render_specs._safe_emphasis_logic(context_text or f"{visual_instruction} {content} {caption}"),
                        "narration": context_text or visual_instruction,
                        "estimated_start_sec": round(start, 2),
                        "estimated_duration_sec": round(duration, 2),
                    }
                )
                normalized.append(safe)
                cursor = start + duration
                continue
            normalized.append(
                {
                    "beat_index": int(beat.get("beat_index") or index),
                    "beat_type": beat_type,
                    "content": content,
                    "caption": caption,
                    "color": self._normalize_beat_color(beat.get("color")),
                    "estimated_start_sec": round(start, 2),
                    "estimated_duration_sec": round(duration, 2),
                }
            )
            cursor = start + duration
        normalized = normalized or self._fallback_visual_beats(visual_type, visual_instruction, scene_duration, context_text=context_text, is_outro=is_outro)
        if not enforce_hook:
            normalized = self._maybe_insert_impact_spike(normalized, context_text or visual_instruction)
        normalized = self._apply_visual_rhythm(normalized)
        if enforce_hook:
            normalized = self.enforceHookRules(normalized, context_text or visual_instruction)
        normalized = self._block_exact_repetition(normalized, context_text or visual_instruction)
        normalized = self._enforce_scene_component_variation(normalized, context_text or visual_instruction, enforce_hook)
        return normalized

    def _block_exact_repetition(self, beats: list[dict[str, Any]], context_text: str) -> list[dict[str, Any]]:
        repaired: list[dict[str, Any]] = []
        for index, beat in enumerate(beats):
            current = dict(beat)
            signature = self._visual_text_signature(current)
            if self.isDuplicateVisual(current):
                replacement_logic = self._dedupe_visual_logic(current, context_text)
                current = self.render_specs.normalize_structured_beat(
                    {
                        "beat_index": current.get("beat_index", index),
                        "intent": self._intent_for_logic(replacement_logic),
                        "pattern": self._pattern_for_logic(replacement_logic),
                        "visual_logic": replacement_logic,
                        "narration": context_text,
                        "estimated_start_sec": current.get("estimated_start_sec", index * 2.5),
                        "estimated_duration_sec": current.get("estimated_duration_sec", 2.5),
                    }
                )
                signature = self._visual_text_signature(current)
                if self.isDuplicateVisual(current):
                    replacement_logic = self._contextual_example_logic(context_text, preferred_pattern=self._next_pattern_after(str(current.get("pattern") or "")))
                    current = self.render_specs.normalize_structured_beat(
                        {
                            "beat_index": current.get("beat_index", index),
                            "intent": self._intent_for_logic(replacement_logic),
                            "pattern": self._pattern_for_logic(replacement_logic),
                            "visual_logic": replacement_logic,
                            "narration": context_text,
                            "estimated_start_sec": current.get("estimated_start_sec", index * 2.5),
                            "estimated_duration_sec": current.get("estimated_duration_sec", 2.5),
                        }
                    )
                    signature = self._visual_text_signature(current)
            if signature:
                self._recent_visual_texts.append(signature)
                self._used_visual_signatures.add(signature)
            repaired.append(current)
        return repaired

    def isDuplicateVisual(self, beat: dict[str, Any]) -> bool:
        signature = self._visual_text_signature(beat)
        return bool(signature and signature in self._used_visual_signatures)

    def _visual_text_signature(self, beat: dict[str, Any]) -> str:
        logic = beat.get("visual_logic")
        text = str(
            beat.get("visual_logic_text")
            or self.render_specs._visual_logic_to_text(logic)
            or beat.get("content")
            or ""
        )
        logic_type = logic.get("type") if isinstance(logic, dict) else "legacy"
        numbers = self.render_specs._money_tokens(text) + self.render_specs._percent_tokens(text)
        entities = sorted(self.render_specs._meaningful_keywords(text))
        entity_part = "-".join(entities[:4])
        if numbers:
            number_part = "-".join(sorted(set(number.lower() for number in numbers)))
            return f"{logic_type}-{number_part}-{entity_part}"
        return f"{logic_type}-no-numbers-{entity_part or 'no-entities'}"

    def _enforce_scene_component_variation(self, beats: list[dict[str, Any]], context_text: str, is_hook: bool) -> list[dict[str, Any]]:
        if not beats:
            return beats
        first = dict(beats[0])
        component = str(first.get("component") or first.get("beat_type") or "")
        pattern = str(first.get("pattern") or component)
        if self._last_scene_pattern and pattern == self._last_scene_pattern and not is_hook:
            replacement_logic = self.deriveFromNarration(
                context_text,
                preferred_pattern=self._next_pattern_after(pattern),
            )
            if self._visual_text_signature({"visual_logic": replacement_logic}) in self._used_visual_signatures:
                replacement_logic = self._contextual_example_logic(context_text, self._next_pattern_after(pattern))
            replacement = self.render_specs.normalize_structured_beat(
                {
                    "beat_index": first.get("beat_index", 0),
                    "intent": self._intent_for_logic(replacement_logic),
                    "pattern": self._pattern_for_logic(replacement_logic),
                    "visual_logic": replacement_logic,
                    "narration": context_text,
                    "estimated_start_sec": first.get("estimated_start_sec", 0),
                    "estimated_duration_sec": first.get("estimated_duration_sec", 3),
                }
            )
            beats = [replacement, *beats[1:]]
            component = str(replacement.get("component") or "")
            pattern = str(replacement.get("pattern") or component)
            replacement_signature = self._visual_text_signature(replacement)
            if replacement_signature:
                self._used_visual_signatures.add(replacement_signature)
                self._recent_visual_texts.append(replacement_signature)
        if component:
            self._last_scene_component = component
        if pattern:
            self._last_scene_pattern = pattern
        return beats

    def _alternate_visual_logic(self, context_text: str) -> str:
        amounts = self.render_specs._money_tokens(context_text)
        percents = self.render_specs._percent_tokens(context_text)
        lowered = context_text.lower()
        if "automate" in lowered or "auto" in lowered:
            amount = amounts[0] if amounts else "₹5,000"
            return f"{amount} manual spend -> {amount} emotional decision -> ₹0 saved"
        if len(amounts) >= 2:
            return f"{amounts[0]} vs {amounts[1]}"
        if amounts and percents:
            return f"{percents[0]} vs {amounts[0]}"
        if amounts:
            return f"{amounts[0]} monthly leak -> {amounts[0]} repeated -> ₹0 saved"
        return "₹5,000 manual choice -> ₹5,000 emotion -> ₹0 saved"

    def _dedupe_visual_logic(self, beat: dict[str, Any], context_text: str) -> dict[str, Any]:
        narration_logic = self.deriveFromNarration(context_text)
        if self._visual_text_signature({"visual_logic": narration_logic}) not in self._used_visual_signatures:
            return narration_logic
        for preferred in ("MONEY_FLOW", "COMPARISON", "VALUE_DECAY", "GROWTH", "EMPHASIS"):
            candidate = self.deriveFromNarration(context_text, preferred_pattern=preferred)
            if self._visual_text_signature({"visual_logic": candidate}) not in self._used_visual_signatures:
                return candidate
        return self._contextual_example_logic(context_text, preferred_pattern="MONEY_FLOW")

    def deriveFromNarration(self, narration: str, preferred_pattern: str = "") -> dict[str, Any]:
        return self.render_specs.deriveFromNarration(narration, preferred_pattern=preferred_pattern)

    def validateRelevance(self, beat: dict[str, Any], narration: str) -> bool:
        return self.render_specs.validateRelevance(beat, narration)

    def _intent_for_logic(self, logic: dict[str, Any]) -> str:
        return "COMPARISON" if isinstance(logic, dict) and logic.get("type") == "comparison" else "EXPLANATION"

    def _pattern_for_logic(self, logic: dict[str, Any]) -> str:
        return self.render_specs.LOGIC_TYPE_TO_PATTERN.get(str(logic.get("type") if isinstance(logic, dict) else ""), "MONEY_FLOW")

    def _next_pattern_after(self, pattern: str) -> str:
        pattern = str(pattern or "").upper()
        return {
            "COMPARISON": "MONEY_FLOW",
            "MONEY_FLOW": "EMPHASIS",
            "VALUE_DECAY": "COMPARISON",
            "GROWTH": "COMPARISON",
            "EMPHASIS": "COMPARISON",
            "CONTEXT": "COMPARISON",
        }.get(pattern, "COMPARISON")

    def _contextual_example_logic(self, context_text: str, preferred_pattern: str = "") -> dict[str, Any]:
        amounts = self.render_specs._money_tokens(context_text)
        percents = self.render_specs._percent_tokens(context_text)
        preferred_pattern = str(preferred_pattern or "").upper()
        if preferred_pattern == "COMPARISON" and len(amounts) >= 2:
            return {"type": "comparison", "left": amounts[0], "right": amounts[1]}
        if preferred_pattern == "COMPARISON" and amounts and percents:
            return {"type": "comparison", "left": percents[0], "right": amounts[0]}
        amount = amounts[0] if amounts else "₹5,000"
        if preferred_pattern == "VALUE_DECAY":
            rate = percents[0] if percents else "6% Inflation"
            return {"type": "decay", "input": amount, "factor": rate, "output": f"{self.render_specs._inflation_output(amount, rate)} Real Value"}
        if preferred_pattern == "GROWTH":
            output = amounts[1] if len(amounts) > 1 else self.render_specs._derived_rupee(amount, 12, "Invested")
            return {"type": "growth", "input": f"{amount} SIP", "rate": percents[0] if percents else "12 months", "output": output}
        if any(word in context_text.lower() for word in ("month", "monthly", "year", "yearly", "leak", "lost", "gone")):
            result = amounts[1] if len(amounts) > 1 else self.render_specs._derived_rupee(amount, 12, "Lost")
            return {"type": "flow", "source": f"{amount} Monthly Leak", "process": "12 months", "result": f"{result} Lost"}
        result = amounts[1] if len(amounts) > 1 else "₹0 Saved"
        entity = next(iter(sorted(self.render_specs._meaningful_keywords(context_text))), "viewer").title()
        return {"type": "flow", "source": f"{amount} {entity} Need", "process": f"{amount} Required", "result": result}

    def _is_generic_fallback_logic(self, logic: Any) -> bool:
        text = self.render_specs._visual_logic_to_text(logic)
        return "76%" in text and "₹5,000" in text and "save" in text.lower()

    def _legacy_beat_needs_safe_emphasis(self, beat_type: str, content: str, caption: str, context_text: str = "") -> bool:
        text = f"{content} {caption}".strip()
        if beat_type == "broll_caption":
            return False
        if beat_type == "reaction_card":
            return bool(
                not text
                or self.render_specs._is_abstract_visual_logic(text)
                or not self._legacy_relevant_to_context(text, context_text)
            )
        if beat_type == "chart":
            return len(self.render_specs._extract_data_points(text)) < 2
        if beat_type == "split_comparison":
            return not self.render_specs._passes_text_gate(text)
        return not (
            self.render_specs._has_number(text)
            and self.render_specs._has_impact(text)
            and not self.render_specs._is_abstract_visual_logic(text)
        )

    def _legacy_relevant_to_context(self, text: str, context_text: str) -> bool:
        if not context_text.strip():
            return True
        text_numbers = set(re.findall(r"\d+(?:\.\d+)?", text))
        context_numbers = set(re.findall(r"\d+(?:\.\d+)?", context_text))
        if text_numbers and context_numbers and text_numbers & context_numbers:
            return True
        text_keywords = self.render_specs._meaningful_keywords(text)
        context_keywords = self.render_specs._meaningful_keywords(context_text)
        return bool(text_keywords and context_keywords and text_keywords & context_keywords)

    def _is_structured_visual_beat(self, beat: dict[str, Any]) -> bool:
        return any(key in beat for key in ("intent", "pattern", "visual_logic", "props", "animation_intent"))

    def _apply_visual_rhythm(self, beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(beats) < 3:
            return beats
        repaired: list[dict[str, Any]] = []
        same_count = 0
        previous_intent = ""
        flow_count = 0
        max_flow = max(1, int(len(beats) * 0.6))
        for index, beat in enumerate(beats):
            current = dict(beat)
            intent = str(current.get("intent") or "").upper()
            pattern = str(current.get("pattern") or "").upper()
            if intent and intent == previous_intent:
                same_count += 1
            else:
                same_count = 1
            if intent and same_count > 2:
                current.update(
                    {
                        "intent": "COMPARISON",
                        "pattern": "COMPARISON",
                        "visual_logic": {"type": "comparison", "left": "₹5,000 Habit", "right": "₹60,000 Yearly Loss"},
                        "props": {},
                        "narration": "A ₹5,000 habit becomes a ₹60,000 yearly loss.",
                        "animation_intent": "highlight",
                    }
                )
                same_count = 1
                intent = "COMPARISON"
                pattern = "COMPARISON"
            if pattern in {"MONEY_FLOW", "VALUE_DECAY", "LOOP", "GROWTH"}:
                flow_count += 1
                if flow_count > max_flow:
                    current.update(
                        {
                            "intent": "COMPARISON",
                            "pattern": "COMPARISON",
                            "visual_logic": {"type": "comparison", "left": "₹5,000 Habit", "right": "₹60,000 Yearly Loss"},
                            "props": {},
                            "narration": "A ₹5,000 habit becomes a ₹60,000 yearly loss.",
                            "animation_intent": "highlight",
                        }
                    )
                    intent = "COMPARISON"
                    pattern = "COMPARISON"
            previous_intent = intent
            repaired.append(self.render_specs.normalize_structured_beat(current) if self._is_structured_visual_beat(current) else current)
        return repaired

    def _enforce_hook_beats(self, beats: list[dict[str, Any]], visual_instruction: str) -> list[dict[str, Any]]:
        first_source = dict(beats[0]) if beats else {}
        first_source["beat_index"] = 0
        first_source["estimated_start_sec"] = 0
        first_source["intent"] = "EMPHASIS"
        first_source["pattern"] = "EMPHASIS"
        first_source["narration"] = visual_instruction
        first_source["visual_logic"] = self.deriveFromNarration(visual_instruction)
        first_source.pop("component", None)
        first = self._force_hook_emphasis(self.render_specs.normalize_structured_beat(first_source), visual_instruction)
        props = first.get("props") if isinstance(first.get("props"), dict) else {}
        props["headline"] = self._hook_headline(str(first.get("visual_logic_text") or props.get("headline") or visual_instruction))
        props["durationSec"] = 2.5
        first["props"] = props
        first["beat_index"] = 0
        first["estimated_start_sec"] = 0
        first["estimated_duration_sec"] = 2.5

        second_text = self._hook_meaning_text(visual_instruction)
        second = {
            "beat_index": 1,
            "beat_type": "text_burst",
            "content": second_text,
            "caption": "",
            "color": "red" if "BROKEN" in second_text or "NOT" in second_text else "orange",
            "estimated_start_sec": 2.5,
            "estimated_duration_sec": 2.5,
        }
        return [first, second]

    def enforceHookRules(self, beats: list[dict[str, Any]], visual_instruction: str) -> list[dict[str, Any]]:
        return self._enforce_hook_beats(beats, visual_instruction)

    def _hook_beat_is_valid(self, beat: dict[str, Any]) -> bool:
        normalized = self.render_specs.normalize_structured_beat(beat)
        if normalized.get("component") == "FlowDiagram":
            return False
        props = normalized.get("props") if isinstance(normalized.get("props"), dict) else {}
        headline = str(props.get("headline") or props.get("content") or normalized.get("visual_logic_text") or "")
        return (
            len(headline.split()) <= 6
            and self.render_specs._has_number(headline + " " + str(props.get("subtext") or ""))
            and self.render_specs._has_impact(headline + " " + str(props.get("subtext") or normalized.get("visual_logic_text") or ""))
        )

    def _safe_hook_beat(self, visual_instruction: str, index: int) -> dict[str, Any]:
        logic = self.render_specs._safe_emphasis_logic(visual_instruction)
        normalized = self.render_specs.normalize_structured_beat(
            {
                "beat_index": index,
                "intent": "EMPHASIS",
                "pattern": "EMPHASIS",
                "visual_logic": logic,
                "props": {
                    "headline": self._hook_headline(logic),
                    "subtext": self.render_specs._short_overlay(logic, 6),
                },
                "animation_intent": "highlight",
                "narration": visual_instruction,
                "estimated_start_sec": index * 2.5,
                "estimated_duration_sec": 2.5,
            }
        )
        props = normalized.get("props") if isinstance(normalized.get("props"), dict) else {}
        headline = str(props.get("headline") or "")
        if len(headline.split()) > 6:
            props["headline"] = " ".join(headline.split()[:6])
        normalized["props"] = props
        return normalized

    def _force_hook_emphasis(self, beat: dict[str, Any], visual_instruction: str) -> dict[str, Any]:
        current = dict(beat)
        visual_text = str(current.get("visual_logic_text") or self.render_specs._visual_logic_to_text(current.get("visual_logic")) or visual_instruction)
        caption = self.render_specs._repair_caption("", visual_text, visual_instruction)
        props = self.render_specs._safe_emphasis_props(visual_text, caption)
        props["headline"] = self._hook_headline(visual_text)
        props["subtext"] = self._hook_subtext(visual_text, str(props["headline"]), caption)
        props["durationSec"] = current.get("estimated_duration_sec") or 2.5
        emphasis_logic = {
            "type": "emphasis",
            "headline": props["headline"],
            "subtext": str(props.get("subtext") or caption),
        }
        current.update(
            {
                "intent": "EMPHASIS",
                "pattern": "EMPHASIS",
                "component": "StatExplosion",
                "visual_logic": emphasis_logic,
                "visual_logic_text": self.render_specs._visual_logic_to_text(emphasis_logic),
                "caption": caption,
                "props": props,
            }
        )
        return current

    def _hook_subtext(self, visual_text: str, headline: str, fallback: str) -> str:
        text = visual_text.replace(headline, "", 1).strip()
        text = re.sub(r"\s+vs\.?\s+", " ", text, flags=re.I)
        text = re.sub(r"\bemergency fund\b", "", text, flags=re.I)
        text = re.sub(r"\bcannot save\b", "can't save", text, flags=re.I)
        text = re.sub(r"\s+", " ", text).strip(" -")
        if re.search(r"\bcan't save\b", text, flags=re.I) and not re.search(r"\b(even|still|just)\b", text, flags=re.I):
            text = re.sub(r"\bcan't save\b", "can't even save", text, count=1, flags=re.I)
        text = (
            self.render_specs._short_overlay(text, 6)
            .replace("can t even save", "can't even save")
            .replace("can t save", "can't save")
        )
        text = text.replace("can't save", "can't even save") if "can't save" in text and "can't even save" not in text else text
        return text or fallback

    def _maybe_insert_impact_spike(self, beats: list[dict[str, Any]], context_text: str) -> list[dict[str, Any]]:
        if not beats or not self._supports_zero_impact_spike(context_text):
            return beats
        first_structured_flow = any(
            str(beat.get("component") or "") == "FlowDiagram"
            or str(beat.get("pattern") or "").upper() == "MONEY_FLOW"
            for beat in beats[:1]
        )
        has_existing_spike = any("₹0 left every month" in str(beat) for beat in beats)
        if not first_structured_flow or has_existing_spike:
            return beats
        spike = {
            "beat_index": 0,
            "beat_type": "stat_explosion",
            "component": "StatExplosion",
            "content": "₹0",
            "caption": "left every month",
            "color": "red",
            "estimated_start_sec": 0,
            "estimated_duration_sec": 2.5,
        }
        shifted = []
        for index, beat in enumerate(beats, start=1):
            current = dict(beat)
            current["beat_index"] = index
            current["estimated_start_sec"] = round(float(current.get("estimated_start_sec") or 0) + 2.5, 2)
            shifted.append(current)
        return [spike, *shifted]

    def _supports_zero_impact_spike(self, context_text: str) -> bool:
        lowered = context_text.lower()
        return (
            "₹0" in context_text
            and any(word in lowered for word in ("automate", "auto", "fix", "solution", "before emotion", "manual spending"))
            and any(word in lowered for word in ("month", "monthly", "spending", "emotion", "left"))
        )

    def _hook_headline(self, text: str) -> str:
        percent = re.search(r"\d+(?:\.\d+)?%", text)
        if percent:
            return percent.group(0)
        return self.render_specs._dominant_phrase(text)

    def _hook_meaning_text(self, visual_instruction: str) -> str:
        lowered = visual_instruction.lower()
        if "system" in lowered or "broken" in lowered:
            return "BROKEN SYSTEM"
        if "discipline" in lowered:
            return "NOT DISCIPLINE"
        if "default" in lowered:
            return "DEFAULTS WIN"
        if "broke" in lowered:
            return "BROKE BY DESIGN"
        return "FIX THE SYSTEM"

    def _fallback_visual_beats(
        self,
        visual_type: Any,
        visual_instruction: str,
        scene_duration: int | float,
        context_text: str = "",
        is_outro: bool = False,
    ) -> list[dict[str, Any]]:
        visual_type = str(visual_type or "motion_text").lower()
        duration = max(float(current_app.config.get("VISUAL_BEAT_MIN_SEC", 2.5)), min(float(scene_duration or 3), 4.0))
        context = context_text or visual_instruction
        if visual_type != "broll":
            preferred = "MONEY_FLOW" if is_outro else ""
            logic = self.deriveFromNarration(context, preferred_pattern=preferred)
            logic_text = self.render_specs._visual_logic_to_text(logic)
            if self._is_generic_fallback_logic(logic) and self._generic_fallback_count >= 1:
                logic = self._contextual_example_logic(context, preferred_pattern=preferred or "MONEY_FLOW")
                logic_text = self.render_specs._visual_logic_to_text(logic)
            if self._is_generic_fallback_logic(logic):
                self._generic_fallback_count += 1
            return [
                {
                    "beat_index": 0,
                    "intent": "EXPLANATION",
                    "pattern": self.render_specs.LOGIC_TYPE_TO_PATTERN.get(logic.get("type") if isinstance(logic, dict) else "", "MONEY_FLOW"),
                    "visual_logic": logic,
                    "visual_logic_text": logic_text,
                    "narration": context,
                    "is_outro": is_outro,
                    "estimated_start_sec": 0,
                    "estimated_duration_sec": round(duration, 2),
                }
            ]
        if visual_type == "graph":
            beat_type = "chart"
            content = visual_instruction
            caption = "watch the gap"
            color = "orange"
        elif visual_type == "broll":
            beat_type = "broll_caption"
            content = self._short_search_query(visual_instruction)
            caption = self._short_caption(visual_instruction)
            color = "navy"
        elif visual_type in {"stat_explosion", "text_burst", "chart", "split_comparison", "broll_caption", "reaction_card"}:
            beat_type = visual_type
            content = visual_instruction
            caption = ""
            color = "orange"
        else:
            beat_type = "text_burst"
            content = visual_instruction or "Money mistake"
            caption = ""
            color = "orange"
        return [
            {
                "beat_index": 0,
                "beat_type": beat_type,
                "content": content,
                "caption": caption,
                "color": color,
                "estimated_start_sec": 0,
                "estimated_duration_sec": round(duration, 2),
            }
        ]

    def _coerce_float(self, value: Any, default: float) -> float:
        try:
            number = float(value)
            return number if number >= 0 else default
        except (TypeError, ValueError):
            return default

    def _normalize_beat_color(self, value: Any) -> str:
        color = str(value or "orange").strip().lower()
        return color if color in {"red", "orange", "teal", "navy", "white"} else "orange"

    def _short_search_query(self, text: str) -> str:
        words = re.findall(r"[A-Za-z]+", text.lower())
        stop = {"the", "a", "an", "of", "in", "on", "for", "with", "and", "or", "is", "are", "to", "from"}
        filtered = [word for word in words if word not in stop]
        return " ".join(filtered[:5]) or "finance stress"

    def _short_caption(self, text: str) -> str:
        words = re.findall(r"[A-Za-z0-9₹%.,]+", text)
        return " ".join(words[:8]) or "money reality"

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
                "narration": "80% of Indians have less than ₹5,000 saved. That is not discipline. That is a broken money system.",
                "estimated_duration_sec": 6,
                "tension_type": "shocking_statistic",
                "visual_instruction": "80% have less than ₹5,000 saved",
                "visual_type": "motion_text",
                "visual_beats": [
                    {
                        "beat_index": 0,
                        "intent": "HOOK",
                        "pattern": "EMPHASIS",
                        "visual_logic": {"type": "comparison", "left": "80% Indians", "right": "₹5,000 saved"},
                        "animation_intent": "highlight",
                    }
                ],
            },
            "scenes": [
                {
                    "kind": "body",
                    "narration": "Most people think money is about discipline. But a ₹8,00,000 salary with a ₹1,60,000 leak proves the real issue is invisible defaults.",
                    "visual_instruction": "₹8,00,000 Salary vs ₹1,60,000 Invisible Leak",
                    "visual_type": "motion_text",
                    "estimated_duration_sec": 35,
                    "visual_beats": [
                        {
                            "beat_index": 0,
                            "intent": "COMPARISON",
                            "pattern": "COMPARISON",
                            "visual_logic": {"type": "comparison", "left": "₹8,00,000 Salary", "right": "₹1,60,000 Invisible Leak"},
                            "animation_intent": "highlight",
                        },
                    ],
                },
                {
                    "kind": "body",
                    "narration": "In your 20s, salary can vanish by day 12. You feel rich for 6 hours, then the card bill starts narrating your life.",
                    "visual_instruction": "Find urban b-roll of young adults paying with cards, checking bills, and scrolling banking apps.",
                    "visual_type": "broll",
                    "estimated_duration_sec": 35,
                    "visual_beats": [
                        {
                            "beat_index": 0,
                            "beat_type": "broll_caption",
                            "content": "credit card stress",
                            "caption": "salary vanished by day 12",
                            "color": "navy",
                            "estimated_start_sec": 0,
                            "estimated_duration_sec": 3,
                        },
                        {
                            "beat_index": 1,
                            "beat_type": "reaction_card",
                            "content": "me every payday",
                            "caption": "rich for 6 hours",
                            "color": "teal",
                            "estimated_start_sec": 3,
                            "estimated_duration_sec": 3,
                        },
                    ],
                },
                {
                    "kind": "body",
                    "narration": "The fix is simple: automate ₹5,000 before emotion gets a vote, so manual spending cannot turn savings into ₹0.",
                    "visual_instruction": "₹5,000 Auto Debit -> Investment -> ₹0 Emotional Spend",
                    "visual_type": "motion_text",
                    "estimated_duration_sec": 35,
                    "visual_beats": [
                        {
                            "beat_index": 0,
                            "intent": "EXPLANATION",
                            "pattern": "MONEY_FLOW",
                            "visual_logic": {"type": "flow", "source": "₹5,000 Auto Debit", "process": "₹5,000 Investment", "result": "₹0 Emotional Spend"},
                            "animation_intent": "progress",
                        }
                    ],
                },
            ],
            "outro": {
                "narration": "If ₹5,000 keeps leaking every month, that is ₹60,000 gone in a year. Fix the system before you blame yourself.",
                "visual_instruction": "₹5,000 monthly leak -> 12 months -> ₹60,000 gone",
                "visual_type": "motion_text",
                "estimated_duration_sec": 18,
                "visual_beats": [
                    {
                        "beat_index": 0,
                        "intent": "EXPLANATION",
                        "pattern": "MONEY_FLOW",
                        "visual_logic": {"type": "flow", "source": "₹5,000 Monthly Leak", "process": "12 Months", "result": "₹60,000 Gone"},
                        "animation_intent": "transform",
                    }
                ],
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
