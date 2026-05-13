from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import current_app

from ..models.repository import ProjectRepository
from .final_production_service import FinalProductionService
from .publish_service import PublishService


class YouTubeUploadService:
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

    def __init__(self) -> None:
        self.repo = ProjectRepository()

    def readiness(self, project_id: int) -> dict[str, Any]:
        project = self.repo.get_project(project_id)
        package = FinalProductionService(self.repo).build_upload_package(project_id)
        client_secret_raw = current_app.config.get("YOUTUBE_CLIENT_SECRETS") or ""
        token_raw = current_app.config.get("YOUTUBE_TOKEN_PATH") or ""
        client_secret = Path(client_secret_raw) if client_secret_raw else None
        token_path = Path(token_raw) if token_raw else None
        checks = [
            {
                "key": "video",
                "label": "Final video file exists",
                "passed": bool(project.get("final_video_path")) and Path(project["final_video_path"]).exists(),
            },
            {
                "key": "thumbnail",
                "label": "Thumbnail file exists",
                "passed": bool(project.get("selected_thumbnail_path")) and Path(project["selected_thumbnail_path"]).exists(),
            },
            {
                "key": "metadata",
                "label": "Upload title and description exist",
                "passed": bool(package.get("selected_title")) and bool(package.get("description")),
            },
            {
                "key": "client_secret",
                "label": "YouTube OAuth client secret configured",
                "passed": bool(client_secret) and client_secret.exists(),
            },
            {
                "key": "token",
                "label": "YouTube OAuth token already authorized",
                "passed": bool(token_path) and token_path.exists(),
            },
        ]
        return {"passed": all(check["passed"] for check in checks), "checks": checks}

    def upload_private(self, project_id: int) -> str:
        project = self.repo.get_project(project_id)
        package = FinalProductionService(self.repo).build_upload_package(project_id)
        readiness = self.readiness(project_id)
        if not readiness["passed"]:
            missing = ", ".join(check["label"] for check in readiness["checks"] if not check["passed"])
            raise RuntimeError(f"YouTube upload is not ready yet: {missing}.")

        youtube = self._authorized_client()
        video_path = project["final_video_path"]
        body = {
            "snippet": {
                "title": package["selected_title"][:100],
                "description": package["description"],
                "tags": package["tags"],
                "categoryId": "27",
            },
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
        }

        from googleapiclient.http import MediaFileUpload

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True),
        )
        response = None
        while response is None:
            _, response = request.next_chunk()
        video_id = response["id"]
        thumbnail_path = project.get("selected_thumbnail_path")
        if thumbnail_path and Path(thumbnail_path).exists():
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path),
            ).execute()
        PublishService().mark_uploaded(project_id, video_id)
        return video_id

    def _authorized_client(self):
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        token_path = Path(current_app.config["YOUTUBE_TOKEN_PATH"])
        client_secret = Path(current_app.config["YOUTUBE_CLIENT_SECRETS"])
        credentials = None
        if token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(token_path), self.SCOPES)
        if not credentials or not credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), self.SCOPES)
            credentials = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(credentials.to_json(), encoding="utf-8")
        return build("youtube", "v3", credentials=credentials, cache_discovery=False)
