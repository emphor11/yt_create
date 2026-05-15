"""Text and label helpers for visual beat expansion."""

from __future__ import annotations

import re
from typing import Any


class BeatExpansionTextHelper:
    def sanitize_viewer_text(self, text: str) -> str:
        clean = " ".join(str(text or "").replace("_", " ").split()).strip()
        if not clean:
            return ""
        lowered = clean.lower()
        if lowered == "state changes":
            return ""
        internal_map = {
            "phone account": "Money hits the account",
            "salary balance": "Salary lands",
            "emi stack": "Fixed payments stack up",
            "debt pressure": "Debt starts compounding",
            "inflation basket": "Buying power starts shrinking",
            "sip jar": "Compounding starts working",
            "portfolio grid": "Risk gets distributed",
            "emergency buffer": "Safety net absorbs the shock",
        }
        return internal_map.get(lowered, clean)

    def target_beat_count(self, text: str, sentences: list[str]) -> int:
        words = len(text.split())
        sentence_target = max(len(sentences), 1)
        if words >= 70:
            word_target = 8
        elif words >= 55:
            word_target = 7
        elif words >= 40:
            word_target = 6
        elif words >= 26:
            word_target = 5
        elif words >= 16:
            word_target = 4
        else:
            word_target = 3
        return max(3, min(9, max(sentence_target, word_target)))

    def beat_text(self, sentence: str, mechanism: str, is_last: bool) -> str:
        clean = " ".join(sentence.strip().strip(".!?").split())
        lowered = clean.lower()
        money = re.search(r"₹\s?\d[\d,]*(?:\.\d+)?(?:\s*(?:lakh|lakhs|crore|crores|k))?", clean, re.IGNORECASE)
        pct = re.search(r"\d+(?:\.\d+)?\s*%", clean)
        if money:
            tail = self.money_tail(lowered)
            return f"{money.group(0).replace(' ', '')} {tail}".strip()
        if pct:
            return f"{pct.group(0)} {self.percent_tail(lowered)}".strip()
        if is_last:
            return self.consequence_text(clean, mechanism)
        return self.short_phrase(clean)

    def money_tail(self, lowered: str) -> str:
        for token, label in (
            ("emi", "EMI"),
            ("rent", "rent"),
            ("interest", "interest"),
            ("leaves", "leaves first"),
            ("leak", "leak"),
            ("sip", "SIP"),
            ("invest", "invested"),
            ("salary", "salary"),
        ):
            if token in lowered:
                return label
        return ""

    def percent_tail(self, lowered: str) -> str:
        if "interest" in lowered:
            return "interest"
        if "return" in lowered:
            return "return"
        if "inflation" in lowered:
            return "inflation"
        return ""

    def consequence_text(self, clean: str, mechanism: str) -> str:
        if mechanism == "emi_pressure":
            return "Five small payments become one leak"
        if mechanism == "expense_leakage":
            return "The leak is the system"
        if mechanism == "debt_trap":
            return "Interest is still winning"
        if mechanism == "inflation_erosion":
            return "Real value keeps falling"
        if mechanism in {"sip_growth", "compounding"}:
            return "Time does the heavy lifting"
        if mechanism == "speculation_risk":
            return "Do not buy what you cannot explain"
        return self.short_phrase(clean, max_words=6)

    def short_phrase(self, text: str, max_words: int = 5) -> str:
        words = [word.strip(" ,.-") for word in text.split() if word.strip(" ,.-")]
        if not words:
            return "Key idea"
        phrase = " ".join(words[:max_words])
        return phrase[:1].upper() + phrase[1:]

    def fallback_texts(self, beats: list[dict[str, Any]], count: int) -> list[str]:
        texts = [str(beat.get("text") or "").strip() for beat in beats if str(beat.get("text") or "").strip()]
        return texts[:count]

    def sentences(self, text: str) -> list[str]:
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+", str(text or "").strip()) if part.strip()]

    def dedupe_adjacent(self, beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        previous = ""
        for beat in beats:
            text = str(beat.get("text") or "").lower()
            if text == previous:
                continue
            previous = text
            deduped.append(beat)
        return deduped
