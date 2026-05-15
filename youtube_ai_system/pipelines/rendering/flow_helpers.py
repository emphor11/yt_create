from __future__ import annotations

import re
from typing import Any


class RenderFlowHelpers:
    """Small helpers for flow-diagram node identity and connections."""

    def flow_connections(self, raw_connections: Any, nodes: list[dict[str, Any]], mode: str) -> list[dict[str, str]]:
        node_ids = {node["id"] for node in nodes}
        connections: list[dict[str, str]] = []
        if isinstance(raw_connections, list):
            for connection in raw_connections:
                if not isinstance(connection, dict):
                    continue
                start = str(connection.get("from") or "")
                end = str(connection.get("to") or "")
                if start in node_ids and end in node_ids and start != end:
                    connections.append({"from": start, "to": end})
        if connections:
            return connections[:6]
        for index in range(len(nodes) - 1):
            connections.append({"from": nodes[index]["id"], "to": nodes[index + 1]["id"]})
        if mode == "loop" and len(nodes) > 2:
            connections.append({"from": nodes[-1]["id"], "to": nodes[0]["id"]})
        return connections

    def default_node_role(self, index: int, total: int) -> str:
        if index == 0:
            return "source"
        if index == total - 1:
            return "result"
        return "process"

    def safe_id(self, value: str, index: int) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
        return cleaned or f"node{index + 1}"
