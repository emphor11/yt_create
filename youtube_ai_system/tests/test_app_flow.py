import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from youtube_ai_system import create_app
from youtube_ai_system.db import close_db, get_db


class AppFlowTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.app = create_app(
            {
                "TESTING": True,
                "LLM_PROVIDER": "demo",
                "VOICE_MODE": "demo",
                "REMOTION_ENABLED": True,
                "DATABASE_PATH": root / "instance" / "database.db",
                "INSTANCE_PATH": root / "instance",
                "STORAGE_ROOT": root / "storage",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        with self.app.app_context():
            close_db()
        self.temp_dir.cleanup()

    def test_project_creation_writes_run_log(self) -> None:
        response = self.client.post("/projects/new", data={"working_title": "Foundation Test"})
        self.assertEqual(response.status_code, 302)
        project_id = int(response.headers["Location"].rstrip("/").split("/")[-1])

        with self.app.app_context():
            db = get_db()
            project = db.execute("SELECT working_title, state FROM video_projects WHERE id = ?", (project_id,)).fetchone()
            log = db.execute("SELECT stage_name, status FROM run_logs WHERE video_project_id = ?", (project_id,)).fetchone()

        self.assertEqual(project["working_title"], "Foundation Test")
        self.assertEqual(project["state"], "idea")
        self.assertEqual(log["stage_name"], "project_creation")
        self.assertEqual(log["status"], "completed")

    def test_script_requires_manual_edit_before_approval(self) -> None:
        project_id = self._create_topic_ready_project()
        self.client.post(f"/projects/{project_id}/script/generate", follow_redirects=True)
        response = self.client.post(f"/projects/{project_id}/script/approve", follow_redirects=True)
        body = response.get_data(as_text=True)
        self.assertIn("You must edit the script before approval.", body)

    def test_topic_settings_persist_on_project(self) -> None:
        project_id = self._create_topic_ready_project()
        with self.app.app_context():
            db = get_db()
            project = db.execute(
                "SELECT target_duration_minutes, channel_niche, script_tone FROM video_projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        self.assertEqual(project["target_duration_minutes"], 9)
        self.assertEqual(project["channel_niche"], "personal finance India")
        self.assertEqual(project["script_tone"], "confident, direct")

    def test_voice_check_demo_mode_returns_info(self) -> None:
        response = self.client.post(
            "/voice/check",
            headers={"Referer": "/projects"},
            follow_redirects=True,
        )
        body = response.get_data(as_text=True)
        self.assertIn("silent fallback audio", body)

    def test_numeric_hook_can_pass_tension_validation_after_edit(self) -> None:
        project_id = self._create_topic_ready_project()
        self.client.post(f"/projects/{project_id}/script/generate", follow_redirects=True)
        response = self.client.post(
            f"/projects/{project_id}/script/save",
            data=self._edited_script_payload(
                hook_narration="80% of Indian millennials are broke by 30",
                hook_tension_type="shocking_statistic",
            ),
            follow_redirects=True,
        )
        body = response.get_data(as_text=True)
        self.assertNotIn("Hook must include a curiosity/tension signal.", body)

    def test_script_editor_shows_derived_pipeline_not_legacy_visual_fields(self) -> None:
        project_id = self._create_topic_ready_project()
        response = self.client.post(f"/projects/{project_id}/script/generate", follow_redirects=True)
        body = response.get_data(as_text=True)
        self.assertIn("Derived Story Plan", body)
        self.assertIn("How this page works now", body)
        self.assertNotIn("Visual instruction", body)
        self.assertNotIn("Visual beats (JSON)", body)

    def test_end_to_end_demo_flow_reaches_scheduled(self) -> None:
        project_id = self._create_topic_ready_project()
        self.client.post(f"/projects/{project_id}/script/generate", follow_redirects=True)
        self.client.post(f"/projects/{project_id}/script/save", data=self._edited_script_payload(), follow_redirects=True)
        self.client.post(f"/projects/{project_id}/script/approve", follow_redirects=True)
        with patch("youtube_ai_system.services.remotion_service.RemotionService.render_video") as render_video:
            render_video.side_effect = lambda spec, output_path: Path(output_path).write_bytes(b"remotion-test-video")
            self.client.post(f"/projects/{project_id}/media/generate", follow_redirects=True)
        self.client.post(f"/projects/{project_id}/scene-review/approve", follow_redirects=True)
        with patch("youtube_ai_system.services.assembly_service.AssemblyService.assemble_project") as assemble:
            def fake_assemble(pid):
                final_path = Path(self.app.config["STORAGE_ROOT"]) / "video" / str(pid) / "final_video.mp4"
                final_path.parent.mkdir(parents=True, exist_ok=True)
                final_path.write_bytes(b"final")
                from youtube_ai_system.models.repository import ProjectRepository
                ProjectRepository().update_project(pid, final_video_path=str(final_path))
                return str(final_path)
            assemble.side_effect = fake_assemble
            with patch("youtube_ai_system.services.remotion_service.RemotionService.render_still") as render_still:
                render_still.side_effect = lambda spec, output_path: Path(output_path).write_bytes(b"remotion-test-jpg")
                self.client.post(f"/projects/{project_id}/assemble", follow_redirects=True)
        self.client.post(
            f"/projects/{project_id}/review/save",
            data={
                "selected_title": "Final Title",
                "selected_description": "Final Description",
                "selected_thumbnail_path": "/tmp/thumb.jpg",
            },
            follow_redirects=False,
        )
        self.client.post(f"/projects/{project_id}/publish/stage", follow_redirects=False)
        self.client.post(
            f"/projects/{project_id}/publish/mock-upload",
            data={"youtube_video_id": "demo-flow"},
            follow_redirects=False,
        )
        self.client.post(
            f"/projects/{project_id}/publish/schedule",
            data={"publish_at": "2026-04-20T12:30:00+00:00"},
            follow_redirects=False,
        )

        with self.app.app_context():
            db = get_db()
            project = db.execute(
                "SELECT state, final_video_path, youtube_video_id FROM video_projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            scene_count = db.execute("SELECT COUNT(*) FROM scenes WHERE video_project_id = ?", (project_id,)).fetchone()[0]
            audio_sources = db.execute(
                "SELECT DISTINCT audio_source FROM scenes WHERE video_project_id = ?",
                (project_id,),
            ).fetchall()

        self.assertEqual(project["state"], "scheduled")
        self.assertTrue(project["final_video_path"].endswith("final_video.mp4"))
        self.assertEqual(project["youtube_video_id"], "demo-flow")
        self.assertEqual(scene_count, 5)
        self.assertEqual({row["audio_source"] for row in audio_sources}, {"demo_silent"})

    def _create_topic_ready_project(self) -> int:
        response = self.client.post("/projects/new", data={"working_title": "Pipeline Test"})
        project_id = int(response.headers["Location"].rstrip("/").split("/")[-1])
        self.client.post(
            f"/projects/{project_id}/topic",
            data={
                "topic": "Saving money",
                "angle": "mistakes that feel normal",
                "target_duration_minutes": "9",
                "channel_niche": "personal finance India",
                "script_tone": "confident, direct",
            },
            follow_redirects=True,
        )
        return project_id

    def _edited_script_payload(
        self,
        hook_narration: str = "Why do smart people keep making this saving mistake?",
        hook_tension_type: str = "curiosity_gap",
    ) -> dict[str, str]:
        return {
            "hook_narration": hook_narration,
            "hook_duration": "6",
            "hook_tension_type": hook_tension_type,
            "hook_visual_instruction": "Bold motion text around invisible saving mistakes",
            "hook_visual_type": "motion_text",
            "scene_count": "3",
            "scene_0_narration": "Scene 1 revised",
            "scene_0_visual_instruction": "Dynamic text",
            "scene_0_visual_type": "motion_text",
            "scene_1_narration": "Scene 2 revised",
            "scene_1_visual_instruction": "B-roll of budgeting",
            "scene_1_visual_type": "broll",
            "scene_2_narration": "Scene 3 revised",
            "scene_2_visual_instruction": "Simple chart",
            "scene_2_visual_type": "graph",
            "outro_narration": "Outro revised",
            "outro_visual_instruction": "Outro text",
            "outro_visual_type": "motion_text",
            "titles": "Title A\nTitle B",
            "description": "desc",
            "tags": "one, two",
        }


if __name__ == "__main__":
    unittest.main()
