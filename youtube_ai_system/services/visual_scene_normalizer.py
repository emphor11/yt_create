from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from .scene_debug import SceneDebugTrace, confidence_for_mechanism, split_sentences


KNOWN_MECHANISMS = {
    "salary_drain",
    "lifestyle_inflation",
    "emi_stack",
    "emi_pressure",
    "debt_trap",
    "inflation_erosion",
    "sip_growth",
    "compounding",
    "risk_return",
    "emergency_fund",
    "fomo_risk",
    "speculation_risk",
    "diversification",
    "tax_drain",
    "tax_saving",
    "rent_burden",
    "subscription_leak",
    "expense_leakage",
    "payment_pain_reduction",
    "affordability_illusion",
    "price_anchoring",
    "subscription_lock_in",
    "commitment_stacking",
    "anchoring",
    "lock_in",
    "delayed_consequence",
    "temptation_discount",
    "liquidity_pressure",
    "social_pressure",
    "risk_concentration",
    "opportunity_cost",
    "leverage",
    "cash_flow_squeeze",
    "definition",
}

MECHANISM_ALIASES = {
    "emi_stack": "emi_pressure",
    "fomo_risk": "speculation_risk",
    "tax_drain": "tax_saving",
    "subscription_leak": "expense_leakage",
}

EMOTION_MAP = {
    "salary_drain": "anxiety",
    "lifestyle_inflation": "anxiety",
    "emi_pressure": "anxiety",
    "debt_trap": "shock",
    "inflation_erosion": "anxiety",
    "sip_growth": "confidence",
    "compounding": "confidence",
    "risk_return": "clarity",
    "emergency_fund": "clarity",
    "speculation_risk": "urgency",
    "diversification": "clarity",
    "tax_saving": "anxiety",
    "rent_burden": "anxiety",
    "expense_leakage": "shock",
    "payment_pain_reduction": "shock",
    "affordability_illusion": "anxiety",
    "price_anchoring": "clarity",
    "subscription_lock_in": "anxiety",
    "commitment_stacking": "anxiety",
    "anchoring": "clarity",
    "lock_in": "anxiety",
    "delayed_consequence": "urgency",
    "temptation_discount": "anxiety",
    "liquidity_pressure": "anxiety",
    "social_pressure": "anxiety",
    "risk_concentration": "urgency",
    "opportunity_cost": "clarity",
    "leverage": "urgency",
    "cash_flow_squeeze": "anxiety",
    "definition": "clarity",
}

MECHANISM_KEYWORDS = {
    "salary_drain": ["salary drain", "salary gone", "salary lands", "take-home", "take home", "vanish", "disappear", "left over", "day 20", "still breathing", "net pay"],
    "lifestyle_inflation": ["lifestyle", "upgrade", "wants more", "buy more", "living better"],
    "emi_pressure": ["emi", "home loan", "car loan", "personal loan", "instalment", "installment"],
    "debt_trap": ["credit card", "minimum payment", "interest", "principal", "debt trap"],
    "inflation_erosion": ["inflation", "purchasing power", "₹100 today", "price rise", "slow poison"],
    "sip_growth": ["sip", "systematic investment"],
    "compounding": ["compound", "compounding"],
    "risk_return": ["risk", "return", "fd", "equity", "high risk", "low risk"],
    "emergency_fund": ["emergency fund", "safety net", "buffer", "unexpected"],
    "speculation_risk": ["fomo", "fear of missing", "impulsive", "speculation", "life savings"],
    "diversification": ["diversif", "basket", "mutual fund", "spread"],
    "tax_saving": ["tax", "tds", "income tax", "slab", "80c"],
    "rent_burden": ["rent", "landlord", "housing"],
    "expense_leakage": ["subscription", "netflix", "prime", "spotify", "ott", "leak"],
    "payment_pain_reduction": ["monthly payment", "monthly payments", "payment pain", "painless", "feels harmless"],
    "affordability_illusion": ["affordable", "only per month", "per month", "full price", "monthly number", "small monthly"],
    "price_anchoring": ["anchor", "anchoring", "full price", "sticker price", "price tag"],
    "subscription_lock_in": ["subscription", "locked in", "auto-renew", "autopay", "recurring payment"],
    "commitment_stacking": ["payments stack", "commitments stack", "monthly commitments", "one more payment", "stacking"],
    "anchoring": ["anchor", "anchoring", "first number", "reference price"],
    "lock_in": ["lock-in", "lock in", "locked", "switching cost", "exit cost"],
    "delayed_consequence": ["delayed consequence", "deferred", "cost later", "later cost", "delay"],
    "temptation_discount": ["temptation", "present bias", "today feels", "future self", "instant reward"],
    "liquidity_pressure": ["liquidity", "cash stuck", "cannot access", "accessible cash", "cash pressure"],
    "social_pressure": ["social pressure", "status", "friends", "comparison", "show off"],
    "risk_concentration": ["risk concentration", "concentration", "single bet", "one stock", "all your money"],
    "opportunity_cost": ["opportunity cost", "cost of not", "what you give up", "missed return"],
    "leverage": ["leverage", "borrowed money", "amplified", "small input"],
    "cash_flow_squeeze": ["cash flow", "squeeze", "fixed payments", "little left"],
}

RUPEE_PATTERN = re.compile(r"(?:₹\s*|Rs\.?\s*)(\d[\d,]*(?:\.\d+)?)\s*(lakh|lakhs|crore|crores|k)?", re.IGNORECASE)
PCT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%")
YEAR_PATTERN = re.compile(r"(\d+)\s*years?", re.IGNORECASE)
DAY_PATTERN = re.compile(r"day\s+(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class VisualScene:
    narration: str
    visual_intent: str
    visual_beats: list[str]
    numbers: list[str]
    emotion: str
    mechanism: str
    scene_id: str = ""
    raw_section: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "narration": self.narration,
            "visual_intent": self.visual_intent,
            "visual_beats": self.visual_beats,
            "numbers": self.numbers,
            "emotion": self.emotion,
            "mechanism": self.mechanism,
        }


class VisualSceneNormalizer:
    """Turns narration sections into visual-ready contracts without an LLM call."""

    def normalize(self, section: dict[str, Any], index: int = 0, debug_trace: SceneDebugTrace | None = None) -> VisualScene:
        narration = self._extract_narration(section)
        mechanism = self._infer_mechanism(section, narration)
        numbers = self._extract_numbers(narration)
        emotion = self._infer_emotion(section, mechanism)
        beats = self._extract_beats(section, narration, mechanism)
        intent = self._build_visual_intent(section, mechanism, beats, narration)
        scene = VisualScene(
            scene_id=str(section.get("scene_id") or f"scene_{index + 1}"),
            narration=narration,
            visual_intent=intent,
            visual_beats=beats,
            numbers=numbers,
            emotion=emotion,
            mechanism=mechanism,
            raw_section=section,
        )
        if debug_trace:
            output = scene.to_dict()
            score, reasons = confidence_for_mechanism(section, mechanism)
            debug_trace.snapshot("normalizer_post", output, owner="visual_scene_normalizer")
            debug_trace.ownership("mechanism", "visual_scene_normalizer", mechanism, self._mechanism_reason(section, narration, mechanism))
            debug_trace.ownership("visual_intent", "visual_scene_normalizer", intent, "visual intent explicit or generated from beats")
            debug_trace.ownership("visual_beats", "visual_scene_normalizer", beats, "explicit beats, visual plan beats, or mechanism defaults")
            debug_trace.ownership("numbers", "visual_scene_normalizer", numbers, "numbers extracted from narration")
            debug_trace.ownership("emotion", "visual_scene_normalizer", emotion, "explicit emotion or mechanism emotion map")
            debug_trace.confidence("normalizer", "mechanism", mechanism, score, reasons)
            mechanism_id = f"mechanism:{index}:{mechanism}"
            debug_trace.lineage_node(
                mechanism_id,
                "mechanism",
                "normalizer",
                mechanism,
                output,
                owner="visual_scene_normalizer",
                confidence=score,
                source_ids=[f"sentence:{index + 1}:all"],
            )
            for sentence_index, _sentence in enumerate(split_sentences(narration)):
                debug_trace.lineage_edge(f"sentence:{index + 1}:{sentence_index}", mechanism_id, "sentence_contains_keyword_or_explicit_visual_scene")
            debug_trace.determinism("normalizer", section, output)
        return scene

    def inject_into_section(self, section: dict[str, Any], index: int = 0, debug_trace: SceneDebugTrace | None = None) -> dict[str, Any]:
        before = dict(section)
        scene = self.normalize(section, index, debug_trace=debug_trace)
        enriched = dict(section)
        enriched["visual_scene"] = scene.to_dict()
        enriched["mechanism"] = scene.mechanism
        enriched["emotion"] = scene.emotion
        if not enriched.get("has_numbers"):
            enriched["has_numbers"] = bool(scene.numbers)
        if debug_trace:
            debug_trace.diff("normalizer_inject", before, enriched)
        return enriched

    def _extract_narration(self, section: dict[str, Any]) -> str:
        for key in ("narration", "text", "voiceover"):
            value = str(section.get(key) or "").strip()
            if value:
                return value
        visual_scene = section.get("visual_scene") or {}
        return str(visual_scene.get("narration") or "").strip()

    def _infer_mechanism(self, section: dict[str, Any], narration: str) -> str:
        for key in ("mechanism", "concept_type", "idea_type"):
            mechanism = self._canonical_mechanism(section.get(key))
            if mechanism:
                return mechanism
        visual_scene = section.get("visual_scene") or {}
        mechanism = self._canonical_mechanism(visual_scene.get("mechanism"))
        if mechanism:
            return mechanism
        finance_concept = section.get("finance_concept") or {}
        mechanism = self._canonical_mechanism(finance_concept.get("concept_type"))
        if mechanism:
            return mechanism
        text = narration.lower()
        for candidate, keywords in MECHANISM_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                return candidate
        return "definition"

    def _mechanism_reason(self, section: dict[str, Any], narration: str, mechanism: str) -> str:
        for key in ("mechanism", "concept_type", "idea_type"):
            if self._canonical_mechanism(section.get(key)) == mechanism:
                return f"explicit section {key}"
        visual_scene = section.get("visual_scene") or {}
        if self._canonical_mechanism(visual_scene.get("mechanism")) == mechanism:
            return "explicit visual_scene mechanism"
        finance_concept = section.get("finance_concept") or {}
        if self._canonical_mechanism(finance_concept.get("concept_type")) == mechanism:
            return "finance concept mechanism"
        return "keyword inference override" if mechanism != "definition" else "definition fallback"

    def _canonical_mechanism(self, value: Any) -> str:
        mechanism = str(value or "").strip().lower()
        if not mechanism:
            return ""
        mechanism = MECHANISM_ALIASES.get(mechanism, mechanism)
        return mechanism if mechanism in KNOWN_MECHANISMS else ""

    def _extract_numbers(self, narration: str) -> list[str]:
        found = [match.group(0).strip() for match in RUPEE_PATTERN.finditer(narration)]
        found.extend(match.group(0).strip() for match in PCT_PATTERN.finditer(narration))
        found.extend(match.group(0).strip() for match in YEAR_PATTERN.finditer(narration))
        found.extend(match.group(0).strip() for match in DAY_PATTERN.finditer(narration))
        return self._dedupe(found)

    def _infer_emotion(self, section: dict[str, Any], mechanism: str) -> str:
        for source in (section, section.get("visual_scene") or {}):
            value = str(source.get("emotion") or "").strip().lower()
            if value in {"anxiety", "shock", "clarity", "confidence", "urgency"}:
                return value
        return EMOTION_MAP.get(mechanism, "clarity")

    def _extract_beats(self, section: dict[str, Any], narration: str, mechanism: str) -> list[str]:
        visual_scene = section.get("visual_scene") or {}
        explicit = [str(beat).strip() for beat in (visual_scene.get("visual_beats") or section.get("visual_beats") or []) if str(beat).strip()]
        if len(explicit) >= 2:
            return explicit[:4]
        plan_beats: list[str] = []
        for item in section.get("visual_plan") or []:
            for beat in ((item.get("beats") or {}).get("beats") or []):
                text = str(beat.get("text") or "").strip()
                if text:
                    plan_beats.append(text)
        if len(plan_beats) >= 2:
            return plan_beats[:4]
        return self._mechanism_beats(mechanism, narration)

    def _mechanism_beats(self, mechanism: str, narration: str) -> list[str]:
        defaults = {
            "salary_drain": ["Salary arrives", "Drains begin", "Almost nothing left"],
            "lifestyle_inflation": ["Income rises", "Lifestyle rises with it", "Savings stay stuck"],
            "emi_pressure": ["One EMI", "More EMIs stack", "Cash flow shrinks"],
            "debt_trap": ["Swipe now", "Interest starts", "Balance barely moves"],
            "inflation_erosion": ["Money today", "Purchasing power falls", "Same rupee buys less"],
            "sip_growth": ["Small monthly SIP", "Compounding starts", "Corpus grows"],
            "compounding": ["First year small", "Growth accelerates", "Exponential end"],
            "risk_return": ["Low risk, low return", "Higher risk, higher return", "Risk is the price"],
            "emergency_fund": ["Unexpected expense hits", "Buffer absorbs shock", "Plan survives"],
            "speculation_risk": ["Market hype peaks", "Impulsive entry", "Panic exit"],
            "diversification": ["One basket", "Diversify", "Risk spreads"],
            "tax_saving": ["Gross salary", "Tax deducted", "Take-home shrinks"],
            "rent_burden": ["Rent paid", "Income drained", "Little left to save"],
            "expense_leakage": ["Subscriptions pile up", "Invisible monthly drain", "Add it up"],
            "payment_pain_reduction": ["Full price hidden", "Monthly price feels smaller", "Pain disappears"],
            "affordability_illusion": ["Big purchase reframed", "Small monthly number", "Real cost expands"],
            "price_anchoring": ["Sticker shock appears", "Monthly anchor replaces it", "Decision feels safer"],
            "subscription_lock_in": ["Recurring promise starts", "Autopay repeats", "Exit feels delayed"],
            "commitment_stacking": ["One payment accepted", "More commitments stack", "Freedom shrinks"],
            "anchoring": ["First number appears", "Judgment bends around it", "Better comparison restores clarity"],
            "lock_in": ["Easy entry", "Exit cost appears", "Choice narrows"],
            "delayed_consequence": ["Benefit arrives now", "Cost waits quietly", "Future month pays"],
            "temptation_discount": ["Today looks rewarding", "Future cost fades", "Choice becomes expensive"],
            "liquidity_pressure": ["Money exists on paper", "Cash access tightens", "Pressure reaches the month"],
            "social_pressure": ["Status signal appears", "Comparison pressure rises", "Budget follows the crowd"],
            "risk_concentration": ["One bet grows large", "Shock hits the same place", "Diversification gap appears"],
            "opportunity_cost": ["One choice consumes cash", "Alternative path disappears", "Hidden cost becomes visible"],
            "leverage": ["Small input enters", "Exposure multiplies", "Outcome amplifies"],
            "cash_flow_squeeze": ["Fixed payments arrive", "Flexible cash shrinks", "Month gets squeezed"],
        }
        return defaults.get(mechanism, ["Problem shown", "Impact revealed", "Key insight"])

    def _build_visual_intent(self, section: dict[str, Any], mechanism: str, beats: list[str], narration: str) -> str:
        visual_scene = section.get("visual_scene") or {}
        explicit = str(visual_scene.get("visual_intent") or section.get("visual_intent") or "").strip()
        if explicit:
            return explicit
        if beats:
            return "Show " + " -> ".join(beats[:3])
        return f"Visualize: {narration[:80]}"

    def _dedupe(self, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = value.lower().replace(" ", "")
            if key and key not in seen:
                seen.add(key)
                result.append(value)
        return result


def visual_script_prompt_contract() -> str:
    return (
        "VISUAL-SCENE CONTRACT:\n"
        "Every body scene should include narration, visual_intent, visual_beats, numbers, emotion, and mechanism.\n"
        "visual_intent is what the viewer must SEE, not what the narration explains.\n"
        "visual_beats must be 2-4 short on-screen beats, each 2-5 words, forming a sequence.\n"
        "numbers must include only numbers spoken in narration. Do not invent visual-only numbers.\n"
        "Prefer concrete Indian finance numbers when truthful, but never add fake numbers just to satisfy the format.\n"
        "mechanism must be one of: salary_drain, lifestyle_inflation, emi_stack, debt_trap, inflation_erosion, "
        "sip_growth, compounding, risk_return, emergency_fund, fomo_risk, diversification, tax_drain, "
        "rent_burden, subscription_leak, payment_pain_reduction, affordability_illusion, price_anchoring, "
        "subscription_lock_in, commitment_stacking, anchoring, lock_in, delayed_consequence, temptation_discount, "
        "liquidity_pressure, social_pressure, risk_concentration, opportunity_cost, leverage, cash_flow_squeeze, definition.\n"
        "Good visual_intent: Show income rising, lifestyle absorbing it, and savings staying flat.\n"
        "Bad visual_intent: Explain lifestyle inflation.\n"
    )
