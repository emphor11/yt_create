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

    CONCEPT_TO_SCENE_ROLE = {
        "salary_drain": "pressure",
        "lifestyle_inflation": "pressure",
        "expense_leakage": "pressure",
        "emi_pressure": "pressure",
        "rent_burden": "pressure",
        "tax_drain": "pressure",
        "subscription_leak": "pressure",
        "debt_trap": "mechanism",
        "inflation_erosion": "mechanism",
        "real_return": "mechanism",
        "fd_vs_inflation": "mechanism",
        "risk_return": "mechanism",
        "diversification": "mechanism",
        "opportunity_cost": "mechanism",
        "sip_growth": "solution",
        "compounding": "solution",
        "compound_growth": "solution",
        "emergency_fund": "solution",
        "savings_rate": "solution",
        "decay": "pressure",
        "growth": "solution",
        "comparison": "mechanism",
        "risk": "mechanism",
        "definition": "mechanism",
        "emphasis": "turning_point",
    }

    CONCEPT_TO_OBJECTS = {
        "salary_drain": ["phone_account", "salary_balance"],
        "lifestyle_inflation": ["phone_account", "salary_balance"],
        "expense_leakage": ["phone_account", "salary_balance"],
        "rent_burden": ["phone_account", "salary_balance"],
        "tax_drain": ["phone_account", "salary_balance"],
        "subscription_leak": ["phone_account", "salary_balance"],
        "emi_pressure": ["emi_stack", "salary_balance"],
        "debt_trap": ["debt_pressure", "phone_account"],
        "inflation_erosion": ["inflation_basket"],
        "real_return": ["inflation_basket", "salary_balance"],
        "fd_vs_inflation": ["inflation_basket", "salary_balance"],
        "sip_growth": ["sip_jar"],
        "compounding": ["sip_jar"],
        "compound_growth": ["sip_jar"],
        "savings_rate": ["sip_jar", "salary_balance"],
        "emergency_fund": ["emergency_buffer"],
        "risk_return": ["portfolio_grid"],
        "diversification": ["portfolio_grid"],
        "opportunity_cost": ["sip_jar", "salary_balance"],
        "decay": ["salary_balance"],
        "growth": ["sip_jar"],
        "comparison": ["phone_account"],
        "risk": ["debt_pressure"],
        "definition": ["phone_account"],
        "emphasis": ["phone_account"],
    }

    CONCEPT_VISUAL_QUESTIONS = {
        "salary_drain": "Where did the salary go?",
        "lifestyle_inflation": "Why does a raise not create savings?",
        "expense_leakage": "What invisible drain is eating the salary?",
        "emi_pressure": "How do small EMIs become one big leak?",
        "debt_trap": "Why does paying not reduce the balance?",
        "inflation_erosion": "Why does the same balance buy less?",
        "real_return": "What is the actual return after inflation?",
        "fd_vs_inflation": "Is the FD actually growing or shrinking?",
        "sip_growth": "What changes when returns start earning returns?",
        "compounding": "Why does time matter more than amount?",
        "compound_growth": "What changes when returns start earning returns?",
        "savings_rate": "How much is actually getting saved each month?",
        "emergency_fund": "What absorbs the next financial shock?",
        "risk_return": "What is the risk that comes with the return?",
        "diversification": "What changes when one bet becomes a system?",
        "opportunity_cost": "What is the cost of not investing?",
    }

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
            "visual_question": self._visual_question(concept_type, active_objects),
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
            "visual_question": self._visual_question(concept_type, active_objects),
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
        if "sip" in lowered or "compound" in lowered or "invest" in lowered:
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
        if concept_type in {"salary_drain", "lifestyle_inflation", "expense_leakage"}:
            return "tempted"
        if concept_type in {"emi_pressure", "debt_trap"}:
            return "stressed"
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
        if concept_type in {"diversification", "risk_return"}:
            return {"from": "concentrated", "to": "spread"}
        if concept_type in {"sip_growth", "compounding", "emergency_fund"}:
            return {"from": "reactive", "to": "planned"}
        return {"from": "", "to": ""}

    def _visual_question(self, concept_type: str, active_objects: list[str]) -> str:
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
        }
        return answers.get(concept_type, "the money state becomes visible")

    def _money_change_label(
        self,
        concept_type: str,
        money_from: str,
        money_to: str,
        directed_data: dict[str, Any] | None = None,
    ) -> str:
        directed_data = directed_data or {}
        if concept_type == "salary_drain" and money_from and money_to:
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
        if "credit card" in lowered or "minimum payment" in lowered or "minimum due" in lowered:
            return "debt_trap"
        if "emi" in lowered or "instalment" in lowered or "installment" in lowered:
            return "emi_pressure"
        if "inflation" in lowered or "purchasing power" in lowered or "buying power" in lowered:
            return "inflation_erosion"
        if "sip" in lowered or "compound" in lowered or "compounding" in lowered:
            return "sip_growth"
        if "emergency" in lowered or "cash buffer" in lowered or "six-month" in lowered:
            return "emergency_fund"
        if "diversification" in lowered or "portfolio" in lowered or "one stock" in lowered or "one basket" in lowered:
            return "diversification"
        if "salary" in lowered and any(token in lowered for token in ("drain", "gone", "disappear", "left", "rent", "expense")):
            return "salary_drain"
        if "lifestyle" in lowered or "upgrade" in lowered:
            return "lifestyle_inflation"
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
        if concept_type == "salary_drain":
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
        if concept_type == "salary_drain" and money_from and money_to:
            return f"{money_from} salary becomes {money_to} by month end"
        if concept_type == "emi_pressure" and money_from:
            return f"{money_from} leaves before the month begins"
        if concept_type == "debt_trap" and money_to:
            return f"paying still leaves {money_to} owed"
        if concept_type == "inflation_erosion" and money_from and money_to:
            return f"{money_from} today buys like {money_to}"
        if concept_type in {"sip_growth", "compounding", "compound_growth"}:
            years = self._as_text(data.get("duration_years"))
            if money_from and money_to and years:
                return f"{money_from}/month becomes {money_to} over {years} years"
            return "small consistent investment creates a large corpus"
        if concept_type == "emergency_fund":
            return "buffer absorbs the shock without breaking the plan"
        if concept_type in {"diversification", "risk_return"}:
            return "one fragile bet becomes a spread portfolio"
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

    def _read_nested(self, data: dict[str, Any], path: str) -> Any:
        value: Any = data
        for part in path.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value

    def _as_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    def _format_money_like(self, value: Any) -> str:
        if value is None or value == "":
            return ""
        if isinstance(value, str):
            return value if "₹" in value else value.strip()
        try:
            amount = float(value)
        except (TypeError, ValueError):
            return str(value)
        rounded = int(round(amount))
        digits = str(abs(rounded))
        if len(digits) <= 3:
            formatted = digits
        else:
            formatted = digits[-3:]
            digits = digits[:-3]
            while digits:
                formatted = digits[-2:] + "," + formatted
                digits = digits[:-2]
        return ("-" if rounded < 0 else "") + "₹" + formatted

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
