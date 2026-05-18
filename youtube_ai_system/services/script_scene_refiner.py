from __future__ import annotations

import re
from typing import Any

from .scene_debug import SceneDebugTrace
from .visual_scene_normalizer import VisualSceneNormalizer


class ScriptSceneRefiner:
    """Expands weak body scenes into visual-ready finance narration."""

    MIN_BODY_WORDS = 160

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
        debug_trace: SceneDebugTrace | None = None,
    ) -> dict[str, Any]:
        source = dict(scene)
        source["narration"] = narration
        visual_scene = self.normalizer.normalize(source, index - 1, debug_trace=debug_trace)
        has_multiple_mechanisms = self._has_multiple_mechanisms(narration)
        if has_multiple_mechanisms and self._is_strong_enough(narration, visual_scene.mechanism):
            result = {
                "narration": narration,
                "visual_scene": visual_scene.to_dict(),
                "refined": False,
                "allow_grouping": True,
            }
            self._trace_result(debug_trace, index, scene, result, "multiple mechanisms; grouping allowed")
            return result
        if self._is_strong_enough(narration, visual_scene.mechanism):
            result = {
                "narration": narration,
                "visual_scene": visual_scene.to_dict(),
                "refined": False,
                "allow_grouping": False,
            }
            self._trace_result(debug_trace, index, scene, result, "narration strong enough")
            return result

        refined = self._template_for(visual_scene.mechanism, narration, topic, angle)
        refined_scene = self.normalizer.normalize(
            {
                **source,
                "narration": refined,
                "mechanism": visual_scene.mechanism,
                "emotion": visual_scene.emotion,
            },
            index - 1,
            debug_trace=debug_trace,
        )
        result = {
            "narration": refined,
            "visual_scene": refined_scene.to_dict(),
            "refined": True,
            "allow_grouping": has_multiple_mechanisms,
        }
        self._trace_result(debug_trace, index, scene, result, "weak scene expanded around original topic")
        return result

    def _trace_result(
        self,
        debug_trace: SceneDebugTrace | None,
        index: int,
        source_scene: dict[str, Any],
        result: dict[str, Any],
        reason: str,
    ) -> None:
        if not debug_trace:
            return
        debug_trace.snapshot("refiner_post", result, owner="script_scene_refiner", note=reason)
        debug_trace.diff("refiner_post", source_scene, result)
        debug_trace.ownership("narration", "script_scene_refiner", result.get("narration"), reason)
        debug_trace.ownership("visual_scene", "script_scene_refiner", result.get("visual_scene"), reason)
        debug_trace.event(
            "scene_refiner",
            "completed",
            {
                "scene_index": index,
                "refined": bool(result.get("refined")),
                "allow_grouping": bool(result.get("allow_grouping")),
                "reason": reason,
            },
        )

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
        if self._word_count(narration) < self.MIN_BODY_WORDS:
            return False
        sentence_count = sum(1 for part in narration.replace("?", ".").replace("!", ".").split(".") if part.strip())
        if sentence_count < 4:
            return False
        if mechanism in {"salary_drain", "debt_trap", "emi_pressure", "inflation_erosion", "sip_growth", "compounding"}:
            return any(token in narration for token in ("₹", "%")) or any(char.isdigit() for char in narration)
        return True

    def _template_for(self, mechanism: str, narration: str, topic: str, angle: str) -> str:
        base = " ".join(str(narration or "").split()).strip()
        if not base:
            base = self._topic_opening(mechanism, topic, angle)
        return self._ensure_min_words(
            base,
            mechanism,
            topic,
            angle,
        )

    def _ensure_min_words(self, narration: str, mechanism: str, topic: str, angle: str) -> str:
        text = " ".join(str(narration or "").split()).strip()
        if self._word_count(text) >= self.MIN_BODY_WORDS:
            return text

        tails = self._expansion_tails(mechanism, topic, angle)
        used: list[str] = []
        for sentence in tails:
            if self._word_count(text) >= self.MIN_BODY_WORDS:
                break
            cleaned = " ".join(sentence.split()).strip()
            if cleaned and cleaned not in used:
                used.append(cleaned)
                text = f"{text} {cleaned}".strip()
        for sentence in self._final_padding_tails(mechanism, topic, angle):
            if self._word_count(text) >= self.MIN_BODY_WORDS:
                break
            cleaned = " ".join(sentence.split()).strip()
            if cleaned and cleaned not in used and cleaned not in text:
                used.append(cleaned)
                text = f"{text} {cleaned}".strip()
        return text

    def _word_count(self, text: str) -> int:
        return len(re.findall(r"[A-Za-z0-9₹%]+(?:[.,][A-Za-z0-9]+)*", str(text or "")))

    def _final_padding_tails(self, mechanism: str, topic: str, angle: str) -> list[str]:
        mechanism_label = mechanism.replace("_", " ") if mechanism else "money habit"
        context = topic or angle or "this money decision"
        return [
            f"This is where the {mechanism_label} stops being theory and starts affecting the actual decision.",
            "The pressure, the number, and the consequence are now part of the same choice.",
            f"For {context}, the takeaway is not motivation. It is a cleaner way to judge the real cost before saying yes.",
            "Once that cost is visible, the next decision becomes easier to question.",
            "That clarity is what separates a smart payment plan from an expensive habit wearing a smaller label.",
        ]

    def _topic_opening(self, mechanism: str, topic: str, angle: str) -> str:
        context = topic or "this finance topic"
        lens = angle or "the viewer's real decision"
        mechanism_label = mechanism.replace("_", " ") if mechanism else "money mechanism"
        return (
            f"The core issue in {context} is not a generic money mistake. "
            f"It is the {mechanism_label} behind {lens}. "
            "The viewer needs to see the decision before it feels expensive, while it still feels normal. "
            "Then the scene can reveal the hidden cost, the emotional trick, and the consequence."
        )

    def _expansion_tails(self, mechanism: str, topic: str, angle: str) -> list[str]:
        mechanism_label = mechanism.replace("_", " ") if mechanism else "money mechanism"
        context = topic or "this finance topic"
        lens = angle or "the pressure behind the decision"
        mechanism_tails = self._mechanism_specific_tails(mechanism, context, lens)
        if mechanism_tails:
            return mechanism_tails
        return [
            f"In {context}, the real pressure comes from {lens}, not from a random finance mistake.",
            f"The {mechanism_label} changes the decision by hiding one cost while making another number feel easier to accept.",
            "The visible choice feels simple in the moment, but the hidden tradeoff shows up later when cash flow has less room.",
            "A rupee amount should be judged against the real total cost, not only against the version that feels comfortable today.",
            "If there is no exact rupee number, one fee, one payment, or one delayed decision can still reveal the same trap.",
            "That keeps the example specific instead of turning it into another generic money lesson.",
            "The strongest question is simple: what does this decision still cost after the painless framing disappears?",
            "Once that question is asked, the next part of the story can show whether the payment is a useful tool or a quiet trap.",
        ]

    def _mechanism_specific_tails(self, mechanism: str, context: str, lens: str) -> list[str]:
        if mechanism == "cash_flow_squeeze":
            return [
                f"In {context}, the monthly number controls the rhythm of the decision.",
                "The lease does not remove the cost. It spreads the cost into a predictable slot on the calendar.",
                "That predictability can be useful when the buyer values liquidity more than ownership pride.",
                "But the same fixed payment also reduces future flexibility because the cash flow is already promised.",
                "The smart question is not whether the monthly amount is affordable today.",
                "The smart question is what options disappear once that payment becomes permanent.",
            ]
        if mechanism == "commitment_stacking":
            return [
                f"In {context}, one payment is easy to respect. Five payments begin behaving like a private tax.",
                "The car lease, insurance, club fee, phone plan, and subscription each feel manageable alone.",
                "Together, they claim future income before the month even starts.",
                "This is why wealthy buyers can like monthly commitments and still become trapped by too many of them.",
                "The risk is not the first commitment. The risk is stacking commitments until flexibility disappears.",
                f"That is the pressure behind {lens}: every small promise borrows a piece of the future.",
            ]
        if mechanism == "emi_pressure":
            return [
                f"In {context}, EMI pressure is not just a payment. It is a claim on future income.",
                "A ₹50,000 car payment can feel premium on purchase day and compulsory on every salary day after that.",
                "Once multiple EMIs join insurance, fuel, service, rent, and card dues, the monthly number stops being small.",
                "It becomes a fixed pressure stack that leaves before the buyer gets to make fresh choices.",
                "That is why the total cost matters more than the clean monthly label.",
                f"The pressure behind {lens} is simple: painless payments can still create painful commitments.",
            ]
        if mechanism == "compounding":
            return [
                f"In {context}, the rational case for monthly payments is opportunity cost.",
                "Paying less upfront can leave more capital available for an asset, a business, or an investment plan.",
                "If that capital compounds at a higher rate than the payment cost, the monthly structure can make sense.",
                "But the math only works when the return is realistic, the risk is understood, and the cash flow is stable.",
                "Otherwise, compounding becomes a story people tell themselves to justify a luxury they simply wanted.",
                f"That is why {lens} must be judged with numbers, not just with the feeling of staying liquid.",
            ]
        if mechanism == "leverage":
            return [
                f"In {context}, leverage is the sharp edge of the monthly-payment logic.",
                "The buyer keeps cash free today by letting borrowed money carry part of the purchase.",
                "That can be rational when the freed capital earns more than the borrowing cost.",
                "But leverage also magnifies mistakes because the payment survives even when the investment underperforms.",
                "A wealthy buyer uses leverage with an exit plan. A careless buyer uses leverage as permission.",
                f"That difference is what makes {lens} either a tool or a trap.",
            ]
        if mechanism == "debt_trap":
            return [
                f"In {context}, the trap begins when the monthly payment feels smaller than the obligation behind it.",
                "A ₹50,000 lease can look controlled while still locking the buyer into a long chain of future payments.",
                "If income changes, priorities shift, or another commitment arrives, the payment does not politely disappear.",
                "Interest, penalties, and rollover decisions can turn a planned expense into a pressure system.",
                "The danger is not that monthly payments are always bad. The danger is treating fixed payments like flexible money.",
                f"That is where {lens} stops feeling premium and starts feeling like a cage.",
            ]
        if mechanism == "lifestyle_inflation":
            return [
                f"In {context}, lifestyle inflation starts after the monthly payment changes the buyer's self-image.",
                "A luxury car EMI does not arrive alone. It invites higher insurance, fuel, service, accessories, valet nights, and weekend plans that match the car.",
                "Each add-on feels smaller than the car payment, so none of them looks like the main problem.",
                "But together, they make the old lifestyle feel outdated and the new lifestyle feel normal.",
                "That is why the first painless EMI can become a permission slip for ten more painless upgrades.",
                f"The pressure inside {lens} is not only the loan. It is the new spending identity that forms around the loan.",
            ]
        if mechanism == "inflation_erosion":
            return [
                f"In {context}, inflation changes what the same rupee amount means over time.",
                "A fixed monthly payment can feel lighter in the future if income rises faster than the payment.",
                "That is one reason wealthy buyers may prefer predictable payments instead of losing liquidity upfront.",
                "But inflation can also raise fuel, maintenance, insurance, and lifestyle costs around the same purchase.",
                "So the payment may stay fixed while the surrounding cost of ownership expands.",
                f"That is why {lens} needs a full-cost view, not just a fixed-payment comfort story.",
            ]
        if mechanism == "affordability_illusion":
            return [
                f"In {context}, the trap starts when the bill looks affordable before the full cost is mentally counted.",
                "The card does not make the dinner, shopping cart, or weekend plan cheaper. It only makes the first yes feel lighter.",
                "A small due amount becomes the number the brain trusts, while the total bill waits quietly in the background.",
                "That is why the same purchase can feel responsible at the counter and reckless when the statement arrives.",
                "The viewer should judge the decision by the final bill, not by the most painless version of the payment.",
                f"That is the psychological pressure behind {lens}: comfort arrives first, cost arrives later.",
            ]
        if mechanism == "payment_pain_reduction":
            return [
                f"In {context}, the card weakens the moment where spending is supposed to feel real.",
                "Cash creates a visible loss. A card creates a clean tap, a reward point, and almost no emotional friction.",
                "That missing friction matters because the brain treats a painless payment like a smaller payment.",
                "The restaurant bill, the ticket booking, and the late-night order all feel easier when the pain is postponed.",
                "By the time the statement arrives, the spending has already become a memory instead of a decision.",
                f"That is why {lens} is dangerous: it removes the emotional brake before the money actually leaves.",
            ]
        if mechanism == "anchoring":
            return [
                f"In {context}, anchoring changes the reference point before the viewer judges value.",
                "Once a high number appears first, every lower number starts looking reasonable even when it is still expensive.",
                "The card offer benefits from that comparison because the brain celebrates the discount instead of testing the purchase.",
                "A deal can be mathematically smaller and still financially unnecessary.",
                "The decision should be compared with the budget that existed before the offer, not only with the inflated sticker price.",
                f"That is the pressure inside {lens}: the anchor makes spending feel like saving.",
            ]
        if mechanism == "delayed_consequence":
            return [
                f"In {context}, the consequence arrives after the excitement has already disappeared.",
                "The purchase happens today, but the bill, interest, and cash-flow squeeze arrive weeks later.",
                "That delay breaks the connection between action and pain, so the mind treats each swipe as isolated.",
                "By the time March or April feels tight, January's purchases no longer feel like the cause.",
                "The real danger is not one purchase. It is a timeline where every consequence arrives after the next temptation.",
                f"That delayed feedback loop is what makes {lens} feel harmless until it becomes hard to reverse.",
            ]
        if mechanism == "expense_leakage":
            return [
                f"In {context}, the leak is not one dramatic purchase. It is the repeat pattern that escapes attention.",
                "A coffee, a delivery fee, a ticket upgrade, and one extra subscription each look too small to challenge.",
                "The card makes those small yeses frictionless, so they travel quietly into one larger monthly bill.",
                "The damage is psychological before it is mathematical: no single spend feels guilty enough to stop.",
                "Only the statement reveals that tiny decisions were acting like one combined expense.",
                f"That is why {lens} needs a visible total, not just a vague promise to spend less.",
            ]
        if mechanism == "price_anchoring":
            return [
                f"In {context}, the seller wants the viewer to stare at the discount before noticing the remaining cost.",
                "A lower price can still be a bad decision if the original purchase was unnecessary.",
                "The card offer makes the reduced number feel like a win, while the final bill still claims real money later.",
                "That is the difference between saving money and being persuaded to spend money more comfortably.",
                "The useful question is not how much was reduced. The useful question is what still leaves the account.",
                f"That is the anchor inside {lens}: the comparison feels smart even when the cash flow gets weaker.",
            ]
        return []
