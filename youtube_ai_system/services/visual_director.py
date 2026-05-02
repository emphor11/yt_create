from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any


THEME = {
    "background": "#0A0A14",
    "surface": "#12121F",
    "text_primary": "#FFFFFF",
    "text_secondary": "rgba(255,255,255,0.6)",
    "accent_positive": "#2EC4B6",
    "accent_warning": "#FF9F1C",
    "accent_danger": "#E63946",
    "accent_neutral": "#4361EE",
}


@dataclass(frozen=True)
class VisualDirectorInput:
    concept_type: str
    concept_name: str
    primary_entity: str
    action: str
    start_value: str | None
    end_value: str | None
    percentage: float | None
    time_period: str | None
    confidence: float
    narration_text: str
    idea_type: str
    has_numbers: bool
    section_position: str
    preceding_concept_type: str | None


@dataclass(frozen=True)
class DirectedBeat:
    component: str
    text: str
    emphasis: str = "normal"
    subtext: str | None = None
    data: dict[str, Any] | None = None
    props: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "component": self.component,
            "text": self.text,
            "emphasis": self.emphasis,
        }
        if self.subtext:
            payload["subtext"] = self.subtext
        if self.data is not None:
            payload["data"] = self.data
        if self.props is not None:
            payload["props"] = self.props
        return payload


@dataclass(frozen=True)
class SceneDirection:
    opening: str
    closing: str
    scene_position: str
    accent: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "emotional_arc": {"opening": self.opening, "closing": self.closing},
            "scene_position": self.scene_position,
            "accent": self.accent,
        }


@dataclass(frozen=True)
class DirectedPlan:
    concept_type: str
    concept_name: str
    pattern: str
    data: dict[str, Any]
    beats: list[DirectedBeat]
    direction: SceneDirection
    theme: dict[str, str]
    fallback_reason: str | None = None

    def is_valid(self) -> bool:
        return len(self.beats) >= 2 and all(beat.component and beat.text for beat in self.beats)

    def to_visual_plan_item(self) -> dict[str, Any]:
        return {
            "concept": {"concept": self.concept_name, "type": self.concept_type},
            "visual": {"pattern": self.pattern, "data": self.data},
            "beats": {"beats": [beat.to_dict() for beat in self.beats]},
        }


class VisualDirector:
    """Deterministic finance-specific visual direction for Remotion scenes."""

    CATEGORY_ESTIMATES = {
        "emi": 0.35,
        "loan": 0.35,
        "rent": 0.25,
        "food": 0.16,
        "groceries": 0.16,
        "lifestyle": 0.18,
        "shopping": 0.14,
        "subscription": 0.04,
        "subscriptions": 0.04,
    }

    def direct(self, director_input: VisualDirectorInput) -> DirectedPlan:
        concept_type = self._normalized_concept_type(director_input)
        if concept_type == "salary_drain":
            return self._salary_drain_plan(director_input, concept_type)
        if concept_type in {"lifestyle_inflation", "expense_leakage", "budgeting", "savings_rate", "emergency_fund"}:
            return self._money_mechanism_plan(director_input, concept_type)
        if concept_type == "debt_trap":
            return self._debt_trap_plan(director_input, concept_type)
        if concept_type in {"emi_pressure", "loan_cost"}:
            return self._loan_pressure_plan(director_input, concept_type)
        if concept_type == "sip_growth":
            return self._sip_growth_plan(director_input, concept_type)
        if concept_type in {"compounding", "net_worth_growth"}:
            return self._growth_mechanism_plan(director_input, concept_type)
        if concept_type in {"inflation_erosion", "inflation_loss", "real_return", "fd_vs_inflation"}:
            return self._inflation_return_plan(director_input, concept_type)
        if concept_type in {"opportunity_cost", "comparison_timeline", "risk_return", "diversification", "tax_saving"}:
            return self._comparison_mechanism_plan(director_input, concept_type)
        return self._generic_plan(director_input, concept_type)

    def _salary_drain_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        flow_data = self._money_flow_data(director_input.narration_text)
        direction = SceneDirection("comfort", "anxiety", director_input.section_position, "danger")
        if flow_data:
            remainder = flow_data["remainder"]
            return DirectedPlan(
                concept_type=concept_type,
                concept_name="Salary Drain",
                pattern="MoneyFlowDiagram",
                data=flow_data,
                direction=direction,
                theme=THEME,
                beats=[
                    DirectedBeat(
                        "StatCard",
                        flow_data["source"]["value"],
                        "normal",
                        flow_data["source"]["label"],
                        {"primary_value": flow_data["source"]["value"], "label": flow_data["source"]["label"], "color": "white"},
                    ),
                    DirectedBeat("MoneyFlowDiagram", "Where salary goes", "subtle", data=flow_data),
                    DirectedBeat(
                        "HighlightText",
                        f"{remainder['value']} left",
                        "hero",
                        "danger zone" if remainder["is_dangerous"] else "left over",
                        {"primary_value": remainder["value"], "label": "left over", "color": "red" if remainder["is_dangerous"] else "orange"},
                    ),
                ],
            )
        return self._fallback_plan(
            director_input,
            concept_type,
            direction,
            "StatCard",
            "Salary Drain",
            "insufficient data for MoneyFlowDiagram",
        )

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
            return DirectedPlan(
                concept_type=concept_type,
                concept_name="Debt Trap",
                pattern="DebtSpiralVisualizer",
                data=debt_data,
                direction=direction,
                theme=THEME,
                beats=[
                    DirectedBeat("StatCard", debt_data["principal"]["value"], "normal", "credit card balance", {"label": "credit card balance"}),
                    DirectedBeat("CalculationStrip", "Interest beats payment", "subtle", data={"steps": steps}),
                    DirectedBeat("DebtSpiralVisualizer", "Debt keeps growing", "hero", data=debt_data),
                ],
            )
        return self._fallback_plan(
            director_input,
            concept_type,
            direction,
            "StatCard",
            "Debt Trap",
            "insufficient data for DebtSpiralVisualizer",
        )

    def _sip_growth_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        sip_data = self._sip_growth_data(director_input.narration_text, director_input)
        direction = SceneDirection("confusion", "confidence", director_input.section_position, "positive")
        if sip_data:
            return DirectedPlan(
                concept_type=concept_type,
                concept_name="SIP Growth",
                pattern="SIPGrowthEngine",
                data=sip_data,
                direction=direction,
                theme=THEME,
                beats=[
                    DirectedBeat("StatCard", sip_data["monthly_sip"]["value"], "normal", "monthly SIP", {"label": "monthly SIP"}),
                    DirectedBeat("SIPGrowthEngine", "Compounding engine", "subtle", data=sip_data),
                    DirectedBeat(
                        "SplitComparison",
                        "Invested vs corpus",
                        "hero",
                        data={
                            "left": {"label": "Invested", "value": self._format_rupee(sip_data["total_invested"])},
                            "right": {"label": "Corpus", "value": self._format_rupee(sip_data["final_corpus"])},
                        },
                    ),
                ],
            )
        return self._fallback_plan(
            director_input,
            concept_type,
            direction,
            "StatCard",
            "SIP Growth",
            "insufficient data for SIPGrowthEngine",
        )

    def _money_mechanism_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        text = director_input.narration_text
        flow_data = self._money_flow_data(text) or self._inferred_money_flow_data(text, concept_type)
        direction = SceneDirection("neutral", "urgency" if concept_type != "emergency_fund" else "relief", director_input.section_position, "warning")
        concept_name = self._display_concept_name(concept_type)
        if not flow_data:
            return self._fallback_plan(director_input, concept_type, direction, "StatCard", concept_name, "insufficient data for money mechanism")
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern="MoneyFlowDiagram",
            data=flow_data,
            direction=direction,
            theme=THEME,
            beats=[
                DirectedBeat(
                    "StatCard",
                    flow_data["source"]["value"],
                    "normal",
                    flow_data["source"]["label"],
                    {"primary_value": flow_data["source"]["value"], "label": flow_data["source"]["label"], "color": "white"},
                ),
                DirectedBeat("MoneyFlowDiagram", self._money_flow_title(concept_type), "subtle", data=flow_data),
                DirectedBeat(
                    "HighlightText",
                    self._money_mechanism_punch(flow_data, concept_type),
                    "hero",
                    data={"primary_value": self._money_mechanism_punch(flow_data, concept_type), "label": concept_name, "color": "teal" if concept_type == "emergency_fund" else "orange"},
                ),
            ],
        )

    def _loan_pressure_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        debt_data = self._debt_spiral_data(director_input.narration_text, director_input)
        direction = SceneDirection("neutral", "urgency", director_input.section_position, "danger")
        concept_name = self._display_concept_name(concept_type)
        if not debt_data:
            return self._fallback_plan(director_input, concept_type, direction, "StatCard", concept_name, "insufficient data for loan pressure")
        steps = [
            {"label": "Loan", "value": debt_data["principal"]["value"]},
            {"label": "Rate", "value": f"{debt_data['annual_interest_rate']:g}%", "operation": "+"},
            {"label": "Month 12", "value": self._format_rupee(debt_data["month_12_balance"]), "operation": "="},
        ]
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern="DebtSpiralVisualizer",
            data=debt_data,
            direction=direction,
            theme=THEME,
            beats=[
                DirectedBeat("StatCard", debt_data["principal"]["value"], "normal", "loan balance", {"primary_value": debt_data["principal"]["value"], "label": "loan balance", "color": "white"}),
                DirectedBeat("CalculationStrip", "Interest cost", "subtle", data={"steps": steps}),
                DirectedBeat("DebtSpiralVisualizer", "Interest pressure", "hero", data=debt_data),
            ],
        )

    def _growth_mechanism_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        sip_data = self._sip_growth_data(director_input.narration_text, director_input) or self._inferred_sip_growth_data(director_input)
        direction = SceneDirection("confusion", "confidence", director_input.section_position, "positive")
        concept_name = self._display_concept_name(concept_type)
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern="SIPGrowthEngine",
            data=sip_data,
            direction=direction,
            theme=THEME,
            beats=[
                DirectedBeat("StatCard", sip_data["monthly_sip"]["value"], "normal", "monthly investment", {"primary_value": sip_data["monthly_sip"]["value"], "label": "monthly investment", "color": "teal"}),
                DirectedBeat("SIPGrowthEngine", "Growth over time", "subtle", data=sip_data),
                DirectedBeat("HighlightText", f"{sip_data['awe_ratio']}x gap", "hero", data={"primary_value": f"{sip_data['awe_ratio']}x", "label": "corpus vs invested", "color": "teal"}),
            ],
        )

    def _inflation_return_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        data = self._inflation_return_data(director_input)
        direction = SceneDirection("false_security", "alarm", director_input.section_position, "danger")
        concept_name = self._display_concept_name(concept_type)
        start = data["start_value"]
        end = data["real_value"]
        rate = data["rate_label"]
        return DirectedPlan(
            concept_type=concept_type,
            concept_name=concept_name,
            pattern="GrowthChart",
            data={"start": start["value"], "end": end["value"], "rate": rate, "curve": "down", "visual_type": "value_decay"},
            direction=direction,
            theme=THEME,
            beats=[
                DirectedBeat("StatCard", start["value"], "normal", "today", {"primary_value": start["value"], "label": "today", "color": "white"}),
                DirectedBeat("GrowthChart", "Purchasing power falls", "subtle", data={"start": start["value"], "end": end["value"], "rate": rate, "curve": "down"}, props={"start": start["value"], "end": end["value"], "rate": rate, "curve": "down"}),
                DirectedBeat("HighlightText", f"{end['value']} buying power", "hero", data={"primary_value": end["value"], "label": "future buying power", "color": "red"}),
            ],
        )

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
            beats=[
                DirectedBeat("StatCard", data["left"]["label"], "normal", "path A", {"primary_value": data["left"]["label"], "label": "path A", "color": "orange"}),
                DirectedBeat("SplitComparison", concept_name, "subtle", data=data),
                DirectedBeat("HighlightText", data["punch"], "hero", data={"primary_value": data["punch"], "label": concept_name, "color": data.get("accent", "teal")}),
            ],
        )

    def _generic_plan(self, director_input: VisualDirectorInput, concept_type: str) -> DirectedPlan:
        direction = SceneDirection("neutral", "clarity", director_input.section_position, "neutral")
        title = director_input.concept_name or "Money Change"
        return self._fallback_plan(director_input, concept_type, direction, "ConceptCard", title, "generic director fallback")

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

    def _money_flow_data(self, text: str) -> dict[str, Any] | None:
        amounts = self._money_mentions(text)
        source = self._source_amount(amounts, text)
        if not source:
            return None
        source_amount = float(source["amount"])
        explicit_flows = self._explicit_flows(text, source)
        percentage_flows = self._percentage_flows(text, source_amount, {flow["label"].lower() for flow in explicit_flows})
        estimate_flows = self._estimated_flows(text, source_amount, {flow["label"].lower() for flow in explicit_flows + percentage_flows})
        flows = explicit_flows + percentage_flows + estimate_flows
        if not flows:
            return None
        flows = sorted(flows, key=lambda flow: flow["amount"], reverse=True)
        flow_total = sum(float(flow["amount"]) for flow in flows)
        remainder_amount = self._remainder_amount(amounts, text, source, flow_total)
        if remainder_amount is None:
            remainder_amount = max(source_amount - flow_total, 0.0)
        if flow_total + remainder_amount > source_amount * 1.05:
            scale = max((source_amount - remainder_amount) / flow_total, 0.0) if flow_total else 1.0
            flows = [{**flow, "amount": round(float(flow["amount"]) * scale, 2), "value": self._format_rupee(float(flow["amount"]) * scale)} for flow in flows]
        elif remainder_amount > 0 and flow_total + remainder_amount < source_amount * 0.98:
            missing = source_amount - flow_total - remainder_amount
            if missing > 0:
                flows.append({"label": "Lifestyle", "value": self._format_rupee(missing), "amount": round(missing, 2), "color": "orange", "order": 0})
                flows = sorted(flows, key=lambda flow: flow["amount"], reverse=True)
        for order, flow in enumerate(flows, start=1):
            flow["order"] = order
            flow["color"] = "red" if order == 1 else "orange"
        ratio = remainder_amount / source_amount if source_amount else 0.0
        return {
            "source": {"label": source["label"] or "Salary", "value": self._format_rupee(source_amount), "amount": source_amount},
            "flows": flows,
            "remainder": {
                "value": self._format_rupee(remainder_amount),
                "amount": round(remainder_amount, 2),
                "is_dangerous": ratio < 0.10,
            },
        }

    def _debt_spiral_data(self, text: str, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        amounts = self._money_mentions(text)
        principal = self._principal_amount(amounts, text, director_input)
        rate = director_input.percentage if director_input.percentage is not None else self._first_percentage(text)
        if principal is None or rate is None:
            return None
        minimum = self._minimum_payment(amounts, text, principal)
        months = self._months_from_text(director_input.time_period or text) or 12
        if minimum is None and months is None:
            return None
        monthly_rate = float(rate) / 100.0 / 12.0
        balance = float(principal)
        balances = []
        payment = float(minimum or 0.0)
        for month in range(1, max(months, 12) + 1):
            interest = balance * monthly_rate
            principal_paid = payment - interest if payment else 0.0
            balance = max(balance + interest - payment, 0.0)
            balances.append(
                {
                    "month": month,
                    "balance": round(balance, 2),
                    "interest": round(interest, 2),
                    "principal_paid": round(principal_paid, 2),
                }
            )
        monthly_interest = float(principal) * monthly_rate
        return {
            "principal": {"value": self._format_rupee(principal), "amount": float(principal)},
            "annual_interest_rate": float(rate),
            "monthly_interest": round(monthly_interest, 2),
            "minimum_payment": round(payment, 2) if payment else None,
            "time_period_months": months,
            "balances": balances[:months],
            "month_12_balance": balances[11]["balance"],
            "is_trap": bool(payment and payment < monthly_interest),
        }

    def _sip_growth_data(self, text: str, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        amounts = self._money_mentions(text)
        monthly = self._sip_amount(amounts, text, director_input)
        rate = director_input.percentage if director_input.percentage is not None else self._first_percentage(text)
        years = self._years_from_text(director_input.time_period or text)
        if monthly is None or (rate is None and years is None):
            return None
        annual_rate = max(float(rate if rate is not None else 12.0), 1.0)
        duration_years = int(years or 20)
        months = duration_years * 12
        monthly_rate = annual_rate / 100.0 / 12.0
        if monthly_rate:
            final_corpus = float(monthly) * (((1 + monthly_rate) ** months - 1) / monthly_rate) * (1 + monthly_rate)
        else:
            final_corpus = float(monthly) * months
        total_invested = float(monthly) * months
        returns_earned = final_corpus - total_invested
        return {
            "monthly_sip": {"value": self._format_rupee(monthly), "amount": float(monthly)},
            "duration_years": duration_years,
            "annual_return_rate": annual_rate,
            "total_invested": round(total_invested, 2),
            "final_corpus": round(final_corpus, 2),
            "returns_earned": round(returns_earned, 2),
            "awe_ratio": round(final_corpus / total_invested, 2) if total_invested else 0.0,
        }

    def _normalized_concept_type(self, director_input: VisualDirectorInput) -> str:
        text = f"{director_input.concept_type} {director_input.concept_name} {director_input.narration_text}".lower()
        if "lifestyle inflation" in text or ("salary" in text and "expenses" in text and any(token in text for token in ("rise", "increase", "doubled", "luxury", "necessities"))):
            return "lifestyle_inflation"
        if "salary" in text and any(token in text for token in ("drain", "depletion", "disappear", "vanish", "left")):
            return "salary_drain"
        if "emi" in text and any(token in text for token in ("pressure", "burden", "loan", "interest")):
            return "emi_pressure"
        if any(token in text for token in ("debt trap", "credit card", "minimum payment", "minimum dues")):
            return "debt_trap"
        if "sip" in text or "compound" in text or "compounding" in text:
            return "sip_growth"
        if "inflation" in text and any(token in text for token in ("fd", "fixed deposit", "real return", "return")):
            return "fd_vs_inflation"
        if "inflation" in text or "purchasing power" in text or "buying power" in text:
            return "inflation_erosion"
        if "real return" in text or ("tax" in text and "return" in text):
            return "real_return"
        if "expense leakage" in text or "subscription" in text or "leak" in text:
            return "expense_leakage"
        if "emergency fund" in text or "cash buffer" in text:
            return "emergency_fund"
        if "opportunity cost" in text or "could have" in text or "instead" in text:
            return "opportunity_cost"
        if "risk" in text and "return" in text:
            return "risk_return"
        if "diversification" in text or "diversify" in text or "asset classes" in text:
            return "diversification"
        if "tax saving" in text or "tax" in text or "80c" in text:
            return "tax_saving"
        if "budget" in text or "allocate" in text:
            return "budgeting"
        if "savings rate" in text or ("save" in text and "income" in text):
            return "savings_rate"
        if "loan" in text and ("cost" in text or "interest" in text):
            return "loan_cost"
        if "net worth" in text or "wealth" in text:
            return "net_worth_growth"
        return str(director_input.concept_type or director_input.idea_type or "definition").strip() or "definition"

    def _display_concept_name(self, concept_type: str) -> str:
        return {
            "lifestyle_inflation": "Lifestyle Inflation",
            "expense_leakage": "Expense Leakage",
            "budgeting": "Budget Allocation",
            "savings_rate": "Savings Rate",
            "emergency_fund": "Emergency Fund",
            "emi_pressure": "EMI Pressure",
            "loan_cost": "Loan Cost",
            "compounding": "Compounding",
            "net_worth_growth": "Net Worth Growth",
            "inflation_erosion": "Inflation Erosion",
            "inflation_loss": "Inflation Loss",
            "real_return": "Real Return",
            "fd_vs_inflation": "FD vs Inflation",
            "opportunity_cost": "Opportunity Cost",
            "comparison_timeline": "Decision Timeline",
            "risk_return": "Risk vs Return",
            "diversification": "Diversification",
            "tax_saving": "Tax Saving",
        }.get(concept_type, concept_type.replace("_", " ").title())

    def _money_flow_title(self, concept_type: str) -> str:
        return {
            "lifestyle_inflation": "Where the raise went",
            "expense_leakage": "Where money leaks",
            "budgeting": "Budget split",
            "savings_rate": "Income allocation",
            "emergency_fund": "Safety buffer",
        }.get(concept_type, "Money movement")

    def _money_mechanism_punch(self, flow_data: dict[str, Any], concept_type: str) -> str:
        if concept_type == "emergency_fund":
            return f"{flow_data['remainder']['value']} buffer"
        if flow_data["remainder"]["is_dangerous"]:
            return f"{flow_data['remainder']['value']} left"
        return "The gap matters"

    def _inferred_money_flow_data(self, text: str, concept_type: str) -> dict[str, Any]:
        source_amount = self._parse_rupee(text) or (80000.0 if concept_type == "lifestyle_inflation" else 50000.0)
        if concept_type == "emergency_fund":
            flows = [
                {"label": "Rent + EMI", "amount": source_amount * 0.45},
                {"label": "Food", "amount": source_amount * 0.16},
                {"label": "Investments", "amount": source_amount * 0.12},
            ]
            remainder_amount = source_amount * 0.27
        elif concept_type in {"budgeting", "savings_rate"}:
            flows = [
                {"label": "Needs", "amount": source_amount * 0.5},
                {"label": "Wants", "amount": source_amount * 0.3},
                {"label": "Invest First", "amount": source_amount * 0.2},
            ]
            remainder_amount = source_amount * 0.2
        elif concept_type == "expense_leakage":
            flows = [
                {"label": "Subscriptions", "amount": source_amount * 0.06},
                {"label": "Food Apps", "amount": source_amount * 0.12},
                {"label": "Impulse Buys", "amount": source_amount * 0.14},
            ]
            remainder_amount = source_amount * 0.08
        else:
            flows = [
                {"label": "Old Lifestyle", "amount": source_amount * 0.35},
                {"label": "Upgrades", "amount": source_amount * 0.28},
                {"label": "Rent + EMI", "amount": source_amount * 0.24},
            ]
            remainder_amount = source_amount * 0.08
        flow_items = []
        for order, flow in enumerate(sorted(flows, key=lambda item: item["amount"], reverse=True), start=1):
            flow_items.append(
                {
                    "label": flow["label"],
                    "value": self._format_rupee(flow["amount"]),
                    "amount": round(flow["amount"], 2),
                    "color": "red" if order == 1 else ("teal" if "Invest" in flow["label"] else "orange"),
                    "order": order,
                }
            )
        return {
            "source": {"label": "Income", "value": self._format_rupee(source_amount), "amount": source_amount},
            "flows": flow_items,
            "remainder": {
                "value": self._format_rupee(remainder_amount),
                "amount": round(remainder_amount, 2),
                "is_dangerous": (remainder_amount / source_amount) < 0.10,
            },
        }

    def _inferred_sip_growth_data(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        monthly = self._parse_rupee(director_input.narration_text) or 5000.0
        rate = max(director_input.percentage or self._first_percentage(director_input.narration_text) or 12.0, 1.0)
        years = self._years_from_text(director_input.time_period or director_input.narration_text) or 20
        synthetic = VisualDirectorInput(
            **{
                **director_input.__dict__,
                "percentage": rate,
                "time_period": f"{years} years",
                "start_value": self._format_rupee(monthly),
                "narration_text": f"Invest {self._format_rupee(monthly)} per month at {rate}% for {years} years",
            }
        )
        return self._sip_growth_data(synthetic.narration_text, synthetic) or {
            "monthly_sip": {"value": self._format_rupee(monthly), "amount": monthly},
            "duration_years": years,
            "annual_return_rate": rate,
            "total_invested": monthly * 12 * years,
            "final_corpus": monthly * 12 * years,
            "returns_earned": 0,
            "awe_ratio": 1,
        }

    def _inflation_return_data(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        amount = self._parse_rupee(director_input.narration_text) or self._parse_rupee(director_input.start_value) or 100000.0
        rate = max(director_input.percentage or self._first_percentage(director_input.narration_text) or 7.0, 1.0)
        years = self._years_from_text(director_input.time_period or director_input.narration_text) or 10
        real_value = amount / ((1 + rate / 100.0) ** years)
        return {
            "start_value": {"value": self._format_rupee(amount), "amount": amount},
            "real_value": {"value": self._format_rupee(real_value), "amount": round(real_value, 2)},
            "inflation_rate": rate,
            "years": years,
            "rate_label": f"{rate:g}% for {years} years",
        }

    def _comparison_data(self, director_input: VisualDirectorInput, concept_type: str) -> dict[str, Any]:
        amount = self._parse_rupee(director_input.narration_text) or 5000.0
        if concept_type == "risk_return":
            return {"left": {"label": "Low Risk / Low Return", "value": "FD"}, "right": {"label": "Higher Risk / Higher Growth", "value": "Equity"}, "punch": "Risk buys upside", "accent": "teal"}
        if concept_type == "diversification":
            return {"left": {"label": "One bet", "value": "100%"}, "right": {"label": "Spread bets", "value": "safer mix"}, "punch": "Spread the risk", "accent": "teal"}
        if concept_type == "tax_saving":
            tax_saved = amount * 0.3
            return {"left": {"label": "Without planning", "value": self._format_rupee(amount)}, "right": {"label": "Tax saved", "value": self._format_rupee(tax_saved)}, "punch": f"{self._format_rupee(tax_saved)} saved", "accent": "teal"}
        if concept_type in {"opportunity_cost", "comparison_timeline"}:
            return {"left": {"label": "Spend today", "value": self._format_rupee(amount)}, "right": {"label": "Invest monthly", "value": self._format_rupee(amount)}, "punch": "Small choice compounds", "accent": "orange"}
        return {"left": {"label": "Path A", "value": "today"}, "right": {"label": "Path B", "value": "future"}, "punch": "Choose the better path", "accent": "teal"}

    def _money_mentions(self, text: str) -> list[dict[str, Any]]:
        pattern = re.compile(r"(?:₹\s*|Rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)\s*(lakh|lakhs|crore|crores|k)?", re.IGNORECASE)
        mentions: list[dict[str, Any]] = []
        for match in pattern.finditer(text):
            raw = match.group(0).strip()
            if text[match.end() : match.end() + 1] == "%":
                continue
            after_unit = text[match.end() : match.end() + 24].lower()
            if re.match(r"\s*(years?\s+old|months?\s+old|days?\s+ago|minutes?|seconds?|hours?)\b", after_unit):
                continue
            before_text = text[max(0, match.start() - 12) : match.start()].lower()
            if "₹" not in raw and not raw.lower().startswith("rs") and re.search(r"(?:day|year|years|month|months)\s*$", before_text):
                continue
            if not raw or not ("₹" in raw or re.search(r"\b(?:rs|emi|rent|salary|sip|payment|balance|food|left|invest)", self._window(text, match.start(), match.end()).lower())):
                continue
            amount = float(match.group(1).replace(",", ""))
            unit = (match.group(2) or "").lower()
            if unit.startswith("lakh"):
                amount *= 100000
            elif unit.startswith("crore"):
                amount *= 10000000
            elif unit == "k":
                amount *= 1000
            mentions.append(
                {
                    "value": self._format_rupee(amount),
                    "amount": amount,
                    "label": self._label_for_amount(text, match.start(), match.end()),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
        return mentions

    def _explicit_flows(self, text: str, source: dict[str, Any]) -> list[dict[str, Any]]:
        flows = []
        for item in self._money_mentions(text):
            if item is source or item["amount"] == source["amount"]:
                continue
            label = item["label"] or ""
            if label.lower() in {"left", "leftover", "remaining", "remainder", "salary", "income"}:
                continue
            if not label:
                label = self._nearest_category(text, int(item["start"]), int(item["end"]))
            if label:
                flows.append({"label": label, "value": self._format_rupee(item["amount"]), "amount": float(item["amount"]), "color": "orange", "order": 0})
        return self._dedupe_flows(flows)

    def _percentage_flows(self, text: str, source_amount: float, seen: set[str]) -> list[dict[str, Any]]:
        flows = []
        for match in re.finditer(r"(\d+(?:\.\d+)?)\s*%\s*(?:on|for|to|towards|in)?\s*([A-Za-z ]{0,24})", text, re.IGNORECASE):
            label = self._category_from_text(match.group(2)) or self._nearest_category(text, match.start(), match.end())
            if not label or label.lower() in seen:
                continue
            amount = source_amount * float(match.group(1)) / 100.0
            flows.append({"label": label, "value": self._format_rupee(amount), "amount": round(amount, 2), "color": "orange", "order": 0})
        return flows

    def _estimated_flows(self, text: str, source_amount: float, seen: set[str]) -> list[dict[str, Any]]:
        lowered = text.lower()
        flows = []
        for token, ratio in self.CATEGORY_ESTIMATES.items():
            label = self._label_from_category(token)
            if token in lowered and label.lower() not in seen:
                amount = source_amount * ratio
                flows.append({"label": label, "value": self._format_rupee(amount), "amount": round(amount, 2), "color": "orange", "order": 0})
        return flows[:3]

    def _source_amount(self, amounts: list[dict[str, Any]], text: str) -> dict[str, Any] | None:
        for item in amounts:
            label = str(item.get("label") or "").lower()
            if label in {"salary", "income"}:
                return item
        if "salary" in text.lower() or "income" in text.lower():
            return max(amounts, key=lambda item: float(item["amount"]), default=None)
        return amounts[0] if amounts else None

    def _principal_amount(self, amounts: list[dict[str, Any]], text: str, director_input: VisualDirectorInput) -> float | None:
        for item in amounts:
            label = str(item.get("label") or "").lower()
            if label in {"balance", "debt", "principal", "loan", "card balance", "credit card balance"}:
                return float(item["amount"])
        parsed = self._parse_rupee(director_input.start_value)
        if parsed is not None:
            return parsed
        return float(amounts[0]["amount"]) if amounts else None

    def _minimum_payment(self, amounts: list[dict[str, Any]], text: str, principal: float) -> float | None:
        for item in amounts:
            label = str(item.get("label") or "").lower()
            if "minimum" in label or "payment" in label:
                return float(item["amount"])
        smaller = [float(item["amount"]) for item in amounts if float(item["amount"]) < principal]
        return min(smaller) if smaller else None

    def _sip_amount(self, amounts: list[dict[str, Any]], text: str, director_input: VisualDirectorInput) -> float | None:
        for item in amounts:
            label = str(item.get("label") or "").lower()
            if "sip" in label or "monthly" in label or "invest" in label:
                return float(item["amount"])
        parsed = self._parse_rupee(director_input.start_value)
        if parsed is not None:
            return parsed
        return float(amounts[0]["amount"]) if amounts else None

    def _remainder_amount(self, amounts: list[dict[str, Any]], text: str, source: dict[str, Any], flow_total: float) -> float | None:
        for item in amounts:
            label = str(item.get("label") or "").lower()
            if label in {"left", "leftover", "remaining", "remainder"}:
                return float(item["amount"])
        match = re.search(r"only\s+(?:₹\s*|Rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)\s*(?:is\s+)?left", text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", ""))
        if flow_total:
            return max(float(source["amount"]) - flow_total, 0.0)
        return None

    def _label_for_amount(self, text: str, start: int, end: int) -> str:
        before = text[max(0, start - 24) : start].lower()
        after = text[end : min(len(text), end + 24)].lower()
        immediate_category = self._nearest_expense_category(before, after)
        if immediate_category:
            return immediate_category
        if "left" in after or "left" in before or "remaining" in after:
            return "left"
        if "salary" in before or "salary" in after:
            return "Salary"
        if "income" in before or "income" in after:
            return "Income"
        if "balance" in before or "balance" in after:
            return "Balance"
        if "payment" in before or "payment" in after:
            return "Minimum payment" if "minimum" in before or "minimum" in after else "Payment"
        window = self._window(text, start, end).lower()
        category = self._category_from_text(window)
        if category:
            return category
        return ""

    def _expense_category_from_text(self, text: str) -> str:
        lowered = text.lower()
        for token, label in (
            ("emi", "EMI"),
            ("rent", "Rent"),
            ("food", "Food"),
            ("groceries", "Groceries"),
            ("grocery", "Groceries"),
            ("lifestyle", "Lifestyle"),
            ("shopping", "Shopping"),
            ("subscription", "Subscriptions"),
        ):
            if token in lowered:
                return label
        return ""

    def _nearest_expense_category(self, before: str, after: str) -> str:
        candidates = (
            ("emi", "EMI"),
            ("rent", "Rent"),
            ("food", "Food"),
            ("groceries", "Groceries"),
            ("grocery", "Groceries"),
            ("lifestyle", "Lifestyle"),
            ("shopping", "Shopping"),
            ("subscription", "Subscriptions"),
        )
        best_before_label = ""
        best_before_distance = 10_000
        for token, label in candidates:
            before_index = before.rfind(token)
            if before_index >= 0:
                distance = len(before) - before_index
                if distance < best_before_distance:
                    best_before_label = label
                    best_before_distance = distance
        if best_before_label:
            return best_before_label

        best_label = ""
        best_distance = 10_000
        for token, label in candidates:
            after_index = after.find(token)
            if after_index >= 0 and after_index + 1 < best_distance:
                best_label = label
                best_distance = after_index + 1
        return best_label

    def _nearest_category(self, text: str, start: int, end: int) -> str:
        return self._category_from_text(self._window(text, start, end))

    def _category_from_text(self, text: str) -> str:
        lowered = text.lower()
        category_map = [
            ("emi", "EMI"),
            ("rent", "Rent"),
            ("food", "Food"),
            ("groceries", "Groceries"),
            ("grocery", "Groceries"),
            ("lifestyle", "Lifestyle"),
            ("shopping", "Shopping"),
            ("subscription", "Subscriptions"),
            ("salary", "Salary"),
            ("income", "Income"),
            ("sip", "SIP"),
            ("invest", "Investment"),
            ("minimum", "Minimum payment"),
            ("payment", "Payment"),
            ("principal", "Principal"),
            ("debt", "Debt"),
            ("loan", "Loan"),
            ("balance", "Balance"),
        ]
        for token, label in category_map:
            if token in lowered:
                return label
        return ""

    def _label_from_category(self, category: str) -> str:
        return self._category_from_text(category) or category.replace("_", " ").title()

    def _dedupe_flows(self, flows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: dict[str, dict[str, Any]] = {}
        for flow in flows:
            key = str(flow["label"]).lower()
            if key not in deduped or float(flow["amount"]) > float(deduped[key]["amount"]):
                deduped[key] = flow
        return list(deduped.values())

    def _first_percentage(self, text: str) -> float | None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        return float(match.group(1)) if match else None

    def _months_from_text(self, text: str) -> int | None:
        match = re.search(r"(\d+)\s*months?", str(text), re.IGNORECASE)
        if match:
            return int(match.group(1))
        years = self._years_from_text(text)
        return years * 12 if years else None

    def _years_from_text(self, text: str) -> int | None:
        match = re.search(r"(\d+)\s*years?", str(text), re.IGNORECASE)
        return int(match.group(1)) if match else None

    def _parse_rupee(self, value: str | None) -> float | None:
        if not value:
            return None
        match = re.search(r"(?:₹\s*|Rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)\s*(lakh|lakhs|crore|crores|k)?", value, re.IGNORECASE)
        if not match:
            return None
        amount = float(match.group(1).replace(",", ""))
        unit = (match.group(2) or "").lower()
        if unit.startswith("lakh"):
            amount *= 100000
        elif unit.startswith("crore"):
            amount *= 10000000
        elif unit == "k":
            amount *= 1000
        return amount

    def _format_rupee(self, amount: float | int) -> str:
        rounded = int(round(float(amount)))
        sign = "-" if rounded < 0 else ""
        digits = str(abs(rounded))
        if len(digits) <= 3:
            grouped = digits
        else:
            grouped = digits[-3:]
            digits = digits[:-3]
            while digits:
                grouped = digits[-2:] + "," + grouped
                digits = digits[:-2]
        return f"{sign}₹{grouped}"

    def _window(self, text: str, start: int, end: int) -> str:
        return text[max(0, start - 36) : min(len(text), end + 36)]

    def _short_phrase(self, text: str, fallback: str) -> str:
        words = [word.strip(" ,.-") for word in text.split() if word.strip(" ,.-")]
        return " ".join(words[:4]) or fallback


def visual_director_input_from_section(
    section: dict[str, Any],
    section_position: str,
    preceding_concept_type: str | None = None,
) -> VisualDirectorInput:
    finance_concept = dict(section.get("finance_concept") or {})
    concept = (section.get("concepts") or [{}])[0] if section.get("concepts") else {}
    return VisualDirectorInput(
        concept_type=str(finance_concept.get("concept_type") or concept.get("type") or section.get("idea_type") or "definition"),
        concept_name=str(finance_concept.get("concept_name") or concept.get("concept") or "Money Change"),
        primary_entity=str(finance_concept.get("primary_entity") or section.get("dominant_entity") or "money"),
        action=str(finance_concept.get("action") or ""),
        start_value=finance_concept.get("start_value"),
        end_value=finance_concept.get("end_value"),
        percentage=finance_concept.get("percentage"),
        time_period=finance_concept.get("time_period"),
        confidence=float(finance_concept.get("confidence") or 0.0),
        narration_text=str(section.get("text") or ""),
        idea_type=str(section.get("idea_type") or "emphasis"),
        has_numbers=bool(section.get("has_numbers")),
        section_position=section_position,
        preceding_concept_type=preceding_concept_type,
    )


def directed_plan_to_dict(plan: DirectedPlan) -> dict[str, Any]:
    payload = asdict(plan)
    payload["beats"] = [beat.to_dict() for beat in plan.beats]
    payload["direction"] = plan.direction.to_dict()
    return payload
