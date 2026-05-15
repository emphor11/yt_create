from __future__ import annotations

from typing import Any

from ..pipelines.concept import (
    ConceptSupportMixin,
    SceneDirector,
    numeric_amount as _numeric_amount,
    validate_numbers,
    validate_numeric_logic,
)
from .render_spec_service import RenderSpecService
from .run_log import RunLogger


class ConceptService(ConceptSupportMixin):
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

