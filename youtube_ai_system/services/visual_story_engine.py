from __future__ import annotations

import re
from typing import Any


class VisualStoryEngine:
    """Builds a deterministic video-level visual story world for finance scenes."""

    OBJECTS = {
        "phone_account",
        "salary_balance",
        "emi_stack",
        "debt_pressure",
        "inflation_basket",
        "sip_jar",
        "portfolio_grid",
        "emergency_buffer",
    }

    def attach_visual_story(self, story_plan: dict[str, Any]) -> dict[str, Any]:
        sections = story_plan.get("sections") or []
        visual_story = self._visual_story(story_plan, sections)
        story_plan["visual_story"] = visual_story
        total = max(len(sections), 1)
        previous_object: str | None = None
        for index, section in enumerate(sections):
            state = self._story_state(section, index, total, previous_object)
            section["visual_story"] = visual_story
            section["story_state"] = state
            active = state.get("active_objects") or []
            previous_object = str(active[0]) if active else previous_object
        return story_plan

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
            "visual_question": self._visual_question(concept_type, active_objects),
            "visual_answer": self._visual_answer(concept_type, active_objects, money_from, money_to),
        }

    def _recurring_objects(self, sections: list[dict[str, Any]]) -> list[str]:
        objects: list[str] = []
        seen: set[str] = set()
        for section in sections:
            for obj in self._objects_for_concept(self._concept_type(section), str(section.get("text") or "")):
                if obj not in seen:
                    seen.add(obj)
                    objects.append(obj)
        if not objects:
            objects = ["phone_account", "salary_balance"]
        return objects

    def _objects_for_concept(self, concept_type: str, text: str) -> list[str]:
        lowered = f"{concept_type} {text}".lower()
        objects: list[str] = []
        if any(token in lowered for token in ("salary", "income", "rent", "expense", "lifestyle", "drain", "leak")):
            objects.extend(["phone_account", "salary_balance"])
        if any(token in lowered for token in ("emi", "loan")):
            objects.append("emi_stack")
        if any(token in lowered for token in ("debt", "credit card", "minimum payment", "interest")):
            objects.append("debt_pressure")
        if "inflation" in lowered or "purchasing power" in lowered:
            objects.append("inflation_basket")
        if "sip" in lowered or "compound" in lowered or "invest" in lowered:
            objects.append("sip_jar")
        if any(token in lowered for token in ("diversification", "risk_return", "portfolio", "stock", "equity", "fd", "fomo", "speculation")):
            objects.append("portfolio_grid")
        if "emergency" in lowered or "buffer" in lowered:
            objects.append("emergency_buffer")
        return self._dedupe([obj for obj in objects if obj in self.OBJECTS])

    def _scene_role(self, concept_type: str, index: int, total: int) -> str:
        if index == 0:
            return "setup"
        if index >= total - 1:
            return "resolution"
        if concept_type in {"salary_drain", "lifestyle_inflation", "expense_leakage", "emi_pressure", "debt_trap"}:
            return "pressure"
        if concept_type in {"inflation_erosion", "real_return", "fd_vs_inflation", "risk_return", "diversification"}:
            return "mechanism"
        if concept_type in {"sip_growth", "compounding", "emergency_fund", "savings_rate"}:
            return "solution"
        return "turning_point" if index >= max(1, int(total * 0.6)) else "mechanism"

    def _protagonist_state(self, concept_type: str, scene_role: str) -> str:
        if scene_role == "setup":
            return "calm"
        if concept_type in {"salary_drain", "lifestyle_inflation", "expense_leakage"}:
            return "tempted"
        if concept_type in {"emi_pressure", "debt_trap"}:
            return "stressed"
        if scene_role in {"mechanism", "turning_point"}:
            return "aware"
        if scene_role == "solution":
            return "disciplined"
        return "confident"

    def _money_state(self, section: dict[str, Any], text: str) -> tuple[str, str]:
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
        if concept_type in {"diversification", "risk_return"}:
            return {"from": "concentrated", "to": "spread"}
        if concept_type in {"sip_growth", "compounding", "emergency_fund"}:
            return {"from": "reactive", "to": "planned"}
        return {"from": "", "to": ""}

    def _visual_question(self, concept_type: str, active_objects: list[str]) -> str:
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

    def _visual_answer(self, concept_type: str, active_objects: list[str], money_from: str, money_to: str) -> str:
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
        }
        return answers.get(concept_type, "the money state becomes visible")

    def _money_change_label(self, concept_type: str, money_from: str, money_to: str) -> str:
        if money_from and money_to and money_from != money_to:
            return f"{money_from} -> {money_to}"
        labels = {
            "salary_drain": "salary drains",
            "lifestyle_inflation": "savings gap stays flat",
            "emi_pressure": "fixed payments stack",
            "debt_trap": "balance resists payoff",
            "inflation_erosion": "real value falls",
            "sip_growth": "corpus grows",
            "diversification": "risk spreads",
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
        visual_scene = section.get("visual_scene") or {}
        finance_concept = section.get("finance_concept") or {}
        concepts = section.get("concepts") or []
        first_concept = concepts[0] if concepts else {}
        return str(
            section.get("concept_type")
            or visual_scene.get("mechanism")
            or finance_concept.get("concept_type")
            or first_concept.get("type")
            or section.get("idea_type")
            or "definition"
        ).strip()

    def _first_money(self, text: str) -> str:
        values = self._money_values(text)
        return values[0] if values else ""

    def _money_values(self, text: str) -> list[str]:
        pattern = re.compile(r"(?:₹\s*|Rs\.?\s*)\d[\d,]*(?:\.\d+)?\s*(?:lakh|lakhs|crore|crores|k)?", re.IGNORECASE)
        return [match.group(0).replace(" ", "") for match in pattern.finditer(text)]

    def _dedupe(self, items: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result
