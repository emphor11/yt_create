from __future__ import annotations

from typing import Any

from .director_types import THEME, DirectedBeat, DirectedPlan, SceneDirection, VisualDirectorInput


class VisualDirectorQualitativePlansMixin:
    def _recap_system_plan(self, director_input: VisualDirectorInput) -> DirectedPlan:
        direction = SceneDirection("aware", "confidence", director_input.section_position, "positive")
        data = {
            "title": "Money system recap",
            "accent": "teal",
            "nodes": [
                {"label": "Track leaks", "subtext": "salary drain, EMI, FOMO"},
                {"label": "Build buffers", "subtext": "emergency fund and diversification"},
                {"label": "Let time work", "subtext": "SIP and compounding"},
            ],
        }
        beats = self._contextualize_beats(
            [
                DirectedBeat("StatCard", "Money gets a system", "normal", "recap", {"primary_value": "Money gets a system", "label": "recap", "color": "teal"}),
                DirectedBeat("FlowDiagram", "Track. Protect. Compound.", "subtle", data=data, props=data),
                DirectedBeat("HighlightText", "Small steps become control", "hero", data={"primary_value": "Small steps become control", "label": "final takeaway", "color": "teal"}),
            ],
            director_input.narration_text,
        )
        return DirectedPlan(
            concept_type="recap_system",
            concept_name="Money System Recap",
            pattern="FlowDiagram",
            data=data,
            beats=beats,
            direction=direction,
            theme=THEME,
        )

    def _qualitative_money_plan(
        self,
        director_input: VisualDirectorInput,
        concept_type: str,
        direction: SceneDirection,
        concept_name: str,
    ) -> DirectedPlan:
        if concept_type == "lifestyle_inflation":
            title = "Income rises. Savings don't."
            nodes = [
                {"label": "Income rises", "subtext": "feels like progress"},
                {"label": "Lifestyle rises", "subtext": "upgrades absorb it"},
                {"label": "Savings stay stuck", "subtext": "the gap never grows"},
            ]
            punch = "The raise never reaches savings"
        elif concept_type == "expense_leakage":
            title = "Small leaks become pressure"
            nodes = [
                {"label": "Tiny spends", "subtext": "easy to ignore"},
                {"label": "Repeated daily", "subtext": "hard to notice"},
                {"label": "Month-end pressure", "subtext": "cash disappears"},
            ]
            punch = "The leak is the system"
        elif concept_type == "emergency_fund":
            title = "Emergency fund absorbs shock"
            nodes = [
                {"label": "Unexpected bill", "subtext": "life happens"},
                {"label": "Cash buffer", "subtext": "no card swipe"},
                {"label": "Plan survives", "subtext": "stress drops"},
            ]
            punch = "The buffer buys breathing room"
        else:
            title = "Income needs a job"
            nodes = [
                {"label": "Money enters", "subtext": "salary day"},
                {"label": "Rules split it", "subtext": "before impulse"},
                {"label": "Savings protected", "subtext": "future first"},
            ]
            punch = "Allocate before you spend"
        return self._qualitative_flow_plan(director_input, concept_type, concept_name, direction, title, nodes, punch, "warning")

    def _qualitative_debt_plan(
        self,
        director_input: VisualDirectorInput,
        concept_type: str,
        direction: SceneDirection,
        concept_name: str,
    ) -> DirectedPlan:
        title = "Small payments stack"
        nodes = [
            {"label": "One EMI", "subtext": "looks harmless"},
            {"label": "More EMIs", "subtext": "fixed every month"},
            {"label": "Cash left shrinks", "subtext": "pressure hits fast"},
        ]
        punch = "Fixed payments steal flexibility"
        if concept_type == "debt_trap":
            title = "Debt trap closes slowly"
            nodes = [
                {"label": "Swipe now", "subtext": "feels free"},
                {"label": "Interest starts", "subtext": "cost keeps moving"},
                {"label": "Balance survives", "subtext": "payment wasn't enough"},
            ]
            punch = "The trap is the interest"
        return self._qualitative_flow_plan(director_input, concept_type, concept_name, direction, title, nodes, punch, "danger")

    def _qualitative_growth_plan(
        self,
        director_input: VisualDirectorInput,
        concept_type: str,
        direction: SceneDirection,
        concept_name: str,
    ) -> DirectedPlan:
        title = "Time does the heavy lifting"
        data = {"start": "Start early", "end": "Growth accelerates", "curve": "up", "visual_type": "growth"}
        beats = self._contextualize_beats(
            [
                DirectedBeat("StatCard", "Start early", "normal", "first advantage", {"primary_value": "Start early", "label": "first advantage", "color": "teal"}),
                DirectedBeat("GrowthChart", title, "subtle", data=data, props=data),
                DirectedBeat("HighlightText", "Patience creates growth", "hero", data={"primary_value": "Patience creates growth", "label": concept_name, "color": "teal"}),
            ],
            director_input.narration_text,
        )
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern="GrowthChart",
            data=data,
            beats=beats,
            direction=direction,
            theme=THEME,
        )

    def _qualitative_flow_plan(
        self,
        director_input: VisualDirectorInput,
        concept_type: str,
        concept_name: str,
        direction: SceneDirection,
        title: str,
        nodes: list[dict[str, str]],
        punch: str,
        accent: str,
    ) -> DirectedPlan:
        data = {"title": title, "nodes": nodes, "accent": accent}
        beats = self._contextualize_beats(
            [
                DirectedBeat("StatCard", nodes[0]["label"], "normal", nodes[0].get("subtext"), {"primary_value": nodes[0]["label"], "label": nodes[0].get("subtext", ""), "color": "white"}),
                DirectedBeat("FlowDiagram", title, "subtle", data=data, props=data),
                DirectedBeat("HighlightText", punch, "hero", data={"primary_value": punch, "label": concept_name, "color": "red" if accent == "danger" else "orange"}),
            ],
            director_input.narration_text,
        )
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern="FlowDiagram",
            data=data,
            beats=beats,
            direction=direction,
            theme=THEME,
        )

    def _generic_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        direction = SceneDirection("neutral", "clarity", director_input.section_position, "neutral")
        title = director_input.concept_name or "Money Change"
        return self._fallback_plan(director_input, concept_type, direction, "UniversalMechanismRenderer", title, "generic director fallback")

    def _fallback_plan(
        self,
        director_input: VisualDirectorInput,
        concept_type: str,
        direction: SceneDirection,
        first_component: str,
        concept_name: str,
        reason: str | None,
    ) -> DirectedPlan:
        values = self._money_mentions(director_input.narration_text)
        rate = self._first_percentage(director_input.narration_text)
        beats: list[DirectedBeat] = []
        if values:
            beats.append(DirectedBeat(first_component, values[0]["value"], "normal", values[0]["label"] or concept_name))
        else:
            beats.append(DirectedBeat(first_component, concept_name, "normal"))
        if rate is not None:
            beats.append(DirectedBeat("StatCard", f"{rate:g}%", "subtle", "rate"))
        elif len(values) > 1:
            steps = [{"label": item["label"] or "value", "value": item["value"]} for item in values[:3]]
            beats.append(DirectedBeat("CalculationStrip", "What changes", "subtle", data={"steps": steps}))
        else:
            beats.append(DirectedBeat("HighlightText", self._short_phrase(director_input.narration_text, concept_name), "hero"))
        if len(beats) == 2 and beats[-1].emphasis != "hero":
            beats.append(DirectedBeat("HighlightText", concept_name, "hero"))
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern=beats[0].component,
            data={"title": concept_name.upper()},
            beats=beats,
            direction=direction,
            theme=THEME,
            fallback_reason=reason,
        )
