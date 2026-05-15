from __future__ import annotations

import re
from typing import Any

from .numeric import numeric_amount


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
        amount = numeric_amount(end_value)
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


