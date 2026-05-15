from __future__ import annotations

import re
from typing import Any

from ...services.financial_governance import first_fact, numeric_role_map
from .director_types import VisualDirectorInput


class VisualDirectorFlowDataMixin:
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
