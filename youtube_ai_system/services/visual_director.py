from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import re
from typing import Any

from .financial_governance import first_fact, numeric_role_map


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
    visual_story: dict[str, Any] = field(default_factory=dict)
    story_state: dict[str, Any] = field(default_factory=dict)
    semantic_scene: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DirectedBeat:
    component: str
    text: str
    emphasis: str = "normal"
    subtext: str | None = None
    data: dict[str, Any] | None = None
    props: dict[str, Any] | None = None
    source_text: str | None = None
    sentence_index: int | None = None
    beat_phase: str = ""

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
        if self.source_text is not None:
            payload["source_text"] = self.source_text
        if self.sentence_index is not None:
            payload["sentence_index"] = self.sentence_index
        if self.beat_phase:
            payload["beat_phase"] = self.beat_phase
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
class CinematicIntent:
    visual_mode: str
    human_action: str
    metaphor: str
    overlay_text: str
    motion_treatment: str
    asset_query: str
    texture: str = "dark_documentary"

    def to_dict(self) -> dict[str, str]:
        return {
            "visual_mode": self.visual_mode,
            "human_action": self.human_action,
            "metaphor": self.metaphor,
            "overlay_text": self.overlay_text,
            "motion_treatment": self.motion_treatment,
            "asset_query": self.asset_query,
            "texture": self.texture,
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
    visual_mode: str = "finance_mechanism"
    cinematic_intent: dict[str, str] = field(default_factory=dict)

    def is_valid(self) -> bool:
        return len(self.beats) >= 2 and all(beat.component and beat.text for beat in self.beats)

    def to_visual_plan_item(self) -> dict[str, Any]:
        return {
            "concept": {"concept": self.concept_name, "type": self.concept_type},
            "visual": {
                "pattern": self.pattern,
                "data": self.data,
                "visual_mode": self.visual_mode,
                "cinematic_intent": self.cinematic_intent,
            },
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

    CINEMATIC_RECIPES = {
        "salary_drain": {
            "visual_mode": "layered_hybrid",
            "human_action": "person checking salary credit on phone",
            "metaphor": "salary drains into fixed expenses before the month starts",
            "motion_treatment": "notification_stack",
            "asset_query": "cinematic phone banking closeup",
            "texture": "dark_documentary",
        },
        "lifestyle_inflation": {
            "visual_mode": "layered_hybrid",
            "human_action": "young professional upgrading lifestyle after salary hike",
            "metaphor": "income rises while expenses rise with it and savings stay flat",
            "motion_treatment": "slow_push",
            "asset_query": "cinematic lifestyle shopping city",
            "texture": "dark_documentary",
        },
        "expense_leakage": {
            "visual_mode": "layered_hybrid",
            "human_action": "person scrolling payment apps and subscriptions",
            "metaphor": "small leaks repeat until the month-end balance breaks",
            "motion_treatment": "notification_stack",
            "asset_query": "cinematic phone payment closeup",
            "texture": "dark_documentary",
        },
        "emi_pressure": {
            "visual_mode": "layered_hybrid",
            "human_action": "person checking bank balance after auto debit",
            "metaphor": "multiple EMI notifications stack into one monthly leak",
            "motion_treatment": "notification_stack",
            "asset_query": "person checking phone stressed office",
            "texture": "dark_documentary",
        },
        "debt_trap": {
            "visual_mode": "layered_hybrid",
            "human_action": "person looking at credit card bill late at night",
            "metaphor": "minimum payment cannot outrun monthly interest",
            "motion_treatment": "dolly_zoom",
            "asset_query": "credit card payment closeup cinematic",
            "texture": "dark_documentary",
        },
        "inflation_erosion": {
            "visual_mode": "layered_hybrid",
            "human_action": "person comparing grocery bill at checkout",
            "metaphor": "same money buys a shrinking basket over time",
            "motion_treatment": "value_erosion",
            "asset_query": "grocery checkout closeup cinematic",
            "texture": "dark_documentary",
        },
        "sip_growth": {
            "visual_mode": "layered_hybrid",
            "human_action": "young professional reviewing investment dashboard",
            "metaphor": "small monthly contributions compound into a larger corpus",
            "motion_treatment": "slow_push",
            "asset_query": "young professional laptop evening",
            "texture": "clean_corporate",
        },
        "compounding": {
            "visual_mode": "object_metaphor",
            "human_action": "person watching long-term investment progress",
            "metaphor": "small units stack slowly before growth accelerates",
            "motion_treatment": "slow_push",
            "asset_query": "investment planning laptop closeup",
            "texture": "clean_corporate",
        },
        "risk_return": {
            "visual_mode": "layered_hybrid",
            "human_action": "professional walking through modern office district",
            "metaphor": "calm returns sit beside volatile upside",
            "motion_treatment": "match_cut",
            "asset_query": "city office walking slow motion",
            "texture": "clean_corporate",
        },
        "diversification": {
            "visual_mode": "layered_hybrid",
            "human_action": "person organizing investment plan on desk",
            "metaphor": "one fragile bet becomes a spread portfolio",
            "motion_treatment": "soft_dissolve",
            "asset_query": "modern desk investment planning",
            "texture": "clean_corporate",
        },
        "speculation_risk": {
            "visual_mode": "human_broll",
            "human_action": "person reacting to market price drop on phone",
            "metaphor": "hype turns into panic when price falls",
            "motion_treatment": "dolly_zoom",
            "asset_query": "stock market phone stress cinematic",
            "texture": "dark_documentary",
        },
        "emergency_fund": {
            "visual_mode": "layered_hybrid",
            "human_action": "person calmly handling unexpected bill",
            "metaphor": "cash buffer absorbs the shock before debt starts",
            "motion_treatment": "soft_dissolve",
            "asset_query": "person paying bill calm home",
            "texture": "clean_corporate",
        },
    }

    def direct(self, director_input: VisualDirectorInput) -> DirectedPlan:
        concept_type = self._normalized_concept_type(director_input)
        if concept_type == "salary_drain":
            return self._with_cinematic_intent(self._salary_drain_plan(director_input, concept_type), director_input)
        if concept_type == "lifestyle_inflation":
            return self._with_cinematic_intent(self._lifestyle_creep_plan(director_input, concept_type), director_input)
        if concept_type in {"expense_leakage", "subscription_leak"}:
            return self._with_cinematic_intent(self._small_leaks_plan(director_input, concept_type), director_input)
        if concept_type == "emergency_fund":
            return self._with_cinematic_intent(self._emergency_fund_plan(director_input, concept_type), director_input)
        if concept_type in {"budgeting", "savings_rate", "rent_burden", "tax_drain"}:
            return self._with_cinematic_intent(self._money_mechanism_plan(director_input, concept_type), director_input)
        if concept_type == "debt_trap":
            return self._with_cinematic_intent(self._debt_trap_plan(director_input, concept_type), director_input)
        if concept_type in {"emi_pressure", "emi_stack"}:
            return self._with_cinematic_intent(self._emi_stack_plan(director_input, concept_type), director_input)
        if concept_type in {"loan_cost"}:
            return self._with_cinematic_intent(self._loan_pressure_plan(director_input, concept_type), director_input)
        if concept_type == "sip_growth":
            return self._with_cinematic_intent(self._sip_growth_plan(director_input, concept_type), director_input)
        if concept_type in {"compounding", "net_worth_growth"}:
            return self._with_cinematic_intent(self._growth_mechanism_plan(director_input, concept_type), director_input)
        if concept_type == "recap_system":
            return self._with_cinematic_intent(self._recap_system_plan(director_input), director_input)
        if concept_type in {"inflation_erosion", "inflation_loss", "real_return", "fd_vs_inflation"}:
            return self._with_cinematic_intent(self._inflation_return_plan(director_input, concept_type), director_input)
        if concept_type in {"speculation_risk", "fomo_risk"}:
            return self._with_cinematic_intent(self._speculation_risk_plan(director_input, concept_type), director_input)
        if concept_type == "diversification":
            return self._with_cinematic_intent(self._diversification_plan(director_input, concept_type), director_input)
        if concept_type == "risk_return":
            return self._with_cinematic_intent(self._risk_return_plan(director_input, concept_type), director_input)
        if concept_type in {"opportunity_cost", "comparison_timeline", "tax_saving"}:
            return self._with_cinematic_intent(self._comparison_mechanism_plan(director_input, concept_type), director_input)
        return self._with_cinematic_intent(self._generic_plan(director_input, concept_type), director_input)

    def _with_cinematic_intent(self, plan: DirectedPlan, director_input: VisualDirectorInput) -> DirectedPlan:
        if plan.cinematic_intent:
            return plan
        intent = self._cinematic_intent(plan.concept_type, plan.concept_name, plan.data)
        intent_payload = self._intent_with_story_state(intent.to_dict(), director_input.story_state)
        beats = self._story_contextualized_beats(plan.beats, director_input.story_state)
        data = dict(plan.data)
        if director_input.story_state:
            data["story_state"] = dict(director_input.story_state)
        if director_input.visual_story:
            data["visual_story"] = dict(director_input.visual_story)
        return replace(plan, data=data, beats=beats, visual_mode=intent.visual_mode, cinematic_intent=intent_payload)

    def _intent_with_story_state(self, intent: dict[str, str], story_state: dict[str, Any]) -> dict[str, str]:
        if not story_state:
            return intent
        visual_answer = str(story_state.get("visual_answer") or "").strip()
        visual_question = str(story_state.get("visual_question") or "").strip()
        active_objects = story_state.get("active_objects") or []
        if visual_answer:
            intent["overlay_text"] = visual_answer
        if active_objects:
            intent["active_object"] = str(active_objects[0])
        if visual_question:
            intent["visual_question"] = visual_question
        intent["protagonist_state"] = str(story_state.get("protagonist_state") or "")
        intent["scene_role"] = str(story_state.get("scene_role") or "")
        return intent

    def _story_contextualized_beats(self, beats: list[DirectedBeat], story_state: dict[str, Any]) -> list[DirectedBeat]:
        if not story_state:
            return beats
        state_change = story_state.get("state_change") or {}
        money = state_change.get("money") if isinstance(state_change.get("money"), dict) else {}
        active_objects = story_state.get("active_objects") or []
        visual_answer = str(story_state.get("visual_answer") or "").strip()
        story_data = {
            "story_state": dict(story_state),
            "active_objects": list(active_objects),
            "money": dict(money),
        }
        if not beats:
            return beats
        updated: list[DirectedBeat] = []
        mechanism_components = {
            "MoneyFlowDiagram",
            "DebtSpiralVisualizer",
            "SIPGrowthEngine",
            "InflationErosionVisualizer",
            "LifestyleCreepVisualizer",
            "EMIStackVisualizer",
            "FOMOPriceCrashVisualizer",
            "PortfolioDiversificationVisualizer",
            "SmallLeaksAccumulator",
            "RiskReturnVisualizer",
            "EmergencyFundVisualizer",
            "OutroRecapVisualizer",
        }
        for index, beat in enumerate(beats):
            data = dict(beat.data or {})
            data.update(story_data)
            text = beat.text
            if index == 0 and money.get("from") and self._story_money_matches_beat(money.get("from"), beat):
                text = self._concept_label_for_amount(beat.component, str(money["from"]), active_objects)
            if index == len(beats) - 1 and visual_answer and beat.component not in mechanism_components:
                text = visual_answer
            subtext = beat.subtext
            updated.append(replace(beat, text=text, subtext=subtext, data=data))
        return updated

    def _story_money_matches_beat(self, money_value: Any, beat: DirectedBeat) -> bool:
        """Only let story-state money relabel a beat when that amount is in this beat's own source text."""
        money_amount = self._parse_rupee(str(money_value or ""))
        if money_amount is None:
            return False
        source_text = str(beat.source_text or beat.text or "")
        if not source_text.strip():
            return False
        for mention in self._money_mentions(source_text):
            try:
                if abs(float(mention.get("amount") or 0) - money_amount) < 100:
                    return True
            except (TypeError, ValueError):
                continue
        return False

    def _concept_label_for_amount(self, component: str, amount: str, active_objects: list[Any]) -> str:
        if "debt_pressure" in active_objects:
            return f"{amount} outstanding"
        if "sip_jar" in active_objects:
            return f"{amount} per month"
        if "inflation_basket" in active_objects:
            return f"{amount} today"
        if "portfolio_grid" in active_objects:
            return f"{amount} at risk"
        if "salary_balance" in active_objects or "phone_account" in active_objects:
            return f"{amount} salary in"
        labels = {
            "MoneyFlowDiagram": f"{amount} salary in",
            "DebtSpiralVisualizer": f"{amount} outstanding",
            "SIPGrowthEngine": f"{amount} per month",
            "GrowthChart": f"{amount} today",
            "CalculationStrip": f"{amount} in motion",
            "StatCard": f"{amount} in focus",
        }
        return labels.get(component, amount)

    def _cinematic_intent(self, concept_type: str, concept_name: str, data: dict[str, Any]) -> CinematicIntent:
        recipe_key = {
            "emi_stack": "emi_pressure",
            "loan_cost": "emi_pressure",
            "inflation_loss": "inflation_erosion",
            "real_return": "inflation_erosion",
            "fd_vs_inflation": "inflation_erosion",
            "fomo_risk": "speculation_risk",
            "tax_drain": "salary_drain",
            "tax_saving": "risk_return",
            "rent_burden": "salary_drain",
            "net_worth_growth": "compounding",
        }.get(concept_type, concept_type)
        recipe = dict(self.CINEMATIC_RECIPES.get(recipe_key) or {})
        if not recipe:
            recipe = {
                "visual_mode": "finance_mechanism",
                "human_action": "minimal human context behind the finance idea",
                "metaphor": f"{concept_name} becomes visible through a clean finance overlay",
                "motion_treatment": "slow_push",
                "asset_query": "cinematic finance office closeup",
                "texture": "clean_corporate",
            }
        overlay_text = self._cinematic_overlay_text(concept_type, concept_name, data)
        return CinematicIntent(
            visual_mode=str(recipe["visual_mode"]),
            human_action=str(recipe["human_action"]),
            metaphor=str(recipe["metaphor"]),
            overlay_text=overlay_text,
            motion_treatment=str(recipe["motion_treatment"]),
            asset_query=str(recipe["asset_query"]),
            texture=str(recipe.get("texture") or "dark_documentary"),
        )

    def _cinematic_overlay_text(self, concept_type: str, concept_name: str, data: dict[str, Any]) -> str:
        if concept_type in {"salary_drain", "rent_burden", "tax_drain"} and data.get("remainder"):
            remainder = data["remainder"]
            return f"{remainder.get('value')} left".strip()
        if concept_type in {"emi_pressure", "emi_stack"}:
            return "Small EMIs become one leak"
        if concept_type == "debt_trap":
            if data.get("minimum_payment") and data.get("monthly_interest"):
                return "Interest beats the payment"
            return "Debt keeps growing"
        if concept_type in {"inflation_erosion", "inflation_loss", "real_return", "fd_vs_inflation"}:
            end = data.get("end") or (data.get("real_value") or {}).get("value")
            return f"{end} buying power".strip() if end else "Same money. Less power."
        if concept_type == "sip_growth" and data.get("final_corpus"):
            return f"{data.get('awe_ratio')}x corpus gap"
        if concept_type in {"lifestyle_inflation", "expense_leakage"}:
            return "The leak is the system"
        if concept_type == "recap_system":
            return "Track. Protect. Compound."
        if concept_type == "risk_return":
            return "Risk buys upside"
        if concept_type == "diversification":
            return "Spread the risk"
        if concept_type == "speculation_risk":
            return "Hype is not a plan"
        if concept_type == "compounding":
            return "Time is doing the work"
        if concept_type in {"budgeting", "savings_rate"}:
            return "First 20% is the whole game"
        if concept_type == "net_worth_growth":
            return "Patience compounds quietly"
        if concept_type == "emergency_fund":
            return "The buffer buys breathing room"
        if concept_type == "rent_burden":
            remainder = data.get("remainder") or {}
            return f"{remainder.get('value', '')} left after rent".strip() or "Rent eats the month"
        if concept_type == "tax_saving":
            return "Plan now, keep more"
        if concept_type == "tax_drain":
            return "Tax eats what you don't plan"
        if concept_type == "opportunity_cost":
            return "Small choice compounds"
        return concept_name

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

    def _contextualize_beats(self, beats: list[DirectedBeat], narration_text: str) -> list[DirectedBeat]:
        sentences = self._sentences(narration_text)
        if not sentences:
            return beats
        if len(beats) == 1:
            return [replace(beats[0], source_text=sentences[0], sentence_index=0)]
        contextualized: list[DirectedBeat] = []
        last_sentence_index = max(len(sentences) - 1, 0)
        last_beat_index = max(len(beats) - 1, 1)
        for beat_index, beat in enumerate(beats):
            sentence_index = round((beat_index / last_beat_index) * last_sentence_index)
            sentence_index = max(0, min(sentence_index, last_sentence_index))
            contextualized.append(
                replace(beat, source_text=sentences[sentence_index], sentence_index=sentence_index)
            )
        return contextualized

    def _sentences(self, text: str) -> list[str]:
        parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]
        if parts:
            return parts
        stripped = text.strip()
        return [stripped] if stripped else []

    def _has_finance_numbers(self, director_input: VisualDirectorInput) -> bool:
        return bool(
            director_input.start_value
            or director_input.end_value
            or director_input.percentage is not None
            or self._semantic_entities(director_input)
            or self._money_mentions(director_input.narration_text)
            or self._first_percentage(director_input.narration_text) is not None
        )

    def _semantic_scene(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        semantic_scene = director_input.semantic_scene if isinstance(director_input.semantic_scene, dict) else {}
        return semantic_scene if semantic_scene.get("source") == "semantic_scene_contract_v1" else semantic_scene

    def _semantic_primary_concept_key(self, director_input: VisualDirectorInput) -> str:
        primary = (self._semantic_scene(director_input).get("primary_concept") or {})
        return str(primary.get("key") or "").strip().lower()

    def _semantic_entities(self, director_input: VisualDirectorInput) -> list[dict[str, Any]]:
        entities = self._semantic_scene(director_input).get("entities") or []
        return [dict(entity) for entity in entities if isinstance(entity, dict)]

    def _semantic_entities_by_role(self, director_input: VisualDirectorInput) -> dict[str, list[dict[str, Any]]]:
        by_role: dict[str, list[dict[str, Any]]] = {}
        for entity in self._semantic_entities(director_input):
            role = str(entity.get("role") or "").strip()
            if role:
                by_role.setdefault(role, []).append(entity)
        return by_role

    def _semantic_entity(self, director_input: VisualDirectorInput, *roles: str) -> dict[str, Any] | None:
        by_role = self._semantic_entities_by_role(director_input)
        for role in roles:
            values = by_role.get(role) or []
            if values:
                return values[0]
        return None

    def _semantic_money_amount(self, entity: dict[str, Any] | None) -> float | None:
        if not entity:
            return None
        try:
            value = float(entity.get("value"))
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def _semantic_money_point(self, entity: dict[str, Any] | None, fallback_label: str = "") -> dict[str, Any] | None:
        amount = self._semantic_money_amount(entity)
        if amount is None:
            return None
        return {
            "value": str(entity.get("display_value") or self._format_rupee(amount)),
            "amount": amount,
            "source_number_ids": [self._semantic_source_id(entity)] if self._semantic_source_id(entity) else [],
            "derived": bool((entity.get("attributes") or {}).get("derived", False)),
            "label": fallback_label or str(entity.get("label") or entity.get("role") or ""),
        }

    def _semantic_source_id(self, entity: dict[str, Any] | None) -> str:
        provenance = entity.get("provenance") if isinstance(entity, dict) else {}
        return str((provenance or {}).get("source_number_id") or "")

    def _semantic_first_money_amount(self, director_input: VisualDirectorInput) -> float | None:
        for entity in self._semantic_entities(director_input):
            if str(entity.get("kind") or "") == "money":
                amount = self._semantic_money_amount(entity)
                if amount is not None:
                    return amount
        return None

    def _semantic_rate(self, director_input: VisualDirectorInput, *roles: str) -> float | None:
        entity = self._semantic_entity(director_input, *roles)
        amount = self._semantic_money_amount(entity)
        if amount is not None:
            return amount
        return director_input.percentage

    def _semantic_years(self, director_input: VisualDirectorInput) -> int | None:
        entity = self._semantic_entity(director_input, "time_period")
        amount = self._semantic_money_amount(entity)
        if amount is not None:
            return int(amount)
        return self._years_from_text(director_input.time_period or "")

    def _semantic_money_flow_data(self, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        by_role = self._semantic_entities_by_role(director_input)
        source = self._semantic_entity(director_input, "salary_income")
        source_amount = self._semantic_money_amount(source)
        if source_amount is None:
            return None
        flow_roles = ("emi_payment", "rent_expense", "living_expense")
        flows: list[dict[str, Any]] = []
        for role in flow_roles:
            for entity in by_role.get(role, []):
                amount = self._semantic_money_amount(entity)
                if amount is None or amount >= source_amount:
                    continue
                label = self._semantic_flow_label(role, entity)
                flows.append({"label": label, "value": self._format_rupee(amount), "amount": amount, "color": "orange", "order": 0})
        if not flows:
            return None
        flows = sorted(flows, key=lambda flow: flow["amount"], reverse=True)
        flow_total = sum(float(flow["amount"]) for flow in flows)
        remainder_entity = self._semantic_entity(director_input, "remaining_balance")
        remainder_amount = self._semantic_money_amount(remainder_entity)
        if remainder_amount is None:
            remainder_amount = max(source_amount - flow_total, 0.0)
        for order, flow in enumerate(flows, start=1):
            flow["order"] = order
            flow["color"] = "red" if order == 1 else "orange"
        ratio = remainder_amount / source_amount if source_amount else 0.0
        return {
            "source": {"label": "Salary", "value": self._format_rupee(source_amount), "amount": source_amount},
            "flows": flows,
            "remainder": {
                "value": self._format_rupee(remainder_amount),
                "amount": round(remainder_amount, 2),
                "is_dangerous": ratio < 0.10,
            },
            "numeric_provenance": self._semantic_scene(director_input).get("spoken_values") or [],
            "semantic_source": "semantic_scene_contract",
        }

    def _semantic_flow_label(self, role: str, entity: dict[str, Any]) -> str:
        if role == "emi_payment":
            return "EMI"
        if role == "rent_expense":
            return "Rent"
        if role == "living_expense":
            source = str(entity.get("source_text") or "").lower()
            if "food" in source and "travel" in source:
                return "Food + travel"
            if "subscription" in source:
                return "Subscriptions"
            return "Lifestyle"
        return str(entity.get("label") or role.replace("_", " ").title())

    def _semantic_sip_growth_data(self, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        monthly = self._semantic_entity(director_input, "monthly_sip")
        monthly_amount = self._semantic_money_amount(monthly)
        if monthly_amount is None:
            return None
        annual_rate = max(float(self._semantic_rate(director_input, "annual_return_rate") or 12.0), 1.0)
        duration_years = int(self._semantic_years(director_input) or 20)
        total_entity = self._semantic_entity(director_input, "total_contribution")
        corpus_entity = self._semantic_entity(director_input, "target_corpus", "target_value")
        total_invested = self._semantic_money_amount(total_entity)
        final_corpus = self._semantic_money_amount(corpus_entity)
        if total_invested is None:
            total_invested = monthly_amount * duration_years * 12
        if final_corpus is None:
            months = duration_years * 12
            monthly_rate = annual_rate / 100.0 / 12.0
            final_corpus = monthly_amount * (((1 + monthly_rate) ** months - 1) / monthly_rate) * (1 + monthly_rate) if monthly_rate else total_invested
        returns_earned = final_corpus - total_invested
        return {
            "monthly_sip": {"value": str(monthly.get("display_value") or self._format_rupee(monthly_amount)), "amount": monthly_amount},
            "duration_years": duration_years,
            "annual_return_rate": annual_rate,
            "total_invested": round(total_invested, 2),
            "final_corpus": round(final_corpus, 2),
            "returns_earned": round(returns_earned, 2),
            "awe_ratio": round(final_corpus / total_invested, 2) if total_invested else 0.0,
            "numeric_provenance": self._semantic_scene(director_input).get("spoken_values") or [],
            "semantic_source": "semantic_scene_contract",
        }

    def _semantic_lifestyle_creep_data(self, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        incomes = self._semantic_entities_by_role(director_input).get("salary_income") or []
        if len(incomes) < 2:
            return None
        start_entity, end_entity = incomes[0], incomes[1]
        start_income = self._semantic_money_amount(start_entity)
        end_income = self._semantic_money_amount(end_entity)
        if start_income is None or end_income is None or end_income <= start_income:
            return None
        raise_entity = self._semantic_entity(director_input, "raise_delta")
        raise_amount = self._semantic_money_amount(raise_entity) or max(end_income - start_income, 0.0)
        old_savings = max(start_income * 0.18, 0.0)
        new_savings = old_savings
        old_spending = max(start_income - old_savings, 0.0)
        new_spending = max(end_income - new_savings, old_spending)
        source_ids = [source_id for source_id in (self._semantic_source_id(start_entity), self._semantic_source_id(end_entity)) if source_id]
        return {
            "title": "Income rises. Savings don't.",
            "start_income": {"value": self._format_rupee(start_income), "amount": round(start_income, 2), "source_number_ids": [self._semantic_source_id(start_entity)], "derived": False},
            "end_income": {"value": self._format_rupee(end_income), "amount": round(end_income, 2), "source_number_ids": [self._semantic_source_id(end_entity)], "derived": False},
            "old_spending": {"value": self._format_rupee(old_spending), "amount": round(old_spending, 2), "derived": True, "derived_from": source_ids, "derivation_method": "estimated baseline spending from income"},
            "new_spending": {"value": self._format_rupee(new_spending), "amount": round(new_spending, 2), "derived": True, "derived_from": source_ids, "derivation_method": "estimated post-raise spending from income and savings"},
            "old_savings": {"value": self._format_rupee(old_savings), "amount": round(old_savings, 2), "derived": True, "derived_from": source_ids, "derivation_method": "estimated baseline savings from income"},
            "new_savings": {"value": self._format_rupee(new_savings), "amount": round(new_savings, 2), "derived": True, "derived_from": source_ids, "derivation_method": "estimated savings after lifestyle expansion"},
            "raise": {"value": self._format_rupee(raise_amount), "amount": round(raise_amount, 2), "source_number_ids": [self._semantic_source_id(raise_entity)] if raise_entity else source_ids, "derived": raise_entity is None, "derived_from": [] if raise_entity else source_ids, "derivation_method": None if raise_entity else "end_income - start_income"},
            "accent": "warning",
            "numeric_provenance": self._semantic_scene(director_input).get("spoken_values") or [],
            "truth_mode": "hard",
            "semantic_source": "semantic_scene_contract",
        }

    def _semantic_debt_spiral_data(self, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        principal_entity = self._semantic_entity(director_input, "debt_principal", "principal_balance")
        principal = self._semantic_money_amount(principal_entity) or self._parse_rupee(director_input.start_value)
        rate = self._semantic_rate(director_input, "annual_interest_rate") or director_input.percentage
        if principal is None or rate is None:
            return None
        minimum = self._semantic_money_amount(self._semantic_entity(director_input, "minimum_payment"))
        months = self._semantic_years(director_input) or 12
        monthly_rate = float(rate) / 100.0 / 12.0
        balance = float(principal)
        balances = []
        payment = float(minimum or 0.0)
        for month in range(1, max(months, 12) + 1):
            interest = balance * monthly_rate
            principal_paid = payment - interest if payment else 0.0
            balance = max(balance + interest - payment, 0.0)
            balances.append({"month": month, "balance": round(balance, 2), "interest": round(interest, 2), "principal_paid": round(principal_paid, 2)})
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
            "semantic_source": "semantic_scene_contract",
        }

    def _semantic_emi_stack_data(self, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        by_role = self._semantic_entities_by_role(director_input)
        emi_entities = by_role.get("emi_payment") or []
        if not emi_entities:
            return None
        salary_amount = self._semantic_money_amount(self._semantic_entity(director_input, "salary_income")) or self._parse_rupee(director_input.start_value) or 50000.0
        labels = ["Phone EMI", "Bike EMI", "Personal loan", "Credit card", "Other EMI"]
        emis = []
        for index, entity in enumerate(emi_entities[:5]):
            amount = self._semantic_money_amount(entity)
            if amount is None:
                continue
            emis.append({"label": labels[index] if index < len(labels) else f"EMI {index + 1}", "value": self._format_rupee(amount), "amount": amount})
        if not emis:
            return None
        total_emi = sum(float(item["amount"]) for item in emis)
        explicit_salary = self._explicit_salary_amount(director_input.narration_text)
        if explicit_salary is not None:
            salary_amount = explicit_salary
        elif salary_amount <= total_emi * 1.05:
            salary_amount = max(50000.0, round(total_emi * 2.6 / 1000.0) * 1000.0)
        remaining_entity = self._semantic_entity(director_input, "remaining_balance")
        remaining = self._semantic_money_amount(remaining_entity)
        if remaining is None:
            remaining = self._explicit_remaining_amount(director_input.narration_text)
        if remaining is None:
            remaining = max(salary_amount - total_emi, 0.0)
        return {
            "salary": {"value": self._format_rupee(salary_amount), "amount": salary_amount},
            "emis": emis,
            "total_emi": {"value": self._format_rupee(total_emi), "amount": round(total_emi, 2)},
            "remaining": {"value": self._format_rupee(remaining), "amount": round(remaining, 2), "is_critical": remaining / max(salary_amount, 1) < 0.15},
            "semantic_source": "semantic_scene_contract",
        }

    def _semantic_inflation_return_data(self, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        rate = self._semantic_rate(director_input, "inflation_rate")
        amount_entity = self._semantic_entity(director_input, "principal_balance", "salary_income")
        amount = self._semantic_money_amount(amount_entity) or self._parse_rupee(director_input.start_value)
        years = self._semantic_years(director_input)
        if amount is None or rate is None:
            return None
        duration_years = years or 10
        real_value = amount / ((1 + float(rate) / 100.0) ** duration_years)
        return {
            "start_value": {"value": self._format_rupee(amount), "amount": amount},
            "real_value": {"value": self._format_rupee(real_value), "amount": round(real_value, 2), "derived": True, "derived_from": [self._semantic_source_id(amount_entity)] if amount_entity else [], "derivation_method": "inflation-adjusted buying power"},
            "inflation_rate": float(rate),
            "years": duration_years,
            "rate_label": f"{float(rate):g}% for {duration_years} years",
            "semantic_source": "semantic_scene_contract",
        }

    def _money_flow_data(self, text_or_input: str | VisualDirectorInput) -> dict[str, Any] | None:
        director_input = text_or_input if isinstance(text_or_input, VisualDirectorInput) else None
        if director_input is not None:
            semantic_data = self._semantic_money_flow_data(director_input)
            if semantic_data:
                return semantic_data
            text = director_input.narration_text
        else:
            text = str(text_or_input or "")
        amounts = self._money_mentions(text)
        source = self._source_amount(amounts, text)
        if not source:
            return None
        source_amount = float(source["amount"])
        explicit_flows = self._explicit_flows(text, source)
        percentage_flows = self._percentage_flows(text, source_amount, {flow["label"].lower() for flow in explicit_flows})
        flows = explicit_flows + percentage_flows
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
            label_lower = str(flow.get("label") or "").lower()
            if any(t in label_lower for t in ("invest", "sip", "savings", "emergency")):
                flow["color"] = "teal"
            else:
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

    def _lifestyle_creep_data(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        semantic_data = self._semantic_lifestyle_creep_data(director_input)
        if semantic_data:
            return semantic_data
        text = director_input.narration_text
        numeric_roles = numeric_role_map(text, scene_id="visual_director")
        facts = list(numeric_roles.get("facts") or [])
        amounts = self._money_mentions(text)
        income_mentions = [
            float(item["amount"])
            for item in amounts
            if str(item.get("label") or "").lower() in {"salary", "income"}
        ]
        all_amounts = [float(item["amount"]) for item in amounts]
        start_fact = first_fact(facts, "start_income", "income")
        end_fact = first_fact(facts, "end_income")
        raise_fact = first_fact(facts, "raise_delta")

        start_income = self._parse_rupee(str(start_fact.get("raw"))) if start_fact else self._parse_rupee(director_input.start_value)
        if start_income is None:
            start_income = income_mentions[0] if income_mentions else (all_amounts[0] if all_amounts else 50000.0)

        end_income = self._parse_rupee(str(end_fact.get("raw"))) if end_fact else self._parse_rupee(director_input.end_value)
        if end_income is None:
            candidates = [amount for amount in [*income_mentions, *all_amounts] if amount > start_income * 1.08]
            end_income = candidates[0] if candidates else start_income * 1.6
        if end_income <= start_income:
            candidates = [amount for amount in [*income_mentions, *all_amounts] if amount > start_income * 1.08]
            end_income = candidates[0] if candidates else start_income * 1.45

        lowered = text.lower()
        savings_flat = any(token in lowered for token in ("savings stay flat", "saving stays flat", "savings are zero", "savings stay stuck", "zero savings"))
        old_savings = max(start_income * (0.0 if "zero" in lowered and "savings" in lowered else 0.18), 0.0)
        if "savings stay flat" in lowered or "savings stay stuck" in lowered:
            new_savings = old_savings
        elif savings_flat:
            new_savings = max(old_savings * 0.65, 0.0)
        else:
            new_savings = max(end_income * 0.12, old_savings * 0.8)

        old_spending = max(start_income - old_savings, 0.0)
        new_spending = max(end_income - new_savings, old_spending)
        explicit_raise = self._parse_rupee(str(raise_fact.get("raw"))) if raise_fact else None
        raise_amount = explicit_raise if explicit_raise is not None else max(end_income - start_income, 0.0)
        source_ids = [str(fact.get("id")) for fact in (start_fact, end_fact) if fact]

        return {
            "title": "Income rises. Savings don't.",
            "start_income": {"value": self._format_rupee(start_income), "amount": round(start_income, 2), "source_number_ids": [start_fact.get("id")] if start_fact else [], "derived": False},
            "end_income": {"value": self._format_rupee(end_income), "amount": round(end_income, 2), "source_number_ids": [end_fact.get("id")] if end_fact else [], "derived": False},
            "old_spending": {
                "value": self._format_rupee(old_spending),
                "amount": round(old_spending, 2),
                "derived": True,
                "derived_from": source_ids,
                "derivation_method": "estimated baseline spending from income",
            },
            "new_spending": {
                "value": self._format_rupee(new_spending),
                "amount": round(new_spending, 2),
                "derived": True,
                "derived_from": source_ids,
                "derivation_method": "estimated post-raise spending from income and savings",
            },
            "old_savings": {
                "value": self._format_rupee(old_savings),
                "amount": round(old_savings, 2),
                "derived": True,
                "derived_from": source_ids,
                "derivation_method": "estimated baseline savings from income",
            },
            "new_savings": {
                "value": self._format_rupee(new_savings),
                "amount": round(new_savings, 2),
                "derived": True,
                "derived_from": source_ids,
                "derivation_method": "estimated savings after lifestyle expansion",
            },
            "raise": {
                "value": self._format_rupee(raise_amount),
                "amount": round(raise_amount, 2),
                "source_number_ids": [raise_fact.get("id")] if raise_fact else source_ids,
                "derived": explicit_raise is None,
                "derived_from": [] if explicit_raise is not None else source_ids,
                "derivation_method": None if explicit_raise is not None else "end_income - start_income",
            },
            "accent": "warning",
            "numeric_provenance": facts,
            "truth_mode": "hard",
        }

    def _debt_spiral_data(self, text: str, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        semantic_data = self._semantic_debt_spiral_data(director_input)
        if semantic_data:
            return semantic_data
        amounts = self._money_mentions(text)
        principal = self._principal_amount(amounts, text, director_input)
        rate = director_input.percentage if director_input.percentage is not None else self._first_percentage(text)
        lowered = text.lower()
        debt_context = any(token in lowered for token in ("debt trap", "credit card", "minimum payment", "minimum dues", "outstanding balance", "debt grows", "debt grow", "debt"))
        if debt_context and amounts:
            if rate is None:
                rate = 40.0
            if principal is None:
                interest_amount = self._interest_amount(amounts, text)
                if interest_amount is not None and rate:
                    principal = interest_amount / (float(rate) / 100.0 / 12.0)
                else:
                    principal = max(float(item["amount"]) for item in amounts)
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

    def _interest_amount(self, amounts: list[dict[str, Any]], text: str) -> float | None:
        for item in amounts:
            window = self._window(text, int(item.get("start") or 0), int(item.get("end") or 0), radius=32).lower()
            if "interest" in window:
                return float(item["amount"])
        return None

    def _sip_growth_data(self, text: str, director_input: VisualDirectorInput) -> dict[str, Any] | None:
        semantic_data = self._semantic_sip_growth_data(director_input)
        if semantic_data:
            return semantic_data
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
        explicit = str(director_input.concept_type or "").strip().lower()
        aliases = {
            "emi_stack": "emi_pressure",
            "fomo_risk": "speculation_risk",
            "salary_depletion": "salary_drain",
            # tax_drain is NOT aliased to tax_saving — they are opposite concepts:
            # tax_drain = money leaking to tax (danger, MoneyFlow)
            # tax_saving = reducing tax via planning (positive, SplitComparison)
        }
        if explicit in aliases:
            return aliases[explicit]
        semantic_key = self._semantic_primary_concept_key(director_input)
        if semantic_key in aliases:
            return aliases[semantic_key]
        if semantic_key and semantic_key not in {"unknown", "definition", "general_point"}:
            return semantic_key
        if explicit in {
            "salary_drain",
            "lifestyle_inflation",
            "emi_pressure",
            "debt_trap",
            "inflation_erosion",
            "sip_growth",
            "compounding",
            "recap_system",
            "risk_return",
            "emergency_fund",
            "speculation_risk",
            "diversification",
            "tax_saving",
            "tax_drain",
            "rent_burden",
            "expense_leakage",
            "subscription_leak",
            "budgeting",
            "savings_rate",
            "loan_cost",
            "net_worth_growth",
        }:
            return explicit
        narration_text = str(director_input.narration_text or "").lower()
        if narration_text.strip().startswith("recap") or ("break free" in narration_text and "future self" in narration_text):
            return "recap_system"
        text = f"{director_input.narration_text} {explicit}".lower()
        if "sip" in text or "systematic investment plan" in text:
            return "sip_growth"
        if any(token in text for token in ("debt trap", "credit card", "minimum payment", "minimum dues")):
            return "debt_trap"
        if "debt" in text and any(token in text for token in ("interest", "compound", "grows", "trapped", "trap")):
            return "debt_trap"
        if "emi" in text and any(token in text for token in ("pressure", "burden", "loan", "interest", "stack", "takes", "fixed", "month")):
            return "emi_pressure"
        if "salary" in text and any(token in text for token in ("drain", "depletion", "disappear", "vanish", "left", "gone", "empty", "broke")):
            return "salary_drain"
        if "lifestyle inflation" in text:
            return "lifestyle_inflation"
        if (
            ("raise" in text or "hike" in text or "income rises" in text or "salary rises" in text)
            and any(token in text for token in ("lifestyle", "upgrade", "luxury", "luxuries", "expenses catch", "spending rises", "savings stay", "savings flat"))
        ):
            return "lifestyle_inflation"
        # loan/debt checks before generic keyword grabs
        if "loan" in text and ("cost" in text or "interest" in text):
            return "loan_cost"
        if "inflation" in text and any(token in text for token in ("fd", "fixed deposit", "real return", "return")):
            return "fd_vs_inflation"
        if "inflation" in text or "purchasing power" in text or "buying power" in text:
            return "inflation_erosion"
        if "fomo" in text or "speculation" in text or "life savings" in text or "don't understand" in text or "do not understand" in text:
            return "speculation_risk"
        if "diversification" in text or "diversify" in text or "asset classes" in text or "one basket" in text or "one stock" in text or "all eggs" in text:
            return "diversification"
        if "compound" in text or "compounding" in text:
            return "compounding"
        if "real return" in text or ("tax" in text and "return" in text):
            return "real_return"
        if (
            "expense leakage" in text
            or "subscription" in text
            or "leak" in text
            or ("small" in text and any(token in text for token in ("choices add", "adding up", "repeats", "tiny", "harmless")))
            or ("pattern" in text and "expensive" in text)
        ):
            return "expense_leakage"
        if "emergency fund" in text or "cash buffer" in text:
            return "emergency_fund"
        # opportunity_cost: require specific intent, not just "instead"
        if "opportunity cost" in text or "could have been" in text or (
            "instead" in text and any(token in text for token in ("invest", "sip", "fd", "savings", "corpus", "compound"))
        ):
            return "opportunity_cost"
        if "risk" in text and "return" in text:
            return "risk_return"
        # tax_saving: only when an explicit planning/saving action is present
        if "80c" in text or ("tax" in text and any(token in text for token in ("save", "saving", "invest", "plan", "deduct", "exemption"))):
            return "tax_saving"
        # tax_drain: informational tax mention (bracket, GST, income tax, etc.)
        if "tax" in text:
            return "tax_drain"
        if "budget" in text or "allocate" in text:
            return "budgeting"
        # savings_rate: require specific phrasing, not just "save" + "income"
        if "savings rate" in text or re.search(r"save\s+\d+\s*%\s*(?:of|from)?\s*income", text):
            return "savings_rate"
        # net_worth_growth: only when growth/building direction is explicit
        negative_wealth_context = any(token in text for token in ("destroy", "debt", "lose", "loss", "erode", "hurt", "trap"))
        if "net worth" in text or (
            "wealth" in text
            and not negative_wealth_context
            and any(token in text for token in ("build", "grow", "create", "compound", "increase"))
        ):
            return "net_worth_growth"
        return str(director_input.concept_type or director_input.idea_type or "definition").strip() or "definition"

    def _display_concept_name(self, concept_type: str) -> str:
        return {
            "lifestyle_inflation": "Lifestyle Inflation",
            "expense_leakage": "Expense Leakage",
            "budgeting": "Budget Allocation",
            "savings_rate": "Savings Rate",
            "emergency_fund": "Emergency Fund",
            "rent_burden": "Rent Burden",
            "emi_pressure": "EMI Pressure",
            "loan_cost": "Loan Cost",
            "compounding": "Compounding",
            "net_worth_growth": "Net Worth Growth",
            "recap_system": "Money System Recap",
            "inflation_erosion": "Inflation Erosion",
            "inflation_loss": "Inflation Loss",
            "real_return": "Real Return",
            "fd_vs_inflation": "FD vs Inflation",
            "opportunity_cost": "Opportunity Cost",
            "comparison_timeline": "Decision Timeline",
            "risk_return": "Risk vs Return",
            "diversification": "Diversification",
            "tax_saving": "Tax Saving",
            "tax_drain": "Tax Drain",
            "speculation_risk": "Investing vs Speculation",
        }.get(concept_type, concept_type.replace("_", " ").title())

    def _money_flow_title(self, concept_type: str) -> str:
        return {
            "lifestyle_inflation": "Where the raise went",
            "expense_leakage": "Where money leaks",
            "budgeting": "Budget split",
            "savings_rate": "Income allocation",
            "emergency_fund": "Safety buffer",
            "tax_drain": "Tax drain",
            "rent_burden": "Rent burden",
        }.get(concept_type, "Money movement")

    def _money_mechanism_punch(self, flow_data: dict[str, Any], concept_type: str) -> str:
        if concept_type == "emergency_fund":
            return f"{flow_data['remainder']['value']} buffer"
        if flow_data["remainder"]["is_dangerous"]:
            return f"{flow_data['remainder']['value']} left"
        return "The gap matters"

    def _emi_stack_data(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        semantic_data = self._semantic_emi_stack_data(director_input)
        if semantic_data:
            return semantic_data
        text = director_input.narration_text
        amounts = self._money_mentions(text)
        salary_amount = self._parse_rupee(director_input.start_value) or 50000.0
        explicit_salary = self._explicit_salary_amount(text)
        if explicit_salary is not None:
            salary_amount = explicit_salary
        for item in amounts:
            if explicit_salary is None and str(item.get("label") or "").lower() in {"salary", "income"}:
                salary_amount = float(item["amount"])
                break
        emi_amounts = [
            float(item["amount"])
            for item in amounts
            if any(token in str(item.get("label") or "").lower() for token in ("emi", "loan", "payment"))
            and float(item["amount"]) < salary_amount
        ]
        if not emi_amounts:
            emi_amounts = [4000.0, 6500.0, 7500.0]
        labels = ["Phone EMI", "Bike EMI", "Personal loan", "Credit card", "Other EMI"]
        emis = [
            {"label": labels[index] if index < len(labels) else f"EMI {index + 1}", "value": self._format_rupee(amount), "amount": amount}
            for index, amount in enumerate(emi_amounts[:5])
        ]
        total_emi = sum(float(item["amount"]) for item in emis)
        if explicit_salary is None and salary_amount <= total_emi * 1.05:
            salary_amount = max(50000.0, round(total_emi * 2.6 / 1000.0) * 1000.0)
        remaining = self._explicit_remaining_amount(text)
        if remaining is None:
            remaining = max(salary_amount - total_emi, 0.0)
        if "nothing" in text.lower() or "trapped" in text.lower():
            remaining = min(remaining, salary_amount * 0.12)
        return {
            "salary": {"value": self._format_rupee(salary_amount), "amount": salary_amount},
            "emis": emis,
            "total_emi": {"value": self._format_rupee(total_emi), "amount": round(total_emi, 2)},
            "remaining": {
                "value": self._format_rupee(remaining),
                "amount": round(remaining, 2),
                "is_critical": remaining / max(salary_amount, 1) < 0.15,
            },
        }

    def _diversification_data(self) -> dict[str, Any]:
        return {
            "assets": [
                {"label": "Equity", "allocation": 45, "color": "#2EC4B6"},
                {"label": "Debt", "allocation": 25, "color": "#4361EE"},
                {"label": "FD", "allocation": 15, "color": "#FF9F1C"},
                {"label": "Gold", "allocation": 10, "color": "#B8A44C"},
                {"label": "Cash", "allocation": 5, "color": "rgba(255,255,255,0.65)"},
            ],
            "shock_asset": "Equity",
            "punch": "One fall does not break all",
        }

    def _fomo_crash_data(self) -> dict[str, Any]:
        return {
            "points": [
                {"x": 0.02, "y": 0.68},
                {"x": 0.18, "y": 0.58},
                {"x": 0.34, "y": 0.42},
                {"x": 0.52, "y": 0.18},
                {"x": 0.66, "y": 0.28},
                {"x": 0.82, "y": 0.62},
                {"x": 0.98, "y": 0.78},
            ],
            "buy_label": "buy at peak",
            "loss_label": "panic after entry",
        }

    def _small_leaks_data(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        text = director_input.narration_text.lower()
        leaks = [
            {"label": "Food apps", "amount": 2400.0},
            {"label": "Subscriptions", "amount": 1200.0},
            {"label": "Impulse buys", "amount": 3500.0},
            {"label": "Convenience fees", "amount": 900.0},
        ]
        if "coffee" in text:
            leaks[0] = {"label": "Coffee runs", "amount": 1800.0}
        if "week" in text:
            leaks.append({"label": "Weekly repeats", "amount": 2600.0})
        return {
            "leaks": [
                {**leak, "value": self._format_rupee(float(leak["amount"]))}
                for leak in leaks[:5]
            ],
            "monthly_loss": round(sum(float(leak["amount"]) for leak in leaks[:5]), 2),
        }

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
        elif concept_type == "rent_burden":
            flows = [
                {"label": "Rent", "amount": source_amount * 0.4},
                {"label": "Bills", "amount": source_amount * 0.18},
                {"label": "Food", "amount": source_amount * 0.16},
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
        semantic_data = self._semantic_inflation_return_data(director_input)
        if semantic_data:
            return semantic_data
        explicit_amount = self._parse_rupee(director_input.narration_text) or self._parse_rupee(director_input.start_value)
        explicit_rate = director_input.percentage if director_input.percentage is not None else self._first_percentage(director_input.narration_text)
        explicit_years = self._years_from_text(director_input.time_period or director_input.narration_text)
        if explicit_amount is None and explicit_rate is None and explicit_years is None:
            return {
                "start_value": {"value": "Savings", "amount": 0.0},
                "real_value": {"value": "Buying power falls", "amount": 0.0},
                "inflation_rate": None,
                "years": None,
                "rate_label": "",
            }
        amount = explicit_amount or 100000.0
        rate = max(explicit_rate or 7.0, 1.0)
        years = explicit_years or 10
        real_value = amount / ((1 + rate / 100.0) ** years)
        return {
            "start_value": {"value": self._format_rupee(amount), "amount": amount},
            "real_value": {"value": self._format_rupee(real_value), "amount": round(real_value, 2)},
            "inflation_rate": rate,
            "years": years,
            "rate_label": f"{rate:g}% for {years} years",
        }

    def _inflation_items(self, start_amount: Any, end_amount: Any) -> list[dict[str, Any]]:
        try:
            start = float(start_amount or 0)
            end = float(end_amount or 0)
        except (TypeError, ValueError):
            return []
        if start <= 0 or end <= 0:
            return []
        ratio = max(0.12, min(end / start, 1.0))
        base_items = [
            {"name": "Groceries", "current": 5, "future": max(1, round(5 * ratio))},
            {"name": "Fuel", "current": 4, "future": max(1, round(4 * ratio))},
            {"name": "Bills", "current": 3, "future": max(1, round(3 * ratio))},
        ]
        return base_items

    def _comparison_data(self, director_input: VisualDirectorInput, concept_type: str) -> dict[str, Any]:
        amount = self._semantic_first_money_amount(director_input) or self._parse_rupee(director_input.start_value) or self._parse_rupee(director_input.narration_text)
        if concept_type == "risk_return":
            return {"left": {"label": "Low Risk / Low Return", "value": "FD"}, "right": {"label": "Higher Risk / Higher Growth", "value": "Equity"}, "punch": "Risk buys upside", "accent": "teal"}
        if concept_type == "diversification":
            return {"left": {"label": "One bet", "value": "100%"}, "right": {"label": "Spread bets", "value": "safer mix"}, "punch": "Spread the risk", "accent": "teal"}
        if concept_type == "tax_saving":
            if amount is not None:
                tax_saved = amount * 0.3
                return {"left": {"label": "Without planning", "value": self._format_rupee(amount)}, "right": {"label": "Tax saved", "value": self._format_rupee(tax_saved)}, "punch": f"{self._format_rupee(tax_saved)} saved", "accent": "teal"}
            return {"left": {"label": "No planning", "value": "tax leak"}, "right": {"label": "Tax plan", "value": "money saved"}, "punch": "Planning reduces leakage", "accent": "teal"}
        if concept_type == "speculation_risk":
            return {"left": {"label": "FOMO trade", "value": "emotion"}, "right": {"label": "Real investing", "value": "understanding"}, "punch": "Do not buy what you cannot explain", "accent": "orange"}
        if concept_type in {"opportunity_cost", "comparison_timeline"}:
            if amount is not None:
                return {"left": {"label": "Spend today", "value": self._format_rupee(amount)}, "right": {"label": "Invest monthly", "value": self._format_rupee(amount)}, "punch": "Small choice compounds", "accent": "orange"}
            return {"left": {"label": "Spend today", "value": "instant"}, "right": {"label": "Invest instead", "value": "future"}, "punch": "Small choice compounds", "accent": "orange"}
        return {"left": {"label": "Path A", "value": "today"}, "right": {"label": "Path B", "value": "future"}, "punch": "Choose the better path", "accent": "teal"}

    def _risk_return_data(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        text = director_input.narration_text
        rates = [float(match.group(1)) for match in re.finditer(r"(\d+(?:\.\d+)?)\s*%", text)]
        fd_rate = next((rate for rate in rates if rate <= 9), 6.0)
        equity_rate = next((rate for rate in rates if rate > 9), 12.0)
        return {
            "safe_asset": "FD",
            "growth_asset": "Equity",
            "safe_rate": f"{fd_rate:g}%",
            "growth_rate": f"{equity_rate:g}%",
            "punch": "Risk buys upside only when you can stay invested",
        }

    def _emergency_fund_data(self, director_input: VisualDirectorInput) -> dict[str, Any]:
        text = director_input.narration_text
        months_match = re.search(r"(\d+)\s*(?:-|to\s*)?(?:month|months)", text, re.IGNORECASE)
        buffer_months = int(months_match.group(1)) if months_match else 6
        amount = self._semantic_first_money_amount(director_input) or self._parse_rupee(director_input.start_value)
        shock = "Unexpected bill"
        lowered = text.lower()
        if "medical" in lowered or "hospital" in lowered:
            shock = "Medical bill"
        elif "job" in lowered or "layoff" in lowered or "income delay" in lowered:
            shock = "Income delay"
        elif "repair" in lowered or "car" in lowered:
            shock = "Repair bill"
        return {
            "buffer_months": buffer_months,
            "buffer_label": f"{buffer_months}-month buffer",
            "buffer_value": self._format_rupee(amount) if amount else f"{buffer_months} months",
            "shock_label": shock,
            "debt_label": "Credit card debt",
            "punch": "The buffer buys breathing room before debt begins",
        }

    def _explicit_salary_amount(self, text: str) -> float | None:
        patterns = (
            r"(?:salary|income|paycheck|pay)\D{0,18}(?:₹\s*|Rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)",
            r"(?:₹\s*|Rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)\D{0,18}(?:salary|income|paycheck|pay)",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount = float(match.group(1).replace(",", ""))
                if amount < 1000 and "lakh" in self._window(text, match.start(), match.end(), 16).lower():
                    amount *= 100000
                return amount
        return None

    def _explicit_remaining_amount(self, text: str) -> float | None:
        match = re.search(
            r"(?:left|leftover|remaining|cash\s+left|survive\s+on|only)\D{0,18}(?:₹\s*|Rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        amount = float(match.group(1).replace(",", ""))
        if amount < 1000 and "lakh" in self._window(text, match.start(), match.end(), 16).lower():
            amount *= 100000
        return amount

    def _money_mentions(self, text: str) -> list[dict[str, Any]]:
        pattern = re.compile(r"(?:₹\s*|Rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)\s*(lakh|lakhs|crore|crores|k)?", re.IGNORECASE)
        mentions: list[dict[str, Any]] = []
        finance_window_re = re.compile(
            r"\b(?:rs|emi|rent|salary|sip|payment|balance|food|left|invest|loan|debt|interest|corpus|returns?|wealth|tax|income|savings?)\b",
            re.IGNORECASE,
        )
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
            if not raw:
                continue
            if "₹" not in raw and not raw.lower().startswith("rs") and not finance_window_re.search(self._window(text, match.start(), match.end(), radius=60)):
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
        if "salary" in before or "salary" in after:
            return "Salary"
        if ("tax" in before or "tax" in after or "gst" in before or "gst" in after) and any(
            token in f"{before} {after}" for token in ("take", "takes", "taken", "cut", "deduct", "before money")
        ):
            return "Tax"
        if "income" in before or "income" in after:
            return "Income"
        if "earn" in before or "earned" in before or "earning" in before:
            return "Salary"
        immediate_category = self._nearest_expense_category(before, after)
        if immediate_category:
            return immediate_category
        if "left" in after or "left" in before or "remaining" in after:
            return "left"
        if "tax" in before or "tax" in after or "gst" in before or "gst" in after:
            return "Tax"
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
            ("tax", "Tax"),
            ("gst", "Tax"),
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

    def _window(self, text: str, start: int, end: int, radius: int = 36) -> str:
        return text[max(0, start - radius) : min(len(text), end + radius)]

    def _short_phrase(self, text: str, fallback: str) -> str:
        words = [word.strip(" ,.-") for word in text.split() if word.strip(" ,.-")]
        return " ".join(words[:4]) or fallback


def _canonical_concept_key_from_name(name: str) -> str:
    normalized = " ".join(str(name or "").strip().lower().split())
    return {
        "salary drain": "salary_drain",
        "salary depletion": "salary_drain",
        "lifestyle inflation": "lifestyle_inflation",
        "emi pressure": "emi_pressure",
        "debt trap": "debt_trap",
        "inflation loss": "inflation_erosion",
        "inflation erosion": "inflation_erosion",
        "sip growth": "sip_growth",
        "compounding growth": "compounding",
        "fomo risk": "speculation_risk",
        "investing vs speculation": "speculation_risk",
        "diversification": "diversification",
        "opportunity cost": "opportunity_cost",
        "savings rate": "savings_rate",
        "tax saving": "tax_saving",
        "risk return": "risk_return",
        "risk vs return": "risk_return",
        "expense leakage": "expense_leakage",
        "emergency fund": "emergency_fund",
        "net worth growth": "net_worth_growth",
    }.get(normalized, "")


def visual_director_input_from_section(
    section: dict[str, Any],
    section_position: str,
    preceding_concept_type: str | None = None,
) -> VisualDirectorInput:
    finance_concept = dict(section.get("finance_concept") or {})
    concept = (section.get("concepts") or [{}])[0] if section.get("concepts") else {}
    visual_scene = dict(section.get("visual_scene") or {})
    mechanism = str(section.get("mechanism") or visual_scene.get("mechanism") or "").strip()
    finance_concept_key = _canonical_concept_key_from_name(str(finance_concept.get("concept_name") or ""))
    finance_confidence = float(finance_concept.get("confidence") or 0.0)
    if finance_concept_key and finance_confidence >= 0.6:
        concept_type = finance_concept_key
    else:
        concept_type = str(
            mechanism
            or section.get("concept_type")
            or finance_concept.get("concept_type")
            or concept.get("type")
            or section.get("idea_type")
            or "definition"
        )
    return VisualDirectorInput(
        concept_type=concept_type,
        concept_name=str(finance_concept.get("concept_name") or concept.get("concept") or "Money Change"),
        primary_entity=str(finance_concept.get("primary_entity") or section.get("dominant_entity") or "money"),
        action=str(finance_concept.get("action") or ""),
        start_value=finance_concept.get("start_value"),
        end_value=finance_concept.get("end_value"),
        percentage=finance_concept.get("percentage"),
        time_period=finance_concept.get("time_period"),
        confidence=float(finance_concept.get("confidence") or 0.0),
        narration_text=str(section.get("text") or ""),
        idea_type=str(section.get("idea_type") or mechanism or "emphasis"),
        has_numbers=bool(section.get("has_numbers")),
        section_position=section_position,
        preceding_concept_type=preceding_concept_type,
        visual_story=dict(section.get("visual_story") or {}),
        story_state=dict(section.get("story_state") or {}),
        semantic_scene=dict(section.get("semantic_scene") or {}),
    )


def directed_plan_to_dict(plan: DirectedPlan) -> dict[str, Any]:
    payload = asdict(plan)
    payload["beats"] = [beat.to_dict() for beat in plan.beats]
    payload["direction"] = plan.direction.to_dict()
    return payload
