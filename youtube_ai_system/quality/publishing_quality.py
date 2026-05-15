"""Publishing readiness quality policy."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class PublishingReadinessPolicy:
    def evaluate(self, project: dict[str, Any], acceptance: Any) -> dict[str, Any]:
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
