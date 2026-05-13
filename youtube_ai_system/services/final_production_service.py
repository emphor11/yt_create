from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from flask import current_app

from ..models.repository import ProjectRepository, utcnow
from .professional_scene_acceptance import ProfessionalSceneAcceptanceService


class FinalProductionService:
    """Builds the upload-facing review package from existing project assets."""

    def __init__(self, repo: ProjectRepository | None = None) -> None:
        self.repo = repo or ProjectRepository()

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
        final_video_path = Path(project.get("final_video_path") or "")
        thumbnail_path = Path(project.get("selected_thumbnail_path") or "")
        checks = [
            {
                "key": "full_video",
                "label": "Full master video assembled",
                "passed": bool(project.get("final_video_path")) and final_video_path.exists(),
            },
            {
                "key": "thumbnail",
                "label": "Creator thumbnail selected",
                "passed": bool(project.get("selected_thumbnail_path")) and thumbnail_path.exists(),
            },
            {
                "key": "metadata",
                "label": "Title and description saved",
                "passed": bool(project.get("selected_title")) and bool(project.get("selected_description")),
            },
            {
                "key": "scene_acceptance",
                "label": "Professional scene QA passes",
                "passed": acceptance.passed,
                "warning": not acceptance.passed,
            },
        ]
        return {
            "passed": all(check["passed"] for check in checks),
            "checks": checks,
            "blocking_issues": acceptance.to_dict().get("blocking_issues", []),
            "warning_count": len(acceptance.blocking_issues),
        }

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
        raw_titles = script_payload.get("titles") or []
        titles = [str(title).strip() for title in raw_titles if str(title).strip()]
        if project.get("working_title"):
            titles.append(str(project["working_title"]).strip())
        topic = str(project.get("topic") or "money habits").strip()
        if topic:
            titles.extend(
                [
                    f"Why {topic} Feels So Hard",
                    f"The Money Mistake Nobody Notices",
                    f"Fix This Before Your Next Salary",
                ]
            )
        return self._dedupe(titles)[:5] or ["The Money Mistake Nobody Notices"]

    def _description(
        self,
        project: dict[str, Any],
        scenes: list[dict[str, Any]],
        script_payload: dict[str, Any],
    ) -> str:
        base = str(script_payload.get("description") or "").strip()
        if not base:
            topic = project.get("topic") or project.get("working_title") or "personal finance"
            base = f"A practical finance breakdown about {topic}, with clear examples and visual explanations."
        chapter_lines = [f"{chapter['timestamp']} {chapter['title']}" for chapter in self._chapters(scenes)]
        tags = ", ".join(self._tags(project, script_payload)[:8])
        return "\n\n".join(
            part
            for part in [
                base,
                "Chapters:\n" + "\n".join(chapter_lines) if chapter_lines else "",
                f"Topics: {tags}" if tags else "",
                "Subscribe for sharper money decisions, one visual lesson at a time.",
            ]
            if part
        )

    def _tags(self, project: dict[str, Any], script_payload: dict[str, Any]) -> list[str]:
        raw_tags = script_payload.get("tags") or []
        tags = [str(tag).strip().lstrip("#") for tag in raw_tags if str(tag).strip()]
        tags.extend(
            [
                str(project.get("channel_niche") or "personal finance India"),
                str(project.get("topic") or "money management"),
                "salary mistakes",
                "finance explained",
                "money habits",
            ]
        )
        return self._dedupe([tag for tag in tags if tag])[:15]

    def _chapters(self, scenes: list[dict[str, Any]]) -> list[dict[str, str]]:
        chapters: list[dict[str, str]] = []
        elapsed = 0.0
        for scene in scenes:
            title = self._chapter_title(scene)
            chapters.append({"timestamp": self._timestamp(elapsed), "title": title})
            elapsed += float(scene.get("audio_duration_sec") or 0.0)
        return chapters

    def _chapter_title(self, scene: dict[str, Any]) -> str:
        text = str(scene.get("narration_text") or scene.get("visual_instruction") or "").strip()
        text = re.sub(r"\s+", " ", text)
        words = text.split()[:7]
        title = " ".join(words).strip(".,:;!?")
        return title or f"Scene {scene.get('scene_order', '')}".strip()

    def _pinned_comment(self, title: str) -> str:
        return f"What part of this video felt most familiar: the spending, the planning, or the surprise at month-end?"

    def _timestamp(self, seconds: float) -> str:
        total_seconds = max(0, int(round(seconds)))
        minutes, secs = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = re.sub(r"\s+", " ", value).strip()
            key = normalized.lower()
            if normalized and key not in seen:
                seen.add(key)
                result.append(normalized)
        return result
