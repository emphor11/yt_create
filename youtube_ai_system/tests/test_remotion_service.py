import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
