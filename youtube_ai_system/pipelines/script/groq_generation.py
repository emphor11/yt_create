"""Groq script generation flow for the current script pipeline."""

from __future__ import annotations

import re
from typing import Any, Callable
from urllib import error

import requests

from ...infrastructure.llm import GroqChatClient
from .json_payload import extract_json_payload


class GroqScriptGenerator:
    def __init__(self, logger: Any) -> None:
        self.logger = logger

    def generate(
        self,
        *,
        topic: str,
        angle: str,
        prompt: str,
        api_key: str,
        config: dict[str, Any],
        post_func: Callable[..., requests.Response] | None = None,
        sleep_func: Callable[[float], None],
    ) -> dict[str, Any]:
        return self.generate_json(
            prompt=prompt,
            api_key=api_key,
            config=config,
            max_tokens=int(config.get("GROQ_MAX_TOKENS", 4200)),
            temperature=0.7,
            timeout=45,
            post_func=post_func,
            sleep_func=sleep_func,
            rate_limit_retries=int(config.get("GROQ_RATE_LIMIT_RETRIES", 2)),
            log_label="script_generation",
        )

    def generate_brief(
        self,
        *,
        prompt: str,
        api_key: str,
        config: dict[str, Any],
        post_func: Callable[..., requests.Response] | None = None,
        sleep_func: Callable[[float], None],
    ) -> dict[str, Any]:
        return self.generate_json(
            prompt=prompt,
            api_key=api_key,
            config=config,
            max_tokens=int(config.get("SCRIPT_BRIEF_MAX_TOKENS", 1800)),
            temperature=float(config.get("SCRIPT_BRIEF_TEMPERATURE", 0.2)),
            timeout=45,
            post_func=post_func,
            sleep_func=sleep_func,
            rate_limit_retries=int(config.get("GROQ_RATE_LIMIT_RETRIES", 2)),
            log_label="script_brief_generation",
        )

    def generate_json(
        self,
        *,
        prompt: str,
        api_key: str,
        config: dict[str, Any],
        max_tokens: int,
        temperature: float,
        timeout: int,
        post_func: Callable[..., requests.Response] | None,
        sleep_func: Callable[[float], None],
        rate_limit_retries: int,
        log_label: str,
    ) -> dict[str, Any]:
        client = GroqChatClient(api_key, post_func=post_func)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a professional YouTube scriptwriter. "
                    "You always return valid JSON only. "
                    "You never add explanations, apologies, markdown formatting, or code fences."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        for attempt in range(rate_limit_retries + 1):
            try:
                response = client.chat_json(
                    model=config["GROQ_MODEL"],
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
                response.raise_for_status()
                response_json = response.json()
                break
            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else "unknown"
                error_body = exc.response.text if exc.response is not None else str(exc)
                if status_code == 429 and attempt < rate_limit_retries:
                    wait_seconds = self.retry_wait_seconds(exc.response)
                    self.logger.log(
                        log_label,
                        "running",
                        (
                            "Groq rate limit reached. "
                            f"Retrying in {wait_seconds:.1f}s "
                            f"(attempt {attempt + 1}/{rate_limit_retries})."
                        ),
                    )
                    sleep_func(wait_seconds)
                    continue
                raise ValueError(f"Groq API error {status_code}: {error_body}") from exc
            except requests.RequestException as exc:
                raise error.URLError(str(exc)) from exc

        text = response_json["choices"][0]["message"]["content"]
        self.logger.log(log_label, "running", f"Raw Groq response before parsing: {text}")
        return self.extract_json_payload(text)

    def retry_wait_seconds(self, response: requests.Response | None) -> float:
        if response is None:
            return 12.0
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(30.0, max(1.0, float(retry_after)))
            except ValueError:
                pass
        try:
            payload = response.json()
            message = str((payload.get("error") or {}).get("message") or "")
        except ValueError:
            message = response.text or ""
        match = re.search(r"try again in\s+([0-9.]+)s", message, flags=re.IGNORECASE)
        if match:
            return min(30.0, max(1.0, float(match.group(1)) + 0.5))
        return 12.0

    def extract_json_payload(self, raw_text: str) -> dict[str, Any]:
        return extract_json_payload(raw_text)
