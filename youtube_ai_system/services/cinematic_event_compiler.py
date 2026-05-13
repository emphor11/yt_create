from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any


@dataclass(frozen=True)
class CinematicEvent:
    id: str
    sentence_index: int
    text: str
    entity_id: str
    label: str
    role: str
    action: str
    visual_verb: str
    visual_mode: str
    variant: str
    start_progress: float
    end_progress: float
    gravity_x: float
    gravity_y: float
    attention_weight: float
    decay_after: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sentence_index": self.sentence_index,
            "text": self.text,
            "entity_id": self.entity_id,
            "label": self.label,
            "role": self.role,
            "action": self.action,
            "visual_verb": self.visual_verb,
            "visual_mode": self.visual_mode,
            "variant": self.variant,
            "start_progress": self.start_progress,
            "end_progress": self.end_progress,
            "gravity": {"x": self.gravity_x, "y": self.gravity_y},
            "attention_weight": self.attention_weight,
            "decay_after": self.decay_after,
        }


@dataclass(frozen=True)
class _Sentence:
    index: int
    text: str
    start_progress: float
    end_progress: float


@dataclass(frozen=True)
class _EntityHit:
    entity_id: str
    label: str
    role: str
    action: str
    visual_verb: str
    visual_mode: str
    hit_index: int


class CinematicEventCompiler:
    """Renderer-facing semantic timeline built from the narration we already have.

    This is deliberately local and deterministic. It does not invent a new
    backend contract; it enriches the existing visual plan with the object that
    should own attention at each spoken meaning shift.
    """

    ENTITY_PATTERNS: tuple[tuple[str, str, str, str, str, str, tuple[str, ...]], ...] = (
        ("salary", "Salary", "income", "arrives", "arrival", "salary_anchor", ("salary", "paycheck", "income", "money comes", "money arrives", "credited")),
        ("raise", "Raise", "income", "expands", "arrival", "hero_arrival", ("raise", "hike", "increment", "bonus", "promotion")),
        ("rent", "Rent", "fixed_expense", "drains", "drain", "expense_attack", ("rent", "apartment", "flat", "upgrade", "house", "housing")),
        ("emi", "EMI", "fixed_expense", "stacks", "stack", "pressure_stack", ("emi", "loan", "installment", "car loan", "home loan")),
        ("food", "Food delivery", "lifestyle_expense", "drains", "drain", "expense_attack", ("food", "delivery", "swiggy", "zomato", "eating out", "restaurant", "coffee")),
        ("shopping", "Shopping", "lifestyle_expense", "drains", "drain", "expense_attack", ("shopping", "clothes", "fashion", "gadgets", "mall", "buying")),
        ("subscriptions", "Subscriptions", "recurring_expense", "repeats", "repeat", "recurring_leak", ("subscription", "subscriptions", "netflix", "spotify", "apps", "membership")),
        ("weekend", "Weekend spending", "lifestyle_expense", "drains", "drain", "expense_attack", ("weekend", "party", "trip", "night out", "outing", "comfort")),
        ("phone", "Phone cost", "lifestyle_expense", "drains", "drain", "expense_attack", ("phone", "mobile", "iphone", "device", "data plan")),
        ("credit_card", "Credit card", "debt", "attaches", "debt", "debt_threat", ("credit card", "swipe", "card bill", "minimum due")),
        ("interest", "Interest", "debt", "compounds", "compound", "spiral", ("interest", "compound", "penalty", "late fee")),
        ("inflation", "Inflation", "erosion", "shrinks", "shrink", "erosion", ("inflation", "price rise", "expensive", "costlier", "purchasing power")),
        ("sip", "SIP", "investment", "grows", "grow", "growth_seed", ("sip", "mutual fund", "invest", "investment", "index fund")),
        ("corpus", "Corpus", "wealth", "reveals", "reveal", "hero_reveal", ("corpus", "wealth", "net worth", "future value")),
        ("emergency_fund", "Emergency fund", "protection", "protects", "protect", "buffer_anchor", ("emergency fund", "buffer", "safety net", "six month", "6 month")),
        ("shock", "Emergency shock", "shock", "hits", "impact", "shock_focus", ("medical", "hospital", "repair", "job loss", "income delay", "unexpected", "emergency")),
        ("savings", "Savings", "survivor", "reveals", "isolate", "survivor_isolation", ("saving", "savings", "leftover", "left over", "remaining", "only", "survive")),
        ("tax", "Tax", "deduction", "drains", "drain", "expense_attack", ("tax", "tds", "gst", "deduction")),
        ("insurance", "Insurance", "protection", "protects", "protect", "protection_layer", ("insurance", "premium", "cover")),
        ("risk", "Risk", "risk", "spreads", "spread", "risk_spread", ("risk", "diversification", "portfolio", "asset allocation")),
    )

    MODE_VARIANTS: dict[str, tuple[str, ...]] = {
        "salary_anchor": ("center_salary", "phone_credit", "account_pulse"),
        "hero_arrival": ("optimistic_expand", "upward_burst", "new_room"),
        "expense_attack": ("left_strike", "right_strike", "top_drop", "diagonal_hit"),
        "pressure_stack": ("vertical_stack", "salary_squeeze", "autopay_wall"),
        "recurring_leak": ("calendar_repeat", "small_chips", "subscription_loop"),
        "debt_threat": ("card_warning", "red_wall", "minimum_due"),
        "spiral": ("ring_attach", "accelerating_curve", "trap_close"),
        "erosion": ("basket_shrink", "silent_fade", "price_lift"),
        "growth_seed": ("seed_drop", "monthly_pulse", "green_lift"),
        "hero_reveal": ("future_hero", "large_number", "wide_reward"),
        "buffer_anchor": ("quiet_reserve", "six_month_wall", "calm_meter"),
        "shock_focus": ("medical_bill", "income_gap", "repair_hit"),
        "survivor_isolation": ("negative_space", "tiny_balance", "last_chip"),
        "protection_layer": ("shield_layer", "claim_buffer", "risk_absorb"),
        "risk_spread": ("grid_spread", "single_to_many", "impact_contained"),
        "generic_focus": ("center_focus", "split_choice", "reveal_card"),
    }

    GRAVITY_POINTS: tuple[tuple[float, float], ...] = (
        (0.5, 0.42),
        (0.72, 0.38),
        (0.29, 0.55),
        (0.62, 0.68),
        (0.38, 0.32),
        (0.78, 0.62),
        (0.5, 0.55),
    )

    def compile(
        self,
        narration: str,
        *,
        component: str = "",
        duration_seconds: float | None = None,
        kind: str = "body",
    ) -> list[dict[str, Any]]:
        sentences = self._sentences(narration)
        if not sentences:
            return []

        events: list[CinematicEvent] = []
        for sentence in sentences:
            hits = self._hits(sentence.text)
            if not hits:
                hits = [self._generic_hit(sentence.text, sentence.index, component)]
            span = max(0.001, sentence.end_progress - sentence.start_progress)
            slot = span / len(hits)
            for local_index, hit in enumerate(hits):
                start = sentence.start_progress + slot * local_index
                end = sentence.start_progress + slot * (local_index + 1)
                events.append(self._event_from_hit(hit, sentence, len(events), start, end))

        events = self._ensure_minimum_density(events, sentences, component, duration_seconds, kind)
        events = self._govern_repetition(events)
        return [event.to_dict() for event in events]

    def attach_to_section(self, section: dict[str, Any], *, duration_seconds: float | None = None) -> dict[str, Any]:
        text = str(section.get("text") or "")
        visual_plan = section.get("visual_plan") or []
        component = ""
        if visual_plan:
            first = visual_plan[0] if isinstance(visual_plan[0], dict) else {}
            component = str(((first.get("visual") or {}) if isinstance(first, dict) else {}).get("pattern") or "")
        events = self.compile(text, component=component, duration_seconds=duration_seconds, kind=str(section.get("kind") or section.get("type") or "body"))
        if not events:
            return section

        updated = dict(section)
        updated["cinematic_events"] = events
        updated_plan: list[dict[str, Any]] = []
        for item in visual_plan:
            if not isinstance(item, dict):
                updated_plan.append(item)
                continue
            next_item = dict(item)
            visual = dict(next_item.get("visual") or {})
            data = dict(visual.get("data") or {})
            data["cinematic_events"] = events
            visual["data"] = data
            next_item["visual"] = visual
            beats_payload = dict(next_item.get("beats") or {})
            beats = []
            for beat in beats_payload.get("beats") or []:
                if not isinstance(beat, dict):
                    beats.append(beat)
                    continue
                next_beat = dict(beat)
                beat_data = dict(next_beat.get("data") or {})
                beat_data["cinematic_events"] = events
                next_beat["data"] = beat_data
                beats.append(next_beat)
            beats_payload["beats"] = beats
            next_item["beats"] = beats_payload
            updated_plan.append(next_item)
        updated["visual_plan"] = updated_plan
        return updated

    def _event_from_hit(self, hit: _EntityHit, sentence: _Sentence, index: int, start: float, end: float) -> CinematicEvent:
        point = self.GRAVITY_POINTS[index % len(self.GRAVITY_POINTS)]
        variants = self.MODE_VARIANTS.get(hit.visual_mode) or self.MODE_VARIANTS["generic_focus"]
        variant = variants[index % len(variants)]
        return CinematicEvent(
            id=f"ce_{index:02d}_{hit.entity_id}",
            sentence_index=sentence.index,
            text=sentence.text,
            entity_id=hit.entity_id,
            label=hit.label,
            role=hit.role,
            action=hit.action,
            visual_verb=hit.visual_verb,
            visual_mode=hit.visual_mode,
            variant=variant,
            start_progress=round(max(0, min(1, start - 0.006)), 4),
            end_progress=round(max(0, min(1, end + 0.01)), 4),
            gravity_x=point[0],
            gravity_y=point[1],
            attention_weight=round(0.78 + min(index % 3, 2) * 0.08, 2),
            decay_after=round(0.055 if hit.visual_mode in {"expense_attack", "shock_focus", "debt_threat"} else 0.08, 3),
        )

    def _ensure_minimum_density(
        self,
        events: list[CinematicEvent],
        sentences: list[_Sentence],
        component: str,
        duration_seconds: float | None,
        kind: str,
    ) -> list[CinematicEvent]:
        duration = float(duration_seconds or 0)
        if kind == "hook":
            target = 2
        elif duration > 0:
            target = max(4, min(9, math.ceil(duration / 10)))
        else:
            target = max(4, min(8, len(sentences)))
        if len(events) >= target:
            return events
        expanded = list(events)
        cursor = len(expanded)
        while len(expanded) < target:
            source = sentences[(len(expanded) - len(events)) % len(sentences)]
            hit = self._generic_hit(source.text, source.index + cursor, component)
            start = len(expanded) / target
            end = (len(expanded) + 1) / target
            expanded.append(self._event_from_hit(hit, source, len(expanded), start, end))
        return sorted(expanded, key=lambda item: (item.start_progress, item.end_progress))

    def _govern_repetition(self, events: list[CinematicEvent]) -> list[CinematicEvent]:
        governed: list[CinematicEvent] = []
        repeat_count = 0
        previous_mode = ""
        for index, event in enumerate(events):
            mode = event.visual_mode
            repeat_count = repeat_count + 1 if mode == previous_mode else 1
            if repeat_count >= 3:
                mode = self._alternate_mode(mode)
                repeat_count = 1
            variants = self.MODE_VARIANTS.get(mode) or self.MODE_VARIANTS["generic_focus"]
            variant = variants[index % len(variants)]
            point = self.GRAVITY_POINTS[index % len(self.GRAVITY_POINTS)]
            governed.append(
                CinematicEvent(
                    **{
                        **event.__dict__,
                        "visual_mode": mode,
                        "variant": variant,
                        "gravity_x": point[0],
                        "gravity_y": point[1],
                    }
                )
            )
            previous_mode = mode
        return governed

    def _alternate_mode(self, mode: str) -> str:
        return {
            "expense_attack": "pressure_stack",
            "shock_focus": "debt_threat",
            "survivor_isolation": "generic_focus",
            "buffer_anchor": "protection_layer",
            "generic_focus": "hero_reveal",
            "pressure_stack": "survivor_isolation",
        }.get(mode, "generic_focus")

    def _hits(self, text: str) -> list[_EntityHit]:
        lowered = text.lower()
        hits: list[_EntityHit] = []
        for entity_id, label, role, action, visual_verb, visual_mode, patterns in self.ENTITY_PATTERNS:
            hit_indexes = [lowered.find(pattern) for pattern in patterns if lowered.find(pattern) >= 0]
            if hit_indexes:
                hits.append(_EntityHit(entity_id, label, role, action, visual_verb, visual_mode, min(hit_indexes)))
        money_hits = list(re.finditer(r"(?:₹\s*|rs\.?\s*)\d[\d,]*(?:\.\d+)?(?:\s*(?:lakh|lakhs|crore|crores|k))?", text, re.IGNORECASE))
        for match in money_hits[:2]:
            if not hits or all(abs(match.start() - hit.hit_index) > 8 for hit in hits):
                label = match.group(0).replace(" ", "")
                hits.append(_EntityHit(f"money_{match.start()}", label, "amount", "reveals", "reveal", self._mode_for_amount_context(lowered), match.start()))
        pct_hits = list(re.finditer(r"\d+(?:\.\d+)?\s*%", text))
        for match in pct_hits[:1]:
            hits.append(_EntityHit(f"rate_{match.start()}", match.group(0), "rate", "changes", "shift", "generic_focus", match.start()))
        return sorted(hits, key=lambda hit: hit.hit_index)[:4]

    def _generic_hit(self, text: str, index: int, component: str) -> _EntityHit:
        label = self._short_label(text)
        lowered = text.lower()
        if any(token in lowered for token in ("grow", "build", "compound", "increase")) or component == "SIPGrowthEngine":
            return _EntityHit(f"generic_growth_{index}", label, "concept", "grows", "grow", "growth_seed", 0)
        if any(token in lowered for token in ("fall", "lose", "shrink", "erode")) or component == "InflationErosionVisualizer":
            return _EntityHit(f"generic_loss_{index}", label, "concept", "shrinks", "shrink", "erosion", 0)
        if any(token in lowered for token in ("protect", "save", "survive", "safe")):
            return _EntityHit(f"generic_protect_{index}", label, "concept", "protects", "protect", "protection_layer", 0)
        if any(token in lowered for token in ("trap", "debt", "interest", "stuck")):
            return _EntityHit(f"generic_debt_{index}", label, "concept", "traps", "debt", "debt_threat", 0)
        return _EntityHit(f"generic_{index}", label, "concept", "reveals", "reveal", "generic_focus", 0)

    def _mode_for_amount_context(self, lowered: str) -> str:
        if re.search(r"left\s*over|only|remaining|survive|savings?", lowered):
            return "survivor_isolation"
        if re.search(r"salary|income|paycheck", lowered):
            return "salary_anchor"
        if re.search(r"invest|sip|corpus|wealth", lowered):
            return "hero_reveal"
        if re.search(r"emi|rent|spend|expense|cost|bill", lowered):
            return "expense_attack"
        return "generic_focus"

    def _sentences(self, text: str) -> list[_Sentence]:
        parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", str(text or "").strip()) if part.strip()]
        if not parts and text.strip():
            parts = [text.strip()]
        total_words = sum(self._word_count(part) for part in parts) or 1
        cursor = 0.0
        sentences: list[_Sentence] = []
        for index, part in enumerate(parts):
            span = self._word_count(part) / total_words
            end = min(1.0, cursor + span)
            sentences.append(_Sentence(index, part, cursor, end))
            cursor = end
        return sentences

    def _word_count(self, text: str) -> int:
        return len(re.findall(r"[A-Za-z0-9₹,]+", text))

    def _short_label(self, text: str) -> str:
        clean = re.sub(r"(?:₹\s*|rs\.?\s*)\d[\d,]*(?:\.\d+)?", "", text, flags=re.IGNORECASE)
        words = [word.strip(" ,.!?;:()[]").title() for word in clean.split() if len(word.strip(" ,.!?;:()[]")) > 2]
        stop = {"The", "And", "But", "This", "That", "Your", "You", "Can", "For", "With", "Into", "From", "When", "Then"}
        filtered = [word for word in words if word not in stop]
        return " ".join(filtered[:3]) or "Key idea"
