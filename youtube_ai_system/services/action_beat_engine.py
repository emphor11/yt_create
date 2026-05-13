from __future__ import annotations

from typing import Any


class ActionBeatEngine:
    """Turns VisualActionGraph actions into micro-beat choreography hints."""

    PRIMARY_COMPONENTS = {
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

    ACTION_PHASES = {
        "salary_arrives": "intro",
        "expense_drains": "drain",
        "balance_revealed": "remainder",
        "contribution_starts": "contribution",
        "contributions_accumulate": "growth",
        "return_rate_activates": "growth",
        "time_extends": "growth",
        "corpus_revealed": "corpus",
        "debt_appears": "principal",
        "interest_rate_attaches": "spiral",
        "interest_accumulates": "spiral",
        "minimum_payment_fails": "consequence",
        "emi_stacks": "stacking",
        "income_baseline": "income_base",
        "income_rises": "raise_arrives",
        "raise_absorbed": "expenses_follow",
        "expenses_follow": "expenses_follow",
        "value_anchor": "today",
        "inflation_erodes": "erosion",
        "time_exposes_loss": "future",
        "safe_asset_anchors": "fd_anchor",
        "growth_asset_rises": "equity_growth",
        "risk_arrives": "volatility_price",
        "risk_choice_revealed": "chosen_risk",
        "buffer_waits": "boring_buffer",
        "shock_hits": "shock_focus",
        "debt_blocked": "debt_prevention",
        "plan_survives": "plan_survives",
        "track_leaks": "track",
        "protect_buffer": "protect",
        "invest_consistently": "invest",
        "start_now": "start",
    }

    ACTION_TEXT = {
        "salary_arrives": "Salary lands",
        "expense_drains": "drains",
        "balance_revealed": "left",
        "contribution_starts": "monthly SIP",
        "contributions_accumulate": "invested",
        "return_rate_activates": "return activates",
        "time_extends": "time expands",
        "corpus_revealed": "corpus reveal",
        "debt_appears": "debt balance",
        "interest_rate_attaches": "interest pressure",
        "interest_accumulates": "interest grows",
        "safe_asset_anchors": "safe return",
        "growth_asset_rises": "upside appears",
        "risk_arrives": "volatility arrives",
        "risk_choice_revealed": "choose your risk",
        "buffer_waits": "cash buffer",
        "shock_hits": "shock hits",
        "debt_blocked": "debt blocked",
        "plan_survives": "plan survives",
        "track_leaks": "track leaks",
        "protect_buffer": "protect buffer",
        "invest_consistently": "invest consistently",
        "start_now": "start now",
        "minimum_payment_fails": "payment falls short",
        "emi_stacks": "EMI stacks",
        "income_baseline": "old income",
        "income_rises": "income rises",
        "raise_absorbed": "raise absorbed",
        "expenses_follow": "expenses follow",
        "value_anchor": "today's value",
        "inflation_erodes": "inflation erodes",
        "time_exposes_loss": "time exposes loss",
        "semantic_value_presented": "value appears",
    }

    def beats_from_section(
        self,
        section: dict[str, Any],
        visual_item: dict[str, Any],
        fallback_beats: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        graph = section.get("visual_action_graph") if isinstance(section.get("visual_action_graph"), dict) else {}
        if graph.get("source") != "visual_action_graph_v1":
            return []
        actions = [dict(action) for action in graph.get("actions") or [] if isinstance(action, dict)]
        if not actions:
            return []
        visual = visual_item.get("visual") if isinstance(visual_item.get("visual"), dict) else {}
        pattern = str(visual.get("pattern") or "").strip() or self._fallback_component(fallback_beats)
        data = visual.get("data") if isinstance(visual.get("data"), dict) else {}
        concept_key = str((graph.get("primary_concept") or {}).get("key") or section.get("concept_type") or "").strip()
        actions = sorted(actions, key=lambda item: int(item.get("sequence_index") or 0))
        beats = [
            self._beat_for_action(
                action=action,
                index=index,
                count=len(actions),
                pattern=pattern,
                concept_key=concept_key,
                data=data,
            )
            for index, action in enumerate(actions)
        ]
        return [beat for beat in beats if beat.get("component") and beat.get("text")]

    def _beat_for_action(
        self,
        *,
        action: dict[str, Any],
        index: int,
        count: int,
        pattern: str,
        concept_key: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        action_name = str(action.get("action") or "").strip()
        beat_phase = self._phase_for_action(action_name, pattern, index, count)
        component = pattern if pattern in self.PRIMARY_COMPONENTS else self._component_for_action(action_name, pattern, index, count)
        window = self._micro_window(index, count, action_name)
        action_payload = {
            "id": action.get("id"),
            "action": action_name,
            "semantic_role": action.get("semantic_role"),
            "motion": action.get("motion"),
            "intent": action.get("intent"),
            "relationship_id": action.get("relationship_id"),
            "source_entity_id": action.get("source_entity_id"),
            "target_entity_id": action.get("target_entity_id"),
            "sequence_index": action.get("sequence_index", index),
            "value": action.get("value") or {},
            "micro_window": window,
        }
        beat_data = dict(data)
        if beat_phase:
            beat_data["active_phase"] = beat_phase
        beat_data["active_action"] = action_payload
        beat_data["action_choreography"] = {
            "unit": "relative_frames",
            "window": window,
            "motion": action.get("motion"),
            "overlap_group": self._overlap_group(action_name, concept_key),
        }
        beat: dict[str, Any] = {
            "component": component,
            "text": self._text_for_action(action),
            "subtext": str(action.get("intent") or "").replace("_", " "),
            "source_text": str(action.get("label") or action_name),
            "sentence_index": action.get("sentence_index"),
            "emphasis": self._emphasis(index, count),
            "beat_role": self._beat_role(action_name, index, count),
            "data": beat_data,
        }
        if beat_phase:
            beat["beat_phase"] = beat_phase
        if component in self.PRIMARY_COMPONENTS or component in {"FlowDiagram", "GrowthChart", "SplitComparison"}:
            beat["props"] = data
        return beat

    def _phase_for_action(self, action_name: str, pattern: str, index: int, count: int) -> str:
        phase = self.ACTION_PHASES.get(action_name)
        if phase:
            return phase
        if index == 0:
            return "intro"
        if index == count - 1:
            return "remainder" if pattern == "MoneyFlowDiagram" else "consequence"
        return "drain" if pattern == "MoneyFlowDiagram" else "growth"

    def _component_for_action(self, action_name: str, pattern: str, index: int, count: int) -> str:
        if index == 0:
            return "StatCard"
        if index == count - 1:
            return "HighlightText"
        if pattern:
            return pattern
        if action_name in {"contribution_starts", "contributions_accumulate", "corpus_revealed"}:
            return "GrowthChart"
        if action_name in {"expense_drains", "salary_arrives", "balance_revealed"}:
            return "FlowDiagram"
        return "StatCard"

    def _text_for_action(self, action: dict[str, Any]) -> str:
        action_name = str(action.get("action") or "").strip()
        value = action.get("value") if isinstance(action.get("value"), dict) else {}
        display_value = str(value.get("display_value") or "").strip()
        semantic_role = str(action.get("semantic_role") or "")
        if action_name == "time_extends" and display_value and "year" not in display_value.lower():
            display_value = f"{display_value} years"
        label = self.ACTION_TEXT.get(action_name) or str(action.get("label") or action_name).replace("_", " ")
        if display_value:
            if action_name == "expense_drains":
                role = semantic_role.replace("_", " ")
                role_label = "EMI" if "emi" in role else ("rent" if "rent" in role else "expense")
                return f"{display_value} {role_label}"
            if action_name in {"salary_arrives", "contribution_starts", "contributions_accumulate", "corpus_revealed", "balance_revealed"}:
                return f"{display_value} {label}".strip()
            if action_name in {"return_rate_activates", "time_extends", "inflation_erodes", "interest_rate_attaches"}:
                return f"{display_value} {label}".strip()
            return display_value
        return label[:1].upper() + label[1:]

    def _micro_window(self, index: int, count: int, action_name: str) -> dict[str, int]:
        if count <= 1:
            return {"start_frame": 0, "end_frame": 45}
        stride = 18 if action_name in {"expense_drains", "emi_stacks"} else 22
        duration = 34 if action_name in {"expense_drains", "emi_stacks", "return_rate_activates"} else 30
        if index == 0:
            start = 0
        elif index == count - 1:
            start = max(0, index * stride + 8)
            duration = 36
        else:
            start = index * stride
        return {"start_frame": int(start), "end_frame": int(start + duration)}

    def _overlap_group(self, action_name: str, concept_key: str) -> str:
        if action_name in {"expense_drains", "emi_stacks"}:
            return "overlapping_outflows"
        if action_name in {"return_rate_activates", "time_extends", "contributions_accumulate"}:
            return "compound_growth"
        return concept_key or "action_sequence"

    def _emphasis(self, index: int, count: int) -> str:
        if index == count - 1:
            return "hero"
        if index == 0:
            return "normal"
        return "subtle"

    def _beat_role(self, action_name: str, index: int, count: int) -> str:
        if index == 0:
            return "introduce"
        if index == count - 1:
            return "resolve"
        if action_name in {"expense_drains", "emi_stacks", "interest_accumulates", "return_rate_activates"}:
            return "escalate"
        return "develop"

    def _fallback_component(self, beats: list[dict[str, Any]]) -> str:
        for beat in beats:
            component = str(beat.get("component") or "").strip()
            if component:
                return component
        return "StatCard"
