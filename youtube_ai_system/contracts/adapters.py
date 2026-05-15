"""Compatibility adapters for current JSON-backed payloads."""

from __future__ import annotations

import json
from typing import Any


def load_json_object(raw_value: Any) -> dict[str, Any]:
    if isinstance(raw_value, dict):
        return dict(raw_value)
    if not raw_value:
        return {}
    try:
        parsed = json.loads(str(raw_value))
    except (TypeError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def load_json_array(raw_value: Any) -> list[Any]:
    if isinstance(raw_value, list):
        return list(raw_value)
    if not raw_value:
        return []
    try:
        parsed = json.loads(str(raw_value))
    except (TypeError, json.JSONDecodeError):
        return []
    return list(parsed) if isinstance(parsed, list) else []


def narration_from_payload(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("narration") or value.get("text") or value.get("voiceover") or "")
    return str(value or "")

