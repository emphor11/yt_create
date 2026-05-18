from __future__ import annotations

from collections.abc import Callable
from typing import Any

import requests


class GeminiChatClient:
    """Small adapter around Google's Gemini generateContent endpoint."""

    endpoint_template = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str, post_func: Callable[..., Any] | None = None) -> None:
        self.api_key = api_key
        self.post_func = post_func or requests.post

    def generate_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
    ) -> Any:
        body = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }
        return self.post_func(
            self.endpoint_template.format(model=model),
            json=body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
                "User-Agent": "YTCreate/1.0",
            },
            timeout=timeout,
        )
