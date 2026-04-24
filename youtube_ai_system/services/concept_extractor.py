from __future__ import annotations

import re
from typing import Any


CONFIDENCE_THRESHOLD = 0.6
MAX_CONCEPTS_PER_SENTENCE = 2

FINANCE_KEYWORDS = (
    "emergency fund",
    "debt trap",
    "compound interest",
    "lifestyle inflation",
    "minimum payment cycle",
    "minimum dues",
    "minimum payment",
    "interest profit",
    "inflation loss",
    "investment",
    "inflation",
    "returns",
    "savings",
    "debt",
    "equity",
    "budgeting",
    "budget",
    "credit",
    "loan",
    "income",
    "fund",
    "money",
)

GENERIC_NOUNS = {"credit", "system", "people", "money", "result", "change", "problem"}
CONCEPT_STOPWORDS = {"we", "if", "this", "that", "it", "they", "let", "start", "thing", "which", "what", "and"}
MEANINGFUL_SUFFIXES = {
    "fund",
    "trap",
    "growth",
    "risk",
    "returns",
    "return",
    "debt",
    "inflation",
    "budget",
    "investment",
    "savings",
    "payment",
    "profit",
    "loss",
    "cycle",
    "erosion",
    "income",
    "interest",
    "impact",
}

VAGUE_CONCEPTS = {
    "this",
    "that",
    "it",
    "money",
    "problem",
    "idea",
    "thing",
    "change",
    "result",
    "impact",
    "process",
}

POSITIVE_TOKENS = {"rich", "stable", "safe", "gain", "profit", "returns", "growth"}
NEGATIVE_TOKENS = {"broke", "debt", "trap", "loss", "lose", "risky", "risk", "danger", "destroy"}

TYPE_PRIORITY = (
    "before_after",
    "comparison",
    "paradox",
    "process",
    "cause_effect",
    "growth",
    "risk",
    "definition",
)


def extract(sentence: str) -> dict[str, Any]:
    concepts = extract_all(sentence)
    return concepts[0]


def extract_all(sentence: str) -> list[dict[str, Any]]:
    text = _normalize(sentence)
    if not text:
        raise ValueError("Sentence is required.")

    candidates: list[dict[str, Any]] = []
    best_unknown = {"concept": None, "type": "unknown", "confidence": 0.0}
    for clause in _candidate_clauses(text):
        result = _extract_from_clause(clause)
        if result["type"] == "unknown":
            if result["confidence"] > best_unknown["confidence"]:
                best_unknown = result
            continue
        if _is_duplicate(candidates, result):
            continue
        candidates.append(result)
        if len(candidates) == MAX_CONCEPTS_PER_SENTENCE:
            break

    if candidates:
        return candidates
    return [best_unknown]


def _extract_from_clause(text: str) -> dict[str, Any]:
    concept_type = _detect_type(text)
    concept = _extract_concept(text, concept_type)
    concept = _normalize_concept(concept, concept_type)
    if not _is_valid_concept_shape(concept):
        concept = _normalize_concept(_retry_stronger_concept(text, concept_type), concept_type)
    confidence = _score_confidence(text, concept_type, concept)

    if confidence < CONFIDENCE_THRESHOLD or not concept:
        return {"concept": None, "type": "unknown", "confidence": round(confidence, 2)}

    try:
        _validate_concept(concept)
    except ValueError:
        return {"concept": None, "type": "unknown", "confidence": round(confidence, 2)}
    return {"concept": concept, "type": concept_type, "confidence": round(confidence, 2)}


def _candidate_clauses(text: str) -> list[str]:
    clauses = [_normalize(text)]
    splitters = (
        r",\s+and\s+",
        r"\s+and\s+(?!after\b)",
        r";\s+",
    )
    for pattern in splitters:
        next_clauses: list[str] = []
        for clause in clauses:
            parts = re.split(pattern, clause, flags=re.IGNORECASE)
            next_clauses.extend(_normalize(part) for part in parts if _normalize(part))
        clauses = next_clauses or clauses
    return clauses[:MAX_CONCEPTS_PER_SENTENCE]


def _detect_type(text: str) -> str:
    lowered = text.lower()
    if _contains_keyword(lowered, "risk", "danger", "trap", "loss", "cost", "destroy"):
        return "risk"
    if _contains_keyword(lowered, "before") and _contains_keyword(lowered, "after"):
        return "before_after"
    if any(token in lowered for token in (" while ", " compared to ", " vs ", " versus ")):
        return "comparison"
    if (" but " in lowered or " yet " in lowered) and _has_contradiction_tone(lowered):
        return "paradox"
    if any(token in lowered for token in ("first", "then", "next", "finally")):
        return "process"
    if any(token in lowered for token in ("leads to", "causes", " because ", " when ", " makes ", "creates")):
        return "cause_effect"
    if any(token in lowered for token in ("grow", "grows", "growth", "increase", "increases", "over time", "years")):
        return "growth"
    if _contains_keyword(lowered, "risk", "danger", "trap", "loss", "cost", "lose", "destroy"):
        return "risk"
    return "definition"


def _has_contradiction_tone(text: str) -> bool:
    tokens = set(_tokens(text))
    return bool(tokens & POSITIVE_TOKENS and tokens & NEGATIVE_TOKENS)


def _extract_concept(text: str, concept_type: str) -> str:
    if concept_type == "before_after":
        return _extract_before_after(text)
    if concept_type == "comparison":
        return _extract_comparison(text)
    if concept_type == "paradox":
        return _extract_paradox(text)
    if concept_type == "process":
        return _extract_process(text)
    if concept_type == "cause_effect":
        return _extract_cause_effect(text)
    if concept_type == "growth":
        return _extract_growth(text)
    if concept_type == "risk":
        return _extract_risk(text)
    return _extract_definition(text)


def _extract_before_after(text: str) -> str:
    entity = _best_entity(text)
    if entity in {"Budget", "Budgeting"}:
        return "Budgeting Impact"
    return f"{entity} Impact" if entity else ""


def _extract_comparison(text: str) -> str:
    lowered = text.lower()
    for marker in (" while ", " compared to ", " vs ", " versus "):
        if marker in lowered:
            left, right = re.split(marker, text, maxsplit=1, flags=re.IGNORECASE)
            left_entity = _best_entity(left)
            right_entity = _best_entity(right)
            if left_entity and right_entity:
                return f"{left_entity} vs {right_entity}"
    return ""


def _extract_paradox(text: str) -> str:
    lowered = text.lower()
    if "rich" in lowered and "broke" in lowered:
        return "Rich but Broke"
    parts = re.split(r"\b(?:but|yet)\b", text, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2:
        left = _best_entity(parts[0])
        right = _best_entity(parts[1])
        if left and right:
            return f"{left} but {right}"
    return ""


def _extract_process(text: str) -> str:
    lowered = text.lower()
    if "invest" in lowered:
        return "Investment Process"
    if "budget" in lowered:
        return "Budget Process"
    if "money" in lowered:
        return "Money Flow"
    if "debt" in lowered:
        return "Debt Process"
    entity = _best_entity(text)
    return f"{entity} Process" if entity else ""


def _extract_cause_effect(text: str) -> str:
    if "trap" in text.lower() or "risk" in text.lower():
        risk_concept = _extract_risk(text)
        if risk_concept:
            return risk_concept
    lowered = text.lower()
    if "minimum payment" in lowered or "minimum dues" in lowered or ("minimum" in lowered and "credit card" in lowered):
        return "Minimum Payment Cycle"
    if "banks" in lowered and "interest" in lowered and any(token in lowered for token in ("earn", "earns", "profit", "profits", "make more money")):
        return "Interest Profit"
    if "inflation" in lowered and any(token in lowered for token in ("lose value", "reduces value", "cuts value", "loss")):
        return "Inflation Loss"
    entity = _finance_keyword_entity(text)
    if entity:
        return entity
    match = re.search(r"^([A-Za-z][A-Za-z ]{0,30}?)\s+(?:leads to|causes|creates|because|makes|when)\b", text, flags=re.IGNORECASE)
    if match:
        return _title_phrase(match.group(1))
    return ""


def _extract_growth(text: str) -> str:
    lowered = text.lower()
    if "invest" in lowered:
        return "Investment Growth"
    if "investment returns growth" in lowered:
        return "Investment Growth"
    if "return" in lowered:
        return "Returns Growth"
    if "saving" in lowered:
        return "Savings Growth"
    entity = _best_entity(text)
    return f"{entity} Growth" if entity else ""


def _extract_risk(text: str) -> str:
    lowered = text.lower()
    match = re.search(r"\b([A-Za-z]+)\s+trap\b", text, flags=re.IGNORECASE)
    if match:
        return f"{_title_phrase(match.group(1))} Trap"
    match = re.search(r"\b([A-Za-z]+)\s+risk\b", text, flags=re.IGNORECASE)
    if match:
        return f"{_title_phrase(match.group(1))} Risk"
    if "interest" in lowered and any(token in lowered for token in ("loss", "cost", "destroy")):
        return "Interest Loss"
    if any(token in lowered for token in ("wealth", "savings", "inflation")) and any(
        token in lowered for token in ("loss", "cost", "destroy", "erosion")
    ):
        return "Wealth Erosion"
    if "debt" in lowered:
        if "trap" in lowered:
            return "Debt Trap"
        return "Debt Risk"
    entity = _best_entity(text)
    return f"{entity} Risk" if entity else ""


def _extract_definition(text: str) -> str:
    lowered = text.lower()
    if "minimum payment" in lowered or "minimum dues" in lowered or ("minimum" in lowered and "credit card" in lowered):
        return "Minimum Payment Cycle"
    if "interest" in lowered and any(token in lowered for token in ("profit", "earns", "earn")):
        return "Interest Profit"
    if "inflation" in lowered and any(token in lowered for token in ("lose value", "reduces value", "cuts value")):
        return "Inflation Loss"
    return _best_entity(text)


def _retry_stronger_concept(text: str, concept_type: str) -> str:
    lowered = text.lower()
    if "minimum" in lowered and any(token in lowered for token in ("payment", "dues", "credit card")):
        return "Minimum Payment Cycle"
    if "interest" in lowered and any(token in lowered for token in ("cost", "loss", "destroy")):
        return "Interest Loss"
    if "banks" in lowered and "interest" in lowered:
        return "Interest Profit"
    if "inflation" in lowered and any(token in lowered for token in ("lose value", "reduces value", "cuts value", "loss")):
        return "Inflation Loss"
    if any(token in lowered for token in ("wealth", "savings", "inflation")) and any(
        token in lowered for token in ("loss", "cost", "destroy", "erosion")
    ):
        return "Wealth Erosion"
    if "debt" in lowered and "trap" in lowered:
        return "Debt Trap"
    if concept_type == "comparison":
        return _extract_comparison(text)
    if concept_type == "growth":
        return _extract_growth(text)
    return ""


def _best_entity(text: str) -> str:
    keyword_entity = _finance_keyword_entity(text)
    if keyword_entity and keyword_entity.lower() not in GENERIC_NOUNS:
        return keyword_entity

    capitalized = re.findall(r"\b[A-Z][a-zA-Z]+\b(?:\s+[A-Z][a-zA-Z]+\b)?", text)
    if capitalized:
        candidate = _title_phrase(capitalized[0])
        if candidate.lower() not in GENERIC_NOUNS:
            return candidate

    noun_phrase = re.search(
        r"\b([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+(fund|trap|growth|risk|returns?|debt|inflation|budget|investment|savings)\b",
        text,
        flags=re.IGNORECASE,
    )
    if noun_phrase:
        return _title_phrase(f"{noun_phrase.group(1)} {noun_phrase.group(2)}")

    tokens = [
        token
        for token in _tokens(text)
        if token not in {"you", "your", "this", "that", "manage", "better", "helps"} and token not in GENERIC_NOUNS
    ]
    return _title_phrase(tokens[0]) if tokens else ""


def _finance_keyword_entity(text: str) -> str:
    lowered = text.lower()
    for keyword in sorted(FINANCE_KEYWORDS, key=len, reverse=True):
        if keyword in lowered:
            if keyword in {"invest", "investment"}:
                return "Investment"
            if keyword == "returns":
                return "Returns"
            return _title_phrase(keyword)
    return ""


def _normalize_concept(concept: str, concept_type: str) -> str:
    cleaned = _title_phrase(re.sub(r"\s+", " ", str(concept or "")).strip(" .,:;!?-"))
    if not cleaned:
        return ""

    if concept_type == "growth":
        base = cleaned.replace(" Growth", "")
        return f"{base} Growth"
    if concept_type == "risk":
        if cleaned.endswith(" Trap") or cleaned.endswith(" Risk") or cleaned.endswith(" Loss") or cleaned.endswith(" Erosion"):
            return cleaned
        return f"{cleaned} Risk"
    if concept_type == "comparison" and " vs " in cleaned:
        left, right = cleaned.split(" vs ", 1)
        return f"{_title_phrase(left)} vs {_title_phrase(right)}"
    if concept_type == "paradox" and " but " in cleaned:
        left, right = cleaned.split(" but ", 1)
        return f"{_title_phrase(left)} but {_title_phrase(right)}"
    return cleaned


def _score_confidence(text: str, concept_type: str, concept: str) -> float:
    score = 0.0
    lowered = text.lower()

    if concept_type != "definition":
        score += 0.45
    else:
        score += 0.2

    if any(keyword in lowered for keyword in FINANCE_KEYWORDS):
        score += 0.25
    if concept and len(concept.split()) <= 3 and concept.lower() not in VAGUE_CONCEPTS:
        score += 0.2
    if re.search(r"\b[A-Z][a-zA-Z]+\b", text):
        score += 0.1

    if concept_type == "comparison" and " vs " in concept:
        score += 0.1
    if concept_type == "growth" and concept.endswith(" Growth"):
        score += 0.1
    if concept_type == "risk" and (concept.endswith(" Trap") or concept.endswith(" Risk")):
        score += 0.1

    return min(score, 1.0)


def _is_duplicate(existing: list[dict[str, Any]], candidate: dict[str, Any]) -> bool:
    for item in existing:
        if item["type"] == candidate["type"] and item["concept"] == candidate["concept"]:
            return True
    return False


def _validate_concept(concept: str) -> None:
    words = concept.split()
    if not concept:
        raise ValueError("Concept cannot be empty.")
    if len(concept) < 4:
        raise ValueError("Concept is too short.")
    if len(words) < 2 or len(words) > 3:
        raise ValueError("Concept must be 1-3 words.")
    lowered = concept.lower()
    if lowered in VAGUE_CONCEPTS or lowered in CONCEPT_STOPWORDS:
        raise ValueError("Concept is too vague.")
    if any(word.lower() in CONCEPT_STOPWORDS for word in words):
        raise ValueError("Concept contains stopword tokens.")
    if not _is_meaningful_phrase(concept):
        raise ValueError("Concept is not a meaningful phrase.")
    if re.search(r"[.!?]", concept):
        raise ValueError("Concept must not be a sentence.")


def _is_valid_concept_shape(concept: str) -> bool:
    if not concept or len(concept) < 4:
        return False
    words = concept.split()
    if len(words) < 2 or len(words) > 3:
        return False
    if any(word.lower() in CONCEPT_STOPWORDS for word in words):
        return False
    if not _is_meaningful_phrase(concept):
        return False
    return True


def _is_meaningful_phrase(concept: str) -> bool:
    words = concept.split()
    if len(words) < 2:
        return False
    lowered_words = [word.lower() for word in words]
    if any(word in GENERIC_NOUNS for word in lowered_words):
        return False
    if lowered_words[-1] in MEANINGFUL_SUFFIXES:
        return True
    if any(" ".join(lowered_words[:length]) in FINANCE_KEYWORDS for length in (2, 3) if len(lowered_words) >= length):
        return True
    return bool(set(lowered_words) & MEANINGFUL_SUFFIXES)


def _title_phrase(text: str) -> str:
    words = []
    for word in re.findall(r"[A-Za-z0-9]+|vs|but", text):
        if word.lower() in {"vs", "but"}:
            words.append(word.lower())
        else:
            words.append(word.capitalize())
    return " ".join(words[:3])


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _contains_keyword(text: str, *keywords: str) -> bool:
    return any(re.search(rf"\b{re.escape(keyword)}\b", text) for keyword in keywords)
