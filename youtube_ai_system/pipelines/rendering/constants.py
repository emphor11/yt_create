from __future__ import annotations


INTENT_PATTERN_MAP = {
    "HOOK": {"EMPHASIS", "CONTEXT"},
    "COMPARISON": {"COMPARISON"},
    "DATA": {"GROWTH", "COMPARISON"},
    "EXPLANATION": {"MONEY_FLOW", "VALUE_DECAY", "LOOP", "GROWTH"},
    "EMPHASIS": {"EMPHASIS"},
    "CONTEXT": {"CONTEXT"},
}

DURATION_BY_INTENT = {
    "HOOK": 2.5,
    "EMPHASIS": 2.5,
    "COMPARISON": 3.0,
    "DATA": 4.0,
    "EXPLANATION": 4.5,
    "CONTEXT": 3.0,
}

ANIMATION_MAP = {
    "reveal": {"type": "fade_sequence"},
    "progress": {"type": "line_draw"},
    "highlight": {"type": "pulse_node"},
    "transform": {"type": "scale_change"},
}

VISUAL_LOGIC_SCHEMA = {
    "decay": ("input", "factor", "output"),
    "flow": ("source", "process", "result"),
    "comparison": ("left", "right"),
    "growth": ("input", "rate", "output"),
    "emphasis": ("headline",),
}

LOGIC_TYPE_TO_PATTERN = {
    "decay": "VALUE_DECAY",
    "flow": "MONEY_FLOW",
    "comparison": "COMPARISON",
    "growth": "GROWTH",
    "emphasis": "EMPHASIS",
}

FLOW_PATTERNS = {"MONEY_FLOW", "VALUE_DECAY", "LOOP", "GROWTH"}

VALID_COMPONENTS = {
    "FlowDiagram",
    "SplitComparison",
    "BarChart",
    "LineChart",
    "StatExplosion",
    "TextBurst",
    "ReactionCard",
    "BrollOverlay",
}

VALID_NODE_ROLES = {"source", "process", "modifier", "result", "actor", "sink"}

ABSTRACT_VISUAL_WORDS = {
    "abstract",
    "chart",
    "contrast",
    "concept",
    "data",
    "display",
    "flow",
    "graph",
    "idea",
    "image",
    "juxtaposition",
    "narrative",
    "show",
    "split screen",
    "static image",
    "statistic",
    "stuff",
    "thing",
    "visual",
}

GENERIC_VISUAL_WORDS = {
    "money reality",
    "reality",
    "system",
    "think",
    "wait what",
}

BEAT_TO_COMPOSITION = {
    "flow_diagram": "FlowDiagram",
    "stat_explosion": "StatExplosion",
    "text_burst": "TextBurst",
    "chart": "BarChart",
    "split_comparison": "SplitComparison",
    "broll_caption": "BrollOverlay",
    "reaction_card": "ReactionCard",
    "graph": "BarChart",
    "broll": "BrollOverlay",
    "motion_text": "StatReveal",
}
