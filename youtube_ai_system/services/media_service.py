from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from flask import current_app
from PIL import Image, ImageDraw, ImageFont
import requests

from ..models.repository import ProjectRepository
from .concept_service import ConceptService
from .remotion_service import RemotionService
from .render_spec_service import RenderSpec
from .render_spec_service import RenderSpecService
from .run_log import RunLogger
from .scene_builder import build_scenes
from .story_pipeline import StoryPipeline
from .voice_service import VoiceService

# ---------------------------------------------------------------------------
# Colour palettes
# ---------------------------------------------------------------------------
SENTIMENT_COLORS = {
    "negative": "#E63946",
    "positive": "#2EC4B6",
    "neutral": "#FF9F1C",
}

CHART_COLORS = {
    "red": "#E63946",
    "green": "#2EC4B6",
    "orange": "#FF9F1C",
    "blue": "#4361EE",
    "teal": "#4CC9F0",
}

PIE_PALETTE = ["#4361EE", "#E63946", "#2EC4B6", "#FF9F1C", "#7209B7"]


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _fade_rgb(color: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    return tuple(int(c * max(0.0, min(1.0, alpha))) for c in color)


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------
_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _get_font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    key = ("bold" if bold else "regular", size)
    if key not in _FONT_CACHE:
        fonts_dir = Path(__file__).resolve().parent.parent / "static" / "fonts"
        filename = "NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf"
        font_path = fonts_dir / filename
        if font_path.exists():
            _FONT_CACHE[key] = ImageFont.truetype(str(font_path), size)
        else:
            _FONT_CACHE[key] = ImageFont.load_default(size=size)
    return _FONT_CACHE[key]


class MediaService:
    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.logger = RunLogger()
        self.voice_service = VoiceService()
        self.render_specs = RenderSpecService()
        self.remotion = RemotionService()
        self.concepts = ConceptService()
        self.story_pipeline = StoryPipeline(logger=self.logger)

    # -----------------------------------------------------------------------
    # Public entry points
    # -----------------------------------------------------------------------
    def generate_voice_and_visuals(self, project_id: int) -> None:
        project = self.repo.get_project(project_id)
        scenes = self.repo.list_scenes(project_id)
        storage_root = Path(current_app.config["STORAGE_ROOT"]).expanduser().resolve()
        audio_root = storage_root / "audio" / str(project_id)
        image_root = storage_root / "images" / str(project_id)
        audio_root.mkdir(parents=True, exist_ok=True)
        image_root.mkdir(parents=True, exist_ok=True)
        self.logger.log("media_generation", "running", "Generating scene media.", project_id)

        for scene in scenes:
            self._generate_scene_media(project_id, scene, audio_root, image_root)

        live_audio_count = sum(
            1
            for scene in self.repo.list_scenes(project_id)
            if str(scene.get("audio_source") or "").startswith(("kokoro", "gtts", "edge_tts"))
        )
        self.logger.log(
            "media_generation",
            "completed",
            (
                f"Generated media assets for {len(scenes)} scenes in project '{project['working_title']}'. "
                f"Narration voice used on {live_audio_count} scene(s)."
            ),
            project_id,
        )

    def generate_scene_media(self, project_id: int, scene_id: int) -> None:
        scene = self.repo.get_scene(scene_id)
        if not scene or int(scene["video_project_id"]) != int(project_id):
            raise ValueError(f"Scene {scene_id} does not belong to project {project_id}.")
        storage_root = Path(current_app.config["STORAGE_ROOT"]).expanduser().resolve()
        audio_root = storage_root / "audio" / str(project_id)
        image_root = storage_root / "images" / str(project_id)
        audio_root.mkdir(parents=True, exist_ok=True)
        image_root.mkdir(parents=True, exist_ok=True)
        self._generate_scene_media(project_id, scene, audio_root, image_root, force=True)

    def _generate_scene_media(
        self,
        project_id: int,
        scene: dict,
        audio_root: Path,
        image_root: Path,
        force: bool = False,
    ) -> None:
        if not force and self._scene_media_complete(scene):
            if self._visual_debug_enabled():
                self._print_existing_scene_debug(scene)
            self.logger.log(
                "media_generation",
                "completed",
                f"Skipping scene {scene['scene_order']} because media already exists.",
                project_id,
            )
            return

        self.logger.log(
            "voice_generation", "running",
            f"Starting voice generation for scene {scene['scene_order']}.",
            project_id,
        )
        try:
            voice_result = self._generate_audio(audio_root, scene["scene_order"], scene["narration_text"])
            audio_path = voice_result.audio_path
            subtitle_path = voice_result.subtitle_path
            duration = voice_result.duration_sec
            audio_source = voice_result.source
            audio_status = "completed"
        except Exception as exc:
            self.logger.log(
                "voice_generation", "failed",
                f"Voice generation failed for scene {scene['scene_order']}: {exc}",
                project_id,
            )
            duration = self._estimate_duration(scene["narration_text"])
            audio_path = audio_root / f"scene-{scene['scene_order']:02d}.wav"
            self._create_silent_wav(audio_path, duration)
            subtitle_path = None
            audio_source = "demo_silent"
            audio_status = "failed"

        self.logger.log(
            "voice_generation", audio_status,
            f"Voice generation {audio_status} for scene {scene['scene_order']} (source={audio_source}, duration={duration}s).",
            project_id,
        )

        self.logger.log(
            "visual_generation", "running",
            f"Starting visual generation for scene {scene['scene_order']} using scene renderer.",
            project_id,
        )
        visual_pattern = str(scene.get("visual_type") or "")
        visual_concept = str(scene.get("visual_instruction") or "")
        scene_section: dict[str, object] = {"visual_plan": self._scene_visual_plan(scene)}
        try:
            scene_section = self._section_for_scene_render(scene, duration, audio_path)
            visual_path, visual_source, visual_pattern, visual_concept = self._render_scene_with_scene_builder(
                image_root,
                scene["scene_order"],
                scene_section,
            )
            visual_status = "completed"
            self.logger.log(
                "visual_generation", "completed",
                f"Visual generation completed for scene {scene['scene_order']} (source={visual_source}).",
                project_id,
            )
        except Exception as exc:
            self.logger.log(
                "visual_generation", "failed",
                f"Visual generation failed for scene {scene['scene_order']}: {exc}",
                project_id,
            )
            visual_path = None
            visual_source = "remotion_failed"
            visual_status = "failed"

        scene_status = "generated" if (audio_status == "completed" and visual_status == "completed") else "failed"
        self.repo.update_scene(
            scene["id"],
            audio_path=str(Path(audio_path).expanduser().resolve()),
            audio_duration_sec=duration,
            subtitle_path=str(subtitle_path) if subtitle_path else None,
            visual_path=str(visual_path) if visual_path else None,
            audio_source=audio_source,
            visual_source=visual_source,
            visual_type=visual_pattern,
            visual_instruction=visual_concept,
            visual_plan_json=json.dumps(scene_section.get("visual_plan") or [], ensure_ascii=False),
            status=scene_status,
        )

    def compute_dynamic_visual_ratio(self, project_id: int) -> tuple[float, list[dict]]:
        scenes = self.repo.list_scenes(project_id)
        if not scenes:
            return 0.0, []
        dynamic_count = sum(
            1
            for scene in scenes
            if scene.get("visual_path") and str(scene.get("visual_source") or "") not in {"remotion_failed", "unknown"}
        )
        return dynamic_count / len(scenes), scenes

    def _section_for_scene_render(self, scene: dict, audio_duration: float, audio_path: Path) -> dict:
        narration = str(scene.get("narration_text") or "")
        kind = str(scene.get("kind") or "body")
        # Pass any stored visual_scene forward so the story pipeline fast-path
        # can use Groq-generated mechanism/beats rather than rebuilding from text.
        stored_visual_scene = self._json_dict_from_scene_field(scene.get("visual_scene_json"))
        intelligence = self._section_intelligence_from_narration(narration, kind, visual_scene=stored_visual_scene)
        stored_finance_concept = self._json_dict_from_scene_field(scene.get("finance_concept_json"))
        if stored_finance_concept:
            intelligence["finance_concept"] = stored_finance_concept

        # Prefer the freshly computed visual plan — it reflects all pipeline
        # improvements. Only fall back to the stored plan if nothing was computed.
        visual_plan = list(intelligence.get("visual_plan") or []) or self._scene_visual_plan(scene)
        return {
            "text": narration,
            "weight": self._weight_for_scene_kind(kind),
            "visual_plan": visual_plan,
            "audio_file": str(audio_path),
            "audio_duration": float(audio_duration),
            "finance_concept": intelligence.get("finance_concept") or {},
            "narrative_arc": intelligence.get("narrative_arc") or {},
            "visual_story": intelligence.get("visual_story") or {},
            "story_state": intelligence.get("story_state") or {},
            "direction": intelligence.get("direction"),
            "visual_mode": intelligence.get("visual_mode"),
            "cinematic_intent": intelligence.get("cinematic_intent") or {},
            "concept_type": str(intelligence.get("concept_type") or ""),
            "theme": intelligence.get("theme") or {},
            "state": intelligence.get("state") or {},
            "visual_type": str(intelligence.get("visual_type") or ""),
            "dominant_entity": str(intelligence.get("dominant_entity") or "money"),
            "idea_type": str(intelligence.get("idea_type") or "emphasis"),
            "has_numbers": bool(intelligence.get("has_numbers")),
            "has_comparison": bool(intelligence.get("has_comparison")),
            "has_causation": bool(intelligence.get("has_causation")),
            "visual_scene": stored_visual_scene or intelligence.get("visual_scene") or {},
        }


    def _scene_visual_plan(self, scene: dict) -> list[dict]:
        raw = scene.get("visual_plan_json")
        if not raw:
            return []
        if isinstance(raw, list):
            return raw
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        return parsed if isinstance(parsed, list) else []

    def _derived_visual_plan_from_narration(self, narration: str, kind: str) -> list[dict]:
        section = self._section_intelligence_from_narration(narration, kind)
        return list(section.get("visual_plan") or [])

    def _section_intelligence_from_narration(self, narration: str, kind: str, visual_scene: dict | None = None) -> dict:
        signals = self._scene_text_signals(narration)
        section: dict = {
            "type": "problem" if kind == "hook" else ("optimization" if kind == "outro" else "explanation"),
            "text": narration,
            "weight": self._weight_for_scene_kind(kind),
            **signals,
        }
        # If the scene already has a Groq-generated visual_scene (mechanism, visual_beats, etc.)
        # inject it so story_pipeline._visual_scene_source() fast-paths this section.
        if visual_scene:
            section["visual_scene"] = visual_scene
        story_plan = {"hook": narration[:60], "agenda": [], "sections": [section]}
        story_plan = self.story_pipeline.attach_section_concepts(story_plan)
        story_plan = self.story_pipeline.attach_section_narrative_arc(story_plan)
        # Seed a concept-aware visual_story so _recurring_objects() picks the right objects
        # instead of always defaulting to ["phone_account", "salary_balance"].
        sections_after_concepts = story_plan.get("sections") or [{}]
        if sections_after_concepts:
            concept_type = str(sections_after_concepts[0].get("concept_type") or "")
            if not concept_type:
                # Derive from finance_concept produced by attach_section_concepts
                fc = sections_after_concepts[0].get("finance_concept") or {}
                concept_type = str(fc.get("concept_type") or "").lower()
            seed_objects = self.story_pipeline.visual_story_engine.CONCEPT_TO_OBJECTS.get(
                concept_type, ["phone_account", "salary_balance"]
            )
            story_plan["visual_story"] = {
                "protagonist": {"role": "young_salaried_professional"},
                "recurring_objects": list(seed_objects),
            }
        story_plan = self.story_pipeline.attach_visual_story(story_plan)
        story_plan = self.story_pipeline.attach_section_visual_plan(story_plan)
        return dict((story_plan.get("sections") or [{}])[0])

    def _scene_text_signals(self, narration: str) -> dict[str, object]:
        return {
            "dominant_entity": self._dominant_entity_from_text(narration),
            "idea_type": self._idea_type_from_text(narration),
            "has_numbers": bool(re.search(r"₹|Rs\.?\s*|\d+|%", narration, re.IGNORECASE)),
            "has_comparison": bool(
                re.search(r"\bvs\b|\bversus\b|\bbut\b|\bhowever\b|\binstead\b|\bcompared to\b", narration, re.IGNORECASE)
            ),
            "has_causation": bool(
                re.search(
                    r"\bbecause\b|\bso\b|\btherefore\b|\bleads to\b|\bresults in\b|\bmeans\b|\bcreates\b|\bcosts\b|\bbecomes\b",
                    narration,
                    re.IGNORECASE,
                )
            ),
        }

    def _dominant_entity_from_text(self, narration: str) -> str:
        lowered = narration.lower()
        ordered_entities = (
            "salary",
            "income",
            "debt",
            "loan",
            "credit",
            "interest",
            "emi",
            "savings",
            "investment",
            "sip",
            "fd",
            "inflation",
            "tax",
            "expense",
            "expenses",
            "rent",
        )
        for entity in ordered_entities:
            if re.search(rf"\b{re.escape(entity)}\b", lowered):
                return "expense" if entity == "expenses" else entity
        return "money"

    def _idea_type_from_text(self, narration: str) -> str:
        lowered = narration.lower()
        if any(token in lowered for token in ("vs", "versus", "compare", "comparison", "difference", "instead", "while")):
            return "comparison"
        if any(token in lowered for token in ("grow", "grows", "growth", "increase", "rise", "compound", "multiply", "build wealth")):
            return "growth"
        if any(token in lowered for token in ("lose", "lost", "drain", "shrinks", "shrink", "fall", "drop", "gone", "vanish", "disappear", "erode", "leak")):
            return "decay"
        if any(token in lowered for token in ("risk", "danger", "trap", "mistake", "debt", "interest", "minimum due")):
            return "risk"
        if any(token in lowered for token in ("automate", "track", "budget", "allocate", "save first", "invest first")):
            return "process"
        return "emphasis"

    def _json_dict_from_scene_field(self, value: object) -> dict:
        if not value:
            return {}
        if isinstance(value, dict):
            return value
        if not isinstance(value, str):
            return {}
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _weight_for_scene_kind(self, kind: str) -> dict[str, object]:
        if kind == "hook":
            return {"level": "high", "score": 0.9}
        if kind == "outro":
            return {"level": "medium", "score": 0.7}
        return {"level": "medium", "score": 0.55}

    def _render_scene_with_scene_builder(
        self,
        image_root: Path,
        scene_order: int,
        section: dict,
    ) -> tuple[Path, str, str, str]:
        scene_result = build_scenes([section])["scenes"][0]
        output_path = image_root / f"scene-{scene_order:02d}.mp4"
        spec = RenderSpec(
            composition="VideoRenderer",
            props={"scenes": [scene_result]},
            duration_sec=float(scene_result.get("duration") or 0),
            source="remotion_scene_builder",
        )
        self.remotion.render_video(spec, output_path)
        return (
            output_path,
            "remotion_scene_builder",
            str(scene_result.get("pattern") or ""),
            str(scene_result.get("concept") or ""),
        )

    def project_media_summary(self, project_id: int) -> dict[str, object]:
        scenes = self.repo.list_scenes(project_id)
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
            live_count = sum(
                count
                for source, count in audio_counts.items()
                if str(source).startswith(("kokoro", "gtts", "edge_tts"))
            )
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

    def project_voice_summary(self, project_id: int) -> dict[str, object]:
        scenes = self.repo.list_scenes(project_id)
        counts: dict[str, int] = {}
        for scene in scenes:
            source = scene.get("audio_source") or "unknown"
            counts[source] = counts.get(source, 0) + 1

        total = len(scenes)
        if not total:
            status = "not_run"
            message = "Voice generation has not run yet for this project."
        else:
            live_count = sum(
                count
                for source, count in counts.items()
                if str(source).startswith(("kokoro", "gtts", "edge_tts"))
            )
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
            "mode": current_app.config.get("VOICE_PROVIDER", current_app.config.get("VOICE_MODE", "demo")),
            "status": status,
            "message": message,
            "counts": counts,
            "total_scenes": total,
        }

    def run_voice_check(self) -> dict[str, object]:
        audio_root = Path(current_app.config["STORAGE_ROOT"]) / "audio" / "voice-check"
        audio_root.mkdir(parents=True, exist_ok=True)
        try:
            result = self.voice_service.run_voice_check(audio_root)
        except Exception as exc:
            friendly_error = self._summarize_tts_error(exc)
            self.logger.log("voice_check", "failed", f"Voice check failed ({friendly_error}).")
            return {
                "mode": current_app.config.get("VOICE_PROVIDER", "kokoro"),
                "status": "failed",
                "audio_source": "voice_failed",
                "audio_path": None,
                "subtitle_path": None,
                "duration": None,
                "message": f"Voice check failed: {friendly_error}",
            }

        live = result.source not in {"demo_silent", "voice_fallback_silent"}
        self.logger.log("voice_check", "completed", f"Voice check completed with {result.source}.")
        return {
            "mode": current_app.config.get("VOICE_PROVIDER", "kokoro"),
            "status": "live" if live else "demo",
            "audio_source": result.source,
            "audio_path": str(result.audio_path),
            "subtitle_path": str(result.subtitle_path) if result.subtitle_path else None,
            "duration": result.duration_sec,
            "message": (
                f"Voice check completed with {result.source}."
                if live
                else "Voice check used silent fallback audio. Install/configure Kokoro for live narration."
            ),
        }

    # -----------------------------------------------------------------------
    # Audio generation
    # -----------------------------------------------------------------------
    def _estimate_duration(self, narration: str) -> float:
        words = max(len(narration.split()), 1)
        return round(max(words / 2.4, 2.5), 2)

    def _generate_audio(self, audio_root: Path, scene_order: int, narration: str):
        return self.voice_service.generate_scene_audio(audio_root, scene_order, narration)

    def _edge_tts_audio(
        self, audio_root: Path, scene_order: int, narration: str
    ) -> tuple[Path, Path | None, float, str]:
        """Generate audio using edge-tts async Python API."""
        import edge_tts

        audio_path = audio_root / f"scene-{scene_order:02d}.mp3"
        subtitle_path = audio_root / f"scene-{scene_order:02d}.vtt"

        voice = current_app.config["EDGE_TTS_VOICE"]
        rate = current_app.config["EDGE_TTS_RATE"]

        async def _generate() -> None:
            communicate = edge_tts.Communicate(narration, voice, rate=rate)
            submaker = edge_tts.SubMaker()
            with open(str(audio_path), "wb") as audio_file:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_file.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        submaker.feed(chunk)
            sub_content = submaker.generate_subs()
            if sub_content and sub_content.strip():
                subtitle_path.write_text(sub_content, encoding="utf-8")

        timeout_sec = int(current_app.config.get("EDGE_TTS_CLI_TIMEOUT", 30))
        try:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(asyncio.wait_for(_generate(), timeout=timeout_sec))
            finally:
                loop.close()
        except asyncio.TimeoutError as exc:
            self._cleanup_empty_file(audio_path)
            self._cleanup_empty_file(subtitle_path)
            raise RuntimeError(f"Edge TTS timed out after {timeout_sec}s") from exc
        except Exception as exc:
            self._cleanup_empty_file(audio_path)
            self._cleanup_empty_file(subtitle_path)
            raise

        if not audio_path.exists() or audio_path.stat().st_size == 0:
            self._cleanup_empty_file(audio_path)
            raise RuntimeError("Edge TTS did not produce an audio file.")

        if subtitle_path.exists() and subtitle_path.stat().st_size == 0:
            subtitle_path.unlink(missing_ok=True)
            sub_out = None
        else:
            sub_out = subtitle_path if subtitle_path.exists() else None

        duration = self._probe_duration(audio_path)
        return audio_path, sub_out, duration, "edge_tts"

    def _cleanup_empty_file(self, path: Path) -> None:
        """Remove a file if it exists and is empty (0 bytes)."""
        try:
            if path.exists() and path.stat().st_size == 0:
                path.unlink(missing_ok=True)
        except OSError:
            pass

    # -----------------------------------------------------------------------
    # Visual generation — dispatcher
    # -----------------------------------------------------------------------
    def _generate_visual(
        self,
        project_id: int,
        image_root: Path,
        scene: dict,
        scene_order: int,
        narration: str,
        visual_type: str | None,
        visual_instruction: str | None,
        target_duration: float,
    ) -> tuple[Path, str]:
        source_asset_path = None
        if visual_type == "broll":
            source_asset_path = None

        if not current_app.config.get("REMOTION_ENABLED", True):
            raise RuntimeError("Remotion visuals are required, but REMOTION_ENABLED=false.")

        spec = self.render_specs.scene_spec(
            {**scene, "visual_type": visual_type},
            target_duration,
            source_asset_path=source_asset_path,
        )
        if self._visual_debug_enabled():
            validated_scene = {
                "visual_type": visual_type,
                "visual_instruction": visual_instruction,
                "narration_text": narration,
            }
            self._print_visual_debug(
                {**scene, "scene_order": scene_order, "narration_text": narration},
                [
                    {
                        "visual_logic": {"type": "scene", "content": visual_instruction or narration},
                        "validated_beat": validated_scene,
                        "render_spec": {"component": spec.composition, "props": spec.props},
                    }
                ],
            )
        output_path = image_root / f"scene-{scene_order:02d}.mp4"
        self.remotion.render_video(spec, output_path)
        return output_path, spec.source

    def _scene_media_complete(self, scene: dict) -> bool:
        audio_path = scene.get("audio_path")
        visual_path = scene.get("visual_path")
        return (
            scene.get("status") == "generated"
            and bool(audio_path)
            and bool(visual_path)
            and Path(str(audio_path)).exists()
            and Path(str(visual_path)).exists()
        )

    def generate_beat_clips(
        self,
        project_id: int,
        image_root: Path,
        scene: dict,
        scene_duration: float,
    ) -> tuple[Path, str]:
        if self._ten_minute_finance_enabled():
            beats = self.concepts.build_scene_beats(
                str(scene.get("narration_text") or scene.get("visual_instruction") or ""),
                scene_duration,
                project_id=project_id,
            )
            scene = {**scene, "visual_plan_json": json.dumps(beats, ensure_ascii=False)}
            if scene.get("id"):
                self.repo.update_scene(scene["id"], visual_plan_json=scene["visual_plan_json"])
        else:
            beats = self._load_scene_beats(scene, scene_duration)
        beats = self._normalize_beat_durations(beats, scene_duration)
        scene_order = int(scene["scene_order"])
        scene_dir = image_root / f"scene-{scene_order:02d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        successful: list[Path] = []
        sources: list[str] = []
        debug_entries: list[dict] = []

        if not current_app.config.get("REMOTION_ENABLED", True):
            raise RuntimeError("Remotion visuals are required, but REMOTION_ENABLED=false.")

        for index, beat in enumerate(beats):
            beat_index = int(beat.get("beat_index", index))
            try:
                source_asset_path = None
                if self.render_specs.beat_requires_source_asset(beat):
                    if not current_app.config.get("PEXELS_API_KEY") and not current_app.config.get("PIXABAY_API_KEY"):
                        beat = self._regenerated_beat_from_scene(scene, beat, beat_index)
                    else:
                        query = self.render_specs.broll_query_for_beat(beat) or str(scene.get("visual_instruction") or scene.get("narration_text"))
                        try:
                            source_asset_path, _asset_source = self._pexels_broll(
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
                            beat = self._regenerated_beat_from_scene(scene, beat, beat_index)
                validated_beat = self._validated_beat_for_debug(beat)
                spec = self.render_specs.beat_spec(beat, source_asset_path=source_asset_path)
                if self._visual_debug_enabled():
                    debug_entries.append(self._debug_entry(validated_beat, spec))
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
            if self._visual_debug_enabled():
                debug_entries.append(self._debug_entry({"beat_type": "text_burst", "content": scene.get("visual_instruction") or scene.get("narration_text") or "money reality"}, fallback_spec))
            self.remotion.render_video(fallback_spec, fallback_path)
            successful = [fallback_path]
            sources = [fallback_spec.source]

        if self._visual_debug_enabled():
            self._print_visual_debug(scene, debug_entries)

        timeline_path = image_root / f"scene-{scene_order:02d}_timeline.mp4"
        self.logger.log(
            "visual_generation",
            "running",
            f"Concatenating {len(successful)} beat clip(s) for scene {scene_order} into a {round(scene_duration, 2)}s timeline.",
            project_id,
        )
        self._concat_beat_clips(successful, timeline_path, scene_duration)
        return timeline_path, "beat_timeline:" + ",".join(sorted(set(sources)))

    def _regenerated_beat_from_scene(self, scene: dict, original: dict, beat_index: int) -> dict:
        narration = str(scene.get("narration_text") or scene.get("visual_instruction") or "")
        classified_intent = self.render_specs.classifyIntent(narration)
        logic = self.render_specs.deriveFromNarration(narration, classified_intent=classified_intent)
        pattern = self.render_specs.LOGIC_TYPE_TO_PATTERN.get(str(logic.get("type") or ""), "MONEY_FLOW")
        return {
            "beat_index": beat_index,
            "intent": "COMPARISON" if logic.get("type") == "comparison" else "EXPLANATION",
            "pattern": pattern,
            "visual_logic": logic,
            "classified_intent": classified_intent,
            "narration": narration,
            "estimated_start_sec": original.get("estimated_start_sec", 0),
            "estimated_duration_sec": original.get("estimated_duration_sec", 3),
        }

    def _visual_debug_enabled(self) -> bool:
        return bool(current_app.config.get("VISUAL_DEBUG", False))

    def _print_existing_scene_debug(self, scene: dict) -> None:
        try:
            duration = self._estimate_duration(str(scene.get("narration_text") or ""))
            if self._ten_minute_finance_enabled():
                entries = []
                for beat in self._load_scene_beats(scene, duration):
                    validated_beat = self._validated_beat_for_debug(beat)
                    try:
                        spec = self.render_specs.beat_spec(beat)
                        entries.append(self._debug_entry(validated_beat, spec))
                    except Exception as exc:
                        entries.append(
                            {
                                "visual_logic": validated_beat.get("visual_logic") or {"type": str(validated_beat.get("beat_type") or "legacy")},
                                "validated_beat": validated_beat,
                                "render_spec": {"error": str(exc)},
                            }
                        )
                self._print_visual_debug(scene, entries)
                return

            try:
                spec = self.render_specs.scene_spec(scene, duration)
                render_spec = {"component": spec.composition, "props": spec.props}
            except Exception as exc:
                render_spec = {"error": str(exc)}
            self._print_visual_debug(
                scene,
                [
                    {
                        "visual_logic": {"type": "scene", "content": scene.get("visual_instruction") or scene.get("narration_text") or ""},
                        "validated_beat": {
                            "visual_type": scene.get("visual_type"),
                            "visual_instruction": scene.get("visual_instruction"),
                            "narration_text": scene.get("narration_text"),
                        },
                        "render_spec": render_spec,
                    }
                ],
            )
        except Exception as exc:
            print(f"\n--- SCENE {scene.get('scene_order', '?')} DEBUG ---\n")
            print("DEBUG_ERROR:")
            print(json.dumps(str(exc), ensure_ascii=False, indent=2))
            print("\n---\n")

    def _validated_beat_for_debug(self, beat: dict) -> dict:
        if self.render_specs._is_structured_beat(beat):
            return self.render_specs.normalize_structured_beat(beat)
        return dict(beat)

    def _debug_entry(self, validated_beat: dict, spec) -> dict:
        visual_logic = validated_beat.get("visual_logic")
        if visual_logic is None:
            visual_logic = {
                "type": str(validated_beat.get("beat_type") or "legacy"),
                "content": str(validated_beat.get("content") or ""),
                "caption": str(validated_beat.get("caption") or ""),
            }
        return {
            "visual_logic": visual_logic,
            "validated_beat": validated_beat,
            "render_spec": {
                "component": spec.composition,
                "props": spec.props,
            },
        }

    def _print_visual_debug(self, scene: dict, entries: list[dict]) -> None:
        scene_order = int(scene.get("scene_order") or scene.get("scene_index") or 0)
        narration = str(scene.get("narration_text") or scene.get("narration") or "")
        visual_logic = [entry["visual_logic"] for entry in entries]
        validated_beats = [entry["validated_beat"] for entry in entries]
        render_specs = [entry["render_spec"] for entry in entries]
        print(f"\n--- SCENE {scene_order} DEBUG ---\n")
        print("NARRATION:")
        print(json.dumps(narration, ensure_ascii=False, indent=2))
        print("\nVISUAL_LOGIC:")
        print(json.dumps(visual_logic[0] if len(visual_logic) == 1 else visual_logic, ensure_ascii=False, indent=2, default=str))
        print("\nVALIDATED_BEAT:")
        print(json.dumps(validated_beats[0] if len(validated_beats) == 1 else validated_beats, ensure_ascii=False, indent=2, default=str))
        print("\nRENDER_SPEC:")
        print(json.dumps(render_specs[0] if len(render_specs) == 1 else render_specs, ensure_ascii=False, indent=2, default=str))
        print("\n---\n")

    def _load_scene_beats(self, scene: dict, scene_duration: float) -> list[dict]:
        raw = scene.get("visual_plan_json")
        beats: list[dict] = []
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    beats = [beat for beat in parsed if isinstance(beat, dict)]
            except json.JSONDecodeError:
                beats = []
        if not beats:
            beats = [
                {
                    "beat_index": 0,
                    "beat_type": self._fallback_beat_type(scene.get("visual_type")),
                    "content": scene.get("visual_instruction") or scene.get("narration_text") or "Money reality",
                    "caption": "",
                    "color": "orange",
                    "estimated_start_sec": 0,
                    "estimated_duration_sec": min(max(scene_duration, 2.5), 4.0),
                }
            ]
        return beats

    def _normalize_beat_durations(self, beats: list[dict], scene_duration: float) -> list[dict]:
        if not beats or scene_duration <= 0:
            return beats
        durations = [max(float(beat.get("estimated_duration_sec") or 3.0), 0.1) for beat in beats]
        total = sum(durations)
        if total <= 0:
            return beats
        scale = scene_duration / total
        normalized: list[dict] = []
        for beat, duration in zip(beats, durations):
            next_beat = dict(beat)
            next_beat["estimated_duration_sec"] = round(duration * scale, 2)
            normalized.append(next_beat)
        actual_total = round(sum(float(beat.get("estimated_duration_sec") or 0) for beat in normalized), 2)
        if normalized:
            normalized[-1]["estimated_duration_sec"] = round(
                float(normalized[-1].get("estimated_duration_sec") or 0) + (scene_duration - actual_total),
                2,
            )
        return normalized

    def _fallback_beat_type(self, visual_type: str | None) -> str:
        if visual_type == "graph":
            return "chart"
        if visual_type == "broll":
            return "broll_caption"
        if visual_type in {"flow_diagram", "stat_explosion", "text_burst", "chart", "split_comparison", "broll_caption", "reaction_card"}:
            return visual_type
        return "text_burst"

    def _concat_beat_clips(self, beat_paths: list[Path], output_path: Path, target_duration: float) -> None:
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            shutil.copy2(beat_paths[0], output_path)
            return
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            manifest = temp_root / "beats.txt"
            concat_path = temp_root / "beats_concat.mp4"
            manifest.write_text(
                "\n".join(f"file '{path.resolve()}'" for path in beat_paths),
                encoding="utf-8",
            )
            subprocess.run(
                [
                    ffmpeg_bin,
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(manifest),
                    "-c",
                    "copy",
                    str(concat_path),
                ],
                check=True,
                capture_output=True,
            )
            duration = self._probe_duration(concat_path)
            if duration < target_duration - 0.1:
                pad = round(target_duration - duration, 2)
                subprocess.run(
                    [
                        ffmpeg_bin,
                        "-y",
                        "-i",
                        str(concat_path),
                        "-vf",
                        f"tpad=stop_mode=clone:stop_duration={pad}",
                        "-t",
                        str(round(target_duration, 2)),
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        "18",
                        "-pix_fmt",
                        "yuv420p",
                        str(output_path),
                    ],
                    check=True,
                    capture_output=True,
                )
            elif duration > target_duration + 0.1:
                subprocess.run(
                    [
                        ffmpeg_bin,
                        "-y",
                        "-i",
                        str(concat_path),
                        "-t",
                        str(round(target_duration, 2)),
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        "18",
                        "-pix_fmt",
                        "yuv420p",
                        str(output_path),
                    ],
                    check=True,
                    capture_output=True,
                )
            else:
                shutil.copy2(concat_path, output_path)

    def _ten_minute_finance_enabled(self) -> bool:
        return str(current_app.config.get("CHANNEL_STYLE", "")).lower() == "ten_minute_finance"

    # -----------------------------------------------------------------------
    # Groq API helper (shared by motion_text, graph, broll micro-calls)
    # -----------------------------------------------------------------------
    def _call_groq_api(self, system_prompt: str, user_prompt: str, purpose: str) -> dict:
        """Call Groq API with retries. Returns parsed JSON dict."""
        api_key = current_app.config.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not configured.")

        model = current_app.config.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 800,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "YTCreate/1.0",
        }

        max_retries = 2
        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=body, headers=headers, timeout=20,
                )
                response.raise_for_status()
                text = response.json()["choices"][0]["message"]["content"]
                return self._extract_json_from_text(text)
            except (requests.RequestException, ValueError, KeyError, json.JSONDecodeError) as exc:
                last_exc = exc
                self.logger.log(
                    purpose, "failed",
                    f"Groq micro-call attempt {attempt}/{max_retries} failed for {purpose}: {exc}",
                )
        raise RuntimeError(f"Groq micro-call failed after {max_retries} retries for {purpose}: {last_exc}")

    def _extract_json_from_text(self, raw_text: str) -> dict:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json", "", 1).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Groq response did not contain a JSON object.")
        return json.loads(cleaned[start : end + 1])

    # -----------------------------------------------------------------------
    # B-roll: Pexels + query simplification
    # -----------------------------------------------------------------------
    def _simplify_broll_query(self, visual_instruction: str) -> str:
        """Use Groq to simplify a visual instruction into a 2-4 word Pexels query."""
        try:
            result = self._call_groq_api(
                system_prompt="You return only a short search query, nothing else.",
                user_prompt=(
                    "Convert this visual instruction into a simple 2-4 word Pexels stock "
                    "footage search query that will return good results.\n\n"
                    "Rules for the query:\n"
                    "- Use generic English words, not location-specific\n"
                    "- Pexels has: people, cities, offices, money, technology, nature, "
                    "food, transportation, business, finance\n"
                    "- Pexels does NOT have: specific Indian text, rupee signs, "
                    "niche financial scenarios\n"
                    "- Prefer the emotional or physical scene over the conceptual meaning\n"
                    "- Return valid JSON with a single field 'query' containing only the search query\n\n"
                    "Examples:\n"
                    "'Indian city streets with rent signs' → 'apartment building city'\n"
                    "'person checking stock market on phone' → 'person phone trading'\n"
                    "'luxury shopping mall lifestyle inflation' → 'shopping mall luxury'\n"
                    "'₹1.2 lakh credit card debt stress' → 'credit card stress person'\n"
                    "'Indian stock market footage' → 'stock market trading floor'\n"
                    "'Wall Street financial analysts working' → 'business analysts office'\n\n"
                    f"Instruction: {visual_instruction}"
                ),
                purpose="broll_query_simplification",
            )
            return str(result.get("query", "")).strip() or "business finance office"
        except RuntimeError:
            # If Groq fails, do basic cleanup
            words = re.findall(r"[a-zA-Z]+", visual_instruction.lower())
            stop = {"the", "a", "an", "of", "in", "on", "for", "with", "and", "or", "is", "are", "to", "from"}
            filtered = [w for w in words if w not in stop][:4]
            return " ".join(filtered) or "business finance"

    def _pexels_broll(
        self,
        project_id: int,
        image_root: Path,
        scene_order: int,
        query: str,
        target_duration: float,
    ) -> tuple[Path, str]:
        simplified_query = self._simplify_broll_query(query)
        self.logger.log(
            "visual_generation", "running",
            f"Pexels search for scene {scene_order}: original='{query[:60]}' → simplified='{simplified_query}'",
            project_id,
        )

        cache_root = Path(current_app.config["STORAGE_ROOT"]) / "cache" / "pexels"
        cache_root.mkdir(parents=True, exist_ok=True)
        cache_key = hashlib.sha1(simplified_query.lower().encode("utf-8")).hexdigest()
        cache_path = cache_root / f"{cache_key}.json"
        result = self._load_pexels_cache(cache_path)
        if result is None:
            result = self._fetch_pexels_result(simplified_query, target_duration)
            cache_path.write_text(json.dumps(result), encoding="utf-8")

        download_url = result["download_url"]
        output_path = self._broll_source_path(project_id, "pexels", scene_order)
        if not output_path.exists():
            response = requests.get(
                download_url,
                timeout=current_app.config["PEXELS_API_TIMEOUT"],
                stream=True,
            )
            response.raise_for_status()
            with output_path.open("wb") as output_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        output_file.write(chunk)
        return output_path, "pexels_video"

    def _load_pexels_cache(self, cache_path: Path) -> dict[str, str] | None:
        if not cache_path.exists():
            return None
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if payload.get("download_url"):
            return payload
        return None

    def _fetch_pexels_result(self, query: str, target_duration: float) -> dict[str, str]:
        response = requests.get(
            "https://api.pexels.com/videos/search",
            params={
                "query": query,
                "per_page": current_app.config.get("PEXELS_SEARCH_LIMIT", 10),
                "orientation": "landscape",
            },
            headers={"Authorization": current_app.config["PEXELS_API_KEY"]},
            timeout=current_app.config["PEXELS_API_TIMEOUT"],
        )
        response.raise_for_status()
        payload = response.json()
        videos = payload.get("videos", [])
        if not videos:
            raise RuntimeError(f"Pexels returned no videos for query: '{query}'")

        # Prefer videos between 10 and 30 seconds
        matching_video = None
        for video in videos:
            vid_duration = float(video.get("duration") or 0)
            if 10 <= vid_duration <= 30:
                matching_video = video
                break
        if matching_video is None:
            # Fallback: any video with duration >= target
            for video in videos:
                if float(video.get("duration") or 0) >= target_duration:
                    matching_video = video
                    break
        if matching_video is None:
            matching_video = videos[0]

        video_files = matching_video.get("video_files", [])
        if not video_files:
            raise RuntimeError("Pexels did not include downloadable files.")

        best_file = next(
            (
                file_info
                for file_info in video_files
                if file_info.get("quality") == "hd" and file_info.get("link")
            ),
            None,
        )
        if best_file is None:
            best_file = next(
                (
                    file_info
                    for file_info in video_files
                    if file_info.get("quality") == "sd" and file_info.get("link")
                ),
                None,
            )
        if best_file is None:
            best_file = next(
                (file_info for file_info in video_files if file_info.get("link")),
                None,
            )
        if best_file is None:
            raise RuntimeError("Pexels did not include a usable download link.")

        return {
            "query": query,
            "video_id": str(matching_video.get("id", "")),
            "duration": str(matching_video.get("duration", "")),
            "download_url": best_file["link"],
        }

    # -----------------------------------------------------------------------
    # B-roll: Pixabay fallback
    # -----------------------------------------------------------------------
    def _pixabay_broll(
        self,
        project_id: int,
        image_root: Path,
        scene_order: int,
        query: str,
        target_duration: float,
    ) -> tuple[Path, str]:
        simplified_query = self._simplify_broll_query(query)
        api_key = current_app.config.get("PIXABAY_API_KEY")
        if not api_key:
            raise RuntimeError("PIXABAY_API_KEY is not configured for fallback.")

        self.logger.log(
            "visual_generation", "running",
            f"Pixabay fallback search for scene {scene_order}: '{simplified_query}'",
            project_id,
        )

        response = requests.get(
            "https://pixabay.com/api/videos/",
            params={
                "key": api_key,
                "q": simplified_query,
                "per_page": 10,
            },
            timeout=current_app.config.get("PEXELS_API_TIMEOUT", 15),
        )
        response.raise_for_status()
        payload = response.json()
        hits = payload.get("hits", [])
        if not hits:
            raise RuntimeError(f"Pixabay returned no videos for query: '{simplified_query}'")

        # Pick first usable hit
        video_data = hits[0]
        video_urls = video_data.get("videos", {})
        # Prefer 'small' quality for fast download
        download_info = video_urls.get("small") or video_urls.get("tiny") or video_urls.get("medium") or {}
        download_url = download_info.get("url")
        if not download_url:
            raise RuntimeError("Pixabay did not include a usable download link.")

        output_path = self._broll_source_path(project_id, "pixabay", scene_order)
        if not output_path.exists():
            dl_response = requests.get(download_url, timeout=30, stream=True)
            dl_response.raise_for_status()
            with output_path.open("wb") as f:
                for chunk in dl_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        self.logger.log(
            "visual_generation", "completed",
            f"Pixabay fallback used for scene {scene_order}.",
            project_id,
        )
        return output_path, "pixabay_video"

    def _broll_source_path(self, project_id: int, provider: str, scene_order: int) -> Path:
        source_root = Path(current_app.config["STORAGE_ROOT"]) / "downloads" / "broll" / str(project_id)
        source_root.mkdir(parents=True, exist_ok=True)
        return source_root / f"{provider}-scene-{scene_order:02d}.mp4"

    # -----------------------------------------------------------------------
    # Motion text: Groq parsing + rendering
    # -----------------------------------------------------------------------
    def _parse_motion_text(self, visual_instruction: str) -> dict:
        """Call Groq API to parse visual instruction into headline/subtext/sentiment."""
        try:
            return self._call_groq_api(
                system_prompt="You are a parsing assistant. Return valid JSON only.",
                user_prompt=(
                    "Parse this visual instruction for a YouTube finance video motion graphics "
                    "frame. Return valid JSON only, no markdown, no explanation.\n"
                    "Fields required:\n"
                    "- headline: main text to display large, maximum 4 words, can include "
                    "numbers and ₹ symbol\n"
                    "- subtext: supporting label displayed smaller below headline, "
                    "maximum 6 words, can be empty string\n"
                    "- sentiment: positive | negative | neutral\n\n"
                    f"Instruction: {visual_instruction}"
                ),
                purpose="motion_text_parsing",
            )
        except RuntimeError:
            # Fallback: extract first few words as headline
            words = visual_instruction.split()
            headline = " ".join(words[:4]).upper() if words else "KEY STAT"
            subtext = " ".join(words[4:10]) if len(words) > 4 else ""
            return {"headline": headline, "subtext": subtext, "sentiment": "neutral"}

    def _render_motion_text_video(
        self,
        image_root: Path,
        scene_order: int,
        text: str,
        target_duration: float,
    ) -> tuple[Path, str]:
        ffmpeg_bin = self._require_ffmpeg()
        output_path = image_root / f"scene-{scene_order:02d}.mp4"
        fps = 30
        frame_count = max(int(target_duration * fps), fps * 2)

        # Parse with Groq
        parsed = self._parse_motion_text(text)
        headline = str(parsed.get("headline", "")).strip() or "KEY STAT"
        subtext = str(parsed.get("subtext", "")).strip()
        sentiment = str(parsed.get("sentiment", "neutral")).strip().lower()
        if sentiment not in SENTIMENT_COLORS:
            sentiment = "neutral"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            for frame_index in range(frame_count):
                frame_path = temp_root / f"frame-{frame_index:04d}.png"
                self._draw_motion_text_frame_v2(
                    frame_path, headline, subtext, sentiment,
                    frame_index, frame_count,
                )
            self._encode_frame_sequence(ffmpeg_bin, temp_root, fps, output_path)

        return output_path, "motion_text_video"

    def _draw_motion_text_frame_v2(
        self, path: Path, headline: str, subtext: str,
        sentiment: str, frame_index: int, frame_count: int,
    ) -> None:
        width, height = 1920, 1080
        bg_color = _hex_to_rgb("#0A0A14")
        image = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(image)

        # Left accent bar — 8px wide, full height
        accent_color = SENTIMENT_COLORS.get(sentiment, SENTIMENT_COLORS["neutral"])
        draw.rectangle((0, 0, 8, height), fill=accent_color)

        # Bottom gradient overlay (bottom 25%)
        gradient_start_y = int(height * 0.75)
        for y in range(gradient_start_y, height):
            progress = (y - gradient_start_y) / (height - gradient_start_y)
            alpha_val = int(progress * 0.4 * 255)
            overlay_color = (0, 0, 0, alpha_val)
            # Blend directly
            darkened = tuple(max(0, bg_color[c] - int(progress * 0.4 * bg_color[c])) for c in range(3))
            draw.line([(0, y), (width, y)], fill=darkened)

        # Headline font + subtext font
        headline_font = _get_font(bold=True, size=96)
        subtext_font = _get_font(bold=False, size=42)

        # Animation: headline fades in frames 0-7, subtext frames 7-14, then hold
        headline_alpha = min(1.0, (frame_index + 1) / 8.0)
        subtext_alpha = max(0.0, min(1.0, (frame_index - 7) / 8.0)) if frame_index >= 7 else 0.0

        # Measure text sizes for centering
        headline_bbox = headline_font.getbbox(headline)
        headline_w = headline_bbox[2] - headline_bbox[0]
        headline_h = headline_bbox[3] - headline_bbox[1]
        headline_x = (width - headline_w) // 2
        headline_y = (height // 2) - headline_h - 20  # slightly above centre

        # Draw headline
        headline_color = _fade_rgb((255, 255, 255), headline_alpha)
        draw.text((headline_x, headline_y), headline, font=headline_font, fill=headline_color)

        # Draw subtext
        if subtext:
            subtext_bbox = subtext_font.getbbox(subtext)
            subtext_w = subtext_bbox[2] - subtext_bbox[0]
            subtext_x = (width - subtext_w) // 2
            subtext_y = headline_y + headline_h + 32
            # 65% opacity white
            subtext_color = _fade_rgb((166, 166, 166), subtext_alpha)  # ~65% of 255
            draw.text((subtext_x, subtext_y), subtext, font=subtext_font, fill=subtext_color)

        image.save(path)

    # -----------------------------------------------------------------------
    # Graph: Groq parsing + 4 renderers
    # -----------------------------------------------------------------------
    def _parse_graph_data(self, instruction: str) -> dict:
        """Call Groq to extract structured chart data from visual instruction."""
        try:
            return self._call_groq_api(
                system_prompt="You are a data parsing assistant. Return valid JSON only.",
                user_prompt=(
                    "Parse this graph visual instruction for a YouTube finance video. "
                    "Return valid JSON only, no markdown, no explanation.\n"
                    "Fields required:\n"
                    "- chart_type: bar | line | pie | number_reveal\n"
                    "- title: string, max 8 words, the chart heading\n"
                    "- x_label: string, label for x axis (empty string for pie and number_reveal)\n"
                    "- y_label: string, label for y axis (empty string for pie and number_reveal)\n"
                    "- color: red | green | orange | blue | teal\n"
                    "- background: dark\n"
                    "- data: array format depends on chart_type:\n"
                    '    for bar: [{"label": "string", "value": number}, ...]\n'
                    '    for line: [{"label": "string", "value": number}, ...] '
                    "where label is the x-axis point (year, month, etc)\n"
                    '    for pie: [{"label": "string", "percentage": number}, ...] '
                    "percentages must sum to 100\n"
                    '    for number_reveal: {"number": "string", "unit": "string", "label": "string"}\n'
                    '                       example: {"number": "40%", "unit": "", '
                    '"label": "Credit Card Interest Rate"}\n\n'
                    "If the instruction does not contain explicit data, infer realistic "
                    "approximate data that matches the narrative context and is consistent "
                    "with publicly known Indian financial statistics.\n\n"
                    f"Instruction: {instruction}"
                ),
                purpose="graph_data_parsing",
            )
        except RuntimeError:
            # Fallback: basic bar chart with dummy data
            return {
                "chart_type": "bar",
                "title": instruction[:60] if instruction else "Financial Overview",
                "x_label": "",
                "y_label": "",
                "color": "blue",
                "data": [
                    {"label": "2020", "value": 45},
                    {"label": "2021", "value": 52},
                    {"label": "2022", "value": 61},
                    {"label": "2023", "value": 58},
                    {"label": "2024", "value": 73},
                ],
            }

    def _render_graph_video(
        self,
        image_root: Path,
        scene_order: int,
        instruction: str,
        target_duration: float,
    ) -> tuple[Path, str]:
        ffmpeg_bin = self._require_ffmpeg()
        output_path = image_root / f"scene-{scene_order:02d}.mp4"
        fps = 30
        frame_count = max(int(target_duration * fps), fps * 2)

        graph_spec = self._parse_graph_data(instruction)
        chart_type = str(graph_spec.get("chart_type", "bar")).lower()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            for frame_index in range(frame_count):
                progress = (frame_index + 1) / frame_count
                frame_path = temp_root / f"frame-{frame_index:04d}.png"

                if chart_type == "pie":
                    self._draw_pie_frame(frame_path, graph_spec, progress)
                elif chart_type == "number_reveal":
                    self._draw_number_reveal_frame(frame_path, graph_spec, progress)
                elif chart_type == "line":
                    self._draw_line_frame(frame_path, graph_spec, progress)
                else:
                    self._draw_bar_frame(frame_path, graph_spec, progress)

            self._encode_frame_sequence(ffmpeg_bin, temp_root, fps, output_path)

        return output_path, "graph_video"

    def _resolve_chart_color(self, color_name: str) -> str:
        return CHART_COLORS.get(color_name.lower(), CHART_COLORS["blue"])

    def _draw_bar_frame(self, path: Path, spec: dict, progress: float) -> None:
        width, height = 1920, 1080
        bg = _hex_to_rgb("#0D1117")
        image = Image.new("RGB", (width, height), color=bg)
        draw = ImageDraw.Draw(image)

        title_font = _get_font(bold=True, size=28)
        label_font = _get_font(bold=False, size=20)
        value_font = _get_font(bold=True, size=20)

        title = str(spec.get("title", "Chart"))
        color_hex = self._resolve_chart_color(str(spec.get("color", "blue")))
        bar_color = _hex_to_rgb(color_hex)
        data = spec.get("data", [])
        if not isinstance(data, list) or len(data) < 2:
            data = [
                {"label": "Start", "value": 40},
                {"label": "Middle", "value": 60},
                {"label": "End", "value": 80},
            ]

        # Title
        t_bbox = title_font.getbbox(title)
        t_w = t_bbox[2] - t_bbox[0]
        draw.text(((width - t_w) // 2, 40), title, font=title_font, fill="white")

        # Chart area
        chart_left, chart_top, chart_right, chart_bottom = 160, 120, 1760, 920

        # Axis lines
        draw.line((chart_left, chart_bottom, chart_right, chart_bottom), fill=(255, 255, 255), width=1)
        draw.line((chart_left, chart_top, chart_left, chart_bottom), fill=(255, 255, 255), width=1)

        # Horizontal grid lines
        for i in range(1, 5):
            gy = chart_bottom - int((chart_bottom - chart_top) * (i / 5))
            draw.line((chart_left, gy, chart_right, gy), fill=(38, 42, 48), width=1)  # ~10% white on #0D1117

        values = [float(d.get("value", 0)) for d in data]
        labels = [str(d.get("label", "")) for d in data]
        max_value = max(values) if values and max(values) > 0 else 1

        # Y-axis labels
        for i in range(6):
            val = int(max_value * i / 5)
            gy = chart_bottom - int((chart_bottom - chart_top) * (i / 5))
            draw.text((chart_left - 60, gy - 10), str(val), font=label_font, fill=(148, 163, 184))

        step_x = (chart_right - chart_left) / max(len(values), 1)
        bar_width = step_x * 0.55
        anim_progress = min(progress / 0.6, 1.0)  # bars grow over first 60%

        for idx, value in enumerate(values):
            animated_value = value * anim_progress
            x1 = chart_left + step_x * idx + (step_x - bar_width) / 2
            x2 = x1 + bar_width
            bar_h = (chart_bottom - chart_top) * (animated_value / max_value)
            y1 = chart_bottom - bar_h

            draw.rounded_rectangle((x1, y1, x2, chart_bottom), radius=6, fill=bar_color)
            # X label
            draw.text((x1, chart_bottom + 12), labels[idx], font=label_font, fill=(148, 163, 184))
            # Value label after animation completes
            if anim_progress >= 1.0:
                val_str = self._format_number(value)
                draw.text((x1, y1 - 28), val_str, font=value_font, fill="white")

        # Axis labels
        x_label = str(spec.get("x_label", ""))
        y_label = str(spec.get("y_label", ""))
        if x_label:
            xl_bbox = label_font.getbbox(x_label)
            draw.text(((width - (xl_bbox[2] - xl_bbox[0])) // 2, chart_bottom + 50), x_label, font=label_font, fill=(148, 163, 184))

        image.save(path)

    def _draw_line_frame(self, path: Path, spec: dict, progress: float) -> None:
        width, height = 1920, 1080
        bg = _hex_to_rgb("#0D1117")
        image = Image.new("RGB", (width, height), color=bg)
        draw = ImageDraw.Draw(image)

        title_font = _get_font(bold=True, size=28)
        label_font = _get_font(bold=False, size=20)
        value_font = _get_font(bold=True, size=18)

        title = str(spec.get("title", "Trend"))
        color_hex = self._resolve_chart_color(str(spec.get("color", "blue")))
        line_color = _hex_to_rgb(color_hex)
        fill_color = _fade_rgb(line_color, 0.15)
        data = spec.get("data", [])
        if not isinstance(data, list) or len(data) < 2:
            data = [
                {"label": "Start", "value": 40},
                {"label": "Middle", "value": 60},
                {"label": "End", "value": 80},
            ]

        # Title
        t_bbox = title_font.getbbox(title)
        t_w = t_bbox[2] - t_bbox[0]
        draw.text(((width - t_w) // 2, 40), title, font=title_font, fill="white")

        chart_left, chart_top, chart_right, chart_bottom = 160, 120, 1760, 920

        # Axes
        draw.line((chart_left, chart_bottom, chart_right, chart_bottom), fill=(255, 255, 255), width=1)
        draw.line((chart_left, chart_top, chart_left, chart_bottom), fill=(255, 255, 255), width=1)

        # Grid
        for i in range(1, 5):
            gy = chart_bottom - int((chart_bottom - chart_top) * (i / 5))
            draw.line((chart_left, gy, chart_right, gy), fill=(38, 42, 48), width=1)  # ~10% white on #0D1117

        values = [float(d.get("value", 0)) for d in data]
        labels = [str(d.get("label", "")) for d in data]
        max_value = max(values) if values and max(values) > 0 else 1

        # Build all points
        step_x = (chart_right - chart_left) / max(len(values) - 1, 1)
        all_points = []
        for idx, value in enumerate(values):
            x = chart_left + step_x * idx
            y = chart_bottom - ((chart_bottom - chart_top) * (value / max_value))
            all_points.append((x, y))

        # Line draws over first 70%
        line_progress = min(progress / 0.7, 1.0)
        visible_count = max(2, int(len(all_points) * line_progress))
        visible_points = all_points[:visible_count]

        # Draw fill polygon below line
        if len(visible_points) >= 2:
            fill_polygon = list(visible_points) + [(visible_points[-1][0], chart_bottom), (visible_points[0][0], chart_bottom)]
            draw.polygon(fill_polygon, fill=fill_color)
            draw.line(visible_points, fill=line_color, width=3)

        # Data points + labels
        for idx, point in enumerate(visible_points):
            draw.ellipse((point[0] - 5, point[1] - 5, point[0] + 5, point[1] + 5), fill=line_color)
            # X labels
            if idx < len(labels):
                draw.text((point[0] - 15, chart_bottom + 12), labels[idx], font=label_font, fill=(148, 163, 184))
            # Value annotation on final frame
            if line_progress >= 1.0 and idx < len(values):
                val_str = self._format_number(values[idx])
                draw.text((point[0] - 15, point[1] - 28), val_str, font=value_font, fill="white")

        image.save(path)

    def _draw_pie_frame(self, path: Path, spec: dict, progress: float) -> None:
        width, height = 1920, 1080
        bg = _hex_to_rgb("#0D1117")
        image = Image.new("RGB", (width, height), color=bg)
        draw = ImageDraw.Draw(image)

        title_font = _get_font(bold=True, size=28)
        label_font = _get_font(bold=False, size=22)
        pct_font = _get_font(bold=True, size=24)

        title = str(spec.get("title", "Distribution"))
        data = spec.get("data", [])
        if not isinstance(data, list) or not data:
            data = [{"label": "N/A", "percentage": 100}]

        # Title
        t_bbox = title_font.getbbox(title)
        t_w = t_bbox[2] - t_bbox[0]
        draw.text(((width - t_w) // 2, 40), title, font=title_font, fill="white")

        # Pie area
        pie_cx, pie_cy, pie_r = 800, 540, 320
        pie_box = (pie_cx - pie_r, pie_cy - pie_r, pie_cx + pie_r, pie_cy + pie_r)

        anim_progress = min(progress / 0.6, 1.0)  # segments over first 60%
        total_angle = 360 * anim_progress
        start_angle = -90  # start from top

        percentages = [float(d.get("percentage", 0)) for d in data]
        labels_list = [str(d.get("label", "")) for d in data]

        for idx, pct in enumerate(percentages):
            segment_angle = (pct / 100) * total_angle
            if segment_angle <= 0:
                continue
            end_angle = start_angle + segment_angle
            color = PIE_PALETTE[idx % len(PIE_PALETTE)]
            draw.pieslice(pie_box, start_angle, end_angle, fill=color)

            # Percentage label inside segment (after animation)
            if anim_progress >= 1.0 and pct >= 5:
                mid_angle = math.radians(start_angle + segment_angle / 2)
                lx = pie_cx + int(pie_r * 0.6 * math.cos(mid_angle))
                ly = pie_cy + int(pie_r * 0.6 * math.sin(mid_angle))
                draw.text((lx - 15, ly - 10), f"{pct:.0f}%", font=pct_font, fill="white")

            start_angle = end_angle

        # Legend on the right
        legend_x = pie_cx + pie_r + 80
        legend_y = 200
        for idx, label in enumerate(labels_list):
            color = PIE_PALETTE[idx % len(PIE_PALETTE)]
            draw.rectangle((legend_x, legend_y, legend_x + 20, legend_y + 20), fill=color)
            draw.text((legend_x + 30, legend_y - 2), f"{label} ({percentages[idx]:.0f}%)", font=label_font, fill=(200, 200, 200))
            legend_y += 40

        image.save(path)

    def _draw_number_reveal_frame(self, path: Path, spec: dict, progress: float) -> None:
        width, height = 1920, 1080
        bg = _hex_to_rgb("#0D1117")
        image = Image.new("RGB", (width, height), color=bg)
        draw = ImageDraw.Draw(image)

        # Left accent bar
        accent_color = self._resolve_chart_color(str(spec.get("color", "teal")))
        draw.rectangle((0, 0, 8, height), fill=accent_color)

        number_font = _get_font(bold=True, size=120)
        unit_font = _get_font(bold=False, size=60)
        label_font = _get_font(bold=False, size=36)

        data = spec.get("data", {})
        if isinstance(data, list):
            data = data[0] if data else {}
        number_str = str(data.get("number", "0"))
        unit = str(data.get("unit", ""))
        label = str(data.get("label", ""))

        # Count up animation over 70%
        count_progress = min(progress / 0.7, 1.0)

        # Extract numeric value for counting
        numeric_part = re.sub(r"[^\d.]", "", number_str)
        suffix = number_str.replace(numeric_part, "") if numeric_part else ""
        try:
            target_value = float(numeric_part) if numeric_part else 0
        except ValueError:
            target_value = 0

        current_value = target_value * count_progress
        if "." in numeric_part:
            display_number = f"{current_value:.1f}{suffix}"
        else:
            display_number = f"{int(current_value)}{suffix}"

        # Centre the number
        full_display = f"{display_number} {unit}".strip() if unit else display_number
        n_bbox = number_font.getbbox(full_display)
        n_w = n_bbox[2] - n_bbox[0]
        n_x = (width - n_w) // 2
        n_y = (height // 2) - 80
        draw.text((n_x, n_y), full_display, font=number_font, fill="white")

        # Label below
        if label:
            l_bbox = label_font.getbbox(label)
            l_w = l_bbox[2] - l_bbox[0]
            l_x = (width - l_w) // 2
            l_y = n_y + 140
            draw.text((l_x, l_y), label, font=label_font, fill=(179, 179, 179))  # ~70% opacity

        image.save(path)

    # -----------------------------------------------------------------------
    # FFmpeg / utility helpers
    # -----------------------------------------------------------------------
    def _encode_frame_sequence(self, ffmpeg_bin: str, frame_root: Path, fps: int, output_path: Path) -> None:
        subprocess.run(
            [
                ffmpeg_bin, "-y",
                "-framerate", str(fps),
                "-i", str(frame_root / "frame-%04d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )

    def _require_ffmpeg(self) -> str:
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            # Check common Homebrew install paths on macOS
            for candidate in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    ffmpeg_bin = candidate
                    break
        if not ffmpeg_bin:
            raise RuntimeError("ffmpeg is required to render animated visual videos.")
        return ffmpeg_bin

    def _summarize_tts_error(self, exc: Exception) -> str:
        message = str(exc).strip()
        lowered = message.lower()
        if "403" in lowered or "invalid response status" in lowered:
            return "Edge TTS was rejected by the provider (403). The app will use demo fallback audio instead."
        if "timed out" in lowered:
            return "Edge TTS timed out. The app will use demo fallback audio instead."
        if "did not produce an audio file" in lowered:
            return "Edge TTS did not return usable audio. The app will use demo fallback audio instead."
        if len(message) > 220:
            message = message[:217].rstrip() + "..."
        return message or "Live Edge TTS failed. The app will use demo fallback audio instead."

    def _format_number(self, value: float) -> str:
        if value >= 10_000_000:
            formatted = f"{value / 10_000_000:.1f}".rstrip("0").rstrip(".")
            return f"{formatted}Cr"
        if value >= 100_000:
            formatted = f"{value / 100_000:.1f}".rstrip("0").rstrip(".")
            return f"{formatted}L"
        if value >= 1000:
            return self._format_indian_grouped_number(int(round(value)))
        if value == int(value):
            return f"{int(value)}"
        return f"{value:.1f}"

    def _format_indian_grouped_number(self, value: int) -> str:
        sign = "-" if value < 0 else ""
        digits = str(abs(value))
        if len(digits) <= 3:
            return f"{sign}{digits}"
        grouped = digits[-3:]
        digits = digits[:-3]
        while digits:
            grouped = digits[-2:] + "," + grouped
            digits = digits[:-2]
        return f"{sign}{grouped}"

    def _create_silent_wav(self, path: Path, duration_sec: float) -> None:
        frame_rate = 16000
        frame_count = int(math.ceil(duration_sec * frame_rate))
        with wave.open(str(path), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(frame_rate)
            silence = b"\x00\x00" * frame_count
            wav_file.writeframes(silence)

    def _probe_duration(self, path: Path) -> float:
        ffprobe_bin = shutil.which("ffprobe")
        if not ffprobe_bin:
            for candidate in ("/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe"):
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    ffprobe_bin = candidate
                    break
        if ffprobe_bin:
            result = subprocess.run(
                [
                    ffprobe_bin, "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "json",
                    str(path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            duration = float(payload["format"]["duration"])
            return round(duration, 2)

        # Fallback to mutagen
        try:
            from mutagen import File as MutagenFile
            audio = MutagenFile(str(path))
            if audio and audio.info:
                return round(audio.info.length, 2)
        except Exception:
            pass
        # Last resort: estimate from file size (assumes ~16kbps mp3)
        return round(max(path.stat().st_size / 2000, 2.5), 2)

    def _render_image(self, path: Path, text: str, visual_type: str | None) -> None:
        title = (visual_type or "scene").replace("_", " ").title()
        image = Image.new("RGB", (1280, 720), color="#0f172a")
        draw = ImageDraw.Draw(image)
        font_large = ImageFont.load_default(size=44)
        font_body = ImageFont.load_default(size=32)
        draw.rectangle((0, 0, 1280, 720), fill="#0f172a")
        draw.text((70, 70), title, fill="#94a3b8", font=font_large)
        wrapped = self._wrap_text(text, line_length=32)
        draw.multiline_text((70, 180), wrapped, fill="white", font=font_body, spacing=16)
        accent = {"graph": "#38bdf8", "broll": "#22c55e", "motion_text": "#f97316"}.get(
            visual_type or "", "#a855f7"
        )
        draw.rounded_rectangle((60, 60, 1220, 660), outline=accent, width=4, radius=24)
        image.save(path)

    def _wrap_text(self, text: str, line_length: int) -> str:
        words = text.split()
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            candidate = " ".join(current + [word])
            if len(candidate) > line_length and current:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            lines.append(" ".join(current))
        return "\n".join(lines)
