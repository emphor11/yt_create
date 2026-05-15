from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from googleapiclient.discovery import build


class YouTubeSearchClient:
    """Infrastructure adapter for YouTube Data API search/stat lookups."""

    def __init__(self, api_key: str, *, result_limit: int, lookback_days: int) -> None:
        self.api_key = api_key
        self.result_limit = result_limit
        self.lookback_days = lookback_days

    def comparable_videos(self, topic: str, angle: str | None) -> list[dict[str, Any]]:
        query = " ".join(part for part in [topic, angle] if part).strip() or topic.strip()
        youtube = build("youtube", "v3", developerKey=self.api_key, cache_discovery=False)
        search_response = (
            youtube.search()
            .list(
                part="snippet",
                q=query,
                type="video",
                order="relevance",
                maxResults=self.result_limit,
                publishedAfter=(
                    datetime.now(timezone.utc) - timedelta(days=self.lookback_days + 21)
                ).isoformat().replace("+00:00", "Z"),
            )
            .execute()
        )
        video_ids = [item["id"]["videoId"] for item in search_response.get("items", []) if item.get("id", {}).get("videoId")]
        if not video_ids:
            return []

        videos_response = youtube.videos().list(part="snippet,statistics", id=",".join(video_ids)).execute()
        channel_ids = {
            item["snippet"]["channelId"] for item in videos_response.get("items", []) if item.get("snippet", {}).get("channelId")
        }
        channel_stats: dict[str, int] = {}
        if channel_ids:
            channels_response = youtube.channels().list(part="statistics", id=",".join(channel_ids)).execute()
            channel_stats = {
                item["id"]: int(item.get("statistics", {}).get("subscriberCount", 0) or 0)
                for item in channels_response.get("items", [])
            }

        samples: list[dict[str, Any]] = []
        for item in videos_response.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            channel_id = snippet.get("channelId", "")
            samples.append(
                {
                    "title": snippet.get("title", ""),
                    "channel": snippet.get("channelTitle", ""),
                    "views": int(stats.get("viewCount", 0) or 0),
                    "channel_subscribers": channel_stats.get(channel_id, 0),
                    "published_at": snippet.get("publishedAt"),
                    "source": "live",
                }
            )
        return samples
