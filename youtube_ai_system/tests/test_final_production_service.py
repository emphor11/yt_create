import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from youtube_ai_system import create_app
from youtube_ai_system.db import close_db
from youtube_ai_system.models.repository import ProjectRepository
from youtube_ai_system.services.final_production_service import FinalProductionService
from youtube_ai_system.services.thumbnail_service import ThumbnailService
from youtube_ai_system.services.youtube_upload_service import YouTubeUploadService


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

    def test_youtube_upload_records_video_when_thumbnail_permission_fails(self) -> None:
        project_id = self.repo.create_project("Upload Test")
        video_path = Path(self.app.config["STORAGE_ROOT"]) / "video" / str(project_id) / "final_video.mp4"
        thumb_path = Path(self.app.config["STORAGE_ROOT"]) / "images" / str(project_id) / "thumb.jpg"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"video")
        thumb_path.write_bytes(b"thumbnail")
        self.repo.update_project(
            project_id,
            state="ready_to_publish",
            final_video_path=str(video_path),
            selected_thumbnail_path=str(thumb_path),
            selected_title="Upload Test",
            selected_description="Upload description",
        )

        service = YouTubeUploadService()
        with patch.object(service, "_authorized_client", return_value=_FakeYouTubeClient()):
            video_id = service.upload_private(project_id)

        project = self.repo.get_project(project_id)
        self.assertEqual(video_id, "video-123")
        self.assertEqual(project["youtube_video_id"], "video-123")
        self.assertIn("custom thumbnail", service.last_thumbnail_warning)

    def test_youtube_client_refreshes_expired_saved_token_without_oauth_prompt(self) -> None:
        token_path = Path(self.app.config["INSTANCE_PATH"]) / "youtube_token.json"
        client_secret_path = Path(self.app.config["INSTANCE_PATH"]) / "client_secret.json"
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text("{}", encoding="utf-8")
        client_secret_path.write_text("{}", encoding="utf-8")
        self.app.config.update(
            {
                "YOUTUBE_TOKEN_PATH": str(token_path),
                "YOUTUBE_CLIENT_SECRETS": str(client_secret_path),
            }
        )
        credentials = _FakeCredentials()

        with patch(
            "google.oauth2.credentials.Credentials.from_authorized_user_file",
            return_value=credentials,
        ), patch("google.auth.transport.requests.Request", return_value=object()) as request_cls, patch(
            "google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file"
        ) as flow_factory, patch("googleapiclient.discovery.build", return_value="youtube-client") as build:
            client = YouTubeUploadService()._authorized_client()

        self.assertEqual(client, "youtube-client")
        self.assertTrue(credentials.refresh_called)
        self.assertFalse(flow_factory.called)
        self.assertTrue(request_cls.called)
        self.assertIn("refreshed-token", token_path.read_text(encoding="utf-8"))
        build.assert_called_once()

class _FakeInsertRequest:
    def next_chunk(self):
        return None, {"id": "video-123"}


class _FakeThumbnailRequest:
    def execute(self):
        raise RuntimeError("thumbnail forbidden")


class _FakeVideos:
    def insert(self, **kwargs):
        return _FakeInsertRequest()


class _FakeThumbnails:
    def set(self, **kwargs):
        return _FakeThumbnailRequest()


class _FakeYouTubeClient:
    def videos(self):
        return _FakeVideos()

    def thumbnails(self):
        return _FakeThumbnails()


class _FakeCredentials:
    expired = True
    valid = False
    refresh_token = "refresh-token"

    def __init__(self) -> None:
        self.refresh_called = False

    def refresh(self, request):
        self.refresh_called = True
        self.expired = False
        self.valid = True

    def to_json(self):
        return '{"token": "refreshed-token", "refresh_token": "refresh-token"}'


if __name__ == "__main__":
    unittest.main()
