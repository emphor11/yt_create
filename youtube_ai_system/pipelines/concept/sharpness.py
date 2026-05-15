from __future__ import annotations

import re
from typing import Any

from .numeric import numeric_amount


class ConceptSharpnessMixin:
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
        amount = numeric_amount(content)
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
        amount = numeric_amount(content)
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
