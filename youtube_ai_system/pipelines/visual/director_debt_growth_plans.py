from __future__ import annotations

from typing import Any

from .director_types import THEME, DirectedBeat, DirectedPlan, SceneDirection, VisualDirectorInput


class VisualDirectorDebtGrowthPlansMixin:
    def _debt_trap_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        debt_data = self._debt_spiral_data(director_input.narration_text, director_input)
        direction = SceneDirection("false_security", "urgency", director_input.section_position, "danger")
        if debt_data:
            minimum = debt_data.get("minimum_payment")
            steps = [
                {"label": "Balance", "value": debt_data["principal"]["value"]},
                {"label": "Monthly interest", "value": self._format_rupee(debt_data["monthly_interest"]), "operation": "+"},
            ]
            if minimum is not None:
                steps.append({"label": "Minimum payment", "value": self._format_rupee(minimum), "operation": "-"})
            principal_data = {**debt_data, "active_phase": "principal", "steps": steps}
            spiral_data = {**debt_data, "active_phase": "spiral", "steps": steps}
            consequence_data = {**debt_data, "active_phase": "consequence", "steps": steps}
            return DirectedPlan(
                concept_type=concept_type,
                concept_name="Debt Trap",
                pattern="DebtSpiralVisualizer",
                data=debt_data,
                direction=direction,
                theme=THEME,
                beats=self._contextualize_beats([
                    DirectedBeat("DebtSpiralVisualizer", debt_data["principal"]["value"], "normal", "credit card balance", data=principal_data, beat_phase="principal"),
                    DirectedBeat("DebtSpiralVisualizer", "Interest beats payment", "subtle", data=spiral_data, beat_phase="spiral"),
                    DirectedBeat(
                        "DebtSpiralVisualizer",
                        f"{self._format_rupee(debt_data['month_12_balance'])} after 12 months",
                        "hero",
                        "debt grew despite payments",
                        data=consequence_data,
                        beat_phase="consequence",
                    ),
                ], director_input.narration_text),
            )
        if self._has_finance_numbers(director_input):
            return self._fallback_plan(
                director_input,
                concept_type,
                direction,
                "StatCard",
                "Debt Trap",
                "insufficient data for DebtSpiralVisualizer",
            )
        if "emi" in director_input.narration_text.lower():
            return self._emi_stack_plan(director_input, "emi_pressure")
        return self._qualitative_debt_plan(director_input, concept_type, direction, "Debt Trap")

    def _sip_growth_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        sip_data = self._sip_growth_data(director_input.narration_text, director_input)
        if not sip_data:
            sip_data = self._inferred_sip_growth_data(director_input)
        direction = SceneDirection("confusion", "confidence", director_input.section_position, "positive")
        contribution_data = {**sip_data, "active_phase": "contribution"}
        growth_data = {**sip_data, "active_phase": "growth"}
        corpus_data = {**sip_data, "active_phase": "corpus"}
        return DirectedPlan(
            concept_type=concept_type,
            concept_name="SIP Growth",
            pattern="SIPGrowthEngine",
            data=sip_data,
            direction=direction,
            theme=THEME,
            beats=self._contextualize_beats([
                DirectedBeat("SIPGrowthEngine", sip_data["monthly_sip"]["value"], "normal", "monthly SIP", data=contribution_data, beat_phase="contribution"),
                DirectedBeat("SIPGrowthEngine", "Compounding engine", "subtle", data=growth_data, beat_phase="growth"),
                DirectedBeat(
                    "SIPGrowthEngine",
                    self._format_rupee(sip_data["final_corpus"]),
                    "hero",
                    f"{sip_data['awe_ratio']}x return",
                    data=corpus_data,
                    beat_phase="corpus",
                ),
            ], director_input.narration_text),
        )

    def _loan_pressure_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        debt_data = self._debt_spiral_data(director_input.narration_text, director_input)
        direction = SceneDirection("neutral", "urgency", director_input.section_position, "danger")
        concept_name = self._display_concept_name(concept_type)
        if not debt_data:
            if concept_type != "emi_pressure" and self._has_finance_numbers(director_input):
                return self._fallback_plan(director_input, concept_type, direction, "StatCard", concept_name, "insufficient data for loan pressure")
            return self._qualitative_debt_plan(director_input, concept_type, direction, concept_name)
        steps = [
            {"label": "Loan", "value": debt_data["principal"]["value"]},
            {"label": "Rate", "value": f"{debt_data['annual_interest_rate']:g}%", "operation": "+"},
            {"label": "Month 12", "value": self._format_rupee(debt_data["month_12_balance"]), "operation": "="},
        ]
        principal_data = {**debt_data, "active_phase": "principal", "steps": steps}
        spiral_data = {**debt_data, "active_phase": "spiral", "steps": steps}
        consequence_data = {**debt_data, "active_phase": "consequence", "steps": steps}
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern="DebtSpiralVisualizer",
            data=debt_data,
            direction=direction,
            theme=THEME,
            beats=self._contextualize_beats([
                DirectedBeat("DebtSpiralVisualizer", debt_data["principal"]["value"], "normal", "loan balance", data=principal_data, beat_phase="principal"),
                DirectedBeat("DebtSpiralVisualizer", "Interest cost", "subtle", data=spiral_data, beat_phase="spiral"),
                DirectedBeat("DebtSpiralVisualizer", "Interest pressure", "hero", data=consequence_data, beat_phase="consequence"),
            ], director_input.narration_text),
        )

    def _growth_mechanism_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        direction = SceneDirection("confusion", "confidence", director_input.section_position, "positive")
        concept_name = self._display_concept_name(concept_type)
        sip_data = self._sip_growth_data(director_input.narration_text, director_input)
        if sip_data is None:
            sip_data = self._inferred_sip_growth_data(director_input)
        contribution_data = {**sip_data, "active_phase": "contribution"}
        growth_data = {**sip_data, "active_phase": "growth"}
        corpus_data = {**sip_data, "active_phase": "corpus"}
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern="SIPGrowthEngine",
            data=sip_data,
            direction=direction,
            theme=THEME,
            beats=self._contextualize_beats([
                DirectedBeat("SIPGrowthEngine", sip_data["monthly_sip"]["value"], "normal", "monthly investment", data=contribution_data, beat_phase="contribution"),
                DirectedBeat("SIPGrowthEngine", "Growth over time", "subtle", data=growth_data, beat_phase="growth"),
                DirectedBeat("SIPGrowthEngine", f"{sip_data['awe_ratio']}x gap", "hero", "corpus vs invested", data=corpus_data, beat_phase="corpus"),
            ], director_input.narration_text),
        )

    def _inflation_return_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        data = self._inflation_return_data(director_input)
        direction = SceneDirection("false_security", "alarm", director_input.section_position, "danger")
        concept_name = self._display_concept_name(concept_type)
        start = data["start_value"]
        end = data["real_value"]
        rate = data["rate_label"]
        final_text = f"{end['value']} buying power" if str(end["value"]).startswith("₹") else str(end["value"])
        final_label = "future buying power" if str(end["value"]).startswith("₹") else concept_name
        visual_data = {
            "start": start["value"],
            "end": end["value"],
            "rate": rate,
            "years": data.get("years"),
            "inflation_rate": data.get("inflation_rate"),
            "curve": "down",
            "visual_type": "value_decay",
            "items": self._inflation_items(start["amount"], end["amount"]),
        }
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern="InflationErosionVisualizer",
            data=visual_data,
            direction=direction,
            theme=THEME,
            beats=self._contextualize_beats([
                DirectedBeat("InflationErosionVisualizer", start["value"], "normal", "today", data={**visual_data, "active_phase": "today"}, beat_phase="today"),
                DirectedBeat("InflationErosionVisualizer", "Purchasing power falls", "subtle", data={**visual_data, "active_phase": "erosion"}, beat_phase="erosion"),
                DirectedBeat("InflationErosionVisualizer", final_text, "hero", final_label, data={**visual_data, "active_phase": "future"}, beat_phase="future"),
            ], director_input.narration_text),
        )
