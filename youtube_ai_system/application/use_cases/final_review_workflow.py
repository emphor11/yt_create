"""Final review page and metadata use-case wrappers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from youtube_ai_system.application.result import UseCaseResult
from youtube_ai_system.infrastructure.persistence import ProjectRepository
from youtube_ai_system.services.final_production_service import FinalProductionService
from youtube_ai_system.services.thumbnail_service import ThumbnailService
from youtube_ai_system.services.youtube_upload_service import YouTubeUploadService


class BuildFinalReviewUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        thumbnail_service: ThumbnailService | None = None,
        final_service: FinalProductionService | None = None,
        upload_service: YouTubeUploadService | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.thumbnail_service = thumbnail_service or ThumbnailService()
        self.final_service = final_service or FinalProductionService(self.repo)
        self.upload_service = upload_service or YouTubeUploadService()

    def execute(self, project_id: int) -> UseCaseResult:
        project = self.repo.get_project(project_id)
        if project["state"] not in {
            "scene_review",
            "assets_ready",
            "ready_to_publish",
            "scheduled",
            "published",
            "analyzed",
            "assembling",
        }:
            return UseCaseResult.fail(
                "Final studio becomes available after scene media exists.",
                redirect_endpoint="projects.project_detail",
            )
        scenes = self.repo.list_scenes(project_id)
        script_version = self.repo.get_latest_script_version(project_id)
        script_payload = json.loads(script_version["full_script_json"]) if script_version else None
        titles = script_payload.get("titles", []) if script_payload else []
        thumbnail_options = self.thumbnail_service.ensure_creator_thumbnails(project_id, titles, scenes)
        upload_package = self.final_service.build_upload_package(project_id)
        youtube_readiness = self.upload_service.readiness(project_id)
        return UseCaseResult.ok(
            data={
                "project": project,
                "scenes": scenes,
                "script_payload": script_payload,
                "thumbnail_options": thumbnail_options,
                "upload_package": upload_package,
                "publish_readiness": upload_package["publish_checklist"],
                "youtube_readiness": youtube_readiness,
                "final_video_exists": bool(project.get("final_video_path"))
                and Path(project["final_video_path"]).exists(),
            }
        )


class RegenerateThumbnailsUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        thumbnail_service: ThumbnailService | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.thumbnail_service = thumbnail_service or ThumbnailService()

    def execute(self, project_id: int) -> UseCaseResult:
        script_version = self.repo.get_latest_script_version(project_id)
        script_payload = json.loads(script_version["full_script_json"]) if script_version else {}
        self.thumbnail_service.ensure_creator_thumbnails(
            project_id,
            script_payload.get("titles", []),
            self.repo.list_scenes(project_id),
            force=True,
        )
        return UseCaseResult.ok("Generated fresh creator thumbnail variants.", redirect_endpoint="publish.final_review")


class SelectThumbnailUseCase:
    def __init__(self, repo: ProjectRepository | None = None) -> None:
        self.repo = repo or ProjectRepository()

    def execute(self, project_id: int, thumbnail_path: str) -> UseCaseResult:
        self.repo.update_project(project_id, selected_thumbnail_path=thumbnail_path.strip())
        return UseCaseResult.ok("Thumbnail selected.", redirect_endpoint="publish.final_review")


class MarkMasterReadyUseCase:
    def __init__(self, repo: ProjectRepository | None = None) -> None:
        self.repo = repo or ProjectRepository()

    def execute(self, project_id: int) -> UseCaseResult:
        project = self.repo.get_project(project_id)
        if not project.get("final_video_path") or not Path(project["final_video_path"]).exists():
            return UseCaseResult.fail(
                "Assemble the full master video before marking the project ready.",
                redirect_endpoint="publish.final_review",
            )
        self.repo.update_project(project_id, state="ready_to_publish")
        return UseCaseResult.ok(
            "Master marked ready for publish review. QA warnings remain visible on this page.",
            redirect_endpoint="publish.final_review",
        )


class SaveUploadPackageUseCase:
    def __init__(
        self,
        repo: ProjectRepository | None = None,
        final_service: FinalProductionService | None = None,
    ) -> None:
        self.repo = repo or ProjectRepository()
        self.final_service = final_service or FinalProductionService(self.repo)

    def execute(self, project_id: int, form: Any) -> UseCaseResult:
        self.repo.update_project(
            project_id,
            selected_title=form.get("selected_title", "").strip(),
            selected_description=form.get("selected_description", "").strip(),
            selected_thumbnail_path=form.get("selected_thumbnail_path", "").strip(),
        )
        upload_package = self.final_service.build_upload_package(project_id)
        return UseCaseResult.ok(
            "Review metadata saved.",
            data={"upload_package": upload_package},
            redirect_endpoint="publish.final_review",
        )
