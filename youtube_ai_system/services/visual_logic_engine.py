from __future__ import annotations

from typing import Any


COMPONENT_BY_TYPE = {
    "definition": "ConceptCard",
    "comparison": "SplitComparison",
    "process": "StepFlow",
    "cause_effect": "FlowBar",
    "risk": "RiskCard",
    "growth": "GrowthChart",
    "before_after": "BeforeAfterSplit",
    "paradox": "RiskCard",
}


def map_concept_to_visual(concept_item: dict[str, Any]) -> dict[str, Any]:
    concept = _normalize_concept(str(concept_item.get("concept") or ""))
    concept_type = str(concept_item.get("type") or "").strip()

    if not concept:
        raise ValueError("Concept is required.")
    if len(concept.split()) > 3:
        raise ValueError("Concept title must be 3 words or fewer.")
    if concept_type not in COMPONENT_BY_TYPE:
        raise ValueError(f"Unsupported concept type: {concept_type}")

    component = COMPONENT_BY_TYPE[concept_type]
    props = _props_for(concept, concept_type)
    return {"component": component, "props": props}


def _props_for(concept: str, concept_type: str) -> dict[str, Any]:
    if concept_type == "definition":
        return {"title": concept.upper()}
    if concept_type == "risk":
        return {"title": concept.upper()}
    if concept_type == "comparison":
        left, right = _split_comparison(concept)
        return {"left": {"label": left}, "right": {"label": right}}
    if concept_type == "process":
        return {"steps": [concept]}
    if concept_type == "cause_effect":
        return {"start_label": concept, "end_label": ""}
    if concept_type == "growth":
        return {"start": "", "end": concept, "curve": "up"}
    if concept_type == "before_after":
        return {"before": "", "after": concept}
    if concept_type == "paradox":
        return {"title": concept.upper()}
    raise ValueError(f"Unsupported concept type: {concept_type}")


def _split_comparison(concept: str) -> tuple[str, str]:
    if " vs " not in concept:
        raise ValueError("Comparison concept must contain 'vs'.")
    left, right = concept.split(" vs ", 1)
    left = left.strip()
    right = right.strip()
    if not left or not right:
        raise ValueError("Comparison concept must contain both sides.")
    return left, right


def _normalize_concept(concept: str) -> str:
    return " ".join(concept.strip().split())
