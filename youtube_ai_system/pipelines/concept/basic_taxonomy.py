from __future__ import annotations


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
