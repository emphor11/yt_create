from __future__ import annotations

import json
from typing import Any, Callable

from ...contracts.scripts import (
    SCRIPT_BRIEF_EMOTIONAL_DIRECTIONS,
    SCRIPT_BRIEF_FORMATS,
    SCRIPT_BRIEF_MECHANISMS,
)
from .constants import (
    BODY_MAX_WORDS,
    BODY_MIN_WORDS,
    DEFAULT_CHANNEL_NICHE,
    DEFAULT_SCRIPT_TONE,
    DEFAULT_TARGET_DURATION_MINUTES,
    HOOK_MAX_WORDS,
    HOOK_MIN_WORDS,
    OUTRO_MAX_WORDS,
    OUTRO_MIN_WORDS,
)


class ScriptPromptBuilder:
    """Builds the Groq script prompt with topic-bound script instructions."""

    def __init__(self, visual_contract: Callable[[], str]) -> None:
        self.visual_contract = visual_contract

    def build(
        self,
        *,
        config: dict[str, Any],
        topic: str,
        angle: str,
        target_duration_minutes: int | None = None,
        niche: str | None = None,
        tone: str | None = None,
        script_brief: dict[str, Any] | None = None,
    ) -> str:
        target_duration_minutes = target_duration_minutes or config.get(
            "TARGET_DURATION_MINUTES",
            DEFAULT_TARGET_DURATION_MINUTES,
        )
        body_scene_count = max(1, int(target_duration_minutes))
        if script_brief and isinstance(script_brief.get("scene_function_map"), list) and script_brief.get("scene_function_map"):
            body_scene_count = len(script_brief["scene_function_map"])
        hook_min_words = HOOK_MIN_WORDS
        hook_max_words = HOOK_MAX_WORDS
        body_min_words = BODY_MIN_WORDS
        body_max_words = BODY_MAX_WORDS
        outro_min_words = OUTRO_MIN_WORDS
        outro_max_words = OUTRO_MAX_WORDS
        total_min_words = body_scene_count * body_min_words + hook_min_words + outro_min_words
        total_max_words = body_scene_count * body_max_words + hook_max_words + outro_max_words
        niche = niche or config.get("CHANNEL_NICHE", DEFAULT_CHANNEL_NICHE)
        tone = tone or config.get("SCRIPT_TONE", DEFAULT_SCRIPT_TONE)
        recurring_example = self._recurring_example(topic, angle)
        mechanism_guidance = self._mechanism_guidance(topic, angle)
        brief_contract = self._script_brief_block(script_brief)
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
            f"* TONE_HINT is binding: write in this creative direction unless it conflicts with financial accuracy: {tone}\n"
            "* Stay knowledgeable, concrete, and spoken-friendly\n"
            "* Conversational (talk to the viewer, not at them)\n"
            "* Use humor only if it fits TONE_HINT; do not soften a dark/psychological topic with cheerful generic jokes\n"
            "* Use Indian finance context naturally (salary, EMI, SIP, inflation, debt trap, lifestyle inflation, compound interest, risk-vs-return, diversification, FOMO, etc.)\n"
            "* Keep language simple and spoken-friendly\n\n"
            f"{brief_contract}"
            "RECURRING FINANCIAL EXAMPLE:\n\n"
            "* Use one recurring financial example throughout the entire video, but it must come from the TOPIC and AUDIENCE, not from a fixed salary curriculum\n"
            f"* Suggested recurring example for this request: {recurring_example}\n"
            "* If the topic is not salary disappearance, do NOT use the ₹50,000 salary/day-20 hook or monthly salary-drain storyline\n"
            "* Do not create a named fictional character\n"
            "* Do not write scenes that require realistic human acting, facial emotion, cinematic b-roll, or live-action continuity\n"
            "* Keep the story mechanism-first, but derive the mechanism from the current topic instead of forcing salary, EMI, inflation, SIP, diversification, FOMO, and emergency-fund scenes into every video\n"
            f"{mechanism_guidance}"
            "* Refer back to earlier numbers explicitly when useful, but only when those numbers belong to this topic\n"
            "* Every body scene should show how the same topic-specific money mechanism changes over time\n"
            "* If a SCRIPT STRATEGY BRIEF is present, its recurring_example overrides the suggested recurring example above\n"
            "* Visuals will be diagrams, financial animations, charts, stacks, flows, comparison visuals, and mechanism visualizers\n\n"
            "---\n\n"
            "CORE WRITING RULES:\n\n"
            "1. ONE CLEAR IDEA PER SENTENCE\n"
            "Each sentence should express one clear spoken idea.\n"
            "Avoid overloaded sentences that combine multiple finance concepts at once.\n\n"
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
            f"* First 1–3 sentences, {hook_min_words}-{hook_max_words} spoken words total\n"
            "* Start with strong curiosity or tension\n"
            "* Must pass this hook contract: under 35 words, and include either a question mark/\"why\", or a ₹ amount with a negative finance word like gone/leak/drain/debt/cost, or a percentage/big number with a people group\n"
            "* Name the current topic's main object, price, habit, trap, or contradiction, not a generic finance statement\n"
            "* Do not copy this old salary hook unless TOPIC is specifically about salary disappearing: \"Why does your ₹50,000 salary feel gone by day 20?\"\n"
            "* For monthly-payment topics, open on the psychological trick: the full price disappears and the monthly number feels harmless\n"
            "* Avoid validator-weak hooks like: \"You work hard but still struggle to save.\"\n"
            "* No greetings, no \"hey guys\", no \"welcome back\"\n"
            "* Make the viewer feel like they are already in the problem (salary, EMIs, lack of savings, debt, inflation, investing confusion)\n\n"
            "BODY:\n\n"
            "* Continuous flow of ideas with no labels, markdown, or bullet points inside narration\n"
            f"* Generate EXACTLY {body_scene_count} body scenes. No more, no fewer\n"
            "* If a SCRIPT STRATEGY BRIEF is present, generate exactly one body scene per scene_function_map entry\n"
            "* Each generated scene's mechanism must match its scene_function_map entry exactly\n"
            "* Every body scene must use the brief's recurring_example to illustrate its mechanism\n"
            "* Do not introduce a different primary example halfway through the video\n"
            f"* Each body scene must be {body_min_words}-{body_max_words} spoken words across 8-12 short sentences\n"
            "* Do NOT write checklist-style scenes. Each scene is one chapter in the same money system\n"
            "* Each body scene must focus on one finance mechanism only\n"
            "* Do not let adjacent finance concepts contaminate the scene. Example: lifestyle inflation is spending expansion after a raise, not macro inflation or CPI erosion\n"
            "* Each body scene must include these five elements in natural narration order, without labeling them:\n"
            "  1. SETUP: Restate where the topic-specific recurring example is now\n"
            "  2. EXAMPLE: Use a concrete Indian finance situation with a specific rupee number\n"
            "  3. MECHANISM: Explain how the financial force works using simple math or logic\n"
            "  4. CONSEQUENCE: Show what happens to savings, debt, purchasing power, risk, or confidence\n"
            "  5. TRANSITION: Create tension or callback that pulls into the next scene\n"
            "* Do not write the words SETUP, EXAMPLE, MECHANISM, CONSEQUENCE, or TRANSITION inside narration\n"
            "* Each concept should be explained in a complete visual sequence, not compressed into tiny sentences\n"
            "* Use relatable Indian-finance examples: salary, rent, EMI, SIP, FD, mutual funds, loans, crypto, etc.\n"
            "* Prefer light, slightly irreverent humor and analogies\n\n"
            "OUTRO:\n\n"
            f"* Last 6-9 sentences, {outro_min_words}-{outro_max_words} spoken words\n"
            "* Recap the major mechanisms from the video in one line each\n"
            "* Give one clear, practical, non-guarantee action the viewer can take today\n"
            "* Avoid platform-specific advice unless the topic explicitly asks for it\n"
            "* End with one strong, memorable line that sticks in the viewer’s mind\n\n"
            "---\n\n"
            "CONSTRAINTS:\n\n"
            "WORD COUNT TARGETS (enforce strictly):\n"
            f"* Hook: {hook_min_words}-{hook_max_words} words\n"
            f"* Each body scene: {body_min_words}-{body_max_words} spoken words\n"
            f"* Outro: {outro_min_words}-{outro_max_words} spoken words\n"
            f"* Total script including hook and outro should be around {total_min_words}-{total_max_words} spoken words\n"
            f"* If any body scene is under {body_min_words} words, expand it before returning JSON\n\n"
            "* Generate semantic visual planning fields for body scenes, but keep narration fields spoken-only\n"
            "* Do NOT write meta-visual narration like \"the viewer should see\", \"the scene should show\", \"not just hear generic advice\", or repeated philosophy like \"every rupee has a job\"\n"
            "* Visual planning must not invent numbers. numbers[] must contain only values spoken in narration; derived calculations belong to the deterministic renderer later\n"
            "* Do NOT add extra fields in the JSON apart from the exact ones listed in the OUTPUT FORMAT below\n"
            "* Do NOT invent fake factual claims, guaranteed returns, or predictions (no \"guaranteed 25% returns\", no \"XYZ stock will go to 1000\")\n"
            "* You may use simple hypothetical numbers only when clearly framed as examples\n"
            "* Duration fields are rough estimates only, but body scenes must still contain enough narration for the target duration\n"
            "* Do NOT request visuals that require a realistic person, actor performance, face continuity, or live-action footage\n"
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
            f"{self.visual_contract()}\n"
            "OUTPUT FORMAT:\n"
            "Return one valid JSON object only.\n"
            "{\n"
            f'  "hook": {{"narration": "<{hook_min_words}-{hook_max_words} word spoken hook>", "duration": "<estimated seconds, usually 6-10>", "tension_type": "<curiosity_gap | shocking_statistic | contrarian_claim | common_mistake_reveal | before_after>"}},\n'
            f'  "scenes": [{{"scene_index": "<1-based scene number>", "kind": "body", "narration": "<{body_min_words}-{body_max_words} words, 8-12 short spoken sentences, one finance mechanism only, includes setup/example/mechanism/consequence/transition>", "duration": "<estimated seconds, usually 55-75>", "visual_intent": "<one sentence describing what visibly changes on screen>", "visual_beats": ["<object/action setup>", "<money or mechanism changes>", "<consequence or emotional payoff>"], "numbers": ["<only numbers actually spoken in narration>"], "emotion": "<anxiety | shock | clarity | confidence | urgency>", "mechanism": "<specific mechanism from the allowed list above>"}}],\n'
            f'  "outro": {{"narration": "<{outro_min_words}-{outro_max_words} words, 6-9 spoken recap sentences with one practical takeaway>", "duration": "<estimated seconds, usually 35-50>"}},\n'
            '  "suggested_titles": ["title option 1", "title option 2"],\n'
            '  "suggested_description": "string",\n'
            '  "tags": ["tag1", "tag2"],\n'
            '  "tension_type_used": "curiosity_gap"\n'
            "}\n"
            f"The total duration across hook + scenes + outro should be approximately {target_duration_minutes * 60} seconds.\n"
            "Before returning, silently count words in every narration field and fix any scene that misses the requested range.\n"
            f"Generate EXACTLY {body_scene_count} body scenes.\n"
            "If a SCRIPT STRATEGY BRIEF is present, each body scene must follow the matching scene_function_map item by scene_index.\n"
            f"Each body scene narration must be {body_min_words}-{body_max_words} words. Check word count before returning.\n"
            f"Total script including hook and outro should be around {total_min_words}-{total_max_words} spoken words.\n"
            "Return only JSON.\n"
        )

    def build_brief_prompt(
        self,
        *,
        config: dict[str, Any],
        topic: str,
        angle: str,
        target_duration_minutes: int | None = None,
        niche: str | None = None,
        tone: str | None = None,
    ) -> str:
        target_duration_minutes = target_duration_minutes or config.get(
            "TARGET_DURATION_MINUTES",
            DEFAULT_TARGET_DURATION_MINUTES,
        )
        scene_count = max(1, int(target_duration_minutes))
        niche = niche or config.get("CHANNEL_NICHE", DEFAULT_CHANNEL_NICHE)
        tone = tone or config.get("SCRIPT_TONE", DEFAULT_SCRIPT_TONE)
        formats = " | ".join(sorted(SCRIPT_BRIEF_FORMATS))
        mechanisms = ", ".join(sorted(SCRIPT_BRIEF_MECHANISMS))
        directions = " | ".join(sorted(SCRIPT_BRIEF_EMOTIONAL_DIRECTIONS))
        return (
            "You are the planning producer for a professional finance YouTube video.\n"
            "Return only one valid JSON object. No markdown. No commentary.\n\n"
            "Create a ScriptBrief that will strictly constrain a later narration-writing call.\n"
            "The brief must be topic-specific, not a generic finance curriculum.\n\n"
            f"TOPIC: {topic}\n"
            f"AUDIENCE_OR_ANGLE: {angle}\n"
            f"CHANNEL_DESCRIPTION: {niche}\n"
            f"TONE_HINT: {tone}\n"
            f"TARGET_DURATION_MINUTES: {target_duration_minutes}\n"
            f"BODY_SCENE_COUNT: {scene_count}\n\n"
            f"selected_format must be one of: {formats}\n"
            f"allowed_mechanisms and scene_function_map[].mechanism must use only these keys: {mechanisms}\n"
            f"scene_function_map[].emotional_direction must be one of: {directions}\n\n"
            "Rules:\n"
            "* topic_interpretation must explain what this video is actually about, in one sentence.\n"
            "* thesis must be one claim the script will prove, not a topic label.\n"
            "* The thesis must answer the exact TOPIC question, not a nearby generic finance lesson.\n"
            "* If TOPIC mentions rich people, wealthy people, businesses, founders, or investors, explain both the strategic use case and the consumer trap. Do not reduce the whole video to overspending advice.\n"
            "* If TOPIC asks why a group loves a behavior, explain the rational incentive for that group before warning about misuse.\n"
            "* recurring_example must be concrete and reusable across every body scene.\n"
            "* forbidden_drift must name 3-6 things the script must not drift into.\n"
            "* scene_function_map must contain exactly BODY_SCENE_COUNT entries.\n"
            "* Each scene function must do a distinct job in the argument.\n"
            "* The first half of scene_function_map should build the exact answer to the TOPIC; the second half may show risks, limits, or viewer action.\n"
            "* Do not choose salary_drain unless the topic is actually about salary disappearing.\n\n"
            "Return this exact JSON shape:\n"
            "{\n"
            '  "topic_interpretation": "string",\n'
            '  "thesis": "string",\n'
            '  "viewer_promise": "string",\n'
            '  "selected_format": "mechanism_explainer | myth_busting | mistake_breakdown | cautionary_story | psychological_essay | case_study | comparison_breakdown | action_plan",\n'
            '  "format_rationale": "string",\n'
            '  "recurring_example": "string",\n'
            '  "allowed_mechanisms": ["mechanism_key"],\n'
            '  "forbidden_drift": ["string"],\n'
            '  "scene_function_map": [\n'
            '    {"scene_index": 1, "function": "string", "mechanism": "mechanism_key", "emotional_direction": "building | revealing | tightening | releasing | warning | clarity"}\n'
            "  ],\n"
            '  "tone_directive": "string"\n'
            "}\n"
        )

    def _script_brief_block(self, script_brief: dict[str, Any] | None) -> str:
        if not script_brief:
            return ""
        brief_json = json.dumps(script_brief, ensure_ascii=False, indent=2)
        return (
            "SCRIPT STRATEGY BRIEF (BINDING CONTRACT):\n"
            f"{brief_json}\n\n"
            "Rules for using this brief:\n"
            "* The hook must create curiosity around the thesis.\n"
            "* Every body scene must use recurring_example as the primary example.\n"
            "* Do not introduce a different primary example.\n"
            "* Generate exactly one body scene per scene_function_map entry.\n"
            "* Each scene's mechanism must match its scene_function_map entry exactly.\n"
            "* Avoid every forbidden_drift item.\n"
            "* tone_directive is binding.\n\n"
            "---\n\n"
        )

    def _recurring_example(self, topic: str, angle: str) -> str:
        text = f"{topic} {angle}".lower()
        if any(token in text for token in ("monthly payment", "monthly payments", "subscription", "bnpl", "no cost emi", "rich people love monthly")):
            return "an expensive purchase being reframed from a painful full price into a harmless-looking monthly payment"
        if any(token in text for token in ("credit card", "minimum payment", "debt")):
            return "a credit-card balance where the minimum payment feels responsible while interest keeps control"
        if any(token in text for token in ("inflation", "fd", "purchasing power")):
            return "money that looks safe in an FD or savings account while real buying power changes"
        if any(token in text for token in ("sip", "compound", "mutual fund")):
            return "a small monthly investment whose result depends more on time and consistency than excitement"
        if any(token in text for token in ("tax", "ctc", "take home")):
            return "a salary offer where CTC, deductions, and actual take-home create different realities"
        if any(token in text for token in ("salary", "month end", "payday", "raise", "lifestyle")):
            return "a salaried Indian household where income, expenses, and savings fight for the same month"
        return f"a concrete Indian finance decision directly tied to {topic or 'the topic'}, using rupee amounts that serve {angle or 'the stated angle'}"

    def _mechanism_guidance(self, topic: str, angle: str) -> str:
        text = f"{topic} {angle}".lower()
        if any(token in text for token in ("monthly payment", "monthly payments", "subscription", "bnpl", "no cost emi", "rich people love monthly")):
            return (
                "* For this topic, prioritize mechanisms like payment pain reduction, affordability illusion, price anchoring, subscription lock-in, luxury financing psychology, and monthly commitment stacking\n"
            )
        if any(token in text for token in ("credit card", "minimum payment", "debt")):
            return "* For this topic, prioritize minimum-payment psychology, interest compounding, principal stagnation, and debt lock-in\n"
        if any(token in text for token in ("inflation", "fd", "purchasing power")):
            return "* For this topic, prioritize real-return gap, purchasing-power erosion, safety illusion, and delayed consequence\n"
        if any(token in text for token in ("sip", "compound", "mutual fund")):
            return "* For this topic, prioritize time, contribution discipline, compounding curve, and delayed payoff\n"
        return "* For this topic, identify the exact financial or psychological mechanism before writing body scenes\n"
