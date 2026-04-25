from __future__ import annotations


SCENE_COMPONENT_BY_PATTERN = {
    "ConceptCard": "ConceptCardScene",
    "SplitComparison": "SplitComparisonScene",
    "StepFlow": "StepFlowScene",
    "GrowthChart": "GrowthChartScene",
    "RiskCard": "RiskCardScene",
    "NumericComparison": "CalculationStrip",
}


def map_pattern_to_component(pattern: str) -> str:
    normalized = str(pattern or "").strip()
    if normalized not in SCENE_COMPONENT_BY_PATTERN:
        raise ValueError(f"Unsupported scene pattern: {normalized}")
    return SCENE_COMPONENT_BY_PATTERN[normalized]
