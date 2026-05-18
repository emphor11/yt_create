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
        return [
            f"For {context}, the danger is not a random finance mistake. It is the specific pressure created by {lens}.",
            f"The {mechanism_label} changes the decision by making one cost feel smaller while another cost becomes easier to ignore.",
            "The visible choice feels simple in the moment. The hidden tradeoff shows up later, when cash flow has less room.",
            "If a rupee amount is involved, that number should be judged against the real total cost, not against the most comfortable monthly version.",
            "If no exact rupee amount is available, even one payment, one fee, or one delayed decision can reveal the same trap.",
            "That makes the example specific instead of turning it into another generic money lesson.",
            "The strongest question is simple: what does this decision still cost after the painless framing disappears?",
            "Once that question is asked, the next part of the story can show whether the payment is a useful tool or a quiet trap.",
        ]
