"""Pure upload package helpers for final review."""

from __future__ import annotations

import re
from typing import Any


class UploadPackageBuilder:
    def title_options(self, project: dict[str, Any], script_payload: dict[str, Any]) -> list[str]:
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
        return self.dedupe(titles)[:5] or ["The Money Mistake Nobody Notices"]

    def description(
        self,
        project: dict[str, Any],
        scenes: list[dict[str, Any]],
        script_payload: dict[str, Any],
    ) -> str:
        base = str(script_payload.get("description") or "").strip()
        if not base:
            topic = project.get("topic") or project.get("working_title") or "personal finance"
            base = f"A practical finance breakdown about {topic}, with clear examples and visual explanations."
        chapter_lines = [f"{chapter['timestamp']} {chapter['title']}" for chapter in self.chapters(scenes)]
        tags = ", ".join(self.tags(project, script_payload)[:8])
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

    def tags(self, project: dict[str, Any], script_payload: dict[str, Any]) -> list[str]:
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
        return self.dedupe([tag for tag in tags if tag])[:15]

    def chapters(self, scenes: list[dict[str, Any]]) -> list[dict[str, str]]:
        chapters: list[dict[str, str]] = []
        elapsed = 0.0
        for scene in scenes:
            title = self.chapter_title(scene)
            chapters.append({"timestamp": self.timestamp(elapsed), "title": title})
            elapsed += float(scene.get("audio_duration_sec") or 0.0)
        return chapters

    def chapter_title(self, scene: dict[str, Any]) -> str:
        text = str(scene.get("narration_text") or scene.get("visual_instruction") or "").strip()
        text = re.sub(r"\s+", " ", text)
        words = text.split()[:7]
        title = " ".join(words).strip(".,:;!?")
        return title or f"Scene {scene.get('scene_order', '')}".strip()

    def pinned_comment(self, title: str) -> str:
        return f"What part of this video felt most familiar: the spending, the planning, or the surprise at month-end?"

    def timestamp(self, seconds: float) -> str:
        total_seconds = max(0, int(round(seconds)))
        minutes, secs = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = re.sub(r"\s+", " ", value).strip()
            key = normalized.lower()
            if normalized and key not in seen:
                seen.add(key)
                result.append(normalized)
        return result

