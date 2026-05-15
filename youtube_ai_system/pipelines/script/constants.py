from __future__ import annotations


TENSION_KEYWORDS = {
    "?",
    "why",
    "how",
    "never",
    "secret",
    "mistake",
    "truth",
    "wrong",
    "actually",
    "shocking",
    "reveal",
    "hidden",
    "nobody",
    "most people",
    "what happens",
    "find out",
    "you think",
    "real reason",
}

PEOPLE_GROUP_WORDS = {
    "indians",
    "people",
    "salary",
    "workers",
    "families",
    "earners",
    "graduates",
    "investors",
}

NEGATIVE_IMPLICATION_WORDS = {
    "lose",
    "lost",
    "losing",
    "paying",
    "gone",
    "spent",
    "debt",
    "broke",
    "savings",
    "interest",
    "leak",
    "drain",
    "cost",
}

DEFAULT_TARGET_DURATION_MINUTES = 8
DEFAULT_CHANNEL_NICHE = "personal finance India"
DEFAULT_SCRIPT_TONE = "confident, direct, slightly provocative"
MIN_BODY_SCENES_FOR_LONG_FORM = 8
HOOK_MIN_WORDS = 8
HOOK_MAX_WORDS = 35
BODY_MIN_WORDS = 160
BODY_MAX_WORDS = 200
OUTRO_MIN_WORDS = 110
OUTRO_MAX_WORDS = 150
TOTAL_WORD_APPROVAL_TOLERANCE_RATIO = 0.02
TOTAL_WORD_APPROVAL_TOLERANCE_MIN_WORDS = 15
DUPLICATE_SCENE_SIMILARITY = 0.92
VALID_TENSION_TYPES = {
    "curiosity_gap",
    "shocking_statistic",
    "contrarian_claim",
    "common_mistake_reveal",
    "before_after",
}
