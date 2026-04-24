from __future__ import annotations

import re
from typing import Any


FINANCE_PHRASES = (
    "minimum payment",
    "minimum dues",
    "debt trap",
    "credit card",
    "interest rate",
    "interest",
    "principal amount",
    "principal",
    "emergency fund",
    "income shocks",
    "income shock",
    "financial freedom",
    "budgeting",
    "inflation",
    "savings",
    "equity",
    "debt",
    "returns",
    "investment",
)

STOPWORDS = {
    "a",
    "an",
    "the",
    "this",
    "that",
    "these",
    "those",
    "you",
    "your",
    "are",
    "is",
    "was",
    "were",
    "be",
    "being",
    "been",
    "can",
    "could",
    "would",
    "should",
    "just",
    "only",
    "really",
    "very",
    "into",
    "with",
    "from",
    "have",
    "has",
    "had",
}


def generate_beats(concept_item: dict[str, Any], sentence: str) -> dict[str, list[dict[str, str]]]:
    concept = _normalize_text(str(concept_item.get("concept") or ""))
    concept_type = str(concept_item.get("type") or "").strip()
    weight_level = str(concept_item.get("weight_level") or "medium").strip().lower()
    sentence = _normalize_text(sentence)

    if not concept:
        raise ValueError("Concept is required.")
    if not concept_type:
        raise ValueError("Concept type is required.")

    beats = _beats_for(concept, concept_type, sentence)
    if not beats:
        beats = [{"component": "ConceptCard", "text": concept}]
    beats = _apply_weight_variation(beats, concept, concept_type, weight_level)
    beats = _dedupe_beats(beats, concept)
    if len(beats) > 3:
        raise ValueError("Beat plan cannot exceed 3 beats.")
    if any(not _normalize_text(beat["text"]) for beat in beats):
        raise ValueError("Beat text cannot be empty.")

    return {"beats": beats}


def _beats_for(concept: str, concept_type: str, sentence: str) -> list[dict[str, str]]:
    phrases = _extract_key_phrases(sentence, concept)

    if concept_type == "risk":
        first = _risk_source_phrase(sentence, phrases) or concept
        second = _risk_process_phrase(sentence, concept)
        return [
            {"component": "StatCard", "text": first},
            {"component": "FlowBar", "text": second},
            {"component": "RiskCard", "text": concept},
        ]

    if concept_type == "comparison":
        left, right = _split_comparison(concept)
        return [
            {"component": "ConceptCard", "text": left},
            {"component": "ConceptCard", "text": right},
            {"component": "SplitComparison", "text": concept},
        ]

    if concept_type == "cause_effect":
        cause = _cause_phrase(sentence, concept, phrases)
        process = _process_phrase(sentence)
        effect = _effect_phrase(sentence, concept, phrases)
        if effect.lower() == concept.lower():
            effect = _impact_phrase(sentence, concept) or _alternate_phrase(phrases, concept) or effect
        if cause and process and effect:
            return [
                {"component": "StatCard", "text": cause},
                {"component": "FlowBar", "text": process},
                {"component": "ConceptCard", "text": effect},
            ]

    if concept_type == "growth":
        start_value, end_value = _growth_phrases(sentence, concept, phrases)
        if start_value and end_value:
            return [
                {"component": "StatCard", "text": start_value},
                {"component": "GrowthChart", "text": "Growth path"},
                {"component": "StatCard", "text": end_value},
            ]

    if concept_type == "before_after":
        before_phrase, after_phrase = _before_after_phrases(sentence, concept, phrases)
        if before_phrase and after_phrase:
            return [
                {"component": "ConceptCard", "text": before_phrase},
                {"component": "BeforeAfterSplit", "text": "Before After"},
                {"component": "ConceptCard", "text": after_phrase},
            ]

    if concept_type == "process":
        return [{"component": "StepFlow", "text": concept}]

    if concept_type == "definition":
        meaning = _definition_phrase(sentence, concept, phrases)
        if meaning and meaning.lower() != concept.lower():
            return [
                {"component": "ConceptCard", "text": concept},
                {"component": "ConceptCard", "text": meaning},
            ]

    if concept_type == "paradox":
        expectation = _paradox_expectation(sentence, phrases)
        if expectation:
            return [
                {"component": "ConceptCard", "text": expectation},
                {"component": "RiskCard", "text": concept},
            ]

    return []


def _apply_weight_variation(
    beats: list[dict[str, str]],
    concept: str,
    concept_type: str,
    weight_level: str,
) -> list[dict[str, str]]:
    adjusted = [dict(beat) for beat in beats]
    if not adjusted:
        return adjusted

    if weight_level == "low":
        if len(adjusted) > 1:
            if concept_type in {"comparison", "growth", "before_after", "cause_effect"}:
                adjusted = [adjusted[0], adjusted[-1]]
            else:
                adjusted = [adjusted[-1]]
    elif weight_level == "medium":
        if len(adjusted) == 3 and concept_type not in {"comparison", "growth", "before_after"}:
            adjusted = [adjusted[0], adjusted[-1]]

    adjusted[-1]["text"] = concept
    return adjusted


def _dedupe_beats(beats: list[dict[str, str]], concept: str) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for beat in beats:
        text = _normalize_text(beat["text"])
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        deduped.append({"component": beat["component"], "text": text})
    if not deduped:
        return [{"component": "ConceptCard", "text": concept}]
    if len(deduped) == 1 and deduped[0]["text"].lower() != concept.lower():
        deduped.append({"component": "ConceptCard", "text": concept})
    deduped[-1]["text"] = concept
    return deduped


def _extract_key_phrases(sentence: str, concept: str) -> list[str]:
    lowered = sentence.lower()
    phrases: list[str] = []

    for phrase in FINANCE_PHRASES:
        if phrase in lowered:
            phrases.append(_title_like(phrase))

    quoted = re.findall(r"'([^']+)'|\"([^\"]+)\"", sentence)
    for pair in quoted:
        text = next((item for item in pair if item), "")
        if text:
            phrases.append(_limit_phrase(text, 4))

    words = re.findall(r"[A-Za-z][A-Za-z']+", sentence)
    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        lower = word.lower()
        if lower in STOPWORDS:
            if current:
                chunks.append(" ".join(current))
                current = []
            continue
        current.append(word)
        if len(current) == 3:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))

    for chunk in chunks:
        phrases.append(_limit_phrase(chunk, 4))

    deduped: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        clean = _normalize_text(phrase)
        if not clean or clean.lower() == concept.lower():
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(clean)
        if len(deduped) == 3:
            break
    return deduped


def _risk_source_phrase(sentence: str, phrases: list[str]) -> str:
    lowered = sentence.lower()
    for phrase in ("Minimum dues", "Minimum payment", "Credit card", "Debt"):
        if phrase.lower() in lowered:
            return phrase
    return phrases[0] if phrases else ""


def _risk_process_phrase(sentence: str, concept: str) -> str:
    lowered = sentence.lower()
    if "minimum dues" in lowered or "minimum payment" in lowered:
        return "Interest grows"
    if "destroy" in lowered:
        return "Loss grows"
    if "risk" in lowered:
        return "Risk rises"
    if "trap" in concept.lower():
        return "Debt grows"
    return "Risk builds"


def _cause_phrase(sentence: str, concept: str, phrases: list[str]) -> str:
    for trigger in (" makes ", " causes ", " creates ", " leads to ", " because ", " when "):
        lowered = f" {sentence.lower()} "
        if trigger in lowered:
            left = sentence[: lowered.index(trigger)].strip(" ,.")
            phrase = _best_phrase(left)
            return phrase or (phrases[0] if phrases else concept)
    return phrases[0] if phrases else concept


def _process_phrase(sentence: str) -> str:
    lowered = sentence.lower()
    if "makes" in lowered or "causes" in lowered or "creates" in lowered:
        return "Effect spreads"
    if "because" in lowered:
        return "Pressure builds"
    if "when" in lowered:
        return "Chain begins"
    return "Effect builds"


def _effect_phrase(sentence: str, concept: str, phrases: list[str]) -> str:
    lowered = f" {sentence.lower()} "
    for trigger in (" makes ", " causes ", " creates ", " leads to "):
        if trigger in lowered:
            right = sentence[lowered.index(trigger) + len(trigger) - 1 :].strip(" ,.")
            phrase = _best_phrase(right)
            return phrase or concept
    return concept


def _alternate_phrase(phrases: list[str], concept: str) -> str:
    for phrase in phrases:
        if phrase.lower() != concept.lower():
            return phrase
    return ""


def _impact_phrase(sentence: str, concept: str) -> str:
    lowered = sentence.lower()
    if "savings" in lowered:
        return "Savings value"
    if "debt" in lowered:
        return "Debt pressure"
    if "interest" in lowered:
        return "Interest cost"
    return _best_phrase(sentence) if _best_phrase(sentence).lower() != concept.lower() else ""


def _growth_phrases(sentence: str, concept: str, phrases: list[str]) -> tuple[str, str]:
    values = re.findall(r"(?:₹|Rs\.?\s*)?\d[\d,]*(?:\.\d+)?\s*(?:%|years?|months?|lakhs?)?", sentence, flags=re.IGNORECASE)
    clean_values = [_normalize_text(value) for value in values if _normalize_text(value)]
    if len(clean_values) >= 2:
        return clean_values[0], clean_values[-1]
    if len(clean_values) == 1:
        return clean_values[0], concept
    if phrases:
        return phrases[0], concept
    return "", ""


def _before_after_phrases(sentence: str, concept: str, phrases: list[str]) -> tuple[str, str]:
    lowered = sentence.lower()
    if " before " in lowered and " after " in lowered:
        before_idx = lowered.index(" before ")
        after_idx = lowered.index(" after ")
        before = _best_phrase(sentence[:before_idx]) or "Before change"
        after = _best_phrase(sentence[after_idx + len(" after ") :]) or concept
        return before, after
    return ("Before change", concept) if concept else ("", "")


def _definition_phrase(sentence: str, concept: str, phrases: list[str]) -> str:
    for phrase in phrases:
        if phrase.lower() != concept.lower():
            return phrase
    if "means" in sentence.lower():
        right = sentence.lower().split("means", 1)[1]
        phrase = _best_phrase(right)
        if phrase:
            return phrase
    words = [
        word
        for word in re.findall(r"[A-Za-z][A-Za-z']+", sentence)
        if word.lower() not in STOPWORDS and word.lower() not in {token.lower() for token in concept.split()}
    ]
    if words:
        return _limit_phrase(" ".join(words[:2]), 4)
    return ""


def _paradox_expectation(sentence: str, phrases: list[str]) -> str:
    lowered = sentence.lower()
    for marker in (" but ", " yet "):
        if marker in lowered:
            left = sentence[: lowered.index(marker)].strip(" ,.")
            phrase = _best_phrase(left)
            if phrase:
                return phrase
    return phrases[0] if phrases else ""


def _split_comparison(concept: str) -> tuple[str, str]:
    if " vs " not in concept:
        return concept, concept
    left, right = concept.split(" vs ", 1)
    return _normalize_text(left), _normalize_text(right)


def _best_phrase(text: str) -> str:
    lowered = text.lower()
    for phrase in FINANCE_PHRASES:
        if phrase in lowered:
            return _title_like(phrase)

    words = [word for word in re.findall(r"[A-Za-z][A-Za-z']+", text) if word.lower() not in STOPWORDS]
    if not words:
        return ""
    return _limit_phrase(" ".join(words[:3]), 4)


def _limit_phrase(text: str, max_words: int) -> str:
    words = _normalize_text(text).split()
    return " ".join(words[:max_words])


def _title_like(text: str) -> str:
    words = _normalize_text(text).split()
    return " ".join(word.capitalize() if word.lower() not in {"vs", "but"} else word.lower() for word in words[:4])


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().split())
