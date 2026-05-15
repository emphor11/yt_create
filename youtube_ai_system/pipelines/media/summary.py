"""Media summary and coverage helpers."""

from __future__ import annotations

from typing import Any


class DynamicVisualCoverageCalculator:
    def compute(self, scenes: list[dict[str, Any]]) -> tuple[float, list[dict[str, Any]]]:
        if not scenes:
            return 0.0, []
        dynamic_count = sum(
            1
            for scene in scenes
            if scene.get("visual_path") and str(scene.get("visual_source") or "") not in {"remotion_failed", "unknown"}
        )
        return dynamic_count / len(scenes), scenes


class MediaSummaryBuilder:
    LIVE_PREFIXES = ("kokoro", "gtts", "edge_tts")

    def project_media_summary(self, scenes: list[dict[str, Any]]) -> dict[str, object]:
        audio_counts: dict[str, int] = {}
        visual_counts: dict[str, int] = {}
        generated_visuals = 0

        for scene in scenes:
            audio_source = scene.get("audio_source") or "unknown"
            visual_source = scene.get("visual_source") or "unknown"
            audio_counts[audio_source] = audio_counts.get(audio_source, 0) + 1
            visual_counts[visual_source] = visual_counts.get(visual_source, 0) + 1
            if scene.get("visual_path"):
                generated_visuals += 1

        total = len(scenes)
        if not total:
            voice_status = "not_run"
            voice_message = "Voice generation has not run yet."
            visual_status = "not_run"
            visual_message = "Visual generation has not run yet."
        else:
            live_count = self._live_count(audio_counts)
            if live_count == total:
                voice_status = "live"
                voice_message = "All scenes used generated narration audio."
            elif live_count > 0:
                voice_status = "mixed"
                voice_message = "Some scenes used generated narration and some used fallback audio."
            elif audio_counts.get("demo_silent") == total:
                voice_status = "demo"
                voice_message = "All scenes used demo fallback audio."
            elif audio_counts.get("voice_fallback_silent") == total:
                voice_status = "fallback"
                voice_message = "All scenes used last-resort silent fallback audio."
            else:
                voice_status = "unknown"
                voice_message = "Voice sources are mixed or unavailable."

            if generated_visuals == total:
                visual_status = "generated"
                visual_message = "Every scene has a generated visual asset."
            elif generated_visuals > 0:
                visual_status = "partial"
                visual_message = "Some scenes have generated visual assets."
            else:
                visual_status = "missing"
                visual_message = "No generated visual assets were found."

        return {
            "total_scenes": total,
            "voice_status": voice_status,
            "voice_message": voice_message,
            "audio_counts": audio_counts,
            "visual_status": visual_status,
            "visual_message": visual_message,
            "visual_counts": visual_counts,
        }

    def project_voice_summary(self, scenes: list[dict[str, Any]], mode: str) -> dict[str, object]:
        counts: dict[str, int] = {}
        for scene in scenes:
            source = scene.get("audio_source") or "unknown"
            counts[source] = counts.get(source, 0) + 1

        total = len(scenes)
        if not total:
            status = "not_run"
            message = "Voice generation has not run yet for this project."
        else:
            live_count = self._live_count(counts)
            if live_count == total:
                status = "live"
                message = "All scene audio was generated with a narration provider."
            elif live_count > 0:
                status = "mixed"
                message = "Some scenes used generated narration and some fell back to silent audio."
            elif counts.get("demo_silent") == total:
                status = "demo"
                message = "All scenes used demo silent audio."
            elif counts.get("voice_fallback_silent") == total:
                status = "fallback"
                message = "All scenes used last-resort silent fallback audio."
            else:
                status = "unknown"
                message = "Audio sources are mixed or unavailable."

        return {
            "mode": mode,
            "status": status,
            "message": message,
            "counts": counts,
            "total_scenes": total,
        }

    def _live_count(self, counts: dict[str, int]) -> int:
        return sum(count for source, count in counts.items() if str(source).startswith(self.LIVE_PREFIXES))

