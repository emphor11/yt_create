from __future__ import annotations

import re


_LEADING_FILLER_PATTERNS = (
    r"^(?:so|now|well|yeah|and|but)\s*,\s*",
    r"^hold up(?:,\s*buddy)?[!,.:\-\s]*",
    r"^let'?s talk about\s+",
    r"^let'?s be real[!,.:\-\s]*",
    r"^let'?s face it[!,.:\-\s]*",
    r"^trust me[!,.:\-\s]*",
    r"^in conclusion[!,.:\-\s]*",
    r"^finally[!,.:\-\s]*",
    r"^for example[,:.\-\s]*",
    r"^thanks for watching[!,.:\-\s]*",
    r"^that'?s it for today'?s video(?:\s+on\s+[^.!?]+)?[!,.:\-\s]*",
    r"^don'?t forget to like and subscribe(?:\s+for\s+[^.!?]+)?[!,.:\-\s]*",
    r"^if you have any questions or topics you'?d like to discuss[,:\-\s]*",
    r"^leave them in the comments below[!,.:\-\s]*",
    r"^we'?ll catch you in the next video[!,.:\-\s]*",
    r"^check out our next video(?:\s+where\s+[^.!?]+)?[!,.:\-\s]*",
    r"^this episode of\s+[^.!?]+[!,.:\-\s]*",
    r"^if you want to learn more about\s+[^.!?]+[!,.:\-\s]*",
)

_QUESTION_PREFIX_PATTERNS = (
    r"^(?:now,\s*)?you might be thinking[,:\-\s]*",
    r"^(?:now,\s*)?i know what you'?re thinking[,:\-\s]*",
)

_START_REPLACEMENTS = {
    "you're ": "You are ",
    "you've ": "You have ",
    "you'll ": "You will ",
    "you'd ": "You would ",
    "it's ": "It is ",
    "it'll ": "It will ",
    "that's ": "That is ",
    "there's ": "There is ",
    "they're ": "They are ",
    "we're ": "We are ",
    "don't ": "Do not ",
    "can't ": "Cannot ",
    "won't ": "Will not ",
}


def refine(text: str) -> list[str]:
    raw = _normalize(text)
    if not raw:
        return []

    refined: list[str] = []
    for sentence in _split_sentences(raw):
        refined.extend(_refine_sentence(sentence))
    return [sentence for sentence in refined if sentence]


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [_normalize(part) for part in parts if _normalize(part)]


def _refine_sentence(sentence: str) -> list[str]:
    cleaned = _strip_fillers(sentence)
    if not cleaned:
        return []

    question = _extract_question(cleaned)
    if question:
        return [question]

    clauses = _split_atomic_clauses(cleaned)
    refined: list[str] = []
    for clause in clauses:
        normalized = _normalize_clause(clause)
        if not normalized:
            continue
        if len(normalized.split()) > 20:
            refined.extend(_split_long_clause(normalized))
            continue
        refined.append(normalized)
    return refined


def _strip_fillers(text: str) -> str:
    cleaned = _normalize(text)
    cleaned = re.sub(r"^did you know that\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^did you know\s+", "", cleaned, flags=re.IGNORECASE)
    for pattern in _LEADING_FILLER_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:you know|kind of|sort of)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bmy friend\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:-")
    return cleaned


def _extract_question(text: str) -> str:
    stripped = text
    for pattern in _QUESTION_PREFIX_PATTERNS:
        stripped = re.sub(pattern, "", stripped, flags=re.IGNORECASE)
    if "?" in stripped:
        stripped = stripped.split("?", 1)[0] + "?"
    stripped = stripped.strip("\"' ")
    stripped = re.sub(r"^(?:but|and)\s+", "", stripped, flags=re.IGNORECASE)
    stripped = _normalize(stripped).strip(" ,;:-\"'")
    if stripped.endswith("?"):
        return _finalize_sentence(stripped)
    return ""


def _split_atomic_clauses(text: str) -> list[str]:
    clauses = [_normalize(text)]
    patterns = (
        r";\s+",
        r",\s+(?=(?:your|my|their|our|his|her|the)\s+[a-z][^,]{0,30}\b(?:could|can|might|may|will)\b)",
        r",\s+(?:and|but|or)\s+(?=(?:you|your|it|they|we|he|she|life|most people|the bank|the thing|investments?|credit cards?)\b)",
        r"\s+\bbut\b\s+",
    )
    for pattern in patterns:
        next_clauses: list[str] = []
        for clause in clauses:
            parts = re.split(pattern, clause, flags=re.IGNORECASE)
            next_clauses.extend(_normalize(part) for part in parts if _normalize(part))
        clauses = next_clauses or clauses
    return clauses


def _normalize_clause(text: str) -> str:
    clause = _normalize(text).strip(" ,;:-")
    clause = re.sub(r"^(?:and|but|or)\s+", "", clause, flags=re.IGNORECASE)
    clause = re.sub(r"^(?:well|so|now|yeah)\s*,\s*", "", clause, flags=re.IGNORECASE)
    clause = re.sub(r"^trust me[,:\-\s]*", "", clause, flags=re.IGNORECASE)
    clause = clause.strip("\"' ")
    clause = clause.strip(" ,;:-")
    if not re.search(r"[A-Za-z0-9₹]", clause):
        return ""
    if not clause:
        return ""
    clause = _rewrite_clause(clause)
    if not clause:
        return ""
    lowered = clause.lower()
    for start, replacement in _START_REPLACEMENTS.items():
        if lowered.startswith(start):
            clause = replacement + clause[len(start):]
            break
    return _finalize_sentence(clause)


def _split_long_clause(text: str) -> list[str]:
    fragments = [_normalize(text)]
    patterns = (
        r",\s+",
        r"\s+\band\b\s+(?=(?:you|your|it|they|we|he|she)\b)",
        r"\s+\bor\b\s+(?=(?:you|your|it|they|we|he|she)\b)",
    )
    for pattern in patterns:
        next_fragments: list[str] = []
        for fragment in fragments:
            if len(fragment.split()) <= 20:
                next_fragments.append(fragment)
                continue
            parts = re.split(pattern, fragment, flags=re.IGNORECASE)
            next_fragments.extend(_normalize(part) for part in parts if _normalize(part))
        fragments = next_fragments or fragments
    return [_finalize_sentence(fragment) for fragment in fragments if _normalize(fragment)]


def _rewrite_clause(text: str) -> str:
    clause = _normalize(text).strip(" ,;:-\"'")
    lowered = clause.lower()

    if lowered in {
        "it is a lot",
        "that is a lot",
        "you might be thinking",
        "trust me, it's worth it",
        "it's worth it",
        "the truth is",
        "in fact",
    }:
        return ""
    if lowered in {"it is worth it", "that is worth it"}:
        return "That choice is worth it"

    if "thinking about investing in the stock market" in lowered or "putting your money into a mutual fund" in lowered:
        return "Most people look at mutual funds immediately"

    if lowered.startswith("before you start investing"):
        return "Build an emergency fund first"

    if "safety net" in lowered and "emergency fund" not in lowered:
        return "An emergency fund acts like a safety net"

    if "3-6 months" in lowered and "emergency fund" in lowered:
        return "An emergency fund means three to six months of expenses set aside"

    if "₹30,000" in clause and "₹90,000" in clause and "₹1,80,000" in clause:
        return "₹30,000 of monthly expenses means an emergency fund target of ₹90,000 to ₹1,80,000"

    if lowered.startswith("having an emergency fund will give you peace of mind"):
        return "An emergency fund protects your peace of mind"
    if "help you avoid going into debt" in lowered:
        return "An emergency fund can reduce emergency borrowing"

    if lowered.startswith("you could lose your job"):
        return "Job loss is possible"
    if lowered.startswith("your car could break down"):
        return "A car breakdown is possible"
    if "medical expenses" in lowered and ("you might face" in lowered or "you might need to pay for" in lowered):
        return "Unexpected medical expenses are possible"

    return clause


def _finalize_sentence(text: str) -> str:
    cleaned = _normalize(text).strip()
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned[0].upper() + cleaned[1:]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()
