from __future__ import annotations


HOOK_TYPES = {"curiosity", "contradiction", "surprise"}
ARC_TYPES = {"reveal_ladder", "contradiction_arc", "transformation", "problem_stack"}
SECTION_TYPES = {"problem", "explanation", "reveal", "decision", "mistake", "optimization"}

FLOW_STAGE = {
    "problem": 0,
    "mistake": 0,
    "explanation": 1,
    "reveal": 2,
    "decision": 3,
    "optimization": 3,
}

SECTION_WEIGHTS = {
    "problem": ("medium", 0.55),
    "mistake": ("medium", 0.6),
    "explanation": ("medium", 0.5),
    "reveal": ("high", 0.82),
    "decision": ("high", 0.88),
    "optimization": ("high", 0.9),
}

GENERIC_HOOK_PREFIXES = (
    "in this video",
    "today we",
    "welcome back",
    "let's talk about",
    "this video is about",
)

SECTION_PRIORITY = (
    "mistake",
    "problem",
    "optimization",
    "decision",
    "reveal",
    "explanation",
)

TERMINAL_SECTION_TYPES = {"reveal", "decision", "optimization"}
OPENING_SECTION_TYPES = {"problem", "mistake"}

AGENDA_FILLER = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "before",
    "because",
    "build",
    "but",
    "by",
    "can",
    "cheap",
    "do",
    "does",
    "feel",
    "fix",
    "for",
    "from",
    "gets",
    "had",
    "has",
    "have",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "just",
    "most",
    "now",
    "of",
    "on",
    "one",
    "or",
    "real",
    "reason",
    "simple",
    "so",
    "still",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "to",
    "too",
    "when",
    "where",
    "why",
    "with",
    "without",
    "you",
    "your",
}

BAD_AGENDA_ENDINGS = {"becomes", "catches", "delay", "faster", "keeps", "than", "this"}
CONTRADICTION_TOKENS = ("but", "still", "yet", "however", "instead", "actually", "not what")
