import json
import tempfile
import unittest
from pathlib import Path

from youtube_ai_system import create_app
from youtube_ai_system.db import close_db
from youtube_ai_system.models.repository import ProjectRepository
from youtube_ai_system.services.final_production_service import FinalProductionService
from youtube_ai_system.services.thumbnail_service import ThumbnailService


class FinalProductionServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": root / "instance" / "database.db",
                "INSTANCE_PATH": root / "instance",
                "STORAGE_ROOT": root / "storage",
                "REMOTION_ENABLED": False,
            }
        )
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.repo = ProjectRepository()

    def tearDown(self) -> None:
        close_db()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def test_creator_package_uses_existing_project_assets(self) -> None:
        project_id = self.repo.create_project("Salary Leak")
        self.repo.update_project(
            project_id,
            topic="Why your salary disappears",
            state="scene_review",
            final_video_path=str(Path(self.app.config["STORAGE_ROOT"]) / "video" / str(project_id) / "final_video.mp4"),
        )
        video_path = Path(self.repo.get_project(project_id)["final_video_path"])
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"video")
        script_id = self.repo.create_script_version(
            project_id,
            {},
            {},
            ["Where Does Your Salary Go?"],
            "A video about hidden salary leaks.",
            ["personal finance", "salary"],
            {"titles": ["Where Does Your Salary Go?"], "description": "A video about hidden salary leaks.", "tags": ["salary"]},
            "test",
        )
        self.repo.replace_scenes(
            project_id,
            script_id,
            [
                {
                    "scene_order": 0,
                    "kind": "hook",
                    "narration_text": "Why does your salary disappear by day twenty?",
                    "visual_instruction": "salary leak",
                    "visual_type": "motion_text",
                    "visual_plan_json": json.dumps({}),
                    "visual_scene_json": json.dumps({}),
                }
            ],
        )

        thumbnails = ThumbnailService().ensure_creator_thumbnails(
            project_id,
            ["Where Does Your Salary Go?"],
            self.repo.list_scenes(project_id),
        )
        self.repo.update_project(project_id, selected_thumbnail_path=thumbnails[0]["path"])
        package = FinalProductionService(self.repo).build_upload_package(project_id)

        self.assertTrue(Path(thumbnails[0]["path"]).exists())
        self.assertEqual(package["selected_title"], "Where Does Your Salary Go?")
        self.assertTrue(package["publish_checklist"]["checks"][0]["passed"])
        self.assertTrue(FinalProductionService(self.repo).package_path(project_id).exists())


if __name__ == "__main__":
    unittest.main()
