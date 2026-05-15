from __future__ import annotations

from collections.abc import Callable
from typing import Any

import requests


class GroqChatClient:
    """Small adapter around Groq's OpenAI-compatible chat endpoint."""

    endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, post_func: Callable[..., Any] | None = None) -> None:
        self.api_key = api_key
        self.post_func = post_func or requests.post

    def chat_json(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout: int,
    ) -> Any:
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        return self.post_func(
            self.endpoint,
            json=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "YTCreate/1.0",
            },
            timeout=timeout,
        )
