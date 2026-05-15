from __future__ import annotations

import re
from typing import Any

from ...services.visual_logic_engine import map_concept_to_visual


class StoryArcSupportMixin:
    def _warn_on_section_flow(self, sections: list[dict[str, Any]]) -> None:
        try:
            self.story_intelligence._validate_section_flow(sections)
        except ValueError as exc:
            self.logger.log("story_planning", "warning", str(exc))

    def _narrative_arc_for_section(self, section: dict[str, Any]) -> dict[str, Any]:
        text = str(section.get("text") or "")
        finance_concept = dict(section.get("finance_concept") or {})
        concept = self._primary_visual_concept(section)
        concept_name = str(concept.get("concept") or finance_concept.get("concept_name") or "Money Change").strip()
        concept_type = str(concept.get("type") or finance_concept.get("concept_type") or "definition").strip()
        numeric_phrases = self.numeric_phrases(text)
        start_value = str(finance_concept.get("start_value") or (numeric_phrases[0] if numeric_phrases else "")).strip()
        end_value = str(finance_concept.get("end_value") or (numeric_phrases[-1] if len(numeric_phrases) > 1 else "")).strip()
        start_value = self._visual_state_value(start_value)
        end_value = self._visual_state_value(end_value)
        rate = self._rate_value(finance_concept, numeric_phrases)
        visual_type = self._visual_type_for_section(section, concept_type, numeric_phrases, rate)
        process = self._arc_process(finance_concept, text, rate)

        return {
            "visual_type": visual_type,
            "visual_pattern": self._semantic_visual_pattern(visual_type, concept_name),
            "render_pattern": self._render_pattern_for_visual_type(visual_type, concept_type),
            "story_goal": self._story_goal(concept_name, start_value, process, end_value or rate),
            "start_state": start_value,
            "process": process,
            "end_state": end_value,
            "rate": rate,
            "punch": self._arc_punch(text, concept_name),
            "numeric_values": numeric_phrases[:3],
            "has_causation": bool(section.get("has_causation")),
            "has_comparison": bool(section.get("has_comparison")),
        }

    def _primary_visual_concept(self, section: dict[str, Any]) -> dict[str, str]:
        concepts = section.get("concepts") or []
        if concepts:
            concept = dict(concepts[0])
            concept_text = str(concept.get("concept") or "Money Change")
            if concept_text == "Money Change":
                inferred = self._concept_from_section_text(str(section.get("text") or ""))
                if inferred:
                    return inferred
            return {
                "concept": concept_text,
                "type": str(concept.get("type") or "definition"),
            }
        finance_concept = dict(section.get("finance_concept") or {})
        concept_name = str(finance_concept.get("concept_name") or "Money Change").strip()
        concept_type = str(finance_concept.get("concept_type") or "definition").strip()
        if concept_name in {"Unknown", "Money Change"}:
            inferred = self._concept_from_section_text(str(section.get("text") or ""))
            if inferred:
                return inferred
        return {"concept": concept_name if concept_name != "Unknown" else "Money Change", "type": concept_type}

    def _concept_from_section_text(self, text: str) -> dict[str, str] | None:
        lowered = text.lower()
        if "salary" in lowered and any(token in lowered for token in ("vanish", "disappear", "gone", "drain", "left")):
            return {"concept": "Salary Depletion", "type": "risk"}
        if "emi" in lowered:
            return {"concept": "EMI Pressure", "type": "risk"}
        if "debt" in lowered and "interest" in lowered:
            return {"concept": "Debt Trap", "type": "risk"}
        if "inflation" in lowered:
            return {"concept": "Inflation Erosion", "type": "risk"}
        if "sip" in lowered or "compound" in lowered:
            return {"concept": "Compounding Growth", "type": "growth"}
        return None

    def _visual_from_narrative_arc(self, section: dict[str, Any]) -> dict[str, Any]:
        arc = dict(section.get("narrative_arc") or {})
        concept = self._primary_visual_concept(section)
        render_pattern = str(arc.get("render_pattern") or "").strip()
        if render_pattern == "NumericComparison":
            values = [value for value in arc.get("numeric_values") or [] if str(value).strip()]
            if not values:
                values = [value for value in (arc.get("start_state"), arc.get("rate"), arc.get("end_state")) if str(value or "").strip()]
            if not values:
                return {"pattern": "ConceptCard", "data": {"title": str(concept.get("concept") or "Money Change").upper()}}
            return {"pattern": "NumericComparison", "data": {"values": values}}

        try:
            visual = map_concept_to_visual(concept)
        except (ValueError, TypeError):
            visual = {"pattern": "ConceptCard", "data": {"title": str(concept.get("concept") or "Money Change").upper()}}
        if render_pattern:
            visual["pattern"] = render_pattern
            visual["data"] = self._data_for_render_pattern(render_pattern, concept, arc, visual.get("data") or {})
        return visual

    def _beats_from_narrative_arc(self, section: dict[str, Any]) -> list[dict[str, Any]]:
        arc = dict(section.get("narrative_arc") or {})
        concept = self._primary_visual_concept(section)
        concept_name = str(concept.get("concept") or "Money Change")
        concept_type = str(concept.get("type") or "definition")
        visual_props = self._visual_props_for_arc(section, arc, concept)
        values = [str(value).strip() for value in arc.get("numeric_values") or [] if str(value).strip()]
        start_state = str(arc.get("start_state") or "").strip()
        end_state = str(arc.get("end_state") or "").strip()
        rate = str(arc.get("rate") or "").strip()
        process = str(arc.get("process") or "").strip()
        punch = str(arc.get("punch") or concept_name).strip()

        if values:
            beats = self._numeric_beats(values, values[-1])
            if visual_props.get("nodes") and len(values) >= 2:
                beats.insert(
                    1,
                    {
                        "component": "FlowBar",
                        "text": self._short_visual_text(str(visual_props.get("title") or "Money flow")),
                        "subtext": "money movement",
                        "props": visual_props,
                    },
                )
            if punch:
                beats.append({"component": "HighlightText", "text": self._short_visual_text(punch), "props": {"title": punch, "subtitle": concept_name}})
            return [beat for beat in beats if self._is_valid_beat(beat)][:6]

        if concept_type == "comparison" or arc.get("has_comparison"):
            beats = [
                {"component": "ConceptCard", "text": self._short_visual_text(concept_name), "props": {"title": concept_name, "subtitle": self._short_visual_text(process)}},
                {"component": "SplitComparison", "text": self._short_visual_text(process or concept_name), "props": visual_props},
                {"component": "HighlightText", "text": self._short_visual_text(punch), "props": {"title": punch, "subtitle": concept_name}},
            ]
            return [beat for beat in beats if self._is_valid_beat(beat)]

        if concept_type == "growth":
            beats = [
                {"component": "StatCard", "text": self._short_visual_text(start_state or "Start small"), "subtext": "start"},
                {"component": "GrowthChart", "text": self._short_visual_text(process or concept_name), "props": visual_props},
                {"component": "StatCard", "text": self._short_visual_text(end_state or "Growth builds"), "subtext": "result"},
                {"component": "HighlightText", "text": self._short_visual_text(punch), "props": {"title": punch, "subtitle": concept_name}},
            ]
            return [beat for beat in beats if self._is_valid_beat(beat)]

        if concept_type == "risk" or arc.get("has_causation"):
            middle_component = "BalanceBar" if visual_props.get("left") and visual_props.get("right") else "FlowBar"
            beats = [
                {"component": "StatCard" if start_state else "ConceptCard", "text": self._short_visual_text(start_state or concept_name), "props": {"title": concept_name, "subtitle": process}},
                {"component": middle_component, "text": self._short_visual_text(rate or process or "Pressure rises"), "props": visual_props},
                {"component": "FlowBar", "text": self._short_visual_text(end_state or "Money leaks"), "props": visual_props},
                {"component": "HighlightText", "text": self._short_visual_text(punch), "props": {"title": punch, "subtitle": concept_name}},
            ]
            return [beat for beat in beats if self._is_valid_beat(beat)]

        beats = [
            {"component": "ConceptCard", "text": self._short_visual_text(concept_name), "props": {"title": concept_name, "subtitle": self._short_visual_text(process)}},
            {"component": "FlowBar", "text": self._short_visual_text(process or "Money moves"), "props": visual_props},
            {"component": "HighlightText", "text": self._short_visual_text(punch), "props": {"title": punch, "subtitle": concept_name}},
        ]
        return [beat for beat in beats if self._is_valid_beat(beat)]

    def _visual_props_for_arc(
        self,
        section: dict[str, Any],
        arc: dict[str, Any],
        concept: dict[str, str],
    ) -> dict[str, Any]:
        text = str(section.get("text") or "")
        concept_name = str(concept.get("concept") or "Money Change").strip()
        visual_type = str(arc.get("visual_type") or "concept").strip()
        start_state = str(arc.get("start_state") or "").strip()
        process = str(arc.get("process") or "").strip()
        end_state = str(arc.get("end_state") or "").strip()
        rate = str(arc.get("rate") or "").strip()
        punch = str(arc.get("punch") or concept_name).strip()
        values = [str(value).strip() for value in arc.get("numeric_values") or [] if str(value).strip()]

        if visual_type == "comparison" or arc.get("has_comparison"):
            left, right = self._comparison_pair(text, start_state, end_state, concept_name)
            return {
                "title": self._short_visual_text(concept_name),
                "left": {"label": left},
                "right": {"label": right},
                "connector": "vs",
            }
        if visual_type == "growth":
            return {
                "title": self._short_visual_text(concept_name),
                "start": start_state or (values[0] if values else "Start"),
                "end": end_state or (values[-1] if values else punch),
                "rate": rate or process,
                "curve": "up",
            }
        if visual_type in {"balance_decay", "pressure"}:
            left_value = self._percent_from_text(rate or text) or 65
            return {
                "title": self._short_visual_text(concept_name),
                "left": {"label": self._balance_left_label(text), "value": left_value, "color": "#E63946"},
                "right": {"label": "leftover", "value": max(0, 100 - left_value), "color": "#2EC4B6"},
                "nodes": self._flow_nodes(values, start_state, process, end_state, punch, text),
            }
        return {
            "title": self._short_visual_text(concept_name if concept_name != "Money Change" else self._flow_title(text)),
            "nodes": self._flow_nodes(values, start_state, process, end_state, punch, text),
        }

    def _flow_nodes(
        self,
        values: list[str],
        start_state: str,
        process: str,
        end_state: str,
        punch: str,
        text: str,
    ) -> list[dict[str, str]]:
        if values:
            nodes = []
            labels = ["start", "cost", "result"]
            for index, value in enumerate(values[:4]):
                subtext = self._value_subtext(value)
                if not ("₹" in value or "%" in value or subtext):
                    continue
                nodes.append({"label": subtext or (labels[index] if index < len(labels) else "value"), "value": self._strip_value_label(value), "subtext": subtext})
            if len(nodes) >= 2:
                return nodes
        candidates = [
            ("salary", "Salary", start_state),
            ("emi", "EMI", process),
            ("rent", "Rent", ""),
            ("spending", "Lifestyle", process),
            ("expense", "Expenses", process),
            ("saving", "Savings", end_state),
            ("sip", "SIP", end_state),
            ("debt", "Debt", start_state),
            ("interest", "Interest", process),
        ]
        lowered = text.lower()
        nodes: list[dict[str, str]] = []
        for token, label, value in candidates:
            if token in lowered and label.lower() not in {node["label"].lower() for node in nodes}:
                nodes.append({"label": label, "value": self._strip_value_label(value) or "", "subtext": self._short_visual_text(value)})
            if len(nodes) >= 4:
                break
        if len(nodes) < 2:
            if "salary" in text.lower():
                return [
                    {"label": "Salary", "value": self._strip_value_label(start_state), "subtext": self._value_subtext(start_state)},
                    {"label": "EMI + rent", "value": "", "subtext": "fixed costs"},
                    {"label": "Lifestyle", "value": "", "subtext": "daily leaks"},
                    {"label": "Left", "value": self._strip_value_label(end_state), "subtext": "month-end reality"},
                ]
            nodes = [
                {"label": self._short_visual_text(start_state or "Start"), "value": self._strip_value_label(start_state), "subtext": self._value_subtext(start_state)},
                {"label": self._short_visual_text(process or "Change"), "value": self._strip_value_label(process), "subtext": self._value_subtext(process)},
                {"label": self._short_visual_text(end_state or punch or "Result"), "value": self._strip_value_label(end_state), "subtext": self._value_subtext(end_state)},
            ]
        return [node for node in nodes if str(node.get("label") or node.get("value") or "").strip()][:4]

    def _comparison_pair(self, text: str, start_state: str, end_state: str, concept_name: str) -> tuple[str, str]:
        lowered = text.lower()
        if " vs " in lowered:
            parts = re.split(r"\bvs\b|\bversus\b", text, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                return self._short_visual_text(parts[0]), self._short_visual_text(parts[1])
        if start_state and end_state:
            return self._short_visual_text(start_state), self._short_visual_text(end_state)
        if "before" in lowered and "after" in lowered:
            return "Before", "After"
        if "saving" in lowered and "spending" in lowered:
            return "Saving", "Spending"
        if "fd" in lowered and ("mutual" in lowered or "sip" in lowered):
            return "FD", "Mutual Fund"
        return "Before", self._short_visual_text(concept_name or "After")

    def _percent_from_text(self, text: str) -> int | None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", str(text or ""))
        if not match:
            return None
        return max(0, min(100, int(round(float(match.group(1))))))

    def _balance_left_label(self, text: str) -> str:
        lowered = text.lower()
        if "emi" in lowered:
            return "EMIs"
        if "debt" in lowered:
            return "debt pressure"
        if "rent" in lowered:
            return "fixed costs"
        return "money out"

    def _flow_title(self, text: str) -> str:
        lowered = text.lower()
        if "salary" in lowered:
            return "Where salary goes"
        if "emi" in lowered:
            return "EMI pressure"
        if "debt" in lowered:
            return "Debt flow"
        return "Money movement"

    def _visual_type_for_section(
        self,
        section: dict[str, Any],
        concept_type: str,
        numeric_phrases: list[str],
        rate: str,
    ) -> str:
        lowered = str(section.get("text") or "").lower()
        if "salary" in lowered and any(token in lowered for token in ("vanish", "disappear", "gone", "drain", "left")):
            return "money_flow"
        if concept_type == "comparison" or section.get("has_comparison"):
            return "comparison"
        if concept_type == "growth":
            return "growth"
        if (
            concept_type == "risk"
            and (numeric_phrases or rate)
            and any(token in lowered for token in ("debt", "interest", "minimum", "trap"))
        ):
            return "balance_decay"
        if numeric_phrases and rate:
            return "money_flow"
        if concept_type == "risk":
            return "pressure"
        if section.get("has_causation"):
            return "money_flow"
        return "concept"

    def _semantic_visual_pattern(self, visual_type: str, concept_name: str) -> str:
        lowered = concept_name.lower()
        if visual_type == "balance_decay" and ("debt" in lowered or "interest" in lowered):
            return "debt_growth_spiral"
        if visual_type == "balance_decay":
            return "balance_decay"
        if visual_type == "growth":
            return "growth_curve"
        if visual_type == "comparison":
            return "comparison_split"
        if visual_type == "money_flow":
            return "money_flow"
        if visual_type == "pressure":
            return "pressure_build"
        return "concept_focus"

    def _render_pattern_for_visual_type(self, visual_type: str, concept_type: str) -> str:
        if visual_type in {"balance_decay", "money_flow"}:
            return "NumericComparison"
        if visual_type == "comparison":
            return "SplitComparison"
        if visual_type == "growth":
            return "GrowthChart"
        if visual_type == "pressure":
            return "RiskCard"
        return {
            "risk": "RiskCard",
            "growth": "GrowthChart",
            "comparison": "SplitComparison",
            "process": "StepFlow",
            "definition": "ConceptCard",
        }.get(concept_type, "ConceptCard")

    def _data_for_render_pattern(
        self,
        pattern: str,
        concept: dict[str, str],
        arc: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        concept_name = str(concept.get("concept") or "Money Change")
        if pattern == "RiskCard":
            return {"title": concept_name.upper()}
        if pattern == "GrowthChart":
            return {
                "start": str(arc.get("start_state") or fallback.get("start") or ""),
                "end": str(arc.get("end_state") or concept_name),
                "curve": "up",
            }
        if pattern == "SplitComparison":
            return fallback if fallback else {"left": {"label": "Before"}, "right": {"label": concept_name}}
        if pattern == "StepFlow":
            steps = [value for value in (arc.get("start_state"), arc.get("process"), arc.get("end_state")) if str(value or "").strip()]
            return {"steps": steps or [concept_name]}
        return fallback if fallback else {"title": concept_name.upper()}

    def _state_from_narrative_arc(self, arc: dict[str, Any]) -> dict[str, str]:
        return {
            "money_in": str(arc.get("start_state") or ""),
            "money_out": str(arc.get("rate") or arc.get("process") or ""),
            "balance_change": str(arc.get("end_state") or arc.get("punch") or ""),
        }

    def _rate_value(self, finance_concept: dict[str, Any], numeric_phrases: list[str]) -> str:
        percentage = finance_concept.get("percentage")
        if percentage is not None:
            try:
                return f"{float(percentage):g}%"
            except (TypeError, ValueError):
                pass
        for phrase in numeric_phrases:
            if "%" in phrase:
                return phrase
        return ""

    def _visual_state_value(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if "₹" in text or "%" in text or text.lower().startswith("rs"):
            return text
        if self._value_subtext(text):
            return text
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            return ""
        return text

    def _arc_process(self, finance_concept: dict[str, Any], text: str, rate: str) -> str:
        action = str(finance_concept.get("action") or "").strip()
        concept_name = str(finance_concept.get("concept_name") or "").lower()
        concept_key = str(finance_concept.get("concept_key") or finance_concept.get("concept_type") or "").lower()
        lowered = text.lower()
        if "lifestyle inflation" in concept_name or "lifestyle_inflation" in concept_key or "lifestyle inflation" in lowered:
            return "Lifestyle absorbs raise"
        if "sip growth" in concept_name or "sip" in lowered:
            return "SIP compounds"
        if "fomo" in concept_name or "fomo" in lowered:
            return "Late entry crashes"
        if "salary" in lowered and any(token in lowered for token in ("vanish", "disappear", "gone", "drain", "left")):
            return "Salary drains"
        if "emi" in lowered:
            return "EMI pressure"
        if rate and "interest" in lowered:
            return f"{rate} interest"
        if rate:
            return rate
        if action and action != "changes":
            return action
        if "inflation" in lowered:
            return "Inflation erodes"
        if "spending" in lowered or "expense" in lowered:
            return "Spending leaks"
        if "invest" in lowered or "sip" in lowered:
            return "Investment grows"
        return "Money changes"

    def _story_goal(self, concept_name: str, start_state: str, process: str, end_state: str) -> str:
        pieces = [piece for piece in (start_state, process, end_state) if piece]
        if pieces:
            return f"Show {concept_name}: {' -> '.join(pieces)}"
        return f"Show {concept_name}"

    def _arc_punch(self, text: str, concept_name: str) -> str:
        lowered = text.lower()
        if "lifestyle inflation" in lowered or "lifestyle inflation" in concept_name.lower():
            return "Raise gets absorbed"
        if "debt" in lowered and "interest" in lowered:
            return "Paying to be broke"
        if "salary" in lowered and any(token in lowered for token in ("gone", "vanish", "disappear", "leak")):
            return "Salary disappears early"
        if "inflation" in lowered:
            return "Money loses power"
        if "compound" in lowered or "compounding" in lowered:
            return "Time does the work"
        if "fomo" in lowered:
            return "FOMO is expensive"
        return concept_name
