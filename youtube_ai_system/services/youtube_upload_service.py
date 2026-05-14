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
        self.last_thumbnail_warning = ""

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
                "label": "YouTube channel authorized",
                "passed": bool(token_path) and token_path.exists(),
                "warning": not (bool(token_path) and token_path.exists()),
                "action": "Authorize on first upload",
            },
        ]
        hard_checks = [check for check in checks if check["key"] != "token"]
        return {"passed": all(check["passed"] for check in hard_checks), "checks": checks}

    def upload_private(self, project_id: int) -> str:
        project = self.repo.get_project(project_id)
        package = FinalProductionService(self.repo).build_upload_package(project_id)
        readiness = self.readiness(project_id)
        if not readiness["passed"]:
            missing = ", ".join(
                check["label"]
                for check in readiness["checks"]
                if not check["passed"] and check["key"] != "token"
            )
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
        PublishService().mark_uploaded(project_id, video_id)
        thumbnail_path = project.get("selected_thumbnail_path")
        if thumbnail_path and Path(thumbnail_path).exists():
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path),
                ).execute()
            except Exception as exc:
                self.last_thumbnail_warning = (
                    "Video uploaded, but YouTube rejected the custom thumbnail. "
                    "Enable custom thumbnails on the channel or set it manually in YouTube Studio."
                )
                current_app.logger.warning("%s Original error: %s", self.last_thumbnail_warning, exc)
        return video_id

    def _authorized_client(self):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        token_path = Path(current_app.config["YOUTUBE_TOKEN_PATH"])
        client_secret = Path(current_app.config["YOUTUBE_CLIENT_SECRETS"])
        credentials = None
        if token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(token_path), self.SCOPES)
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(credentials.to_json(), encoding="utf-8")
        if not credentials or not credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), self.SCOPES)
            credentials = flow.run_local_server(
                port=0,
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent",
            )
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(credentials.to_json(), encoding="utf-8")
        return build("youtube", "v3", credentials=credentials, cache_discovery=False)
