from __future__ import annotations

import re
from typing import Any

from .flow_helpers import RenderFlowHelpers
from .flow_labels import RenderFlowLabelHelper
from .text_utils import RenderTextUtils
from .visual_gate import RenderVisualGate


class RenderFlowPropsBuilder:
    """Builds and polishes FlowDiagram props."""

    VALID_NODE_ROLES = {"source", "process", "modifier", "result", "actor", "sink"}

    def __init__(
        self,
        *,
        flow_helpers: RenderFlowHelpers,
        flow_labels: RenderFlowLabelHelper,
        text_utils: RenderTextUtils,
        visual_gate: RenderVisualGate,
    ) -> None:
        self.flow_helpers = flow_helpers
        self.flow_labels = flow_labels
        self.text_utils = text_utils
        self.visual_gate = visual_gate

    def flow_props(
        self,
        pattern: str,
        visual_logic: str,
        caption: str,
        raw_props: dict[str, Any],
        color: str,
        beat: dict[str, Any],
    ) -> dict[str, Any]:
        mode = self.flow_mode(pattern, raw_props.get("mode"))
        layout = self.flow_layout(mode, raw_props.get("layout"))
        nodes = self.flow_nodes(raw_props.get("nodes"), visual_logic, pattern)
        connections = self.flow_helpers.flow_connections(raw_props.get("connections"), nodes, mode)
        if beat.get("context_ref"):
            layout = str(raw_props.get("layout") or layout)
        caption = self.flow_labels.complete_caption(caption)
        semantic_color = (
            self.flow_labels.color_for_label(" ".join(str(node.get("label") or "") for node in nodes))
            or self.flow_labels.color_for_label(caption)
            or self.flow_labels.color_for_label(visual_logic)
            or color
        )
        return {
            "mode": mode,
            "layout": layout,
            "spacing": str(raw_props.get("spacing") or "equal") if raw_props.get("spacing") in {"equal", "weighted"} else "equal",
            "direction": str(raw_props.get("direction") or "forward") if raw_props.get("direction") in {"forward", "reverse"} else "forward",
            "nodes": nodes,
            "connections": connections,
            "caption": caption,
            "captionColor": self.flow_labels.color_for_label(caption) or semantic_color,
            "color": semantic_color,
            "contextRef": str(beat.get("context_ref") or ""),
            "isOutro": bool(beat.get("is_outro")),
        }

    def polish_flow_display_props(self, props: dict[str, Any], visual_logic: str) -> dict[str, Any]:
        nodes = props.get("nodes")
        if not isinstance(nodes, list):
            return props
        polished = dict(props)
        result_text = str(nodes[-1].get("label") if nodes and isinstance(nodes[-1], dict) else "")
        flow_text = f"{visual_logic} {result_text} {polished.get('caption', '')}"
        if self.flow_labels.is_loss_result(flow_text):
            polished["captionColor"] = "red"
            polished["color"] = "red"
        if props.get("isOutro") and self.flow_labels.looks_like_outro_loss(flow_text) and len(nodes) >= 3:
            first = dict(nodes[0])
            last = dict(nodes[-1])
            first["label"] = self.monthly_punchline_source(str(first.get("label") or ""))
            first["style"] = self.node_style(str(first.get("role") or "source"), first["label"], "MONEY_FLOW")
            last["label"] = self.flow_labels.humanize_money_phrase(str(last.get("label") or ""))
            last["style"] = self.node_style("result", last["label"], "MONEY_FLOW")
            polished["nodes"] = [first, last]
            polished["connections"] = [{"from": first["id"], "to": last["id"]}]
            polished["caption"] = f"{self.short_money(first['label'])}/month -> {self.short_money(last['label'])} gone"
            polished["captionColor"] = "red"
            polished["color"] = "red"
        return polished

    def flow_mode(self, pattern: str, value: Any) -> str:
        mode = str(value or "").lower()
        if mode in {"linear", "branch", "loop", "decay", "growth"}:
            return mode
        return {
            "MONEY_FLOW": "linear",
            "VALUE_DECAY": "decay",
            "LOOP": "loop",
            "GROWTH": "growth",
        }.get(pattern, "linear")

    def flow_layout(self, mode: str, value: Any) -> str:
        layout = str(value or "").lower()
        if layout in {"horizontal", "vertical", "radial"}:
            return layout
        return {"branch": "vertical", "loop": "radial"}.get(mode, "horizontal")

    def flow_nodes(self, raw_nodes: Any, visual_logic: str, pattern: str) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        if isinstance(raw_nodes, list):
            for index, node in enumerate(raw_nodes[:5]):
                if isinstance(node, dict):
                    node_id = str(node.get("id") or f"node{index + 1}")
                    label = self.flow_labels.humanize_money_phrase(str(node.get("label") or node_id))
                    if self.visual_gate.is_abstract_visual_logic(label):
                        label = self.fallback_node_label(visual_logic, index, pattern)
                    role = str(node.get("role") or self.flow_helpers.default_node_role(index, len(raw_nodes))).lower()
                    children = node.get("children") if isinstance(node.get("children"), list) else []
                    nodes.append(
                        {
                            "id": self.flow_helpers.safe_id(node_id, index),
                            "label": self.text_utils.short_overlay(label, 4) or f"Step {index + 1}",
                            "role": role if role in self.VALID_NODE_ROLES else self.flow_helpers.default_node_role(index, len(raw_nodes)),
                            "style": self.node_style(role if role in self.VALID_NODE_ROLES else self.flow_helpers.default_node_role(index, len(raw_nodes)), label, pattern),
                            "children": [self.text_utils.short_overlay(str(child), 3) for child in children[:4] if str(child).strip()],
                        }
                    )
                else:
                    label = (
                        self.flow_labels.humanize_money_phrase(self.text_utils.short_overlay(str(node), 4))
                        if not self.visual_gate.is_abstract_visual_logic(str(node))
                        else self.fallback_node_label(visual_logic, index, pattern)
                    )
                    role = self.flow_helpers.default_node_role(index, len(raw_nodes))
                    nodes.append(
                        {
                            "id": f"node{index + 1}",
                            "label": label,
                            "role": role,
                            "style": self.node_style(role, label, pattern),
                            "children": [],
                        }
                    )
        if len(nodes) < 2:
            nodes = self.fallback_flow_nodes(visual_logic, pattern)
        return nodes[:5]

    def fallback_node_label(self, visual_logic: str, index: int, pattern: str) -> str:
        fallback_nodes = self.fallback_flow_nodes(visual_logic, pattern)
        if index < len(fallback_nodes):
            return fallback_nodes[index]["label"]
        return f"Step {index + 1}"

    def fallback_flow_nodes(self, visual_logic: str, pattern: str) -> list[dict[str, Any]]:
        arrow_parts = [
            self.flow_labels.humanize_money_phrase(self.text_utils.short_overlay(part, 4))
            for part in re.split(r"\s*(?:->|→)\s*", visual_logic)
            if part.strip()
        ]
        if len(arrow_parts) >= 3:
            labels = arrow_parts[:5]
            if pattern == "VALUE_DECAY":
                roles = ["source", "modifier", "result"]
            elif pattern == "GROWTH":
                roles = ["source", "modifier", "result"]
            else:
                roles = ["source"] + ["process"] * max(len(labels) - 2, 0) + ["result"]
        elif pattern == "VALUE_DECAY":
            labels = ["₹1,00,000", "6% Inflation", "₹94,000 Value"]
            roles = ["source", "modifier", "result"]
        elif pattern == "LOOP":
            labels = ["₹25,000 Start", "spending", "₹0 Left", "Repeat"]
            roles = ["source", "process", "result", "process"]
        elif pattern == "GROWTH":
            labels = ["₹5,000 SIP", "12% Growth", "₹60,000 Invested", "Wealth"]
            roles = ["source", "process", "modifier", "result"]
        else:
            words = [word for word in re.findall(r"[A-Za-z₹0-9%.,]+", visual_logic) if len(word) > 2][:4]
            labels = words if len(words) >= 3 else ["₹25,000 Salary", "₹23,000 Expenses", "₹2,000 Left"]
            roles = ["source"] + ["process"] * max(len(labels) - 2, 0) + ["result"]
        return [
            {
                "id": f"node{index + 1}",
                "label": label,
                "role": roles[min(index, len(roles) - 1)],
                "style": self.node_style(roles[min(index, len(roles) - 1)], label, pattern),
                "children": [],
            }
            for index, label in enumerate(labels[:5])
        ]

    def node_style(self, role: str, label: str, pattern: str = "") -> dict[str, str]:
        semantic_color = self.flow_labels.color_for_label(label)
        if role == "source":
            return {"size": "large", "color": semantic_color or "teal"}
        if role == "modifier":
            return {"size": "small", "color": semantic_color or "orange"}
        if role == "result":
            is_loss_result = pattern == "VALUE_DECAY" or self.text_utils.sentiment(label) == "negative" or "left" in label.lower()
            return {"size": "large", "color": semantic_color or ("red" if is_loss_result else "teal")}
        return {"size": "medium", "color": semantic_color or "orange"}

    def monthly_punchline_source(self, label: str) -> str:
        money = self.short_money(label)
        return f"{money} leaks every month" if money else self.flow_labels.humanize_money_phrase(label)

    def short_money(self, text: str) -> str:
        tokens = self.flow_labels.number_utils.money_tokens(text)
        return tokens[0] if tokens else ""
