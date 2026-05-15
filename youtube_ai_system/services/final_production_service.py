from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import current_app

from ..models.repository import ProjectRepository, utcnow
from ..pipelines.publishing.upload_package import UploadPackageBuilder
from ..quality.publishing_quality import PublishingReadinessPolicy
from .professional_scene_acceptance import ProfessionalSceneAcceptanceService


class FinalProductionService:
    """Builds the upload-facing review package from existing project assets."""

    def __init__(self, repo: ProjectRepository | None = None) -> None:
        self.repo = repo or ProjectRepository()
        self.package_builder = UploadPackageBuilder()
        self.readiness_policy = PublishingReadinessPolicy()

    def build_upload_package(self, project_id: int) -> dict[str, Any]:
        project = self.repo.get_project(project_id)
        scenes = self.repo.list_scenes(project_id)
        script_payload = self._latest_script_payload(project_id)
        title_options = self._title_options(project, script_payload)
        selected_title = project.get("selected_title") or title_options[0]
        description = project.get("selected_description") or self._description(project, scenes, script_payload)
        tags = self._tags(project, script_payload)
        package = {
            "project_id": project_id,
            "generated_at": utcnow(),
            "video_path": project.get("final_video_path") or "",
            "thumbnail_path": project.get("selected_thumbnail_path") or "",
            "title_options": title_options,
            "selected_title": selected_title,
            "description": description,
            "tags": tags,
            "chapters": self._chapters(scenes),
            "pinned_comment": self._pinned_comment(selected_title),
            "publish_checklist": self.publish_readiness(project_id),
        }
        output_path = self.package_path(project_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(package, indent=2, ensure_ascii=False), encoding="utf-8")
        return package

    def publish_readiness(self, project_id: int) -> dict[str, Any]:
        project = self.repo.get_project(project_id)
        acceptance = ProfessionalSceneAcceptanceService(self.repo).evaluate_project(project_id)
        return self.readiness_policy.evaluate(project, acceptance)

    def package_path(self, project_id: int) -> Path:
        return Path(current_app.config["STORAGE_ROOT"]) / "video" / str(project_id) / "upload_package.json"

    def _latest_script_payload(self, project_id: int) -> dict[str, Any]:
        script_version = self.repo.get_latest_script_version(project_id)
        if not script_version:
            return {}
        try:
            return json.loads(script_version["full_script_json"] or "{}")
        except json.JSONDecodeError:
            return {}

    def _title_options(self, project: dict[str, Any], script_payload: dict[str, Any]) -> list[str]:
        return self.package_builder.title_options(project, script_payload)

    def _description(
        self,
        project: dict[str, Any],
        scenes: list[dict[str, Any]],
        script_payload: dict[str, Any],
    ) -> str:
        return self.package_builder.description(project, scenes, script_payload)

    def _tags(self, project: dict[str, Any], script_payload: dict[str, Any]) -> list[str]:
        return self.package_builder.tags(project, script_payload)

    def _chapters(self, scenes: list[dict[str, Any]]) -> list[dict[str, str]]:
        return self.package_builder.chapters(scenes)

    def _chapter_title(self, scene: dict[str, Any]) -> str:
        return self.package_builder.chapter_title(scene)

    def _pinned_comment(self, title: str) -> str:
        return self.package_builder.pinned_comment(title)

    def _timestamp(self, seconds: float) -> str:
        return self.package_builder.timestamp(seconds)

    def _dedupe(self, values: list[str]) -> list[str]:
        return self.package_builder.dedupe(values)
