from __future__ import annotations

from dataclasses import dataclass
from typing import List
import re


@dataclass
class IdeaGroup:
    group_id: str
    sentences: List[str]
    combined_text: str
    dominant_entity: str
    idea_type: str
    has_numbers: bool
    has_comparison: bool
    has_causation: bool


class IdeaGrouper:
    """
    Groups narration into idea-complete sections instead of micro sentence fragments.
    Target: one group should usually hold one full finance idea.
    """

    FINANCE_ENTITIES = {
        "salary", "income", "earnings", "pay", "wage",
        "debt", "loan", "emi", "credit", "interest",
        "savings", "save", "saved", "saving",
        "investment", "invest", "returns", "portfolio",
        "inflation", "prices", "cost", "expense", "expenses", "spending", "subscription",
        "fd", "fixed deposit", "ppf", "sip", "mutual fund",
        "tax", "income tax", "gst",
        "wealth", "net worth", "asset", "liability",
        "emergency fund", "buffer", "insurance",
    }

    CONTINUATION_SIGNALS = [
        r"^this ",
        r"^that ",
        r"^which ",
        r"^so ",
        r"^as a result",
        r"^because ",
        r"^therefore ",
        r"^in other words",
        r"^for example",
        r"^for instance",
        r"^in fact",
        r"^and ",
        r"^but this",
        r"^whether ",
        r"^without ",
        r"^with ",
        r"^if ",
    ]

    NEW_IDEA_SIGNALS = [
        r"^now,? let",
        r"^the (second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|next|real|biggest)",
        r"^another ",
        r"^here\'?s? (the|what|why|how)",
        r"^what about",
        r"^consider ",
        r"^think about",
        r"^imagine ",
    ]

    MECHANISM_RULES = {
        "lifestyle_inflation": ("raise", "salary increases", "income increases", "lifestyle", "fancy phone", "car", "wedding", "upgrade"),
        "debt_trap": ("credit card", "minimum payment", "minimum dues", "interest rate", "outstanding balance", "debt"),
        "expense_leakage": ("expense", "expenses", "spending", "subscription", "dining out", "ordering in", "premium"),
        "emergency_fund": ("emergency fund", "medical emergency", "lose your job", "cash buffer"),
        "tax_saving": ("tax", "ppf", "nps", "elss", "tax benefit"),
        "budgeting": ("budget", "track", "50/30/20", "allocate"),
        "investment_growth": ("investment", "investing", "returns", "compound", "wealth grow"),
        "insurance": ("insurance", "policy", "premium"),
        "salary_growth": ("negotiate", "salary negotiation", "earning ₹12", "difference of ₹2"),
    }

    RELATED_MECHANISMS = {
        "lifestyle_inflation": {"expense_leakage", "salary_growth"},
        "expense_leakage": {"lifestyle_inflation"},
        "debt_trap": {"expense_leakage"},
        "emergency_fund": {"investment_growth"},
        "investment_growth": {"emergency_fund", "salary_growth"},
    }

    CONSEQUENCE_SIGNALS = {
        "lose", "losing", "lost", "drop", "fall", "drain", "leak", "leaks", "gone",
        "debt", "trap", "risk", "danger", "destroy", "cost", "paying", "interest",
        "grow", "grows", "increase", "increases", "rise", "rises", "faster", "slow", "slows",
        "save", "saving", "wealth", "investing",
        "benefit", "return", "returns",
    }

    def group(self, narration_text: str) -> List[IdeaGroup]:
        sentences = self._split_into_sentences(narration_text)
        groups: list[IdeaGroup] = []
        current_sentences: list[str] = []
        current_entity: str | None = None
        current_mechanism: str | None = None
        group_counter = 0

        for sentence in sentences:
            entity = self._extract_dominant_entity(sentence)
            mechanism = self._extract_mechanism(sentence)
            is_continuation = self._is_continuation(sentence)
            is_new_idea = self._is_new_idea_start(sentence)

            should_start_new_group = False
            if current_sentences:
                current_complete = self._has_complete_idea(current_sentences)
                signature_changed = self._signature_changed(
                    current_entity=current_entity,
                    current_mechanism=current_mechanism,
                    next_entity=entity,
                    next_mechanism=mechanism,
                )
                should_start_new_group = (
                    len(current_sentences) >= 5
                    or (is_new_idea and current_complete)
                    or (signature_changed and not is_continuation and current_complete and len(current_sentences) >= 2)
                    or self._would_mix_distinct_ideas(current_sentences, sentence, current_mechanism, mechanism)
                )

            if should_start_new_group and current_sentences:
                groups.append(self._build_group(group_counter, current_sentences, current_entity, current_mechanism))
                group_counter += 1
                current_sentences = []
                current_entity = None
                current_mechanism = None

            current_sentences.append(sentence)
            if not current_entity and entity:
                current_entity = entity
            if not current_mechanism and mechanism:
                current_mechanism = mechanism

        if current_sentences:
            groups.append(self._build_group(group_counter, current_sentences, current_entity, current_mechanism))

        return groups

    def _build_group(
        self,
        counter: int,
        sentences: List[str],
        entity: str | None,
        mechanism: str | None,
    ) -> IdeaGroup:
        combined = " ".join(sentences)
        dominant_entity = entity or self._extract_dominant_entity(combined) or "money"
        idea_type = self._classify_idea_type(combined)
        if mechanism in {"debt_trap", "expense_leakage", "insurance", "emergency_fund"}:
            idea_type = "risk"
        if mechanism in {"investment_growth", "salary_growth"}:
            idea_type = "growth"
        if mechanism == "budgeting":
            idea_type = "process"
        return IdeaGroup(
            group_id=f"idea_{counter:02d}",
            sentences=sentences,
            combined_text=combined,
            dominant_entity=dominant_entity,
            idea_type=idea_type,
            has_numbers=bool(re.search(r"₹|%|\d+", combined)),
            has_comparison=bool(re.search(r"\bvs\b|\bversus\b|\bbut\b|\bhowever\b|\binstead\b", combined, re.IGNORECASE)),
            has_causation=bool(re.search(r"\bbecause\b|\bso\b|\btherefore\b|\bleads to\b|\bresults in\b", combined, re.IGNORECASE)),
        )

    def _split_into_sentences(self, text: str) -> List[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    def _extract_dominant_entity(self, sentence: str) -> str | None:
        sentence_lower = sentence.lower()
        ordered = sorted(self.FINANCE_ENTITIES, key=len, reverse=True)
        for entity in ordered:
            if entity in sentence_lower:
                return entity
        return None

    def _extract_mechanism(self, sentence: str) -> str | None:
        lowered = sentence.lower()
        for mechanism, keywords in self.MECHANISM_RULES.items():
            if any(keyword in lowered for keyword in keywords):
                return mechanism
        return None

    def _is_continuation(self, sentence: str) -> bool:
        sentence_lower = sentence.lower().strip()
        return any(re.match(pattern, sentence_lower) for pattern in self.CONTINUATION_SIGNALS)

    def _is_new_idea_start(self, sentence: str) -> bool:
        sentence_lower = sentence.lower().strip()
        return any(re.match(pattern, sentence_lower) for pattern in self.NEW_IDEA_SIGNALS)

    def _has_complete_idea(self, sentences: List[str]) -> bool:
        if not sentences:
            return False
        combined = " ".join(sentences).lower()
        if len(sentences) >= 3:
            return True
        if any(token in combined for token in self.CONSEQUENCE_SIGNALS):
            return True
        if len(sentences) >= 2 and re.search(r"\bbut\b|\bhowever\b|\bfaster\b|\bbecause\b|\bso\b", combined):
            return True
        if re.search(r"₹|%|\d+", combined) and len(sentences) >= 2:
            return True
        return False

    def _signature_changed(
        self,
        *,
        current_entity: str | None,
        current_mechanism: str | None,
        next_entity: str | None,
        next_mechanism: str | None,
    ) -> bool:
        if next_mechanism and current_mechanism and next_mechanism != current_mechanism:
            if next_mechanism in self.RELATED_MECHANISMS.get(current_mechanism, set()):
                return False
            return True
        if next_entity and current_entity and next_entity != current_entity and not current_mechanism:
            return True
        return False

    def _would_mix_distinct_ideas(
        self,
        current_sentences: List[str],
        next_sentence: str,
        current_mechanism: str | None,
        next_mechanism: str | None,
    ) -> bool:
        if not current_sentences:
            return False
        if current_mechanism and next_mechanism and current_mechanism != next_mechanism and len(current_sentences) >= 2:
            if next_mechanism in self.RELATED_MECHANISMS.get(current_mechanism, set()):
                return False
            return True
        combined = " ".join(current_sentences).lower()
        next_lower = next_sentence.lower()
        if "credit card" in combined and "emergency fund" in next_lower:
            return True
        if "emergency fund" in combined and "credit card" in next_lower:
            return True
        return False

    def _classify_idea_type(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ["lose", "lost", "gone", "drain", "shrink", "fall", "drop", "leak", "debt", "trap"]):
            return "decay"
        if any(w in text_lower for w in ["grow", "increase", "rise", "compound", "multiply"]):
            return "growth"
        if any(w in text_lower for w in ["vs", "versus", "compare", "difference", "instead"]):
            return "comparison"
        if any(w in text_lower for w in ["because", "leads to", "results in", "causes"]):
            return "causation"
        if any(w in text_lower for w in ["step", "first", "then", "next", "finally", "allocate", "track"]):
            return "process"
        if any(w in text_lower for w in ["risk", "danger", "trap", "mistake", "wrong"]):
            return "risk"
        if any(w in text_lower for w in ["is", "means", "defined", "called", "known as"]):
            return "definition"
        return "emphasis"
