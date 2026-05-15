from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import current_app

from ..infrastructure.youtube import YouTubeClient, YouTubeVideoUploader
from ..models.repository import ProjectRepository
from .final_production_service import FinalProductionService
from .publish_service import PublishService


class YouTubeUploadService:
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.last_thumbnail_warning = ""
        self.uploader = YouTubeVideoUploader()

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
        video_id = self.uploader.upload_private_video(youtube, video_path, package)
        PublishService().mark_uploaded(project_id, video_id)
        thumbnail_path = project.get("selected_thumbnail_path")
        if thumbnail_path and Path(thumbnail_path).exists():
            try:
                self.uploader.set_thumbnail(youtube, video_id, thumbnail_path)
            except Exception as exc:
                self.last_thumbnail_warning = (
                    "Video uploaded, but YouTube rejected the custom thumbnail. "
                    "Enable custom thumbnails on the channel or set it manually in YouTube Studio."
                )
                current_app.logger.warning("%s Original error: %s", self.last_thumbnail_warning, exc)
        return video_id

    def _authorized_client(self):
        token_path = Path(current_app.config["YOUTUBE_TOKEN_PATH"])
        client_secret = Path(current_app.config["YOUTUBE_CLIENT_SECRETS"])
        return YouTubeClient(token_path=token_path, client_secret_path=client_secret).authorized_client(self.SCOPES)
