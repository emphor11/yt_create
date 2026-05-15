from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


class BeatClipGenerator:
    """Renders structured beat clips and concatenates them into a scene timeline."""

    def __init__(
        self,
        *,
        concepts,
        repo,
        render_specs,
        remotion,
        logger,
        ten_minute_finance_enabled: Callable[[], bool],
        load_scene_beats: Callable[[dict, float], list[dict]],
        normalize_beat_durations: Callable[[list[dict], float], list[dict]],
        regenerated_beat_from_scene: Callable[[dict, dict, int], dict],
        visual_debug_enabled: Callable[[], bool],
        validated_beat_for_debug: Callable[[dict], dict],
        debug_entry: Callable[[dict, object], dict],
        print_visual_debug: Callable[[dict, list[dict]], None],
        pexels_broll: Callable[[int, Path, int, str, float], tuple[Path, str]],
        concat_beat_clips: Callable[[list[Path], Path, float], None],
    ) -> None:
        self.concepts = concepts
        self.repo = repo
        self.render_specs = render_specs
        self.remotion = remotion
        self.logger = logger
        self.ten_minute_finance_enabled = ten_minute_finance_enabled
        self.load_scene_beats = load_scene_beats
        self.normalize_beat_durations = normalize_beat_durations
        self.regenerated_beat_from_scene = regenerated_beat_from_scene
        self.visual_debug_enabled = visual_debug_enabled
        self.validated_beat_for_debug = validated_beat_for_debug
        self.debug_entry = debug_entry
        self.print_visual_debug = print_visual_debug
        self.pexels_broll = pexels_broll
        self.concat_beat_clips = concat_beat_clips

    def generate(
        self,
        *,
        config: dict,
        project_id: int,
        image_root: Path,
        scene: dict,
        scene_duration: float,
    ) -> tuple[Path, str]:
        if self.ten_minute_finance_enabled():
            beats = self.concepts.build_scene_beats(
                str(scene.get("narration_text") or scene.get("visual_instruction") or ""),
                scene_duration,
                project_id=project_id,
            )
            scene = {**scene, "visual_plan_json": json.dumps(beats, ensure_ascii=False)}
            if scene.get("id"):
                self.repo.update_scene(scene["id"], visual_plan_json=scene["visual_plan_json"])
        else:
            beats = self.load_scene_beats(scene, scene_duration)
        beats = self.normalize_beat_durations(beats, scene_duration)
        scene_order = int(scene["scene_order"])
        scene_dir = image_root / f"scene-{scene_order:02d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        successful: list[Path] = []
        sources: list[str] = []
        debug_entries: list[dict] = []

        if not config.get("REMOTION_ENABLED", True):
            raise RuntimeError("Remotion visuals are required, but REMOTION_ENABLED=false.")

        for index, beat in enumerate(beats):
            beat_index = int(beat.get("beat_index", index))
            try:
                source_asset_path = None
                if self.render_specs.beat_requires_source_asset(beat):
                    if not config.get("PEXELS_API_KEY") and not config.get("PIXABAY_API_KEY"):
                        beat = self.regenerated_beat_from_scene(scene, beat, beat_index)
                    else:
                        query = self.render_specs.broll_query_for_beat(beat) or str(scene.get("visual_instruction") or scene.get("narration_text"))
                        try:
                            source_asset_path, _asset_source = self.pexels_broll(
                                project_id,
                                image_root,
                                (scene_order * 100) + beat_index,
                                query,
                                float(beat.get("estimated_duration_sec") or 3),
                            )
                        except Exception as exc:
                            self.logger.log(
                                "visual_generation",
                                "failed",
                                f"Pexels b-roll failed for scene {scene_order} beat {beat_index} ({exc}). Regenerating from narration.",
                                project_id,
                            )
                            beat = self.regenerated_beat_from_scene(scene, beat, beat_index)
                validated_beat = self.validated_beat_for_debug(beat)
                spec = self.render_specs.beat_spec(beat, source_asset_path=source_asset_path)
                if self.visual_debug_enabled():
                    debug_entries.append(self.debug_entry(validated_beat, spec))
                beat_path = scene_dir / f"beat-{beat_index:02d}.mp4"
                self.remotion.render_video(spec, beat_path)
                successful.append(beat_path)
                sources.append(spec.source)
                self.logger.log(
                    "visual_generation",
                    "completed",
                    f"Rendered scene {scene_order} beat {beat_index} ({beat.get('beat_type')}).",
                    project_id,
                )
            except Exception as exc:
                self.logger.log(
                    "visual_generation",
                    "failed",
                    f"Beat render failed for scene {scene_order} beat {beat_index}: {exc}",
                    project_id,
                )

        if not successful:
            self.logger.log(
                "visual_generation",
                "failed",
                f"No beats rendered for scene {scene_order}; rendering short text fallback.",
                project_id,
            )
            fallback_path = scene_dir / "beat-fallback.mp4"
            fallback_spec = self.render_specs.beat_spec(
                {
                    "beat_type": "text_burst",
                    "content": scene.get("visual_instruction") or scene.get("narration_text") or "money reality",
                    "caption": "",
                    "color": "orange",
                    "estimated_duration_sec": min(max(scene_duration, 2.5), 4.0),
                }
            )
            if self.visual_debug_enabled():
                debug_entries.append(
                    self.debug_entry(
                        {"beat_type": "text_burst", "content": scene.get("visual_instruction") or scene.get("narration_text") or "money reality"},
                        fallback_spec,
                    )
                )
            self.remotion.render_video(fallback_spec, fallback_path)
            successful = [fallback_path]
            sources = [fallback_spec.source]

        if self.visual_debug_enabled():
            self.print_visual_debug(scene, debug_entries)

        timeline_path = image_root / f"scene-{scene_order:02d}_timeline.mp4"
        self.logger.log(
            "visual_generation",
            "running",
            f"Concatenating {len(successful)} beat clip(s) for scene {scene_order} into a {round(scene_duration, 2)}s timeline.",
            project_id,
        )
        self.concat_beat_clips(successful, timeline_path, scene_duration)
        return timeline_path, "beat_timeline:" + ",".join(sorted(set(sources)))
