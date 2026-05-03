from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


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
    "definition": "clarity",
}

MECHANISM_KEYWORDS = {
    "salary_drain": ["salary", "take-home", "take home", "vanish", "disappear", "left over", "net pay"],
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

    def normalize(self, section: dict[str, Any], index: int = 0) -> VisualScene:
        narration = self._extract_narration(section)
        mechanism = self._infer_mechanism(section, narration)
        numbers = self._extract_numbers(narration)
        emotion = self._infer_emotion(section, mechanism)
        beats = self._extract_beats(section, narration, mechanism)
        intent = self._build_visual_intent(section, mechanism, beats, narration)
        return VisualScene(
            scene_id=str(section.get("scene_id") or f"scene_{index + 1}"),
            narration=narration,
            visual_intent=intent,
            visual_beats=beats,
            numbers=numbers,
            emotion=emotion,
            mechanism=mechanism,
            raw_section=section,
        )

    def inject_into_section(self, section: dict[str, Any], index: int = 0) -> dict[str, Any]:
        scene = self.normalize(section, index)
        enriched = dict(section)
        enriched["visual_scene"] = scene.to_dict()
        enriched["mechanism"] = scene.mechanism
        enriched["emotion"] = scene.emotion
        if not enriched.get("has_numbers"):
            enriched["has_numbers"] = bool(scene.numbers)
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
        "rent_burden, subscription_leak, definition.\n"
        "Good visual_intent: Show income rising, lifestyle absorbing it, and savings staying flat.\n"
        "Bad visual_intent: Explain lifestyle inflation.\n"
    )
