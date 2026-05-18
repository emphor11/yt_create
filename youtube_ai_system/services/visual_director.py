from __future__ import annotations

from dataclasses import replace
import re
from typing import Any

from ..pipelines.visual import (
    CinematicIntent,
    DirectedBeat,
    DirectedPlan,
    SceneDirection,
    THEME,
    VisualDirectorInput,
    VisualDirectorPlansMixin,
)
from .financial_governance import first_fact, numeric_role_map
from .visual_scene_normalizer import KNOWN_MECHANISMS, MECHANISM_ALIASES


class VisualDirector(VisualDirectorPlansMixin):
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
        if concept_type in {"cash_flow_squeeze", "commitment_stacking"}:
            return self._with_cinematic_intent(self._emi_stack_plan(director_input, concept_type), director_input)
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
        if concept_type == "opportunity_cost":
            return self._with_cinematic_intent(self._opportunity_cost_plan(director_input), director_input)
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
        if concept_type in {
            "opportunity_cost",
            "comparison_timeline",
            "tax_saving",
            "affordability_illusion",
            "payment_pain_reduction",
            "anchoring",
            "price_anchoring",
            "delayed_consequence",
            "leverage",
        }:
            return self._with_cinematic_intent(self._comparison_mechanism_plan(director_input, concept_type), director_input)
        return self._with_cinematic_intent(self._generic_plan(director_input, concept_type), director_input)

    def _opportunity_cost_plan(self, director_input: VisualDirectorInput) -> DirectedPlan:
        amounts = [float(item["amount"]) for item in self._money_mentions(director_input.narration_text) if item.get("amount")]
        source_amount = max(amounts) if amounts else (self._parse_rupee(director_input.start_value) or 100000.0)
        missed_amount = next((amount for amount in sorted(set(amounts), reverse=True) if 0 < amount < source_amount), source_amount * 0.1)
        data = {
            "source": {"label": "Capital choice", "value": self._format_rupee(source_amount), "amount": source_amount},
            "flows": [
                {
                    "label": "Cash locked in purchase",
                    "value": self._format_rupee(source_amount),
                    "amount": source_amount,
                    "color": "orange",
                    "order": 1,
                },
                {
                    "label": "Annual profit missed",
                    "value": self._format_rupee(missed_amount),
                    "amount": missed_amount,
                    "color": "red",
                    "order": 2,
                },
            ],
            "remainder": {
                "value": self._format_rupee(source_amount),
                "amount": source_amount,
                "is_dangerous": False,
            },
            "punch": "The hidden cost is the return you give up",
        }
        direction = SceneDirection("confusion", "clarity", director_input.section_position, "warning")
        beats = self._contextualize_beats(
            [
                DirectedBeat("MoneyFlowDiagram", data["source"]["value"], "normal", "capital before decision", data={**data, "active_phase": "intro"}, beat_phase="intro"),
                DirectedBeat("MoneyFlowDiagram", "Cash stops working", "subtle", "purchase path", data={**data, "active_phase": "drain"}, beat_phase="drain"),
                DirectedBeat("MoneyFlowDiagram", data["punch"], "hero", "opportunity cost revealed", data={**data, "active_phase": "remainder"}, beat_phase="remainder"),
            ],
            director_input.narration_text,
        )
        return DirectedPlan(
            concept_type="opportunity_cost",
            concept_name="Opportunity Cost",
            pattern="MoneyFlowDiagram",
            data=data,
            direction=direction,
            theme=THEME,
            beats=beats,
        )

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
        if "monthly_payment" in active_objects:
            return f"{amount} monthly payment"
        if "full_price" in active_objects:
            return f"{amount} full price"
        if "capital_pool" in active_objects or "investment_engine" in active_objects:
            return f"{amount} capital"
        if "future_obligation" in active_objects:
            return f"{amount} future claim"
        labels = {
            "MoneyFlowDiagram": f"{amount} in motion",
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
    mechanism = _trusted_section_mechanism(section)
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


def _trusted_section_mechanism(section: dict[str, Any]) -> str:
    """Use generated ScriptBrief mechanisms, but do not let stale stored visual_scene_json steer render-time scenes."""
    mechanism_source = str(section.get("mechanism_source") or "").strip()
    if mechanism_source and mechanism_source not in {"explicit_section", "explicit_visual_scene"}:
        return ""
    for key in ("mechanism", "idea_type"):
        mechanism = _canonical_director_mechanism(section.get(key))
        if mechanism:
            return mechanism
    return ""


def _canonical_director_mechanism(value: Any) -> str:
    mechanism = str(value or "").strip().lower()
    alias_map = {key: target for key, target in MECHANISM_ALIASES.items() if key != "tax_drain"}
    mechanism = alias_map.get(mechanism, mechanism)
    return mechanism if mechanism in KNOWN_MECHANISMS and mechanism != "definition" else ""


def directed_plan_to_dict(plan: DirectedPlan) -> dict[str, Any]:
    payload = asdict(plan)
    payload["beats"] = [beat.to_dict() for beat in plan.beats]
    payload["direction"] = plan.direction.to_dict()
    return payload
