from __future__ import annotations

import json
import re
from typing import Any

import requests
from flask import current_app

from .render_spec_service import RenderSpecService
from .run_log import RunLogger


def _numeric_amount(text: str) -> float:
    raw = str(text or "")
    money = re.search(r"₹\s?([\d,.]+)(?:\s?(crores?|lakhs?|k)\b)?", raw, re.I)
    if money:
        value = float(money.group(1).replace(",", ""))
        unit = str(money.group(2) or "").lower()
        if unit.startswith("crore"):
            return value * 10_000_000
        if unit.startswith("lakh"):
            return value * 100_000
        if unit == "k":
            return value * 1_000
        return value
    cleaned = raw.lower().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if not match:
        return 0.0
    value = float(match.group(1))
    if "crore" in cleaned:
        return value * 10_000_000
    if "lakh" in cleaned:
        return value * 100_000
    if re.search(r"\bk\b", cleaned):
        return value * 1_000
    return value


def validate_numbers(
    start: str,
    change: str,
    end: str,
    concept_type: str,
    narration: str = "",
) -> tuple[bool, str]:
    """Validate visible finance math before a beat can reach rendering."""

    start_value = _numeric_amount(start)
    end_value = _numeric_amount(end)
    process_text = str(change or "").lower()
    concept = "flow" if str(concept_type or "").lower() == "process" else str(concept_type or "").lower()
    context = f"{start} {change} {end} {narration}"

    if concept == "emphasis":
        return (start_value > 0 or end_value > 0 or bool(re.search(r"\d+(?:\.\d+)?%", f"{start} {end}"))), "emphasis_number"

    if start_value <= 0 or end_value < 0:
        return False, "missing_start_or_end"

    if re.search(r"\b12\s*months?\b|\byear(?:ly)?\b", process_text):
        expected = round(start_value * 12)
        if abs(end_value - expected) > max(1, expected * 0.02):
            return False, "monthly_yearly_math_mismatch"
        return True, "valid_monthly_yearly"

    pct = re.search(r"(\d+(?:\.\d+)?)%", process_text)
    if pct and start_value > 0:
        rate = float(pct.group(1)) / 100.0
        if concept == "growth":
            expected = start_value * (1 + rate)
        else:
            expected = start_value * (1 - rate)
        rate_amount = start_value * rate
        if abs(end_value - expected) > max(2, expected * 0.03) and not (
            concept == "decay" and abs(end_value - rate_amount) <= max(2, rate_amount * 0.03)
        ):
            return False, "percent_math_mismatch"

    if concept == "decay" and not end_value < start_value:
        return False, "decay_must_decrease"
    if concept == "growth" and not end_value > start_value:
        return False, "growth_must_increase"

    if start_value > 0 and end_value / start_value > 100 and not re.search(r"\b(years?|months?|age|%|return|sip)\b", process_text):
        return False, "implausible_jump"
    if start_value > 0 and end_value / start_value > 1000 and not re.search(r"\b(crore|lakh|years?|months?|age|%|return|sip|compound|wealth)\b", context, re.I):
        return False, "random_number_jump"
    return True, "valid"


def validate_numeric_logic(start: str, process: str, end: str, concept_type: str) -> tuple[bool, str]:
    return validate_numbers(start, process, end, concept_type)


class SceneDirector:
    """Owns narration-led beat direction before anything reaches rendering.

    Pipeline: narration → concept → scene_goal → direct_scene → validate → beats
    """

    # Component sequences keyed by visual_verb
    VERB_COMPONENT_MAP: dict[str, list[str]] = {
        "show_decay": ["stat_explosion", "flow_diagram", "stat_explosion"],
        "show_growth": ["stat_explosion", "flow_diagram", "stat_explosion"],
        "show_contrast": ["stat_explosion", "split_comparison", "text_burst"],
        "emphasize": ["stat_explosion", "text_burst"],
    }

    MAX_REGEN_ATTEMPTS = 2

    def __init__(self, concepts: "ConceptService", project_id: int | None = None) -> None:
        self.concepts = concepts
        self.project_id = project_id

    # ------------------------------------------------------------------
    # 1. Scene Goal Generator
    # ------------------------------------------------------------------

    def generate_scene_goal(self, narration: str, concept: dict[str, Any]) -> dict[str, str]:
        """Return {"scene_goal": "...", "visual_verb": "show_decay|show_growth|show_contrast|emphasize"}."""
        concept_type = self.concepts._concept_type(concept)
        scene_goal = str(concept.get("scene_goal") or self.concepts._scene_goal_from_narration(narration, concept_type))

        verb_map = {
            "decay": "show_decay",
            "growth": "show_growth",
            "comparison": "show_contrast",
            "flow": "show_decay",
            "emphasis": "emphasize",
        }
        visual_verb = verb_map.get(concept_type, "emphasize")

        # Override verb if narration signals growth within a decay/flow concept
        lowered = narration.lower()
        if visual_verb == "show_decay" and any(w in lowered for w in ("invest", "sip", "compound", "wealth", "accumulate")):
            visual_verb = "show_growth"

        return {"scene_goal": scene_goal, "visual_verb": visual_verb}

    # ------------------------------------------------------------------
    # 2. Direct Scene — produces 2-4 beats with strict roles
    # ------------------------------------------------------------------

    def direct_scene(
        self,
        narration: str,
        concept: dict[str, Any],
        scene_goal: dict[str, str],
        duration: int | float,
    ) -> list[dict[str, Any]]:
        """Produce 2–4 beats. Beat 0=INTRODUCE, 1=CHANGE, 2=RESULT, 3=OPTIONAL PUNCH."""
        service = self.concepts
        visual_verb = scene_goal.get("visual_verb", "emphasize")
        component_sequence = list(self.VERB_COMPONENT_MAP.get(visual_verb, self.VERB_COMPONENT_MAP["emphasize"]))
        stages = service.flow_stages(concept, narration)

        # Determine beat count from component sequence (2-4)
        max_beats = len(component_sequence)
        if visual_verb == "emphasize":
            max_beats = min(2, max_beats)
        count = max(2, min(4, max_beats))
        beat_duration = max(2.0, min(5.0, max(float(duration or 0), 2.0) / count))

        beats: list[dict[str, Any]] = []
        for index in range(count):
            role = service._role_for_index(index)
            beat_type = component_sequence[index] if index < len(component_sequence) else "text_burst"
            content = service._primary_content_for_index(concept, narration, index)
            caption = service._supporting_idea_for_index(concept, narration, index)

            beat: dict[str, Any] = {
                "beat_index": index,
                "beat_type": beat_type,
                "content": content,
                "caption": caption,
                "color": service.ROLE_COLORS.get(role, "orange"),
                "estimated_start_sec": round(index * beat_duration, 2),
                "estimated_duration_sec": round(beat_duration, 2),
                "concept_metadata": dict(concept),
                "visual_role": role,
            }
            if beat_type == "flow_diagram":
                beat["flow_stages"] = list(stages)
            beats.append(beat)

        # RULE 9/10 — Payoff: final beat must answer "why does this matter?"
        beats = self._ensure_payoff(beats, concept, narration)

        return beats

    # ------------------------------------------------------------------
    # 3. Main orchestrator — build_scene_beats
    # ------------------------------------------------------------------

    def build_scene_beats(self, narration: str, duration: int | float) -> list[dict[str, Any]]:
        service = self.concepts
        narration = str(narration or "")

        # Step 1: extract concept
        concept = service.extract_concept(narration, project_id=self.project_id)
        concept["narration"] = narration

        # Step 2: generate scene goal
        scene_goal = self.generate_scene_goal(narration, concept)
        concept["scene_goal"] = scene_goal["scene_goal"]
        concept["visual_verb"] = scene_goal["visual_verb"]

        service.logger.log(
            "scene_director",
            "running",
            f"Concept extracted: type={service._concept_type(concept)}; verb={scene_goal['visual_verb']}; goal={scene_goal['scene_goal']}; numbers={service._debug_numbers(narration, concept)}.",
            self.project_id,
        )

        # Step 3: direct scene
        beats = self.direct_scene(narration, concept, scene_goal, duration)

        # Step 4: validate beats
        beats = service.validate_beats(beats, narration, concept, project_id=self.project_id)

        # Step 5/6: regenerate if needed (max 2 attempts)
        for attempt in range(self.MAX_REGEN_ATTEMPTS):
            if self._beats_pass_all_rules(beats, concept, narration):
                break
            service.logger.log(
                "scene_director", "running",
                f"Regeneration attempt {attempt + 1}: beats failed rules",
                self.project_id,
            )
            if attempt == 0:
                # Attempt 1: rebuild from scene_goal
                beats = self.direct_scene(narration, concept, scene_goal, duration)
                beats = service.validate_beats(beats, narration, concept, project_id=self.project_id)
            else:
                # Attempt 2: kill switch
                service.logger.log("scene_director", "running", "Kill switch activated", self.project_id)
                beats = [self._kill_switch_beat(concept, narration, duration)]
                break

        return beats

    # ------------------------------------------------------------------
    # Rule enforcement helpers
    # ------------------------------------------------------------------

    def _beats_pass_all_rules(self, beats: list[dict[str, Any]], concept: dict[str, Any], narration: str) -> bool:
        """Check all 13 rules. Return True only if every rule passes."""
        if len(beats) < 1:
            return False

        # RULE 4 — No duplicate components consecutively
        for i in range(1, len(beats)):
            if beats[i]["beat_type"] == beats[i - 1]["beat_type"] and beats[i]["beat_type"] != "text_burst":
                return False

        # RULE 1/2 — Information progression & uniqueness
        seen: set[str] = set()
        for beat in beats:
            sig = self.concepts._information_signature(beat)
            if sig in seen:
                return False
            seen.add(sig)

        # RULE 11 — Visual rhythm: at least 2 different component types
        unique_types = {beat["beat_type"] for beat in beats}
        if len(beats) >= 2 and len(unique_types) < 2:
            return False

        # RULE 12 — Emphasis constraint: max 2 beats
        visual_verb = str(concept.get("visual_verb", ""))
        if visual_verb == "emphasize" and len(beats) > 2:
            return False

        # RULE 9 — Payoff required on final beat
        if not self._has_payoff(beats[-1], concept, narration):
            return False

        return True

    def _has_payoff(self, beat: dict[str, Any], concept: dict[str, Any], narration: str) -> bool:
        """Final beat must answer 'why does this matter?'"""
        caption = str(beat.get("caption") or "")
        content = str(beat.get("content") or "")
        combined = f"{content} {caption}".lower()
        # Must have a number AND some consequence word
        if not self.concepts._has_gravity(content):
            return False
        payoff_signals = ("gone", "left", "lost", "save", "saved", "rent", "month", "year",
                          "wealth", "zero", "₹0", "impact", "total", "final", "worth", "real")
        return any(w in combined for w in payoff_signals) or beat.get("beat_type") == "text_burst"

    def _ensure_payoff(self, beats: list[dict[str, Any]], concept: dict[str, Any], narration: str) -> list[dict[str, Any]]:
        """RULE 9/10: If final beat has no payoff, generate one."""
        if not beats:
            return beats
        last = beats[-1]
        if self._has_payoff(last, concept, narration):
            return beats

        # Generate payoff from real-life meaning
        service = self.concepts
        stages = service.flow_stages(concept, narration)
        end_value = stages[-1]["value"] if stages else str(concept.get("end_value") or "")
        payoff_caption = self._generate_payoff_caption(end_value, narration, concept)

        last["caption"] = payoff_caption
        if last["beat_type"] not in ("text_burst", "stat_explosion"):
            last["beat_type"] = "text_burst"
            last["color"] = "red"
        return beats

    def _generate_payoff_caption(self, end_value: str, narration: str, concept: dict[str, Any]) -> str:
        """Convert numbers into real-life meaning: time, loss, lifestyle impact."""
        amount = _numeric_amount(end_value)
        lowered = narration.lower()

        if amount <= 0 or "₹0" in end_value:
            if "day" in lowered:
                day_match = re.search(r"day\s*(\d+)", lowered)
                return f"Gone in {day_match.group(1)} days" if day_match else "Gone completely"
            return "Gone completely"

        if "year" in lowered or "month" in lowered:
            if amount >= 60000:
                months = round(amount / 30000)
                return f"That's {months} months rent"
            if amount >= 12000:
                return f"₹{int(amount):,}/year lost"
            return f"₹{int(amount):,} every year"

        concept_type = self.concepts._concept_type(concept)
        if concept_type == "growth":
            return f"₹{int(amount):,} built"
        return f"₹{int(amount):,} real impact"

    def _kill_switch_beat(self, concept: dict[str, Any], narration: str, duration: float | int) -> dict[str, Any]:
        """KILL SWITCH: Replace entire scene with single safe stat_explosion."""
        service = self.concepts
        value = service._first_number_from_context(narration, concept) or service._dynamic_fallback_number(narration)
        consequence = self._generate_payoff_caption(
            str(concept.get("end_value") or value), narration, concept
        )
        return {
            "beat_index": 0,
            "beat_type": "stat_explosion",
            "content": service._primary_number_from_text(value) or value,
            "caption": consequence,
            "color": "red",
            "estimated_start_sec": 0.0,
            "estimated_duration_sec": float(duration or 4.0),
            "concept_metadata": dict(concept),
        }

    def _has_transformation_beat(self, beats: list[dict[str, Any]]) -> bool:
        return len(beats) >= 2 and self.concepts._role_for_index(1) == "change" and bool(str(beats[1].get("content") or "").strip())


class ConceptService:
    """Build concept-first, numeric visual beats from narration."""

    CONCEPT_TYPES = {"decay", "growth", "comparison", "flow", "emphasis", "process"}
    ROLE_COLORS = {
        "introduce": "teal",
        "change": "orange",
        "result": "red",
        "emotion": "white",
    }
    COMPONENT_TO_BEAT_TYPE = {
        "FlowDiagram": "flow_diagram",
        "SplitComparison": "split_comparison",
        "StatExplosion": "stat_explosion",
        "TextBurst": "text_burst",
    }
    BANNED_WORDS = {
        "concept",
        "idea",
        "thing",
        "system",
        "flow",
        "contrast",
        "wait what",
        "me every payday",
        "reaction",
        "money decreases",
        "expenses increase",
        "financial stress",
        "value changes",
        "money reality",
        "money problem",
        "this hits different",
        "can't even save",
        "cant even save",
    }
    BANNED_LABEL_WORDS = {"flow", "concept", "idea", "thing", "system"}
    # RULE 17 — Weak caption words to reject
    WEAK_CAPTION_WORDS = {
        "final value", "result", "amount", "savings", "start value",
        "change step", "loss step", "growth step", "numeric change",
        "key number", "impact number", "main stat", "left value",
        "right value", "gap shown", "money punch", "loss punch",
        "wealth punch", "clear winner", "remember this",
    }
    # RULE 14 — Impact signal words (caption-level consequence markers)
    IMPACT_WORDS = {
        "lost", "vanished", "gone", "wasted", "left", "leaked",
        "destroyed", "wiped", "burnt", "drained", "blown",
        "zero", "nothing", "empty", "broke",
        "built", "grew", "earned", "saved", "protected",
        "rent", "emi", "grocery",
        "worse", "better", "real", "actual", "hidden",
        "silent", "invisible", "shocking", "painful",
    }
    STRICT_COMPONENT_BY_CONCEPT = {
        "decay": "flow_diagram",
        "growth": "flow_diagram",
        "flow": "flow_diagram",
        "process": "flow_diagram",
        "comparison": "split_comparison",
        "emphasis": "stat_explosion",
    }

    def __init__(self) -> None:
        self.logger = RunLogger()
        self.render_specs = RenderSpecService()

    def extract_concept(self, narration_text: str, project_id: int | None = None) -> dict[str, Any]:
        narration = str(narration_text or "")
        fallback = self._fallback_concept(narration)
        try:
            payload = self._call_groq_api(
                self._concept_prompt(narration),
                purpose="concept_extraction",
            )
            concept = self._repair_concept(payload, narration)
            self.logger.log("concept_extraction", "completed", "Extracted concept-first visual goal.", project_id)
            return concept
        except Exception as exc:
            self.logger.log("concept_extraction", "failed", f"Concept extraction fallback used: {exc}", project_id)
            return fallback

    def build_visual_explanation(self, concept: dict[str, Any], project_id: int | None = None) -> dict[str, Any]:
        concept = self._repair_concept(concept, str(concept.get("narration") or ""))
        try:
            payload = self._call_groq_api(
                self._visual_explanation_prompt(concept),
                purpose="visual_explanation",
            )
            explanation = self._repair_visual_explanation(payload, concept)
            self.logger.log("visual_explanation", "completed", "Built numeric visual state progression.", project_id)
            return explanation
        except Exception as exc:
            self.logger.log("visual_explanation", "failed", f"Visual explanation fallback used: {exc}", project_id)
            return self._fallback_visual_explanation(concept)

    def build_scene_beats(
        self,
        narration: str,
        duration: int | float,
        project_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return SceneDirector(self, project_id=project_id).build_scene_beats(narration, duration)

    def validate_beats(
        self,
        beats: list[dict[str, Any]],
        narration: str,
        concept: dict[str, Any],
        project_id: int | None = None,
    ) -> list[dict[str, Any]]:
        concept = self._repair_concept(concept, narration)
        stages = self.flow_stages(concept, narration)
        if not stages and self._concept_type(concept) != "emphasis":
            concept = self._downgrade_to_emphasis(concept, narration, "no_valid_stages")
            stages = self.flow_stages(concept, narration)

        repaired: list[dict[str, Any]] = []
        seen_signatures: dict[str, int] = {}
        seen_information: set[str] = set()
        for index, beat in enumerate((beats or [])[:4]):
            current = dict(beat) if isinstance(beat, dict) else {}
            current["beat_index"] = len(repaired)
            current.setdefault("estimated_start_sec", round(len(repaired) * 2.0, 2))
            current.setdefault("estimated_duration_sec", 2.0)
            current["concept_metadata"] = dict(concept)

            role = self._role_for_index(len(repaired))
            current["beat_type"] = self._enforced_beat_type(str(current.get("beat_type") or ""), concept, role, len(repaired))
            current["content"] = self._primary_content_for_index(concept, narration, len(repaired), str(current.get("content") or ""))
            current["caption"] = self._supporting_idea_for_index(concept, narration, len(repaired), str(current.get("caption") or ""))

            # RULE 8 — No fragmented beats: reject single-word meaningless content
            if self._is_fragmented(current):
                self.logger.log("beat_validation", "running", f"Regenerating beat {index}: fragmented_content", project_id)
                current = self._regenerated_beat(concept, narration, len(repaired), "fragmented_content")
                current = self._simplify_beat(current, concept, narration, len(repaired))

            # RULE 13 — Simplicity check: each beat understandable in 2 seconds
            if self._is_overloaded(current):
                self.logger.log("beat_validation", "running", f"Simplifying beat {index}: overloaded_content", project_id)
                current = self._simplify_beat(current, concept, narration, len(repaired))

            valid, reason = self._beat_is_valid(current, concept, narration)
            if not valid:
                self.logger.log("beat_validation", "running", f"Regenerating beat {index}: {reason}", project_id)
                current = self._regenerated_beat(concept, narration, len(repaired), reason)
                current = self._simplify_beat(current, concept, narration, len(repaired))

            if not self._supports_scene_goal(current, concept):
                self.logger.log("beat_validation", "running", f"Regenerating beat {index}: scene_goal_mismatch", project_id)
                current = self._regenerated_beat(concept, narration, len(repaired), "scene_goal_mismatch")
                current = self._simplify_beat(current, concept, narration, len(repaired))

            # RULE 2 — Information uniqueness check
            information_signature = self._information_signature(current)
            if information_signature in seen_information:
                self.logger.log("beat_validation", "running", f"Deleting duplicate beat {index}: repeated_information", project_id)
                continue

            # RULE 4 — No duplicate components consecutively (exception: text_burst)
            if repaired and current["beat_type"] == repaired[-1]["beat_type"] and current["beat_type"] != "text_burst":
                self.logger.log("beat_validation", "running", f"Fixing consecutive duplicate component at beat {index}", project_id)
                current = self._variation_beat(concept, narration, len(repaired))
                current = self._simplify_beat(current, concept, narration, len(repaired))

            signature = self._visual_structure_signature(current)
            seen_signatures[signature] = seen_signatures.get(signature, 0) + 1
            if seen_signatures[signature] > 2:
                self.logger.log("beat_validation", "running", f"Regenerating beat {index}: duplicate_structure", project_id)
                current = self._variation_beat(concept, narration, len(repaired))
                current = self._simplify_beat(current, concept, narration, len(repaired))
                signature = self._visual_structure_signature(current)
                seen_signatures[signature] = seen_signatures.get(signature, 0) + 1

            if current.get("beat_type") == "flow_diagram":
                current["flow_stages"] = list(stages)
            repaired.append(current)
            seen_information.add(self._information_signature(current))

        if len(repaired) < 2:
            repaired = self._beats_from_fallback(concept)

        # RULE 11 — Visual rhythm: ensure at least 2 different component types
        repaired = self._enforce_visual_rhythm(repaired, concept, narration)

        repaired = self._normalize_beat_timing(repaired[:4], narration, concept)
        final: list[dict[str, Any]] = []
        for beat in repaired:
            beat = self._simplify_beat(beat, concept, narration, len(final))
            valid, reason = self._beat_is_valid(beat, concept, narration)
            progression_valid = not final or not self._same_information(final[-1], beat)
            if not valid or not progression_valid or not self._supports_scene_goal(beat, concept):
                failure = reason if valid else reason
                if not progression_valid:
                    failure = "repeated_information"
                self.logger.log("beat_validation", "failed", f"Kill switch safe emphasis: {failure}", project_id)
                final.append(self._safe_emphasis_beat(concept, narration, len(final), reason))
            else:
                final.append(beat)

        # ── SEMANTIC SHARPNESS LAYER (Rules 14-18) ──
        for idx in range(len(final)):
            beat = final[idx]
            # RULE 14/15 — Impact check: upgrade neutral/weak beats
            if not self._creates_impact(beat):
                self.logger.log("beat_validation", "running", f"Upgrading beat {idx}: neutral_no_impact", project_id)
                final[idx] = self._upgrade_to_impact(beat, concept, narration, idx)
            # RULE 17 — Strong wording: replace weak captions
            caption_lower = str(final[idx].get("caption") or "").strip().lower()
            if caption_lower in self.WEAK_CAPTION_WORDS:
                self.logger.log("beat_validation", "running", f"Replacing weak caption at beat {idx}", project_id)
                final[idx] = self._upgrade_to_impact(final[idx], concept, narration, idx)

        # RULE 18 — Final beat must hit hard
        if final:
            final[-1] = self._sharpen_final_beat(final[-1], concept, narration, project_id)

        self.logger.log(
            "beat_validation",
            "completed",
            f"Validated {len(final)} beat(s); concept={self._concept_type(concept)}; numbers={self._debug_numbers(narration, concept)}.",
            project_id,
        )
        return final

    def flow_stages(self, concept: dict[str, Any], narration: str | None = None) -> list[dict[str, str]]:
        narration_text = str(narration or concept.get("narration") or "")
        explicit = concept.get("flow_stages")
        if isinstance(explicit, list) and len(explicit) >= 3:
            stages = [
                {"label": str(stage.get("label") or self._role_for_index(index)), "value": str(stage.get("value") or "")}
                for index, stage in enumerate(explicit[:3])
                if isinstance(stage, dict) and str(stage.get("value") or "").strip()
            ]
            if len(stages) >= 3 and self._stages_are_valid(stages, concept, narration_text):
                return stages

        start = str(concept.get("start_value") or "")
        end = str(concept.get("end_value") or "")
        lowered = narration_text.lower()
        amounts = self.render_specs._money_tokens(narration_text)
        percents = self.render_specs._percent_tokens(narration_text)
        concept_type = self._concept_type(concept)

        if concept_type == "emphasis":
            value = self._first_number_from_context(narration_text, concept) or self._dynamic_fallback_number(narration_text)
            return [
                {"label": "number", "value": value},
                {"label": "impact", "value": self._emphasis_impact_value(narration_text, value)},
            ]

        time_match = re.search(r"\bday\s*(\d+)\b", lowered)
        if time_match:
            start_tokens = self.render_specs._money_tokens(start)
            start_value = amounts[0] if amounts else (start_tokens[0] if start_tokens else start)
            end_value = next((amount for amount in amounts[1:] if self.render_specs._first_numeric_value(amount) == 0), "₹0")
            stages = [
                {"label": "start", "value": f"Day 1 {start_value}"},
                {"label": "change", "value": f"Day {time_match.group(1)}"},
                {"label": "result", "value": end_value},
            ]
            return stages if self._stages_are_valid(stages, concept, narration_text) else []

        investment_years = self._investment_years(lowered)
        if concept_type == "growth" and amounts and investment_years:
            end_amount = self._largest_money_token(amounts[1:] or amounts)
            stages = [
                {"label": "start", "value": f"{amounts[0]}/month" if "month" in lowered else amounts[0]},
                {"label": "change", "value": investment_years},
                {"label": "result", "value": end_amount},
            ]
            return stages if self._stages_are_valid(stages, concept, narration_text) else []

        if percents:
            principal = amounts[0] if amounts else start
            if not principal:
                return []
            rate = percents[0]
            output = self._percentage_output(principal, rate, concept_type)
            explicit_output = self._valid_explicit_percent_output(amounts, principal, rate, concept_type)
            if explicit_output:
                output = explicit_output
            stages = [
                {"label": "start", "value": principal},
                {"label": "change", "value": f"{rate} change"},
                {"label": "result", "value": output},
            ]
            return stages if self._stages_are_valid(stages, concept, narration_text) else []

        if amounts and self._has_time_context(lowered):
            monthly = amounts[0]
            time_label, multiplier = self._time_multiplier_from_narration(lowered)
            derived_total = self.render_specs._format_rupees(_numeric_amount(monthly) * multiplier)
            total = next((amount for amount in amounts[1:] if abs(_numeric_amount(amount) - _numeric_amount(derived_total)) <= max(2, _numeric_amount(derived_total) * 0.05)), derived_total)
            stages = [
                {"label": "start", "value": f"{monthly}/month"},
                {"label": "change", "value": time_label},
                {"label": "result", "value": total},
            ]
            return stages if self._stages_are_valid(stages, concept, narration_text) else []

        if len(amounts) >= 3 and concept_type in {"flow", "decay", "growth"}:
            stages = [
                {"label": "start", "value": amounts[0]},
                {"label": "change", "value": amounts[1]},
                {"label": "result", "value": amounts[2]},
            ]
            return stages if self._stages_are_valid(stages, concept, narration_text) else []

        if len(amounts) >= 2:
            start_value = amounts[0]
            end_value = amounts[1]
            change_value = self._change_label_from_context(narration_text, start_value, end_value, concept_type)
            stages = [
                {"label": "start", "value": start_value},
                {"label": "change", "value": change_value},
                {"label": "result", "value": end_value},
            ]
            return stages if self._stages_are_valid(stages, concept, narration_text) else []

        if self._has_gravity(start) and self._has_gravity(end):
            middle_value = self._derived_midpoint(start, end, concept_type)
            stages = [
                {"label": "start", "value": start},
                {"label": "change", "value": middle_value},
                {"label": "result", "value": end},
            ]
            return stages if self._stages_are_valid(stages, concept, narration_text) else []

        return []

    def _derive_concept_from_narration(self, narration: str) -> dict[str, Any]:
        narration = str(narration or "")
        logic = self.render_specs.deriveFromNarration(narration)
        logic_type = str(logic.get("type") or "flow") if isinstance(logic, dict) else "flow"
        concept_type = self._infer_concept_type(narration, logic_type)
        scene_goal = self._scene_goal_from_narration(narration, concept_type)
        values = self._values_from_logic(logic)
        start = values[0] if values else ""
        end = values[-1] if len(values) >= 2 else ""
        concept = {
            "scene_goal": scene_goal,
            "concept_name": self._concept_name_from_logic(concept_type),
            "concept_type": concept_type,
            "entities": self._entities_from_narration(narration),
            "transformation": self.render_specs._visual_logic_to_text(logic),
            "start_value": start,
            "end_value": end,
            "outcome": end,
            "explanation_sentence": self.render_specs._visual_logic_to_text(logic),
            "narration": narration,
        }
        stages = self.flow_stages(concept, narration)
        if stages:
            concept["flow_stages"] = stages
            concept["start_value"] = stages[0]["value"]
            concept["end_value"] = stages[-1]["value"]
            concept["transformation"] = " -> ".join(stage["value"] for stage in stages)
            concept["outcome"] = stages[-1]["value"]
            concept["explanation_sentence"] = concept["transformation"]
        elif concept_type != "emphasis":
            concept = self._downgrade_to_emphasis(concept, narration, "unusable_numbers")
        return concept

    def _safe_emphasis_states(self, concept: dict[str, Any]) -> list[dict[str, Any]]:
        stages = self.flow_stages(concept)
        first = stages[0]["value"] if stages else self._first_number_from_context(str(concept.get("narration") or ""), concept) or self._dynamic_fallback_number(str(concept.get("narration") or ""))
        second = stages[-1]["value"] if len(stages) > 1 else self._emphasis_impact_value(str(concept.get("narration") or ""), first)
        return [
            {"beat_position": 0, "key_value": first, "supporting_text": self._caption_for_role(concept, 0), "visual_role": "introduce", "suggested_component": "StatExplosion"},
            {"beat_position": 1, "key_value": second, "supporting_text": self._caption_for_role(concept, 1), "visual_role": "result", "suggested_component": "StatExplosion"},
        ]

    def _stages_are_valid(self, stages: list[dict[str, str]], concept: dict[str, Any], narration: str) -> bool:
        if len(stages) < 2:
            return False
        concept_type = self._concept_type(concept)
        if concept_type == "emphasis":
            return all(self._has_gravity(stage.get("value", "")) for stage in stages)
        if len(stages) < 3:
            return False
        start = stages[0]["value"]
        process = stages[1]["value"]
        end = stages[-1]["value"]
        if not self._numbers_allowed_by_narration([start, process, end], narration):
            return False
        valid, _reason = validate_numbers(start, process, end, concept_type, narration)
        return valid

    def _supports_monthly_yearly(self, lowered: str) -> bool:
        return bool(
            re.search(r"\b(per\s+month|monthly|/month|every month|each month)\b", lowered)
            and re.search(r"\b(year|yearly|annual|annum|12\s+months?)\b", lowered)
        )

    def _has_time_context(self, lowered: str) -> bool:
        """More relaxed than _supports_monthly_yearly: accepts month OR year OR time periods."""
        return bool(re.search(
            r"\b(per\s+month|monthly|/month|every month|each month|per\s+year|yearly|annual|every year|\d+\s*years?|\d+\s*months?)\b",
            lowered,
        ))

    def _time_multiplier_from_narration(self, lowered: str) -> tuple[str, int]:
        """Extract time period and multiplier from narration."""
        years_match = re.search(r"(\d+)\s*years?", lowered)
        months_match = re.search(r"(\d+)\s*months?", lowered)
        if years_match:
            years = int(years_match.group(1))
            return f"{years} years", years * 12
        if months_match:
            months = int(months_match.group(1))
            return f"{months} months", months
        if re.search(r"\b(yearly|annual|per\s+year|every year)\b", lowered):
            return "12 months", 12
        return "12 months", 12

    def _investment_years(self, lowered: str) -> str:
        age_match = re.search(r"\b(?:age\s+of|age)\s+(\d{1,2}).*?\b(?:time\s+you(?:'re| are)?|you\s+are|by)\s+(\d{1,2})\b", lowered)
        if age_match:
            years = int(age_match.group(2)) - int(age_match.group(1))
            if years > 0:
                return f"{years} years"
        years_match = re.search(r"\b(\d{1,2})\s*years?\b", lowered)
        if years_match:
            return f"{years_match.group(1)} years"
        if "long term" in lowered or "long-term" in lowered:
            return "long term"
        return ""

    def _largest_money_token(self, values: list[str]) -> str:
        if not values:
            return ""
        return max(values, key=_numeric_amount)

    def _percentage_output(self, principal: str, rate: str, concept_type: str) -> str:
        principal_value = _numeric_amount(principal)
        rate_value = _numeric_amount(rate) / 100.0
        if concept_type == "growth":
            return self.render_specs._format_rupees(principal_value * (1 + rate_value))
        return self.render_specs._format_rupees(principal_value * (1 - rate_value))

    def _valid_explicit_percent_output(self, amounts: list[str], principal: str, rate: str, concept_type: str) -> str:
        expected = _numeric_amount(self._percentage_output(principal, rate, concept_type))
        rate_amount = _numeric_amount(principal) * (_numeric_amount(rate) / 100.0)
        for amount in amounts[1:]:
            amount_value = _numeric_amount(amount)
            if abs(amount_value - expected) <= max(2, expected * 0.03):
                return amount
            if concept_type == "decay" and abs(amount_value - rate_amount) <= max(2, rate_amount * 0.03):
                return amount
        return ""

    def _change_label_from_context(self, narration: str, start: str, end: str, concept_type: str) -> str:
        lowered = narration.lower()
        if "leak" in lowered:
            return "leak"
        if "expense" in lowered or "spend" in lowered:
            return "spend"
        if "save" in lowered:
            return "saved"
        if concept_type == "growth":
            return "growth"
        if concept_type == "decay":
            return "loss"
        return f"{start} to {end}"

    def _derived_midpoint(self, start: str, end: str, concept_type: str) -> str:
        start_value = _numeric_amount(start)
        end_value = _numeric_amount(end)
        if concept_type == "growth":
            return self.render_specs._format_rupees((start_value + end_value) / 2)
        return self.render_specs._format_rupees(max(end_value, start_value / 2))

    def _first_number_from_context(self, narration: str, concept: dict[str, Any]) -> str:
        # Priority: money tokens first (₹X), then percentages
        money = self.render_specs._money_tokens(narration)
        if money:
            return money[0]
        percents = self.render_specs._percent_tokens(narration)
        if percents:
            return percents[0]
        # Try concept fields
        for key in ("start_value", "end_value", "outcome", "transformation", "explanation_sentence"):
            values = self._values_from_text(str(concept.get(key) or ""))
            if values:
                return values[0]
        # Try narration embedded numbers (e.g. "5 lakh")
        lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*lakhs?", narration, re.I)
        if lakh_match:
            return self.render_specs._format_rupees(float(lakh_match.group(1)) * 100_000)
        crore_match = re.search(r"(\d+(?:\.\d+)?)\s*crores?", narration, re.I)
        if crore_match:
            return self.render_specs._format_rupees(float(crore_match.group(1)) * 10_000_000)
        return ""

    def _dynamic_fallback_number(self, narration: str) -> str:
        """Generate a context-appropriate fallback instead of always using ₹5,000."""
        lowered = narration.lower()
        # Insurance (check before rent/emi since "premium" contains "emi")
        if any(w in lowered for w in ("insurance", "premium", "policy", "cover")):
            return "₹20,000"
        # Salary context
        if any(w in lowered for w in ("salary", "income", "paycheck", "payday", "ctc")):
            return "₹25,000"
        # Investment context
        if any(w in lowered for w in ("sip", "invest", "mutual fund", "portfolio")):
            return "₹10,000"
        # Rent/EMI context (use word boundary to avoid substring matches)
        if re.search(r"\b(rent|emi|loan|mortgage)\b", lowered):
            return "₹15,000"
        # Debt/credit context
        if any(w in lowered for w in ("debt", "credit card", "interest", "borrow")):
            return "₹50,000"
        # Food/dining/subscription
        if any(w in lowered for w in ("food", "dining", "zomato", "swiggy", "subscription", "netflix")):
            return "₹2,000"
        # Generic finance
        return "₹5,000"

    def _emphasis_impact_value(self, narration: str, value: str) -> str:
        amounts = self.render_specs._money_tokens(narration)
        percents = self.render_specs._percent_tokens(narration)
        if value in percents and amounts:
            return amounts[0]
        if value in amounts and percents:
            return percents[0]
        return value

    def _downgrade_to_emphasis(self, concept: dict[str, Any], narration: str, reason: str) -> dict[str, Any]:
        value = self._first_number_from_context(narration, concept) or self._dynamic_fallback_number(narration)
        return {
            **concept,
            "concept_type": "emphasis",
            "concept_name": "finance stat",
            "scene_goal": self._clean_phrase(str(concept.get("scene_goal") or "prove the key number"), "prove the key number"),
            "transformation": value,
            "start_value": value,
            "end_value": self._emphasis_impact_value(narration, value),
            "outcome": self._emphasis_impact_value(narration, value),
            "explanation_sentence": f"{value} matters",
            "fallback_reason": reason,
            "narration": narration,
        }

    def _numbers_allowed_by_narration(self, values: list[str], narration: str) -> bool:
        """RELAXED: Accept if number is in narration, derived, OR close to a narration amount."""
        if not narration.strip():
            return True
        allowed = set(self.render_specs._money_tokens(narration) + self.render_specs._percent_tokens(narration))
        derived = self._derived_numbers_from_narration(narration)
        allowed.update(derived)

        # Pre-compute narration amounts for proximity check
        narration_amounts = [_numeric_amount(t) for t in allowed if _numeric_amount(t) > 0]

        for value in values:
            tokens = self.render_specs._money_tokens(value) + self.render_specs._percent_tokens(value)
            for token in tokens:
                if token in allowed:
                    continue
                # RELAXED: accept if within 5% of any narration/derived amount
                token_amount = _numeric_amount(token)
                if token_amount > 0 and any(
                    abs(token_amount - na) <= max(2, na * 0.05) for na in narration_amounts
                ):
                    continue
                # RELAXED: accept time references (e.g. "Day 12", "12 months")
                if re.search(r"\b(day|month|year|week)\b", value, re.I):
                    continue
                # RELAXED: accept ₹0 endpoint (common in decay)
                if token_amount == 0:
                    continue
                return False
        return True

    def _derived_numbers_from_narration(self, narration: str) -> set[str]:
        lowered = narration.lower()
        amounts = self.render_specs._money_tokens(narration)
        percents = self.render_specs._percent_tokens(narration)
        derived: set[str] = set()

        # Monthly → yearly (both strict and relaxed)
        if amounts and self._has_time_context(lowered):
            _label, multiplier = self._time_multiplier_from_narration(lowered)
            for amt in amounts:
                derived.add(self.render_specs._format_rupees(_numeric_amount(amt) * multiplier))

        # Percentage derivations: apply to ALL amounts, not just first
        if amounts and percents:
            for amt in amounts:
                for pct in percents:
                    derived.add(self._percentage_output(amt, pct, "decay"))
                    derived.add(self._percentage_output(amt, pct, "growth"))

        # Compound growth: amt * (1 + rate)^years
        years_match = re.search(r"(\d+)\s*years?", lowered)
        if amounts and percents and years_match:
            years = int(years_match.group(1))
            for amt in amounts:
                for pct in percents:
                    rate = float(re.search(r"(\d+(?:\.\d+)?)", pct).group(1)) / 100.0
                    compound = _numeric_amount(amt) * ((1 + rate) ** years)
                    derived.add(self.render_specs._format_rupees(compound))

        # Multi-amount derivations: difference between amounts
        if len(amounts) >= 2:
            for i in range(len(amounts)):
                for j in range(i + 1, len(amounts)):
                    diff = abs(_numeric_amount(amounts[i]) - _numeric_amount(amounts[j]))
                    if diff > 0:
                        derived.add(self.render_specs._format_rupees(diff))

        # Common endpoints
        if any(word in lowered for word in ("vanish", "zero", "₹0", "manual", "emotion", "gone", "nothing")):
            derived.add("₹0")
        if any(word in lowered for word in ("vanish", "salary", "payday", "paycheck")) and not amounts:
            derived.add("₹25,000")

        return derived

    def _debug_numbers(self, narration: str, concept: dict[str, Any]) -> str:
        values = self.render_specs._money_tokens(narration) + self.render_specs._percent_tokens(narration)
        derived = sorted(self._derived_numbers_from_narration(narration))
        return json.dumps({"narration": values, "derived": derived, "concept": concept.get("flow_stages")}, ensure_ascii=False)

    def _call_groq_api(self, prompt: str, purpose: str) -> dict[str, Any]:
        api_key = current_app.config.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not configured.")
        body = {
            "model": current_app.config.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            "messages": [
                {"role": "system", "content": "Return strict JSON only. No markdown, no commentary."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.35,
            "max_tokens": 900,
            "response_format": {"type": "json_object"},
        }
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "YTCreate/1.0",
            },
            timeout=25,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return self._extract_json(text)

    def _extract_json(self, raw_text: str) -> dict[str, Any]:
        cleaned = str(raw_text or "").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Model response did not contain JSON.")
        return json.loads(cleaned[start : end + 1])

    def _concept_prompt(self, narration: str) -> str:
        return (
            "You are a concept extraction engine for finance education videos.\n\n"
            "CRITICAL RULE:\n"
            "Your output must contain visualizable elements:\n"
            "- at least one number OR\n"
            "- a clear transformation OR\n"
            "- a comparison\n\n"
            "NUMBER RULE:\n"
            "Use numbers from narration if present.\n"
            "Do NOT invent unrelated numbers.\n\n"
            "Return JSON:\n\n"
            "{\n"
            '  "scene_goal": "",\n'
            '  "concept_name": "",\n'
            '  "concept_type": "decay|growth|comparison|flow|emphasis|process",\n'
            '  "entities": [],\n'
            '  "transformation": "",\n'
            '  "start_value": "",\n'
            '  "end_value": "",\n'
            '  "outcome": "",\n'
            '  "explanation_sentence": ""\n'
            "}\n\n"
            "Rules:\n"
            "- scene_goal must say what this scene is trying to prove\n"
            "- entities must be concrete\n"
            "- transformation must describe visible change\n"
            "- explanation_sentence must describe numeric states only\n"
            "- Reject vague outputs\n\n"
            f"Narration: {narration}"
        )

    def _visual_explanation_prompt(self, concept: dict[str, Any]) -> str:
        return (
            "You are a visual explanation designer.\n\n"
            "CRITICAL RULE:\n"
            "- NO sentences\n"
            "- ONLY visual states\n"
            "- MUST contain numbers or labeled values\n"
            "- MUST show progression\n"
            "- Every beat must support scene_goal\n"
            "STRICT FORMAT:\n"
            "{\n"
            '  "visual_narrative": [\n'
            "    {\n"
            '      "beat_position": 0,\n'
            '      "key_value": "",\n'
            '      "supporting_text": "",\n'
            '      "visual_role": "introduce|change|result|emotion",\n'
            '      "suggested_component": ""\n'
            "    }\n"
            "  ],\n"
            '  "overall_structure": "",\n'
            '  "story_arc": ""\n'
            "}\n\n"
            "Rules:\n"
            "- 2-4 beats\n"
            "- beat 0 = introduce\n"
            "- beat 1 = change\n"
            "- beat 2 = result\n"
            "- beat 3 = optional emotion\n"
            "- key_value MUST be number OR short value with ₹ or %\n"
            "- supporting_text max 6 words\n"
            "- decay/growth/flow/process -> FlowDiagram\n"
            "- comparison -> SplitComparison\n"
            "- emphasis -> StatExplosion\n"
            "- beat 3 -> TextBurst\n"
            "- BANNED: ReactionCard, descriptive sentences\n\n"
            f"Concept: {json.dumps(concept, ensure_ascii=False)}"
        )

    def _repair_concept(self, payload: dict[str, Any], narration: str) -> dict[str, Any]:
        fallback = self._fallback_concept(narration)
        if not isinstance(payload, dict):
            return fallback
        concept = {**fallback, **payload}
        concept["concept_type"] = self._concept_type(concept)
        concept["entities"] = self._concrete_entities(concept.get("entities"), fallback["entities"])
        concept["scene_goal"] = self._clean_phrase(str(concept.get("scene_goal") or fallback["scene_goal"]), fallback["scene_goal"])
        for key in ("concept_name", "transformation", "start_value", "end_value", "outcome", "explanation_sentence"):
            concept[key] = self._clean_phrase(str(concept.get(key) or fallback[key]), fallback[key])
        if not self._has_gravity(" ".join(str(concept.get(key) or "") for key in ("transformation", "start_value", "end_value", "outcome", "explanation_sentence"))):
            return fallback
        concept["narration"] = narration
        stages = self.flow_stages(concept, narration)
        if stages:
            concept["flow_stages"] = stages
            if concept["concept_type"] != "emphasis":
                concept["start_value"] = stages[0]["value"]
                concept["end_value"] = stages[-1]["value"]
                concept["transformation"] = " -> ".join(stage["value"] for stage in stages)
                concept["outcome"] = stages[-1]["value"]
                concept["explanation_sentence"] = concept["transformation"]
        elif concept["concept_type"] != "emphasis":
            return self._downgrade_to_emphasis(concept, narration, "concept_numbers_failed_validation")
        return concept

    def _fallback_concept(self, narration: str) -> dict[str, Any]:
        return self._derive_concept_from_narration(narration)

    def _repair_visual_explanation(self, payload: dict[str, Any], concept: dict[str, Any]) -> dict[str, Any]:
        raw_beats = payload.get("visual_narrative") if isinstance(payload, dict) else None
        if not isinstance(raw_beats, list):
            return self._fallback_visual_explanation(concept)
        beats: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_beats[:4]):
            if not isinstance(raw, dict):
                continue
            role = str(raw.get("visual_role") or self._role_for_index(index)).lower()
            component = str(raw.get("suggested_component") or self._component_for_concept(concept, index))
            key_value = self._numeric_value(str(raw.get("key_value") or ""), concept, index)
            supporting = self._clean_supporting_text(str(raw.get("supporting_text") or ""), concept)
            beats.append(
                {
                    "beat_position": index,
                    "key_value": key_value,
                    "supporting_text": supporting,
                    "visual_role": role if role in self.ROLE_COLORS else self._role_for_index(index),
                    "suggested_component": component if component in self.COMPONENT_TO_BEAT_TYPE else self._component_for_concept(concept, index),
                }
            )
        if len(beats) < 2:
            return self._fallback_visual_explanation(concept)
        return {
            "visual_narrative": beats,
            "overall_structure": "numeric_progression",
            "story_arc": str(concept.get("scene_goal") or ""),
        }

    def _fallback_visual_explanation(self, concept: dict[str, Any]) -> dict[str, Any]:
        stages = self.flow_stages(concept)
        if len(stages) < 2:
            narrative = self._safe_emphasis_states(concept)
            return {"visual_narrative": narrative, "overall_structure": "safe_emphasis", "story_arc": str(concept.get("scene_goal") or "")}
        concept_type = self._concept_type(concept)
        component = self._component_for_concept(concept, 0)
        if concept_type == "comparison":
            values = self._values_from_text(str(concept.get("transformation") or ""))
            left = values[0] if values else stages[0]["value"]
            right = values[1] if len(values) > 1 else stages[-1]["value"]
            narrative = [
                {"beat_position": 0, "key_value": left, "supporting_text": self._caption_for_role(concept, 0), "visual_role": "introduce", "suggested_component": "SplitComparison"},
                {"beat_position": 1, "key_value": right, "supporting_text": self._caption_for_role(concept, 1), "visual_role": "change", "suggested_component": "SplitComparison"},
                {"beat_position": 2, "key_value": f"{left} vs {right}", "supporting_text": "gap shown", "visual_role": "result", "suggested_component": "SplitComparison"},
            ]
        else:
            narrative = [
                {"beat_position": 0, "key_value": stages[0]["value"], "supporting_text": self._caption_for_role(concept, 0), "visual_role": "introduce", "suggested_component": component},
                {"beat_position": 1, "key_value": " -> ".join(stage["value"] for stage in stages[:3]) if len(stages) >= 3 else stages[1]["value"], "supporting_text": self._caption_for_role(concept, 1), "visual_role": "change", "suggested_component": component},
                {"beat_position": 2, "key_value": stages[-1]["value"], "supporting_text": self._caption_for_role(concept, 2), "visual_role": "result", "suggested_component": component},
            ]
        return {"visual_narrative": narrative, "overall_structure": "numeric_progression", "story_arc": str(concept.get("scene_goal") or "")}

    def _beats_from_fallback(self, concept: dict[str, Any]) -> list[dict[str, Any]]:
        stages = self.flow_stages(concept)
        if len(stages) < 2:
            return [self._safe_emphasis_beat(concept, str(concept.get("narration") or ""), 0, "no_fallback_stages")]
        return [
            {
                "beat_index": index,
                "beat_type": self._beat_type_for_role(concept, index, self._role_for_index(index)),
                "content": stage["value"],
                "caption": self._caption_for_role(concept, index),
                "color": self.ROLE_COLORS.get(self._role_for_index(index), "orange"),
                "estimated_start_sec": index * 2.0,
                "estimated_duration_sec": 2.0,
                "concept_metadata": dict(concept),
                "flow_stages": list(stages) if self._beat_type_for_role(concept, index, self._role_for_index(index)) == "flow_diagram" else None,
            }
            for index, stage in enumerate(stages)
        ]

    def _values_from_logic(self, logic: Any) -> list[str]:
        if not isinstance(logic, dict):
            return []
        if logic.get("type") == "comparison":
            return [str(logic.get("left") or ""), str(logic.get("right") or "")]
        if logic.get("type") == "flow":
            return [str(logic.get("source") or ""), str(logic.get("result") or "")]
        if logic.get("type") in {"decay", "growth"}:
            return [str(logic.get("input") or ""), str(logic.get("output") or "")]
        if logic.get("type") == "emphasis":
            return [str(logic.get("headline") or ""), str(logic.get("subtext") or "")]
        return []

    def _values_from_text(self, text: str) -> list[str]:
        tokens = self.render_specs._money_tokens(text) + self.render_specs._percent_tokens(text)
        if tokens:
            return list(dict.fromkeys(tokens))
        return re.findall(r"\b\d+(?:\.\d+)?\b", text)

    def _numeric_value(self, value: str, concept: dict[str, Any], index: int) -> str:
        cleaned = self._clean_phrase(value, "")
        if cleaned and self._has_gravity(cleaned) and not self._is_sentence(cleaned):
            return self._primary_number_from_text(cleaned) or cleaned
        stages = self.flow_stages(concept)
        if index < len(stages):
            return self._primary_number_from_text(stages[index]["value"]) or stages[index]["value"]
        return self._first_number_from_context(str(concept.get("narration") or ""), concept) or self._dynamic_fallback_number(str(concept.get("narration") or ""))

    def _primary_content_for_index(self, concept: dict[str, Any], narration: str, index: int, requested: str = "") -> str:
        concept_type = self._concept_type(concept)
        if concept_type == "comparison":
            return self._comparison_content_for_index(concept, narration, index)
        stages = self.flow_stages(concept, narration)
        if index < len(stages):
            primary = self._primary_number_from_text(str(stages[index].get("value") or ""))
            if primary:
                return primary
        primary = self._primary_number_from_text(requested)
        if primary:
            return primary
        if index == 1 and len(stages) >= 3:
            return self._primary_number_from_text(str(stages[1].get("value") or "")) or str(stages[1].get("value") or "")
        return self._numeric_value(requested, concept, index)

    def _comparison_content_for_index(self, concept: dict[str, Any], narration: str, index: int) -> str:
        values = self._comparison_values(concept, narration)
        if len(values) >= 2:
            left, right = values[0], values[1]
            if index == 0:
                return self._primary_number_from_text(left) or left
            if index == 1:
                return self._primary_number_from_text(right) or right
            return f"{left} vs {right}"
        return self._first_number_from_context(narration, concept) or self._dynamic_fallback_number(narration)

    def _comparison_values(self, concept: dict[str, Any], narration: str) -> list[str]:
        values = self._values_from_text(str(concept.get("transformation") or ""))
        if len(values) >= 2:
            return values[:2]
        amounts = self.render_specs._money_tokens(narration)
        percents = self.render_specs._percent_tokens(narration)
        values = amounts + percents
        if len(values) >= 2:
            return values[:2]
        stages = self.flow_stages(concept, narration)
        return [str(stage.get("value") or "") for stage in stages[:2] if str(stage.get("value") or "").strip()]

    def _supporting_idea_for_index(self, concept: dict[str, Any], narration: str, index: int, requested: str = "") -> str:
        requested_clean = self._clean_supporting_text(requested, concept) if str(requested or "").strip() else ""
        if requested_clean and not self._generic_caption(requested_clean):
            return requested_clean
        stages = self.flow_stages(concept, narration)
        if index < len(stages):
            idea = self._supporting_idea_from_value(str(stages[index].get("value") or ""), str(stages[index].get("label") or ""))
            semantic = self._semantic_label_for_index(concept, narration, index)
            if semantic and (not idea or idea.lower() in {"start", "change", "result", "day"}):
                return semantic
            if idea:
                return idea
        semantic = self._semantic_label_for_index(concept, narration, index)
        if semantic:
            return semantic
        return self._caption_for_role(concept, index)

    def _semantic_label_for_index(self, concept: dict[str, Any], narration: str, index: int) -> str:
        lowered = f"{narration} {concept.get('scene_goal', '')} {concept.get('transformation', '')}".lower()
        concept_type = self._concept_type(concept)
        if concept_type == "growth":
            return ["Invested", "Growth", "Final Value", "Wealth"][min(index, 3)]
        if "month" in lowered and "year" in lowered:
            return ["Monthly", "12 Months", "Yearly Loss", "Total"][min(index, 3)]
        if "salary" in lowered and index == 0:
            return "Salary"
        if any(word in lowered for word in ("leak", "lost", "loss", "gone", "vanish", "inflation")) and index == 1:
            return "Leak" if "leak" in lowered else ("Day" if "day" in lowered else "Loss")
        if any(word in lowered for word in ("left", "leaves", "save", "saving", "savings", "vanish", "gone")) and index == 2:
            return "Left" if any(word in lowered for word in ("left", "leaves", "vanish", "gone")) else "Saved"
        return ""

    def _supporting_idea_from_value(self, value: str, label: str = "") -> str:
        cleaned = re.sub(r"₹\s?[\d,.]+(?:\s?(?:lakhs?|crores?|k|m)\b)?", " ", str(value or ""), flags=re.I)
        cleaned = re.sub(r"\d+(?:\.\d+)?%", " ", cleaned)
        cleaned = re.sub(r"\b\d+(?:\.\d+)?\b", " ", cleaned)
        words = [word for word in re.findall(r"[A-Za-z]+", cleaned) if word.lower() not in {"per", "month", "year", "years", "change"}]
        if words:
            return " ".join(words[:3]).title()
        label = str(label or "").strip()
        if label and label.lower() not in {"start", "change", "result", "number", "impact"}:
            return label.title()
        return ""

    def _primary_number_from_text(self, text: str) -> str:
        text = str(text or "")
        money = self.render_specs._money_tokens(text)
        if money:
            return money[0]
        percents = self.render_specs._percent_tokens(text)
        if percents:
            return percents[0]
        day = re.search(r"\bday\s*\d+\b", text, re.I)
        if day:
            return day.group(0).title()
        number = re.search(r"\b\d+(?:\.\d+)?\b", text)
        return number.group(0) if number else ""

    def _numeric_token_count(self, text: str) -> int:
        text = str(text or "")
        money = self.render_specs._money_tokens(text)
        percent = self.render_specs._percent_tokens(text)
        stripped = text
        for token in money + percent:
            stripped = stripped.replace(token, " ")
        bare = re.findall(r"\b\d+(?:\.\d+)?\b", stripped)
        return len(money) + len(percent) + len(bare)

    def _generic_caption(self, text: str) -> bool:
        lowered = " ".join(str(text or "").lower().split())
        return lowered in {
            "start value",
            "change step",
            "result value",
            "loss step",
            "growth step",
            "final value",
            "left value",
            "right value",
            "gap shown",
            "key number",
            "impact number",
            "main stat",
            "numeric change",
        } or self._contains_banned(lowered) or self._contains_label_banned(lowered)

    def _progression_content(self, concept: dict[str, Any]) -> str:
        stages = self.flow_stages(concept)
        if len(stages) < 2:
            return self._first_number_from_context(str(concept.get("narration") or ""), concept) or self._dynamic_fallback_number(str(concept.get("narration") or ""))
        return f"{stages[0]['value']} -> {stages[-1]['value']}"

    def _supports_scene_goal(self, beat: dict[str, Any], concept: dict[str, Any]) -> bool:
        text = f"{beat.get('content', '')} {beat.get('caption', '')}"
        if not self._has_gravity(text):
            return False
        if self._contains_label_banned(text):
            return False
        goal_keywords = self.render_specs._meaningful_keywords(str(concept.get("scene_goal") or ""))
        beat_keywords = self.render_specs._meaningful_keywords(f"{text} {concept.get('transformation', '')}")
        return not goal_keywords or bool(goal_keywords & beat_keywords) or self._content_number_in_concept(str(beat.get("content") or ""), concept)

    def _goal_supporting_beat(self, beat: dict[str, Any], concept: dict[str, Any], index: int) -> dict[str, Any]:
        current = dict(beat)
        current["beat_type"] = str(current.get("beat_type") or "flow_diagram")
        current["content"] = self._numeric_value(str(current.get("content") or ""), concept, index)
        current["caption"] = self._caption_from_concept(concept)
        current["concept_metadata"] = dict(concept)
        return current

    def _alternate_beat_type(self, beat_type: str, seen_types: set[str], concept: dict[str, Any]) -> str:
        if "flow_diagram" not in seen_types:
            return "flow_diagram"
        if str(concept.get("concept_type")) == "comparison" and "split_comparison" not in seen_types:
            return "split_comparison"
        if "stat_explosion" not in seen_types:
            return "stat_explosion"
        return "text_burst"

    def _concept_type(self, concept: dict[str, Any]) -> str:
        raw = str(concept.get("concept_type") or "").strip().lower()
        if raw == "process":
            return "flow"
        if raw in {"decay", "growth", "comparison", "flow", "emphasis"}:
            return raw
        start = _numeric_amount(str(concept.get("start_value") or ""))
        end = _numeric_amount(str(concept.get("end_value") or ""))
        if start > 0 and end >= 0:
            return "growth" if end > start else "decay"
        return "emphasis"

    def _infer_concept_type(self, narration: str, logic_type: str) -> str:
        lowered = str(narration or "").lower()
        if re.search(r"\b(vs|versus|compared|less than|more than)\b", lowered):
            if "cannot" not in lowered and "can't" not in lowered:
                return "comparison"
        if any(word in lowered for word in ("sip", "compound", "invest", "return", "growth", "increase", "accumulate", "wealth")):
            return "growth"
        if any(word in lowered for word in ("inflation", "leak", "lost", "loss", "vanish", "gone", "debt", "interest", "decrease")):
            return "decay"
        if str(logic_type).lower() == "comparison":
            return "comparison"
        if str(logic_type).lower() == "emphasis":
            return "emphasis"
        return "flow"

    def _beat_type_for_role(self, concept: dict[str, Any], index: int, role: str) -> str:
        concept_type = self._concept_type(concept)
        if concept_type == "comparison":
            return "split_comparison"
        if concept_type == "emphasis":
            return "stat_explosion"
        return "flow_diagram"

    def _enforced_beat_type(self, requested: str, concept: dict[str, Any], role: str, index: int) -> str:
        expected = self._beat_type_for_role(concept, index, role)
        requested = str(requested or "").lower()
        if requested != expected and requested != "text_burst":
            return expected
        return requested or expected

    def _beat_is_valid(self, beat: dict[str, Any], concept: dict[str, Any], narration: str) -> tuple[bool, str]:
        content = str(beat.get("content") or "")
        caption = str(beat.get("caption") or "")
        if not self._has_gravity(content):
            return False, "content_missing_number"
        if not content.strip():
            return False, "empty_content"
        if not caption.strip() or self._contains_banned(caption) or self._contains_label_banned(caption):
            return False, "vague_caption"
        if not self._visual_simplification_valid(beat, concept):
            return False, "too_many_primary_numbers"
        if not self._beat_matches_concept_type(beat, concept):
            return False, "concept_component_mismatch"
        # RULE 5 — Meaningful contrast only
        if self._concept_type(concept) in {"comparison", "emphasis"} and not self._has_required_contrast(beat, concept, narration):
            return False, "missing_contrast"
        if not self._numbers_allowed_by_narration([content], narration):
            return False, "number_not_from_narration_or_derivation"
        concept_type = self._concept_type(concept)
        if beat.get("beat_type") == "flow_diagram":
            stages = beat.get("flow_stages") if isinstance(beat.get("flow_stages"), list) else self.flow_stages(concept, narration)
            if len(stages) < 3:
                return False, "flow_missing_start_change_result"
            valid, reason = validate_numbers(stages[0]["value"], stages[1]["value"], stages[-1]["value"], concept_type, narration)
            if not valid:
                return False, reason
            if not self._numbers_allowed_by_narration([stage["value"] for stage in stages], narration):
                return False, "flow_number_not_supported"
            # RULE 6 — Real transformation: reject identical start/change/end
            if not self._flow_has_real_transformation(stages):
                return False, "fake_transformation"
            # RULE 7 — Flow change rule: middle stage must show measurable change
            if not self._flow_middle_has_change(stages):
                return False, "flow_middle_no_change"
        return True, "valid"

    def _visual_simplification_valid(self, beat: dict[str, Any], concept: dict[str, Any]) -> bool:
        count = self._numeric_token_count(str(beat.get("content") or ""))
        if self._concept_type(concept) == "comparison" and int(beat.get("beat_index") or 0) >= 2:
            return count <= 2
        return count <= 1

    def _beat_matches_concept_type(self, beat: dict[str, Any], concept: dict[str, Any]) -> bool:
        beat_type = str(beat.get("beat_type") or "").lower()
        concept_type = self._concept_type(concept)
        strict = self.STRICT_COMPONENT_BY_CONCEPT.get(concept_type, "flow_diagram")
        if beat_type == strict:
            return True
        # Also accept types from visual_verb component mapping (SceneDirector sequences)
        visual_verb = str(concept.get("visual_verb") or "")
        if visual_verb and visual_verb in SceneDirector.VERB_COMPONENT_MAP:
            return beat_type in SceneDirector.VERB_COMPONENT_MAP[visual_verb]
        # text_burst is always acceptable as a final/punch beat
        return beat_type == "text_burst"

    def _has_required_contrast(self, beat: dict[str, Any], concept: dict[str, Any], narration: str) -> bool:
        concept_type = self._concept_type(concept)
        if concept_type == "comparison":
            return len(self._comparison_values(concept, narration)) >= 2 or bool(re.search(r"\bvs\b|\bversus\b", str(beat.get("content") or ""), re.I))
        if concept_type == "emphasis":
            numbers = self.render_specs._money_tokens(narration) + self.render_specs._percent_tokens(narration)
            return len(set(numbers)) >= 2 or self._numeric_token_count(str(beat.get("content") or "")) == 1
        return True

    def _simplify_beat(self, beat: dict[str, Any], concept: dict[str, Any], narration: str, index: int) -> dict[str, Any]:
        current = dict(beat)
        role = self._role_for_index(index)
        current["beat_index"] = index
        current["beat_type"] = self._beat_type_for_role(concept, index, role)
        current["content"] = self._primary_content_for_index(concept, narration, index, str(current.get("content") or ""))
        current["caption"] = self._supporting_idea_for_index(concept, narration, index, str(current.get("caption") or ""))
        current["concept_metadata"] = dict(concept)
        if current["beat_type"] == "flow_diagram":
            current["flow_stages"] = list(self.flow_stages(concept, narration))
        return current

    # ------------------------------------------------------------------
    # RULE 6 — Real transformation check
    # ------------------------------------------------------------------

    def _flow_has_real_transformation(self, stages: list[dict[str, str]]) -> bool:
        """Reject flows where all stages show the same value (e.g. ₹5000 → ₹5000 → ₹5000)."""
        if len(stages) < 3:
            return False
        values = [_numeric_amount(stage["value"]) for stage in stages]
        # If all numeric values are identical and non-zero, it's fake
        if values[0] > 0 and values[0] == values[1] == values[2]:
            return False
        return True

    # ------------------------------------------------------------------
    # RULE 7 — Flow middle must show measurable change
    # ------------------------------------------------------------------

    def _flow_middle_has_change(self, stages: list[dict[str, str]]) -> bool:
        """Middle stage must show measurable change (time, %, amount difference)."""
        if len(stages) < 3:
            return False
        middle = stages[1]["value"].lower()
        # Accept if middle contains: time reference, percentage, or a numeric value
        if re.search(r"(day|month|year|week|%|\d+\s*months?|\d+\s*years?)", middle, re.I):
            return True
        # Accept if middle has a numeric value different from start
        middle_amount = _numeric_amount(middle)
        start_amount = _numeric_amount(stages[0]["value"])
        if middle_amount > 0 and middle_amount != start_amount:
            return True
        # Accept descriptive change labels (e.g. "leak", "growth", "spend")
        change_words = {"leak", "loss", "growth", "spend", "saved", "change", "inflation", "interest"}
        if any(w in middle for w in change_words):
            return True
        return False

    # ------------------------------------------------------------------
    # RULE 8 — Fragmented beat check
    # ------------------------------------------------------------------

    def _is_fragmented(self, beat: dict[str, Any]) -> bool:
        """Reject single-word meaningless beats. Each beat must be self-contained."""
        content = str(beat.get("content") or "").strip()
        caption = str(beat.get("caption") or "").strip()
        # A beat with no numbers and only one word is fragmented
        if not self._has_gravity(content) and len(content.split()) <= 1:
            return True
        # Caption must exist
        if not caption:
            return True
        return False

    # ------------------------------------------------------------------
    # RULE 13 — Overloaded beat check
    # ------------------------------------------------------------------

    def _is_overloaded(self, beat: dict[str, Any]) -> bool:
        """Each beat must be understandable in 2 seconds. Reject if too many tokens."""
        content = str(beat.get("content") or "")
        caption = str(beat.get("caption") or "")
        # More than 2 numeric tokens in content = overloaded (RULE 3: one idea per beat)
        if self._numeric_token_count(content) > 2:
            return True
        # Caption too long to read in 2 seconds
        if len(caption.split()) > 8:
            return True
        return False

    # ------------------------------------------------------------------
    # RULE 11 — Visual rhythm enforcement
    # ------------------------------------------------------------------

    def _enforce_visual_rhythm(self, beats: list[dict[str, Any]], concept: dict[str, Any], narration: str) -> list[dict[str, Any]]:
        """Ensure at least 2 different component types. Convert middle beat if all same."""
        if len(beats) < 2:
            return beats
        unique_types = {beat["beat_type"] for beat in beats}
        if len(unique_types) >= 2:
            return beats

        # All beats are the same type — convert middle beat
        concept_type = self._concept_type(concept)
        mid_index = len(beats) // 2
        current_type = beats[mid_index]["beat_type"]

        if current_type == "stat_explosion":
            new_type = "flow_diagram" if concept_type != "emphasis" else "text_burst"
        elif current_type == "flow_diagram":
            new_type = "split_comparison" if concept_type == "comparison" else "stat_explosion"
        else:
            new_type = "stat_explosion"

        beats[mid_index] = dict(beats[mid_index])
        beats[mid_index]["beat_type"] = new_type
        if new_type == "flow_diagram":
            beats[mid_index]["flow_stages"] = list(self.flow_stages(concept, narration))
        return beats

    # ------------------------------------------------------------------
    # RULES 14-18 — Semantic Sharpness helpers
    # ------------------------------------------------------------------

    def _creates_impact(self, beat: dict[str, Any]) -> bool:
        """RULE 14: Check if beat creates loss, urgency, surprise, contrast, or consequence."""
        content = str(beat.get("content") or "").lower()
        caption = str(beat.get("caption") or "").lower()
        combined = f"{content} {caption}"

        # Caption is a weak/generic label? → no impact regardless
        caption_stripped = caption.strip()
        if caption_stripped in self.WEAK_CAPTION_WORDS:
            return False

        # RULE 15 — Neutral numbers: "₹X/year" or "₹X/month" need consequence in caption
        if re.search(r"₹[\d,]+/(?:year|month)", content):
            # Only passes if caption itself carries consequence
            caption_impact = {"lost", "vanished", "gone", "wasted", "leaked", "drained",
                              "blown", "wiped", "burnt", "destroyed", "rent", "emi",
                              "built", "earned", "saved", "hurts", "painful", "shocking"}
            return any(w in caption for w in caption_impact)

        # Has strong impact words in caption?
        if any(w in caption for w in self.IMPACT_WORDS):
            return True

        # Has ₹0 or zero endpoint?
        if "₹0" in combined or "zero" in combined:
            return True

        # Has strong transformation signal (arrow with different values)?
        if "->" in combined or "→" in combined:
            return True

        # Has percentage that implies loss/gain?
        if re.search(r"\d+%", combined) and any(w in combined for w in ("cut", "lose", "gain", "grow", "drop")):
            return True

        # Content has a number and caption has some substance (not just a label)
        if self._has_gravity(content) and len(caption.split()) >= 2:
            return True

        return False

    def _upgrade_to_impact(self, beat: dict[str, Any], concept: dict[str, Any], narration: str, index: int) -> dict[str, Any]:
        """RULE 16: Convert neutral beat into one with human meaning."""
        upgraded = dict(beat)
        content = str(upgraded.get("content") or "")
        concept_type = self._concept_type(concept)

        # Build a strong caption from the number
        new_caption = self._humanize_number(content, narration, concept_type, index)
        if new_caption:
            upgraded["caption"] = new_caption
        else:
            # Fallback: use semantic label + consequence
            role_caption = self._semantic_label_for_index(concept, narration, index)
            if role_caption and role_caption.lower() not in self.WEAK_CAPTION_WORDS:
                upgraded["caption"] = role_caption
            else:
                upgraded["caption"] = self._consequence_from_concept(concept, narration, index)

        return upgraded

    def _humanize_number(self, content: str, narration: str, concept_type: str, index: int) -> str:
        """RULE 16: Turn raw numbers into real-world meaning."""
        amount = _numeric_amount(content)
        lowered = narration.lower()

        if amount <= 0 or "₹0" in content:
            if "day" in lowered:
                day_match = re.search(r"day\s*(\d+)", lowered)
                return f"Gone in {day_match.group(1)} days" if day_match else "Completely gone"
            return "Completely gone"

        # Monthly → yearly conversion for impact
        if "month" in lowered and amount < 50000:
            yearly = int(amount * 12)
            return f"₹{yearly:,} wasted yearly"

        # Large amounts → lifestyle anchor
        if amount >= 100000:
            months_rent = round(amount / 30000)
            if months_rent >= 2:
                return f"That's {months_rent} months rent"

        # Decay: emphasize loss
        if concept_type == "decay":
            if index == 0:
                return "Had this much"
            return "Lost forever"

        # Growth: emphasize gain
        if concept_type == "growth":
            if index == 0:
                return "Started here"
            return f"₹{int(amount):,} built"

        # Comparison: emphasize gap
        if concept_type == "comparison":
            return "See the gap"

        return ""

    def _consequence_from_concept(self, concept: dict[str, Any], narration: str, index: int) -> str:
        """Generate a consequence-driven caption when humanize fails."""
        concept_type = self._concept_type(concept)
        lowered = narration.lower()

        if concept_type == "decay":
            labels = ["Your money", "Silent leak", "Lost forever", "This hurts"]
        elif concept_type == "growth":
            labels = ["Starts small", "Growing", "Real wealth", "Worth it"]
        elif concept_type == "comparison":
            labels = ["One side", "Other side", "Gap is real", "Winner clear"]
        else:
            labels = ["The number", "What happens", "Real impact", "Remember this"]

        return labels[min(index, len(labels) - 1)]

    def _sharpen_final_beat(self, beat: dict[str, Any], concept: dict[str, Any], narration: str, project_id: int | None = None) -> dict[str, Any]:
        """RULE 18: Final beat must hit hard — conclusion, realization, or punch."""
        sharpened = dict(beat)
        caption = str(sharpened.get("caption") or "").lower().strip()
        content = str(sharpened.get("content") or "")

        # Already strong?
        punch_signals = (
            "gone", "vanished", "wasted", "lost", "wiped", "destroyed",
            "built", "earned", "worth", "rent", "emi", "hurts",
            "real impact", "remember", "that's", "completely",
        )
        if any(w in caption for w in punch_signals):
            return sharpened

        # Upgrade: generate punch caption
        self.logger.log("beat_validation", "running", "Sharpening final beat for impact", project_id)
        concept_type = self._concept_type(concept)
        amount = _numeric_amount(content)
        lowered = narration.lower()

        if amount <= 0 or "₹0" in content:
            day_match = re.search(r"day\s*(\d+)", lowered)
            sharpened["caption"] = f"Gone in {day_match.group(1)} days" if day_match else "Completely gone"
        elif concept_type == "decay":
            if amount >= 60000:
                months = round(amount / 30000)
                sharpened["caption"] = f"That's {months} months rent — lost"
            else:
                sharpened["caption"] = f"₹{int(amount):,} lost silently"
        elif concept_type == "growth":
            sharpened["caption"] = f"₹{int(amount):,} — real wealth built"
        elif concept_type == "comparison":
            sharpened["caption"] = "The gap is real"
        else:
            if "month" in lowered and amount > 0:
                yearly = int(amount * 12)
                sharpened["caption"] = f"₹{yearly:,} wasted every year"
            else:
                sharpened["caption"] = f"₹{int(amount):,} — remember this"

        # Ensure final beat color signals urgency
        if concept_type in ("decay", "comparison"):
            sharpened["color"] = "red"

        return sharpened

    def _same_information(self, previous: dict[str, Any], current: dict[str, Any]) -> bool:
        return self._information_signature(previous) == self._information_signature(current)

    def _information_signature(self, beat: dict[str, Any]) -> str:
        content = str(beat.get("content") or "")
        primary = self._primary_number_from_text(content) or content
        caption = re.sub(r"\d|₹|%|[,./-]", "", str(beat.get("caption") or "")).strip().lower()
        return self._content_signature(f"{beat.get('beat_type')}|{primary}|{caption}")

    def _regenerated_beat(self, concept: dict[str, Any], narration: str, index: int, reason: str) -> dict[str, Any]:
        stages = self.flow_stages(concept, narration)
        if len(stages) < 2:
            return self._safe_emphasis_beat(concept, narration, index, reason)
        role = self._role_for_index(index)
        beat_type = self._beat_type_for_role(concept, index, role)
        content = self._primary_content_for_index(concept, narration, index)
        beat = {
            "beat_index": index,
            "beat_type": beat_type,
            "content": content,
            "caption": self._supporting_idea_for_index(concept, narration, index),
            "color": self.ROLE_COLORS.get(role, "orange"),
            "estimated_start_sec": round(index * 2.0, 2),
            "estimated_duration_sec": 2.0,
            "concept_metadata": dict(concept),
            "regenerated_reason": reason,
        }
        if beat_type == "flow_diagram":
            beat["flow_stages"] = list(stages)
        return beat

    def _variation_beat(self, concept: dict[str, Any], narration: str, index: int) -> dict[str, Any]:
        beat = self._regenerated_beat(concept, narration, index, "forced_variation")
        if index == 3:
            beat["beat_type"] = "text_burst"
        elif beat["beat_type"] == "flow_diagram":
            beat["caption"] = "change shown"
        else:
            beat["caption"] = self._caption_for_role(concept, index)
        return beat

    def _safe_emphasis_beat(self, concept: dict[str, Any], narration: str, index: int, reason: str) -> dict[str, Any]:
        value = self._first_number_from_context(narration, concept) or self._dynamic_fallback_number(narration)
        impact = self._emphasis_impact_value(narration, value)
        if impact == value and re.search(r"\b(cannot|can't|cant|broke|save|left|manual|emotion)\b", narration, re.I):
            impact = "₹0"
        content = value if index == 0 else impact
        return {
            "beat_index": index,
            "beat_type": "stat_explosion",
            "content": self._primary_number_from_text(content) or content,
            "caption": self._supporting_idea_for_index(self._downgrade_to_emphasis(concept, narration, reason), narration, index),
            "color": self.ROLE_COLORS.get(self._role_for_index(index), "orange"),
            "estimated_start_sec": round(index * 2.0, 2),
            "estimated_duration_sec": 2.0,
            "concept_metadata": dict(self._downgrade_to_emphasis(concept, narration, reason)),
            "regenerated_reason": reason,
        }

    def _normalize_beat_timing(self, beats: list[dict[str, Any]], narration: str, concept: dict[str, Any]) -> list[dict[str, Any]]:
        count = max(2, min(4, len(beats)))
        if len(beats) < count:
            while len(beats) < count:
                beats.append(self._regenerated_beat(concept, narration, len(beats), "min_beat_count"))
        duration = sum(float(beat.get("estimated_duration_sec") or 2.0) for beat in beats) or count * 2.0
        beat_duration = max(2.0, min(5.0, duration / count))
        normalized = []
        for index, beat in enumerate(beats[:count]):
            current = {key: value for key, value in beat.items() if value is not None}
            current["beat_index"] = index
            current["estimated_start_sec"] = round(index * beat_duration, 2)
            current["estimated_duration_sec"] = round(beat_duration, 2)
            normalized.append(current)
        return normalized

    def _visual_structure_signature(self, beat: dict[str, Any]) -> str:
        stages = beat.get("flow_stages") if isinstance(beat.get("flow_stages"), list) else []
        stage_text = "->".join(str(stage.get("value") or "") for stage in stages if isinstance(stage, dict))
        return self._content_signature(f"{beat.get('beat_type')}|{beat.get('content')}|{stage_text}")

    def _caption_for_role(self, concept: dict[str, Any], index: int) -> str:
        concept_type = self._concept_type(concept)
        if concept_type == "growth":
            labels = ["start amount", "growth step", "final value", "wealth punch"]
        elif concept_type == "decay":
            labels = ["start value", "loss step", "final value", "loss punch"]
        elif concept_type == "comparison":
            labels = ["left value", "right value", "gap shown", "clear winner"]
        elif concept_type == "emphasis":
            labels = ["key number", "impact number", "main stat", "remember this"]
        else:
            labels = ["start value", "change step", "result value", "money punch"]
        return labels[min(index, len(labels) - 1)]

    def _content_number_in_concept(self, content: str, concept: dict[str, Any]) -> bool:
        concept_text = " ".join(
            str(concept.get(key) or "")
            for key in ("transformation", "start_value", "end_value", "outcome", "explanation_sentence")
        )
        content_tokens = set(self.render_specs._money_tokens(content) + self.render_specs._percent_tokens(content))
        concept_tokens = set(self.render_specs._money_tokens(concept_text) + self.render_specs._percent_tokens(concept_text))
        primary = self._primary_number_from_text(content)
        return bool(content_tokens & concept_tokens) or bool(primary and primary.lower() in concept_text.lower())

    def _component_for_concept(self, concept: dict[str, Any], index: int) -> str:
        concept_type = self._concept_type(concept)
        if concept_type == "comparison":
            return "SplitComparison"
        if concept_type == "emphasis":
            return "StatExplosion"
        return "FlowDiagram"

    def _role_for_index(self, index: int) -> str:
        return ["introduce", "change", "result", "emotion"][min(index, 3)]

    def _clean_supporting_text(self, text: str, concept: dict[str, Any]) -> str:
        cleaned = self._clean_phrase(text, "")
        if not cleaned or self._contains_banned(cleaned) or self._contains_label_banned(cleaned) or self._is_sentence(cleaned):
            cleaned = self._caption_from_concept(concept)
        words = re.findall(r"[A-Za-z0-9₹%.,/-]+", cleaned)
        cleaned = " ".join(words[:6]).strip()
        if self._contains_label_banned(cleaned):
            return self._caption_for_role(concept, 0)
        return cleaned

    def _caption_from_concept(self, concept: dict[str, Any]) -> str:
        scene_goal = str(concept.get("scene_goal") or "")
        goal_words = [
            word
            for word in re.findall(r"[A-Za-z0-9₹%.,/-]+", scene_goal)
            if word.lower() not in {"prove", "show", "that", "this", "scene"}
        ]
        if goal_words:
            return " ".join(goal_words[:6])
        return self.render_specs._short_overlay(str(concept.get("explanation_sentence") or ""), 6) or "numeric change"

    def _clean_phrase(self, text: str, fallback: str) -> str:
        cleaned = " ".join(str(text or "").replace("→", "->").split()).strip()
        if not cleaned or self._contains_banned(cleaned):
            return fallback
        return cleaned

    def _contains_banned(self, text: str) -> bool:
        lowered = " ".join(str(text or "").lower().split())
        return any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in self.BANNED_WORDS)

    def _contains_label_banned(self, text: str) -> bool:
        lowered = " ".join(str(text or "").lower().split())
        return any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in self.BANNED_LABEL_WORDS)

    def _is_sentence(self, text: str) -> bool:
        words = re.findall(r"\w+", text)
        return len(words) > 6 or text.strip().endswith(".")

    def _has_gravity(self, text: str) -> bool:
        return bool(re.search(r"(₹|%|\d|->|\bvs\b|\bversus\b)", str(text or ""), re.I))

    def _content_signature(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip().lower())

    def _value_or_default(self, value: str, fallback: str) -> str:
        value = str(value or "").strip()
        return value if self._has_gravity(value) else fallback

    def _concrete_entities(self, raw: Any, fallback: list[str]) -> list[str]:
        if not isinstance(raw, list):
            return fallback
        entities = []
        for item in raw[:5]:
            text = self._clean_phrase(str(item), "")
            if text and not self._contains_banned(text):
                entities.append(text)
        return entities or fallback

    def _entities_from_narration(self, narration: str) -> list[str]:
        lowered = narration.lower()
        entities = []
        for candidate in ("salary", "expenses", "inflation", "savings", "debt", "interest", "monthly leak", "auto debit"):
            if candidate in lowered:
                entities.append(candidate)
        return entities[:4] or ["money"]

    def _scene_goal_from_narration(self, narration: str, logic_type: str) -> str:
        lowered = narration.lower()
        if "vanish" in lowered or "day" in lowered:
            return "prove salary disappears quickly"
        if "inflation" in lowered:
            return "prove inflation cuts real value"
        if any(word in lowered for word in ("sip", "invest", "return", "compound", "wealth", "accumulate")):
            return "prove money grows over time"
        if "month" in lowered or "year" in lowered:
            return "prove small monthly loss becomes yearly loss"
        if "auto" in lowered or "automate" in lowered:
            return "prove automation protects savings"
        if logic_type == "comparison":
            return "prove the money gap"
        return "prove money changes visibly"

    def _concept_name_from_logic(self, logic_type: str) -> str:
        return {
            "comparison": "money comparison",
            "decay": "value decay",
            "growth": "money growth",
            "emphasis": "money stat",
            "flow": "money progression",
        }.get(logic_type, "money progression")
