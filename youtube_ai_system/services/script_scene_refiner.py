from __future__ import annotations

from typing import Any

from .visual_scene_normalizer import VisualSceneNormalizer


class ScriptSceneRefiner:
    """Expands weak body scenes into visual-ready finance narration."""

    MIN_BODY_WORDS = 45

    def __init__(self) -> None:
        self.normalizer = VisualSceneNormalizer()

    def refine_scene(
        self,
        scene: dict[str, Any],
        narration: str,
        *,
        index: int,
        topic: str,
        angle: str,
    ) -> dict[str, Any]:
        source = dict(scene)
        source["narration"] = narration
        visual_scene = self.normalizer.normalize(source, index - 1)
        if self._has_multiple_mechanisms(narration):
            return {
                "narration": narration,
                "visual_scene": visual_scene.to_dict(),
                "refined": False,
                "allow_grouping": True,
            }
        if self._is_strong_enough(narration, visual_scene.mechanism):
            return {
                "narration": narration,
                "visual_scene": visual_scene.to_dict(),
                "refined": False,
                "allow_grouping": False,
            }

        refined = self._template_for(visual_scene.mechanism, narration, topic, angle)
        refined_scene = self.normalizer.normalize(
            {
                **source,
                "narration": refined,
                "mechanism": visual_scene.mechanism,
                "emotion": visual_scene.emotion,
            },
            index - 1,
        )
        return {
            "narration": refined,
            "visual_scene": refined_scene.to_dict(),
            "refined": True,
            "allow_grouping": False,
        }

    def _has_multiple_mechanisms(self, narration: str) -> bool:
        lowered = narration.lower()
        groups = [
            ("lifestyle", ("lifestyle", "raise", "upgrade", "spending rises")),
            ("debt", ("credit card", "minimum payment", "minimum dues", "debt trap", "interest")),
            ("inflation", ("inflation", "purchasing power")),
            ("sip", ("sip", "compound", "compounding")),
            ("risk", ("risk", "return", "diversification")),
        ]
        hits = 0
        for _, keywords in groups:
            if any(keyword in lowered for keyword in keywords):
                hits += 1
        return hits >= 2

    def _is_strong_enough(self, narration: str, mechanism: str) -> bool:
        words = narration.split()
        if len(words) < self.MIN_BODY_WORDS:
            return False
        sentence_count = sum(1 for part in narration.replace("?", ".").replace("!", ".").split(".") if part.strip())
        if sentence_count < 4:
            return False
        if mechanism in {"salary_drain", "debt_trap", "emi_pressure", "inflation_erosion", "sip_growth", "compounding"}:
            return any(token in narration for token in ("₹", "%")) or any(char.isdigit() for char in narration)
        return True

    def _template_for(self, mechanism: str, narration: str, topic: str, angle: str) -> str:
        templates = {
            "salary_drain": (
                "Your ₹50,000 salary lands and feels powerful for one day. Then ₹18,000 goes to EMI. "
                "₹12,000 goes to rent. Food, travel, and small spends take another ₹14,000. "
                "By day 20, only ₹6,000 is still breathing. The salary did not disappear randomly. "
                "It drained through fixed costs before you started making choices."
            ),
            "lifestyle_inflation": (
                "Your salary rises from ₹50,000 to ₹80,000. At first, it feels like progress. "
                "Then rent upgrades, food apps, weekend plans, and shopping expand with it. "
                "The extra ₹30,000 never reaches savings. Lifestyle absorbs the raise before you notice it. "
                "The problem is not earning more. The problem is giving every raise a new expense."
            ),
            "emi_pressure": (
                "One EMI feels harmless. Then a phone EMI joins it. Then a bike EMI joins it. "
                "Then a personal loan starts taking its share. Suddenly ₹18,000 leaves before the month even begins. "
                "That is how EMI pressure builds. The trap is not one huge payment. "
                "It is five small payments behaving like one big leak."
            ),
            "debt_trap": (
                "A ₹1,00,000 credit card balance does not look scary at first. The bank says the minimum payment is only ₹3,000. "
                "But at 40% annual interest, the monthly interest itself is around ₹3,300. "
                "So even after paying, the balance barely moves. Sometimes it grows. "
                "That is the debt trap. The payment feels responsible, but the interest is still winning."
            ),
            "inflation_erosion": (
                "Inflation does not attack your savings loudly. It works quietly. "
                "If ₹1,00,000 sits idle while prices rise at 7%, its buying power keeps shrinking. "
                "After 10 years, the same money feels almost half as useful. "
                "Your bank balance may look stable. But the real value is leaking every year."
            ),
            "sip_growth": (
                "A ₹5,000 SIP looks boring in the first month. It still looks small in the first year. "
                "But at 12% annual return over 20 years, the story changes. "
                "You invest about ₹12 lakh from your pocket. Compounding can turn it into nearly ₹50 lakh. "
                "The magic is not speed. The magic is staying invested long enough."
            ),
            "compounding": (
                "Compound interest feels slow because the first few years look unimpressive. "
                "A ₹5,000 monthly investment does not explode immediately. "
                "But every year, returns start earning their own returns. "
                "After 10 years, the curve bends. After 20 years, time does most of the work. "
                "That is why starting early beats waiting for the perfect amount."
            ),
            "risk_return": (
                "Risk and return are connected. An FD may offer around 6% and feel calm. "
                "Equity can offer higher long-term growth, but the price is volatility. "
                "Low risk usually means lower upside. Higher upside usually means emotional discomfort. "
                "The goal is not to avoid risk completely. The goal is to choose risk you understand."
            ),
            "diversification": (
                "Putting all your money into one stock feels exciting when it rises. "
                "But one bad result, one bad quarter, or one panic fall can hurt everything. "
                "Diversification spreads the risk across assets. Some money can sit in equity. "
                "Some can sit in debt funds or FD. The point is simple. One basket should not decide your future."
            ),
            "speculation_risk": (
                "FOMO investing feels like action. A stock runs up, everyone talks about it, and you enter late. "
                "Then the price falls and panic starts. That is not investing. That is emotion wearing a finance costume. "
                "Real investing starts with understanding what you own. If you cannot explain it, you probably should not buy it."
            ),
            "emergency_fund": (
                "An emergency fund looks boring until life becomes expensive. "
                "One medical bill, job delay, or family emergency can break a perfect budget. "
                "A six-month cash buffer stops that shock from becoming credit card debt. "
                "It does not make you rich. It keeps one bad month from destroying the plan."
            ),
        }
        if mechanism in templates:
            return templates[mechanism]
        context = topic or angle or "money"
        return (
            f"This scene is about {context}. The weak version says: {narration.strip()} "
            "But the real story needs a mechanism. First, show the money decision. "
            "Then show what changes because of it. Finally, show the consequence the viewer can feel. "
            "That is how a finance idea becomes visual instead of becoming another generic statement."
        )
