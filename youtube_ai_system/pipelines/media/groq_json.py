"""Small Groq JSON calls used by media helper stages."""

from __future__ import annotations

import json
from typing import Any, Callable

import requests

from ...infrastructure.llm import GroqChatClient


class MediaGroqJsonClient:
    def __init__(self, logger: Any) -> None:
        self.logger = logger

    def call_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        purpose: str,
        api_key: str,
        model: str,
        post_func: Callable[..., requests.Response] | None = None,
    ) -> dict:
        client = GroqChatClient(api_key, post_func=post_func)
        max_retries = 2
        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                response = client.chat_json(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.4,
                    max_tokens=800,
                    timeout=20,
                )
                response.raise_for_status()
                text = response.json()["choices"][0]["message"]["content"]
                return self.extract_json_from_text(text)
            except (requests.RequestException, ValueError, KeyError, json.JSONDecodeError) as exc:
                last_exc = exc
                self.logger.log(
                    purpose,
                    "failed",
                    f"Groq micro-call attempt {attempt}/{max_retries} failed for {purpose}: {exc}",
                )
        raise RuntimeError(f"Groq micro-call failed after {max_retries} retries for {purpose}: {last_exc}")

    def extract_json_from_text(self, raw_text: str) -> dict:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json", "", 1).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Groq response did not contain a JSON object.")
        return json.loads(cleaned[start : end + 1])
