from __future__ import annotations

import re


class StorySectionTextSupportMixin:
    def _split_story_sentences(self, text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
        return [part.strip() for part in parts if part.strip()]

    def _sentence_starts_new_section(self, sentence: str) -> bool:
        lowered = sentence.lower().strip()
        if any(lowered.startswith(token) for token in ("but", "however", "so", "now", "because", "this means")):
            return True
        return len(sentence.split()) > 15

    def _keep_story_sentence(self, sentence: str, allow_short: bool = False) -> bool:
        lowered = sentence.lower().strip()
        if len(sentence.split()) < 6 and not allow_short:
            finance_short_tokens = (
                "debt",
                "credit",
                "interest",
                "salary",
                "lifestyle",
                "upgrade",
                "upgrades",
                "buy",
                "broke",
                "income",
                "expense",
                "expenses",
                "spending",
                "savings",
                "investment",
                "inflation",
                "budget",
                "fund",
                "payment",
                "trap",
                "risk",
                "wealth",
                "tax",
            )
            if not re.search(r"₹|%|\d+", sentence) and not any(token in lowered for token in finance_short_tokens):
                return False
        if any(phrase in lowered for phrase in ("for instance", "let's", "we've all", "you know")):
            return False
        return True

    def _normalize_text(self, text: str) -> str:
        return " ".join(str(text or "").strip().split())

    def _shares_topic_with_current(self, current: list[str], next_sentence: str) -> bool:
        if not next_sentence:
            return False
        current_terms = self._topic_terms(" ".join(current))
        next_terms = self._topic_terms(next_sentence)
        return bool(current_terms.intersection(next_terms))

    def _topic_terms(self, text: str) -> set[str]:
        keywords = {
            "debt",
            "credit",
            "payment",
            "minimum",
            "interest",
            "inflation",
            "savings",
            "investment",
            "returns",
            "budget",
            "budgeting",
            "income",
            "fund",
            "loan",
            "emi",
            "sip",
            "trap",
            "risk",
        }
        return {word for word in re.findall(r"[a-z]+", text.lower()) if word in keywords}

    def _section_word_count(self, section: list[str]) -> int:
        return len(" ".join(section).split())

    def _merge_short_sections(self, groups: list[list[str]]) -> list[list[str]]:
        merged: list[list[str]] = []
        index = 0
        while index < len(groups):
            current = list(groups[index])
            next_group = groups[index + 1] if index + 1 < len(groups) else None
            if (
                self._section_word_count(current) < 8
                and next_group is not None
                and self._can_merge_short_sections(current, next_group)
            ):
                current.extend(groups[index + 1])
                index += 1
            merged.append(current)
            index += 1
        return merged

    def _can_merge_short_sections(self, current: list[str], next_group: list[str]) -> bool:
        current_text = " ".join(current)
        next_text = " ".join(next_group)
        current_terms = self._topic_terms(current_text)
        next_terms = self._topic_terms(next_text)
        if current_terms and next_terms:
            return True
        return bool(current_terms.intersection(next_terms))
