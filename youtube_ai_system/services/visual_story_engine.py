from __future__ import annotations

from typing import Any

from ..pipelines.story.visual_story_taxonomy import (
    CONCEPT_TO_OBJECTS,
    CONCEPT_TO_SCENE_ROLE,
    CONCEPT_VISUAL_QUESTIONS,
    VISUAL_STORY_OBJECTS,
)
from ..pipelines.story.visual_story_values import VisualStoryValueHelper


class VisualStoryEngine:
    """Builds a deterministic video-level visual story world for finance scenes."""

    OBJECTS = VISUAL_STORY_OBJECTS
    CONCEPT_TO_SCENE_ROLE = CONCEPT_TO_SCENE_ROLE
    CONCEPT_TO_OBJECTS = CONCEPT_TO_OBJECTS
    CONCEPT_VISUAL_QUESTIONS = CONCEPT_VISUAL_QUESTIONS

    def __init__(self) -> None:
        self.value_helper = VisualStoryValueHelper()

    def attach_visual_story(self, story_plan: dict[str, Any]) -> dict[str, Any]:
        sections = story_plan.get("sections") or []
        visual_story = self._visual_story(story_plan, sections)
        story_plan["visual_story"] = visual_story
        total = max(len(sections), 1)
        previous_object: str | None = None
        for index, section in enumerate(sections):
            state = self._story_state(section, index, total, previous_object)
            section["concept_type"] = self._concept_type(section)
            section["visual_story"] = visual_story
            section["story_state"] = state
            active = state.get("active_objects") or []
            previous_object = str(active[0]) if active else previous_object
        return story_plan

    def enrich_section_from_visual_plan(self, section: dict[str, Any], visual_story: dict[str, Any] | None = None) -> dict[str, Any]:
        """Refresh story state after VisualDirector has produced typed visual data."""
        concept_type = self._concept_type(section)
        section["concept_type"] = concept_type
        directed_data = self._extract_directed_data(section)
        existing_state = section.get("story_state") if isinstance(section.get("story_state"), dict) else {}
        active_objects = self._objects_for_concept(concept_type, str(section.get("text") or ""))
        money_from, money_to = self._money_state(section, str(section.get("text") or ""), concept_type, directed_data)
        scene_role = self._scene_role(concept_type, 0, 1)
        protagonist_state = self._protagonist_state(concept_type, scene_role)
        emotion_from, emotion_to = self._emotion_state(protagonist_state, scene_role)
        enriched_state = {
            **existing_state,
            "scene_role": scene_role,
            "protagonist_state": protagonist_state,
            "active_objects": active_objects,
            "state_change": {
                "money": {
                    "from": money_from or "",
                    "to": money_to or "",
                    "change_label": self._money_change_label(concept_type, money_from, money_to, directed_data),
                },
                "emotion": {"from": emotion_from, "to": emotion_to},
                "risk": self._risk_change(concept_type),
            },
            "visual_question": self._visual_question(concept_type, active_objects, str(section.get("text") or ""), directed_data),
            "visual_answer": self._visual_answer(concept_type, active_objects, money_from, money_to, directed_data),
        }
        if enriched_state.get("callback_to") not in active_objects:
            enriched_state["callback_to"] = active_objects[0] if active_objects else None
        section["story_state"] = enriched_state
        if visual_story is not None:
            section["visual_story"] = visual_story
        self._inject_story_state_into_visual_plan(section)
        return section

    def _visual_story(self, story_plan: dict[str, Any], sections: list[dict[str, Any]]) -> dict[str, Any]:
        all_text = " ".join(str(section.get("text") or "") for section in sections)
        start_amount = self._first_money(all_text)
        goal_label = self._goal_label(story_plan, all_text, start_amount)
        recurring_objects = self._recurring_objects(sections)
        opening_emotion = "hopeful" if start_amount else "confused"
        ending_emotion = "confident" if any(obj in recurring_objects for obj in ("sip_jar", "portfolio_grid", "emergency_buffer")) else "aware"
        return {
            "protagonist": {
                "role": "young_salaried_professional",
                "visual_id": "protagonist_01",
                "emotional_state": opening_emotion,
            },
            "goal": {
                "label": goal_label,
                "target_amount": start_amount,
                "desired_outcome": "keep more money by giving every rupee a job before spending begins",
            },
            "recurring_objects": recurring_objects,
            "opening_state": {
                "money": start_amount or "",
                "emotion": opening_emotion,
                "system": "unclear",
            },
            "ending_state": {
                "emotion": ending_emotion,
                "system": "money has a visible plan",
            },
        }

    def _story_state(
        self,
        section: dict[str, Any],
        index: int,
        total: int,
        previous_object: str | None,
    ) -> dict[str, Any]:
        concept_type = self._concept_type(section)
        text = str(section.get("text") or "")
        active_objects = self._objects_for_concept(concept_type, text)
        scene_role = self._scene_role(concept_type, index, total)
        protagonist_state = self._protagonist_state(concept_type, scene_role)
        money_from, money_to = self._money_state(section, text)
        emotion_from, emotion_to = self._emotion_state(protagonist_state, scene_role)
        callback_from = previous_object if previous_object and previous_object not in active_objects else None
        callback_to = active_objects[0] if active_objects else None
        return {
            "scene_role": scene_role,
            "protagonist_state": protagonist_state,
            "active_objects": active_objects,
            "state_change": {
                "money": {
                    "from": money_from or "",
                    "to": money_to or "",
                    "change_label": self._money_change_label(concept_type, money_from, money_to),
                },
                "emotion": {"from": emotion_from, "to": emotion_to},
                "risk": self._risk_change(concept_type),
            },
            "callback_from": callback_from,
            "callback_to": callback_to,
            "visual_question": self._visual_question(concept_type, active_objects, text),
            "visual_answer": self._visual_answer(concept_type, active_objects, money_from, money_to),
        }

    def _recurring_objects(self, sections: list[dict[str, Any]]) -> list[str]:
        counts: dict[str, int] = {}
        for section in sections:
            for obj in self._objects_for_concept(self._concept_type(section), str(section.get("text") or "")):
                counts[obj] = counts.get(obj, 0) + 1
        ranked = [obj for obj, count in sorted(counts.items(), key=lambda item: item[1], reverse=True) if count >= 2]
        if not ranked:
            ranked = [obj for obj, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:2]]
        return ranked or ["phone_account", "salary_balance"]

    def _objects_for_concept(self, concept_type: str, text: str) -> list[str]:
        mapped = self.CONCEPT_TO_OBJECTS.get(concept_type)
        if mapped:
            return list(mapped)
        mapped = self.CONCEPT_TO_OBJECTS.get(str(concept_type or "").lower())
        if mapped:
            return list(mapped)
        return self._objects_from_text_fallback(text)

    def _objects_from_text_fallback(self, text: str) -> list[str]:
        lowered = str(text or "").lower()
        objects: list[str] = []
        if any(token in lowered for token in ("salary", "income", "rent", "expense", "lifestyle", "drain", "leak")):
            objects.extend(["phone_account", "salary_balance"])
        if any(token in lowered for token in ("emi", "loan")):
            objects.append("emi_stack")
        if any(token in lowered for token in ("debt", "credit card", "minimum payment", "minimum due", "outstanding balance")):
            objects.append("debt_pressure")
        if "inflation" in lowered or "purchasing power" in lowered:
            objects.append("inflation_basket")
        if "sip" in lowered or "compound" in lowered or "monthly investment" in lowered:
            objects.append("sip_jar")
        if any(token in lowered for token in ("diversification", "risk_return", "portfolio", "stock", "equity", "fd", "fomo", "speculation")):
            objects.append("portfolio_grid")
        if "emergency" in lowered or "buffer" in lowered:
            objects.append("emergency_buffer")
        return self._dedupe([obj for obj in objects if obj in self.OBJECTS])

    def _scene_role(self, concept_type: str, index: int, total: int) -> str:
        concept_role = self.CONCEPT_TO_SCENE_ROLE.get(concept_type)
        if total == 1:
            return concept_role or "mechanism"
        if concept_role:
            return concept_role
        if index == 0:
            return "setup"
        if index >= total - 1:
            return "resolution"
        return "turning_point"

    def _protagonist_state(self, concept_type: str, scene_role: str) -> str:
        if scene_role == "setup":
            return "calm"
        if concept_type in {"salary_drain", "salary_depletion", "lifestyle_inflation", "expense_leakage"}:
            return "tempted"
        if concept_type in {"emi_pressure", "debt_trap"}:
            return "stressed"
        if concept_type in {"fomo_risk", "speculation_risk"}:
            return "aware"
        if scene_role in {"mechanism", "turning_point"}:
            return "aware"
        if scene_role == "solution":
            return "disciplined"
        return "confident"

    def _money_state(
        self,
        section: dict[str, Any],
        text: str,
        concept_type: str | None = None,
        directed_data: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        concept_type = concept_type or self._concept_type(section)
        directed_data = directed_data or {}
        from_directed, to_directed = self._money_state_from_directed_data(concept_type, directed_data)
        if from_directed:
            return from_directed, to_directed
        finance_concept = section.get("finance_concept") or {}
        start = str(finance_concept.get("start_value") or "").strip()
        end = str(finance_concept.get("end_value") or "").strip()
        values = self._money_values(text)
        if not start and values:
            start = values[0]
        if not end and len(values) > 1:
            end = values[-1]
        return start, end

    def _emotion_state(self, protagonist_state: str, scene_role: str) -> tuple[str, str]:
        if scene_role == "setup":
            return "hopeful", "curious"
        if protagonist_state in {"tempted", "stressed"}:
            return "calm", "anxious"
        if protagonist_state == "aware":
            return "confused", "clear"
        if protagonist_state == "disciplined":
            return "anxious", "relieved"
        return "aware", "confident"

    def _risk_change(self, concept_type: str) -> dict[str, str]:
        if concept_type in {"debt_trap", "emi_pressure"}:
            return {"from": "hidden", "to": "visible"}
        if concept_type in {"diversification", "risk_return", "fomo_risk", "speculation_risk"}:
            return {"from": "concentrated", "to": "spread"}
        if concept_type == "recap_system":
            return {"from": "scattered", "to": "planned"}
        if concept_type in {"sip_growth", "compounding", "emergency_fund"}:
            return {"from": "reactive", "to": "planned"}
        return {"from": "", "to": ""}

    def _visual_question(
        self,
        concept_type: str,
        active_objects: list[str],
        text: str = "",
        directed_data: dict[str, Any] | None = None,
    ) -> str:
        directed_data = directed_data or {}
        lowered = " ".join([str(text or ""), str(directed_data.get("title") or "")]).lower()
        if concept_type == "lifestyle_inflation" and any(token in lowered for token in ("emi", "monthly payment", "luxury car", "car loan")):
            return "How does one EMI become a lifestyle upgrade?"
        if concept_type in self.CONCEPT_VISUAL_QUESTIONS:
            return self.CONCEPT_VISUAL_QUESTIONS[concept_type]
        if "salary_balance" in active_objects:
            return "Where did the salary go?"
        if "debt_pressure" in active_objects:
            return "Why does paying still not reduce the pressure?"
        if "inflation_basket" in active_objects:
            return "Why does the same balance buy less?"
        if "sip_jar" in active_objects:
            return "What changes when time starts working?"
        if "portfolio_grid" in active_objects:
            return "What happens when one bet becomes a system?"
        return f"What changes in {concept_type.replace('_', ' ')}?"

    def _visual_answer(
        self,
        concept_type: str,
        active_objects: list[str],
        money_from: str,
        money_to: str,
        directed_data: dict[str, Any] | None = None,
    ) -> str:
        directed_data = directed_data or {}
        answer = self._concept_answer(concept_type, money_from, money_to, directed_data)
        if answer:
            return answer
        if money_from and money_to and money_from != money_to:
            return f"{money_from} becomes {money_to}"
        if "portfolio_grid" in active_objects:
            return "one fragile bet becomes a spread portfolio"
        if "sip_jar" in active_objects:
            return "small investments create a growing corpus"
        if "inflation_basket" in active_objects:
            return "buying power keeps shrinking"
        if "debt_pressure" in active_objects:
            return "interest pressure stays visible"
        answers = {
            "salary_drain": "salary drains through fixed costs",
            "lifestyle_inflation": "expenses rise with income",
            "emi_pressure": "small payments stack into one leak",
            "debt_trap": "interest beats the payment",
            "inflation_erosion": "buying power keeps shrinking",
            "sip_growth": "small investments create a growing corpus",
            "diversification": "one fragile bet becomes a spread portfolio",
            "recap_system": "leaks get tracked, buffers protect, investments compound",
        }
        if concept_type == "lifestyle_inflation" and str(directed_data.get("title") or "").lower().startswith("the emi"):
            return "the EMI pulls extra lifestyle costs behind it"
        return answers.get(concept_type, "the money state becomes visible")

    def _money_change_label(
        self,
        concept_type: str,
        money_from: str,
        money_to: str,
        directed_data: dict[str, Any] | None = None,
    ) -> str:
        directed_data = directed_data or {}
        if concept_type in {"salary_drain", "salary_depletion"} and money_from and money_to:
            return f"{money_from} salary → {money_to} left"
        if concept_type == "inflation_erosion" and money_from and money_to:
            return f"{money_from} today → {money_to} buying power"
        if concept_type in {"sip_growth", "compounding", "compound_growth"} and money_from and money_to:
            return f"{money_from}/month → {money_to} corpus"
        if concept_type == "debt_trap" and money_from and money_to:
            return f"{money_from} debt → {money_to}"
        if concept_type == "emi_pressure" and money_from:
            return f"{money_from} leaves before the month begins"
        if money_from and money_to and money_from != money_to:
            return f"{money_from} -> {money_to}"
        labels = {
            "salary_drain": "salary drains",
            "salary_depletion": "salary drains",
            "lifestyle_inflation": "savings gap stays flat",
            "emi_pressure": "fixed payments stack",
            "debt_trap": "balance resists payoff",
            "inflation_erosion": "real value falls",
            "sip_growth": "corpus grows",
            "recap_system": "money gets a system",
            "diversification": "risk spreads",
            "fomo_risk": "emotion drives the trade",
            "speculation_risk": "emotion drives the trade",
        }
        return labels.get(concept_type, "state changes")

    def _goal_label(self, story_plan: dict[str, Any], text: str, start_amount: str) -> str:
        hook = str(story_plan.get("hook") or "").strip()
        if start_amount and "salary" in text.lower():
            return f"make {start_amount} last beyond day 20"
        if hook:
            return hook[:90]
        return "turn money confusion into a visible plan"

    def _concept_type(self, section: dict[str, Any]) -> str:
        finance_concept = section.get("finance_concept") or {}
        concepts = section.get("concepts") or []
        first_concept = concepts[0] if concepts else {}
        concept_type = str(
            section.get("concept_type")
            or finance_concept.get("concept_type")
            or first_concept.get("type")
            or section.get("idea_type")
            or "definition"
        ).strip()
        if concept_type in {"", "definition", "emphasis", "process", "risk", "growth", "decay"}:
            inferred = self._concept_from_text(str(section.get("text") or ""))
            if inferred:
                return inferred
        return concept_type

    def _concept_from_text(self, text: str) -> str:
        lowered = text.lower()
        if lowered.startswith("recap") or ("break free" in lowered and "future self" in lowered):
            return "recap_system"
        if "lifestyle inflation" in lowered or "lifestyle" in lowered or "upgrade" in lowered:
            return "lifestyle_inflation"
        if "salary" in lowered and any(token in lowered for token in ("drain", "gone", "disappear", "left", "rent", "expense", "breathing", "day 20")):
            return "salary_drain"
        if "credit card" in lowered or "minimum payment" in lowered or "minimum due" in lowered:
            return "debt_trap"
        if "emi" in lowered or "instalment" in lowered or "installment" in lowered:
            return "emi_pressure"
        if "sip" in lowered:
            return "sip_growth"
        if "compound" in lowered or "compounding" in lowered:
            return "compounding"
        if "inflation" in lowered or "purchasing power" in lowered or "buying power" in lowered:
            return "inflation_erosion"
        if "emergency" in lowered or "cash buffer" in lowered or "six-month" in lowered:
            return "emergency_fund"
        if (
            "fomo" in lowered
            or "speculation" in lowered
            or "enter late" in lowered
            or "panic" in lowered
            or "emotion wearing" in lowered
            or "cannot explain" in lowered
            or "do not understand" in lowered
            or "don't understand" in lowered
        ):
            return "fomo_risk"
        if "diversification" in lowered or "portfolio" in lowered or "one stock" in lowered or "one basket" in lowered:
            return "diversification"
        return ""

    def _extract_directed_data(self, section: dict[str, Any]) -> dict[str, Any]:
        visual_plan = section.get("visual_plan") or []
        if not visual_plan:
            return {}
        visual_data = (visual_plan[0].get("visual") or {}).get("data")
        if isinstance(visual_data, dict) and visual_data:
            return dict(visual_data)
        beats = (visual_plan[0].get("beats") or {}).get("beats") or []
        for beat in beats:
            data = beat.get("data")
            if isinstance(data, dict) and data:
                return dict(data)
        return {}

    def _money_state_from_directed_data(self, concept_type: str, data: dict[str, Any]) -> tuple[str, str]:
        if not data:
            return "", ""
        if concept_type in {"salary_drain", "salary_depletion"}:
            return self._as_text(self._read_nested(data, "source.value")), self._as_text(self._read_nested(data, "remainder.value"))
        if concept_type in {"sip_growth", "compounding", "compound_growth"}:
            return self._as_text(self._read_nested(data, "monthly_sip.value")), self._format_money_like(self._read_nested(data, "final_corpus"))
        if concept_type == "debt_trap":
            return self._as_text(self._read_nested(data, "principal.value")), self._format_money_like(self._read_nested(data, "month_12_balance"))
        if concept_type == "inflation_erosion":
            return self._as_text(data.get("start")), self._as_text(data.get("end"))
        if concept_type == "emi_pressure":
            return self._first_money(str(data.get("title") or "")) or self._as_text(data.get("start")), self._as_text(data.get("end"))
        return "", ""

    def _concept_answer(self, concept_type: str, money_from: str, money_to: str, data: dict[str, Any]) -> str:
        if concept_type in {"salary_drain", "salary_depletion"} and money_from and money_to:
            return f"{money_from} salary becomes {money_to} by month end"
        if concept_type == "emi_pressure" and money_from:
            return f"{money_from} leaves before the month begins"
        if concept_type == "debt_trap":
            monthly_interest = self._format_money_like(data.get("monthly_interest")) if data else ""
            minimum_payment = self._format_money_like(data.get("minimum_payment")) if data and data.get("minimum_payment") else ""
            if monthly_interest and minimum_payment:
                return f"{minimum_payment} payment cannot beat {monthly_interest} interest"
            if money_to:
                return f"balance can grow to {money_to}"
            return "minimum payment cannot beat the interest"
        if concept_type == "inflation_erosion" and money_from and money_to:
            return f"{money_from} today buys like {money_to}"
        if concept_type in {"sip_growth", "compounding", "compound_growth"}:
            years = self._as_text(data.get("duration_years"))
            if money_from and money_to and years:
                return f"{money_from}/month becomes {money_to} over {years} years"
            return "small consistent investment creates a large corpus"
        if concept_type == "emergency_fund":
            return "buffer absorbs the shock without breaking the plan"
        if concept_type in {"fomo_risk", "speculation_risk"}:
            return "emotion stops pretending to be a strategy"
        if concept_type in {"diversification", "risk_return"}:
            return "one fragile bet becomes a spread portfolio"
        if concept_type == "recap_system":
            return "leaks get tracked, buffers protect, investments compound"
        return ""

    def _inject_story_state_into_visual_plan(self, section: dict[str, Any]) -> None:
        visual_plan = section.get("visual_plan") or []
        if not visual_plan:
            return
        story_state = dict(section.get("story_state") or {})
        visual_story = dict(section.get("visual_story") or {})
        for item in visual_plan:
            visual = item.get("visual")
            if isinstance(visual, dict):
                intent = visual.get("cinematic_intent")
                if isinstance(intent, dict):
                    active_objects = story_state.get("active_objects") or []
                    visual_answer = str(story_state.get("visual_answer") or "").strip()
                    if visual_answer:
                        intent["overlay_text"] = visual_answer
                    intent["active_object"] = str(active_objects[0]) if active_objects else ""
                    intent["visual_question"] = str(story_state.get("visual_question") or "")
                    intent["protagonist_state"] = str(story_state.get("protagonist_state") or "")
                    intent["scene_role"] = str(story_state.get("scene_role") or "")
                data = visual.get("data")
                if isinstance(data, dict):
                    data["story_state"] = story_state
                    if visual_story:
                        data["visual_story"] = visual_story
            beats = (item.get("beats") or {}).get("beats") or []
            for beat in beats:
                data = beat.get("data")
                if isinstance(data, dict):
                    data["story_state"] = story_state
                    if visual_story:
                        data["visual_story"] = visual_story
        section_intent = section.get("cinematic_intent")
        if isinstance(section_intent, dict):
            visual_answer = str(story_state.get("visual_answer") or "").strip()
            if visual_answer:
                section_intent["overlay_text"] = visual_answer
            active_objects = story_state.get("active_objects") or []
            section_intent["active_object"] = str(active_objects[0]) if active_objects else ""
            section_intent["visual_question"] = str(story_state.get("visual_question") or "")
            section_intent["protagonist_state"] = str(story_state.get("protagonist_state") or "")
            section_intent["scene_role"] = str(story_state.get("scene_role") or "")

    def _read_nested(self, data: dict[str, Any], path: str) -> Any:
        return self.value_helper.read_nested(data, path)

    def _as_text(self, value: Any) -> str:
        return self.value_helper.as_text(value)

    def _format_money_like(self, value: Any) -> str:
        return self.value_helper.format_money_like(value)

    def _first_money(self, text: str) -> str:
        return self.value_helper.first_money(text)

    def _money_values(self, text: str) -> list[str]:
        return self.value_helper.money_values(text)

    def _dedupe(self, items: list[str]) -> list[str]:
        return self.value_helper.dedupe(items)
