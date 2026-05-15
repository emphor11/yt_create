from __future__ import annotations

from typing import Any

from .director_types import THEME, DirectedBeat, DirectedPlan, SceneDirection, VisualDirectorInput


class VisualDirectorRiskPlansMixin:
    def _comparison_mechanism_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        data = self._comparison_data(director_input, concept_type)
        direction = SceneDirection("confusion", "clarity", director_input.section_position, "neutral")
        concept_name = self._display_concept_name(concept_type)
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern="SplitComparison",
            data=data,
            direction=direction,
            theme=THEME,
            beats=self._contextualize_beats([
                DirectedBeat("StatCard", data["left"]["label"], "normal", "path A", {"primary_value": data["left"]["label"], "label": "path A", "color": "orange"}),
                DirectedBeat("SplitComparison", concept_name, "subtle", data=data),
                DirectedBeat("HighlightText", data["punch"], "hero", data={"primary_value": data["punch"], "label": concept_name, "color": data.get("accent", "teal")}),
            ], director_input.narration_text),
        )

    def _diversification_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        data = self._diversification_data()
        direction = SceneDirection("concentrated", "systematic", director_input.section_position, "positive")
        concept_name = self._display_concept_name(concept_type)
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern="PortfolioDiversificationVisualizer",
            data=data,
            direction=direction,
            theme=THEME,
            beats=self._contextualize_beats(
                [
                    DirectedBeat("PortfolioDiversificationVisualizer", "One bet decides everything", "normal", data={**data, "active_phase": "concentrated"}, beat_phase="concentrated"),
                    DirectedBeat("PortfolioDiversificationVisualizer", "Risk spreads across assets", "subtle", data={**data, "active_phase": "spread"}, beat_phase="spread"),
                    DirectedBeat("PortfolioDiversificationVisualizer", "One fall does not break all", "hero", data={**data, "active_phase": "impact"}, beat_phase="impact"),
                ],
                director_input.narration_text,
            ),
        )

    def _risk_return_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        data = self._risk_return_data(director_input)
        direction = SceneDirection("confusion", "clarity", director_input.section_position, "neutral")
        beats = self._contextualize_beats(
            [
                DirectedBeat(
                    "RiskReturnVisualizer",
                    "FD feels calm",
                    "normal",
                    "low risk baseline",
                    data={**data, "active_phase": "fd_anchor"},
                    beat_phase="fd_anchor",
                ),
                DirectedBeat(
                    "RiskReturnVisualizer",
                    "Equity can grow faster",
                    "subtle",
                    "upside",
                    data={**data, "active_phase": "equity_growth"},
                    beat_phase="equity_growth",
                ),
                DirectedBeat(
                    "RiskReturnVisualizer",
                    "Volatility is the price",
                    "subtle",
                    "risk",
                    data={**data, "active_phase": "volatility_price"},
                    beat_phase="volatility_price",
                ),
                DirectedBeat(
                    "RiskReturnVisualizer",
                    "Choose risk you can stay with",
                    "hero",
                    "decision",
                    data={**data, "active_phase": "chosen_risk"},
                    beat_phase="chosen_risk",
                ),
            ],
            director_input.narration_text,
        )
        return DirectedPlan(
            concept_type=concept_type,
            concept_name="Risk vs Return",
            pattern="RiskReturnVisualizer",
            data=data,
            beats=beats,
            direction=direction,
            theme=THEME,
        )

    def _emergency_fund_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        data = self._emergency_fund_data(director_input)
        direction = SceneDirection("fragile", "relief", director_input.section_position, "positive")
        beats = self._contextualize_beats(
            [
                DirectedBeat(
                    "EmergencyFundVisualizer",
                    "Cash buffer waits",
                    "normal",
                    "boring protection",
                    data={**data, "active_phase": "boring_buffer"},
                    beat_phase="boring_buffer",
                ),
                DirectedBeat(
                    "EmergencyFundVisualizer",
                    "Life shock hits",
                    "subtle",
                    "unexpected bill",
                    data={**data, "active_phase": "shock_focus"},
                    beat_phase="shock_focus",
                ),
                DirectedBeat(
                    "EmergencyFundVisualizer",
                    "Buffer blocks debt",
                    "subtle",
                    "no credit card spiral",
                    data={**data, "active_phase": "debt_prevention"},
                    beat_phase="debt_prevention",
                ),
                DirectedBeat(
                    "EmergencyFundVisualizer",
                    "The plan survives",
                    "hero",
                    "breathing room",
                    data={**data, "active_phase": "plan_survives"},
                    beat_phase="plan_survives",
                ),
            ],
            director_input.narration_text,
        )
        return DirectedPlan(
            concept_type=concept_type,
            concept_name="Emergency Fund",
            pattern="EmergencyFundVisualizer",
            data=data,
            beats=beats,
            direction=direction,
            theme=THEME,
        )

    def _speculation_risk_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        direction = SceneDirection("overconfidence", "alarm", director_input.section_position, "danger")
        concept_name = self._display_concept_name(concept_type)
        data = self._fomo_crash_data()
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern="FOMOPriceCrashVisualizer",
            data=data,
            direction=direction,
            theme=THEME,
            beats=self._contextualize_beats(
                [
                    DirectedBeat("FOMOPriceCrashVisualizer", "Hype runs first", "normal", data={**data, "active_phase": "rise"}, beat_phase="rise"),
                    DirectedBeat("FOMOPriceCrashVisualizer", "The crash arrives", "subtle", data={**data, "active_phase": "crash"}, beat_phase="crash"),
                    DirectedBeat("FOMOPriceCrashVisualizer", "Do not buy what you cannot explain", "hero", data={**data, "active_phase": "loss"}, beat_phase="loss"),
                ],
                director_input.narration_text,
            ),
        )
