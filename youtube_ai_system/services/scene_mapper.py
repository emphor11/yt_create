from __future__ import annotations


SCENE_COMPONENT_BY_PATTERN = {
    "StatCard": "StatCard",
    "HighlightText": "ConceptCard",
    "ConceptCard": "ConceptCardScene",
    "SplitComparison": "SplitComparisonScene",
    "StepFlow": "StepFlowScene",
    "GrowthChart": "GrowthChartScene",
    "RiskCard": "RiskCardScene",
    "NumericComparison": "CalculationStrip",
    "CalculationStrip": "CalculationStrip",
    "FlowDiagram": "FlowDiagram",
    "FlowBar": "FlowDiagram",
    "BalanceBar": "BalanceBar",
    "MoneyFlowDiagram": "MoneyFlowDiagram",
    "DebtSpiralVisualizer": "DebtSpiralVisualizer",
    "SIPGrowthEngine": "SIPGrowthEngine",
}


def map_pattern_to_component(pattern: str) -> str:
    normalized = str(pattern or "").strip()
    if normalized not in SCENE_COMPONENT_BY_PATTERN:
        raise ValueError(f"Unsupported scene pattern: {normalized}")
    return SCENE_COMPONENT_BY_PATTERN[normalized]
