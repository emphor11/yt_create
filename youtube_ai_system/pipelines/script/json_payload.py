"""JSON extraction helpers for LLM script responses."""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_payload(raw_text: str, *, incomplete_message: str | None = None) -> dict[str, Any]:
    """Extract and parse a JSON object from a model response.

    Script generation prompts demand strict JSON, but long model outputs can still
    contain recoverable formatting flaws. Keep recovery conservative so invalid
    structure still fails loudly instead of silently changing meaning.
    """

    segment = _extract_balanced_object(_strip_code_fence(str(raw_text or "")))
    if segment is None:
        if "{" in str(raw_text or "") and incomplete_message:
            raise ValueError(incomplete_message)
        raise ValueError("Model did not return a JSON object.")

    attempts = [segment, _repair_common_json_glitches(segment)]
    last_exc: json.JSONDecodeError | None = None
    for candidate in attempts:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_exc = exc
            continue
        if not isinstance(payload, dict):
            raise ValueError("Model JSON payload was not an object.")
        return payload

    assert last_exc is not None
    excerpt = _error_excerpt(attempts[-1], last_exc.pos)
    raise ValueError(
        f"Model returned invalid JSON at line {last_exc.lineno} column {last_exc.colno}: {excerpt}"
    ) from last_exc


def _strip_code_fence(raw_text: str) -> str:
    cleaned = raw_text.strip()
    if not cleaned.startswith("```"):
        return cleaned
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _extract_balanced_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _repair_common_json_glitches(segment: str) -> str:
    repaired = segment
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    repaired = re.sub(r'([}\]"0-9])\s*\n(\s*"[^"\n]+":)', r"\1,\n\2", repaired)
    return repaired


def _error_excerpt(text: str, position: int) -> str:
    start = max(0, position - 80)
    end = min(len(text), position + 80)
    excerpt = text[start:end].replace("\n", "\\n")
    return excerpt.strip()
