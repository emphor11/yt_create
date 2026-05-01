import tempfile
import unittest
from pathlib import Path
from subprocess import TimeoutExpired
from unittest.mock import patch

from youtube_ai_system import create_app
from youtube_ai_system.db import close_db
from youtube_ai_system.services.remotion_service import RemotionService
from youtube_ai_system.services.render_spec_service import RenderSpec


class RemotionServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        project_root = Path("/Users/dakshyadav/YTCreate/remotion_templates")
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": root / "instance" / "database.db",
                "INSTANCE_PATH": root / "instance",
                "STORAGE_ROOT": root / "storage",
                "REMOTION_PROJECT_PATH": project_root,
            }
        )
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self) -> None:
        close_db()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def test_video_renderer_props_stage_audio_into_public_assets(self) -> None:
        audio_path = Path(self.temp_dir.name) / "sample.wav"
        audio_path.write_bytes(b"fake-wav")
        spec = RenderSpec(
            composition="VideoRenderer",
            props={
                "scenes": [
                    {
                        "scene_id": "scene_1",
                        "pattern": "ConceptCard",
                        "data": {"title": "TEST"},
                        "beats": [
                            {
                                "component": "StatCard",
                                "text": "Test",
                                "start_time": 0.0,
                                "end_time": 1.0,
                                "emphasis": "hero",
                            }
                        ],
                        "duration": 1.0,
                        "audio_file": str(audio_path),
                    }
                ]
            },
            duration_sec=1.0,
            source="test",
        )

        props = RemotionService()._props_for_render(spec, Path("/Users/dakshyadav/YTCreate/remotion_templates"))
        staged = props["scenes"][0]["audio_file"]

        self.assertTrue(staged.startswith("render-assets/audio/"))
        self.assertTrue((Path("/Users/dakshyadav/YTCreate/remotion_templates/public") / staged).exists())
        self.assertIn("theme", props)

    def test_props_stage_generic_file_path_props(self) -> None:
        video_path = Path(self.temp_dir.name) / "source.mp4"
        video_path.write_bytes(b"fake-video")
        spec = RenderSpec(
            composition="BrollOverlay",
            props={"videoPath": str(video_path)},
            duration_sec=1.0,
            source="test",
        )

        props = RemotionService()._props_for_render(spec, Path("/Users/dakshyadav/YTCreate/remotion_templates"))

        self.assertTrue(props["videoPath"].startswith("render-assets/broll/"))
        self.assertTrue((Path("/Users/dakshyadav/YTCreate/remotion_templates/public") / props["videoPath"]).exists())

    def test_render_video_uses_timeout_and_quality_flags(self) -> None:
        spec = RenderSpec(
            composition="VideoRenderer",
            props={"scenes": []},
            duration_sec=1.0,
            source="test",
        )
        output_path = Path(self.temp_dir.name) / "out.mp4"
        self.app.config["REMOTION_RENDER_TIMEOUT"] = 123
        self.app.config["REMOTION_CONCURRENCY"] = 3

        with patch.object(RemotionService, "is_available", return_value=True), patch(
            "youtube_ai_system.services.remotion_service.subprocess.run"
        ) as run:
            RemotionService().render_video(spec, output_path)

        command = run.call_args.args[0]
        self.assertIn("--codec=h264", command)
        self.assertIn("--crf=18", command)
        self.assertIn("--pixel-format=yuv420p", command)
        self.assertIn("--concurrency=3", command)
        self.assertIn("--log=error", command)
        self.assertEqual(run.call_args.kwargs["timeout"], 123)

    def test_render_timeout_raises_clear_error(self) -> None:
        spec = RenderSpec(
            composition="VideoRenderer",
            props={"scenes": []},
            duration_sec=1.0,
            source="test",
        )
        self.app.config["REMOTION_RENDER_TIMEOUT"] = 7

        with patch.object(RemotionService, "is_available", return_value=True), patch(
            "youtube_ai_system.services.remotion_service.subprocess.run",
            side_effect=TimeoutExpired(cmd=["npx"], timeout=7),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed out after 7s"):
                RemotionService().render_video(spec, Path(self.temp_dir.name) / "out.mp4")

    def test_render_still_uses_still_command_without_video_flags(self) -> None:
        spec = RenderSpec(
            composition="Thumbnail",
            props={"title": "Test"},
            duration_sec=1.0,
            source="test",
        )
        output_path = Path(self.temp_dir.name) / "thumb.jpg"

        with patch.object(RemotionService, "is_available", return_value=True), patch(
            "youtube_ai_system.services.remotion_service.subprocess.run"
        ) as run:
            RemotionService().render_still(spec, output_path)

        command = run.call_args.args[0]
        self.assertEqual(command[1:3], ["remotion", "still"])
        self.assertIn(str(output_path), command)
        self.assertIn("--log=error", command)
        self.assertNotIn("--crf=18", command)


if __name__ == "__main__":
    unittest.main()
