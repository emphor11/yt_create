from __future__ import annotations

from pathlib import Path
from typing import Any


class YouTubeVideoUploader:
    """Executes YouTube video and thumbnail upload calls against an authorized client."""

    def upload_private_video(self, youtube: Any, video_path: str | Path, package: dict[str, Any]) -> str:
        from googleapiclient.http import MediaFileUpload

        body = {
            "snippet": {
                "title": package["selected_title"][:100],
                "description": package["description"],
                "tags": package["tags"],
                "categoryId": "27",
            },
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
        }
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=MediaFileUpload(str(video_path), chunksize=-1, resumable=True),
        )
        response = None
        while response is None:
            _, response = request.next_chunk()
        return str(response["id"])

    def set_thumbnail(self, youtube: Any, video_id: str, thumbnail_path: str | Path) -> None:
        from googleapiclient.http import MediaFileUpload

        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path)),
        ).execute()
