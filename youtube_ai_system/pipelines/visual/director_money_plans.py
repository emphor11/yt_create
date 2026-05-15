from __future__ import annotations

from typing import Any

from .director_types import THEME, DirectedBeat, DirectedPlan, SceneDirection, VisualDirectorInput


class VisualDirectorMoneyPlansMixin:
    def _salary_drain_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        flow_data = self._money_flow_data(director_input)
        direction = SceneDirection("comfort", "anxiety", director_input.section_position, "danger")
        if flow_data:
            remainder = flow_data["remainder"]
            intro_data = {**flow_data, "active_phase": "intro"}
            drain_data = {**flow_data, "active_phase": "drain"}
            remainder_data = {**flow_data, "active_phase": "remainder"}
            return DirectedPlan(
                concept_type=concept_type,
                concept_name="Salary Drain",
                pattern="MoneyFlowDiagram",
                data=flow_data,
                direction=direction,
                theme=THEME,
                beats=self._contextualize_beats([
                    DirectedBeat(
                        "MoneyFlowDiagram",
                        flow_data["source"]["value"],
                        "normal",
                        flow_data["source"]["label"],
                        data=intro_data,
                        beat_phase="intro",
                    ),
                    DirectedBeat("MoneyFlowDiagram", "Where salary goes", "subtle", data=drain_data, beat_phase="drain"),
                    DirectedBeat(
                        "MoneyFlowDiagram",
                        f"{remainder['value']} left",
                        "hero",
                        "danger zone" if remainder["is_dangerous"] else "left over",
                        data=remainder_data,
                        beat_phase="remainder",
                    ),
                ], director_input.narration_text),
            )
        return self._fallback_plan(
            director_input,
            concept_type,
            direction,
            "StatCard",
            "Salary Drain",
            "insufficient data for MoneyFlowDiagram",
        )

    def _lifestyle_creep_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        data = self._lifestyle_creep_data(director_input)
        direction = SceneDirection("hopeful", "anxiety", director_input.section_position, "warning")
        return DirectedPlan(
            concept_type=concept_type,
            concept_name="Lifestyle Inflation",
            pattern="LifestyleCreepVisualizer",
            data=data,
            direction=direction,
            theme=THEME,
            beats=self._contextualize_beats(
                [
                    DirectedBeat(
                        "LifestyleCreepVisualizer",
                        f"{data['start_income']['value']} income",
                        "normal",
                        "before the raise",
                        data={**data, "active_phase": "income_base"},
                        beat_phase="income_base",
                    ),
                    DirectedBeat(
                        "LifestyleCreepVisualizer",
                        f"{data['end_income']['value']} income",
                        "subtle",
                        "raise arrives",
                        data={**data, "active_phase": "raise_arrives"},
                        beat_phase="raise_arrives",
                    ),
                    DirectedBeat(
                        "LifestyleCreepVisualizer",
                        "Lifestyle catches up",
                        "subtle",
                        "spending rises too",
                        data={**data, "active_phase": "expenses_follow"},
                        beat_phase="expenses_follow",
                    ),
                    DirectedBeat(
                        "LifestyleCreepVisualizer",
                        "Savings gap stays flat",
                        "hero",
                        "raise absorbed",
                        data={**data, "active_phase": "gap_revealed"},
                        beat_phase="gap_revealed",
                    ),
                ],
                director_input.narration_text,
            ),
        )

    def _money_mechanism_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        text = director_input.narration_text
        flow_data = self._money_flow_data(director_input)
        direction = SceneDirection("neutral", "urgency" if concept_type != "emergency_fund" else "relief", director_input.section_position, "warning")
        concept_name = self._display_concept_name(concept_type)
        if not flow_data:
            return self._qualitative_money_plan(director_input, concept_type, direction, concept_name)
        intro_data = {**flow_data, "active_phase": "intro"}
        drain_data = {**flow_data, "active_phase": "drain"}
        remainder_data = {**flow_data, "active_phase": "remainder"}
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern="MoneyFlowDiagram",
            data=flow_data,
            direction=direction,
            theme=THEME,
            beats=self._contextualize_beats([
                DirectedBeat(
                    "MoneyFlowDiagram",
                    flow_data["source"]["value"],
                    "normal",
                    flow_data["source"]["label"],
                    data=intro_data,
                    beat_phase="intro",
                ),
                DirectedBeat("MoneyFlowDiagram", self._money_flow_title(concept_type), "subtle", data=drain_data, beat_phase="drain"),
                DirectedBeat(
                    "MoneyFlowDiagram",
                    self._money_mechanism_punch(flow_data, concept_type),
                    "hero",
                    data=remainder_data,
                    beat_phase="remainder",
                ),
            ], text),
        )

    def _emi_stack_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        data = self._emi_stack_data(director_input)
        direction = SceneDirection("calm", "pressure", director_input.section_position, "danger")
        concept_name = self._display_concept_name(concept_type)
        first_data = {**data, "active_phase": "first_emi"}
        stacking_data = {**data, "active_phase": "stacking"}
        pressure_data = {**data, "active_phase": "pressure"}
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern="EMIStackVisualizer",
            data=data,
            direction=direction,
            theme=THEME,
            beats=self._contextualize_beats(
                [
                    DirectedBeat("EMIStackVisualizer", "One EMI looks harmless", "normal", data=first_data, beat_phase="first_emi"),
                    DirectedBeat("EMIStackVisualizer", "Fixed payments stack", "subtle", data=stacking_data, beat_phase="stacking"),
                    DirectedBeat("EMIStackVisualizer", f"{data['remaining']['value']} left after EMIs", "hero", data=pressure_data, beat_phase="pressure"),
                ],
                director_input.narration_text,
            ),
        )

    def _small_leaks_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        direction = SceneDirection("unaware", "aware", director_input.section_position, "warning")
        concept_name = self._display_concept_name(concept_type)
        data = self._small_leaks_data(director_input)
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern="SmallLeaksAccumulator",
            data=data,
            direction=direction,
            theme=THEME,
            beats=self._contextualize_beats(
                [
                    DirectedBeat("SmallLeaksAccumulator", "One small spend", "normal", data={**data, "active_phase": "first_leak"}, beat_phase="first_leak"),
                    DirectedBeat("SmallLeaksAccumulator", "Small leaks repeat", "subtle", data={**data, "active_phase": "repeat"}, beat_phase="repeat"),
                    DirectedBeat("SmallLeaksAccumulator", f"{self._format_rupee(data['monthly_loss'])} monthly pressure", "hero", data={**data, "active_phase": "month_end"}, beat_phase="month_end"),
                ],
                director_input.narration_text,
            ),
        )
