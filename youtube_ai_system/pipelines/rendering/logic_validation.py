from __future__ import annotations

from typing import Any

from .context_gate import RenderContextGate
from .logic_text import RenderLogicTextFormatter
from .visual_gate import RenderVisualGate


class RenderLogicValidator:
    """Validation rules for typed render visual-logic objects."""

    def __init__(
        self,
        schema: dict[str, tuple[str, ...]],
        *,
        context_gate: RenderContextGate,
        logic_text: RenderLogicTextFormatter,
        visual_gate: RenderVisualGate,
    ) -> None:
        self.schema = schema
        self.context_gate = context_gate
        self.logic_text = logic_text
        self.visual_gate = visual_gate

    def logic_type(self, visual_logic: Any) -> str:
        if isinstance(visual_logic, dict):
            return str(visual_logic.get("type") or "").strip().lower()
        return ""

    def typed_visual_logic_is_valid(self, visual_logic: Any) -> bool:
        if not isinstance(visual_logic, dict):
            return False
        logic_type = self.logic_type(visual_logic)
        required = self.schema.get(logic_type)
        if not required:
            return False
        if not all(str(visual_logic.get(key) or "").strip() for key in required):
            return False
        text = self.logic_text.visual_logic_to_text(visual_logic, logic_type=logic_type)
        if self.visual_gate.is_abstract_visual_logic(text) or not self.visual_gate.has_number(text) or not self.visual_gate.has_impact(text):
            return False
        if logic_type == "comparison":
            return (
                self.visual_gate.has_number(str(visual_logic.get("left") or ""))
                and self.visual_gate.has_number(str(visual_logic.get("right") or ""))
                and self.context_gate.comparison_units_match(visual_logic)
            )
        if logic_type == "emphasis":
            return self.visual_gate.has_number(text) and self.visual_gate.has_impact(text)
        if logic_type == "flow" and not self.flow_semantically_valid(visual_logic):
            return False
        if logic_type in {"flow", "decay", "growth"}:
            return self.visual_gate.has_visual_structure(text) and all(
                self.visual_gate.has_number(str(visual_logic.get(key) or "")) for key in required
            )
        return True

    def flow_semantically_valid(self, visual_logic: dict[str, Any]) -> bool:
        source = str(visual_logic.get("source") or "")
        process = str(visual_logic.get("process") or "")
        result = str(visual_logic.get("result") or "")
        lowered = f"{source} {process} {result}".lower()
        if any(word in lowered for word in ("salary", "income", "paycheck")):
            return (
                any(word in source.lower() for word in ("salary", "income", "paycheck"))
                and any(
                    word in process.lower()
                    for word in (
                        "expense",
                        "expenses",
                        "tax",
                        "spend",
                        "spent",
                        "emi",
                        "rent",
                        "day",
                        "leak",
                        "lost",
                        "loss",
                        "vanish",
                    )
                )
                and any(word in result.lower() for word in ("left", "saving", "savings", "leak", "loss", "lost"))
            )
        values = [
            self.context_gate.number_utils.first_numeric_value(part)
            for part in (source, process, result)
        ]
        money_parts = [part for part in (source, process, result) if "₹" in part]
        if len(money_parts) == 3 and all(value > 0 for value in values):
            return values[0] >= values[1] >= values[2] or values[0] <= values[1] <= values[2]
        return True

    def logic_can_reach_render(self, visual_logic: Any, beat: dict[str, Any]) -> bool:
        if not self.typed_visual_logic_is_valid(visual_logic):
            return False
        logic_type = self.logic_type(visual_logic)
        text = self.logic_text.visual_logic_to_text(visual_logic, logic_type=logic_type)
        if self.visual_gate.contains_generic_visual_words(text):
            return False
        if logic_type in {"flow", "comparison"}:
            return True
        return logic_type == "emphasis" and str(beat.get("intent") or "").upper() in {"HOOK", "EMPHASIS"}
