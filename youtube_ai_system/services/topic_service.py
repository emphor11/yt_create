from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from flask import current_app
from googleapiclient.errors import HttpError
from httplib2.error import ServerNotFoundError

from ..infrastructure.youtube import YouTubeSearchClient


class TopicService:
    def __init__(self) -> None:
        self.last_lookup_mode = "demo"
        self.last_lookup_message = "Using demo comparable videos."

    def score_candidate(self, candidate: dict) -> int:
        score = 0
        published_at = candidate.get("published_at")
        if published_at:
            try:
                published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                if published_dt >= datetime.now(timezone.utc) - timedelta(days=7):
                    score += 3
            except ValueError:
                pass
        if candidate.get("strong_traction"):
            score += 3
        if candidate.get("curiosity_pattern"):
            score += 2
        return score

    def lookup_comparable_videos(self, topic: str, angle: str | None = None) -> list[dict]:
        api_key = current_app.config.get("YOUTUBE_API_KEY")
        if api_key:
            try:
                samples = self._live_lookup(topic, angle, api_key)
                if samples:
                    self.last_lookup_mode = "live"
                    self.last_lookup_message = "Using live YouTube Data API results."
                    return samples
                self.last_lookup_mode = "demo"
                self.last_lookup_message = "Live lookup returned no results. Showing demo comparable videos."
            except (HttpError, OSError, ValueError, ServerNotFoundError, Exception) as exc:
                self.last_lookup_mode = "demo"
                self.last_lookup_message = f"Live YouTube lookup failed ({exc}). Showing demo comparable videos."

        query = " ".join(part for part in [topic, angle] if part).strip()
        # Demo-mode results designed to enforce manual final selection.
        samples = [
            {
                "title": f"Why {query or 'most people'} stay broke in their 20s",
                "channel": "Finance Breakdowns",
                "views": 198000,
                "channel_subscribers": 54000,
                "published_at": datetime.now(timezone.utc).isoformat(),
                "strong_traction": True,
                "curiosity_pattern": True,
            },
            {
                "title": f"The hidden mistake behind {topic or 'personal finance'} failure",
                "channel": "Money Truth Lab",
                "views": 83000,
                "channel_subscribers": 41000,
                "published_at": (datetime.now(timezone.utc) - timedelta(days=4)).isoformat(),
                "strong_traction": True,
                "curiosity_pattern": True,
            },
            {
                "title": f"How to avoid the wrong {topic or 'money'} habits in your 20s",
                "channel": "Growth Ledger",
                "views": 26000,
                "channel_subscribers": 129000,
                "published_at": (datetime.now(timezone.utc) - timedelta(days=9)).isoformat(),
                "strong_traction": False,
                "curiosity_pattern": False,
            },
        ]
        for sample in samples:
            sample["score"] = self.score_candidate(sample)
            sample["source"] = "demo"
        return samples

    def _live_lookup(self, topic: str, angle: str | None, api_key: str) -> list[dict[str, Any]]:
        client = YouTubeSearchClient(
            api_key,
            result_limit=current_app.config["TOPIC_RESULT_LIMIT"],
            lookback_days=current_app.config["TOPIC_LOOKBACK_DAYS"],
        )
        samples: list[dict[str, Any]] = []
        for candidate in client.comparable_videos(topic, angle):
            candidate = dict(candidate)
            views = int(candidate.get("views") or 0)
            subscribers = int(candidate.get("channel_subscribers") or 0)
            candidate["strong_traction"] = self._is_strong_traction(views, subscribers)
            candidate["curiosity_pattern"] = self._has_curiosity_pattern(str(candidate.get("title") or ""))
            candidate["source"] = "live"
            candidate["score"] = self.score_candidate(candidate)
            samples.append(candidate)
        return sorted(samples, key=lambda item: item["score"], reverse=True)

    def _is_strong_traction(self, views: int, subscribers: int) -> bool:
        if subscribers <= 0:
            return views >= 10000
        return views >= max(int(subscribers * 0.35), 10000)

    def _has_curiosity_pattern(self, title: str) -> bool:
        lowered = title.lower()
        signals = ("why", "how", "secret", "hidden", "mistake", "truth", "wrong", "actually", "?")
        return any(signal in lowered for signal in signals)
