from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from youtube_ai_system import create_app
from youtube_ai_system.db import close_db, get_db
from youtube_ai_system.models.repository import ProjectRepository
from youtube_ai_system.services.professional_scene_acceptance import ProfessionalSceneAcceptanceService


def scene(
    order: int,
    kind: str,
    narration: str,
    component: str,
    phases: list[str] | None = None,
    duration: float = 40.0,
) -> dict:
    phases = phases or ["intro", "process", "result"]
    return {
        "scene_order": order,
        "kind": kind,
        "narration_text": narration,
        "audio_path": f"/tmp/scene-{order:02d}.wav",
        "visual_path": f"/tmp/scene-{order:02d}.mp4",
        "audio_duration_sec": duration,
        "visual_type": component,
        "visual_plan_json": json.dumps(
            [
                {
                    "visual": {"pattern": component, "data": {"title": component}},
                    "beats": {
                        "beats": [
                            {
                                "component": component,
                                "text": phase,
                                "data": {"active_phase": phase},
                            }
                            for phase in phases
                        ]
                    },
                }
            ]
        ),
    }


class ProfessionalSceneAcceptanceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ProfessionalSceneAcceptanceService(repo=None)

    def test_blocks_internal_planning_language_and_generic_visuals(self) -> None:
        report = self.service.evaluate_scenes(
            [
                scene(
                    1,
                    "body",
                    "The topic is Why your salary disappears before month end. The scene still needs one concrete mechanism.",
                    "ConceptCard",
                    phases=["card"],
                )
            ],
            project={"working_title": "Why your salary disappears before month end"},
        )

        self.assertFalse(report.passed)
        codes = {issue.code for issue in report.blocking_issues}
        self.assertIn("internal_planning_language", codes)
        self.assertIn("generic_body_visual", codes)
        self.assertIn("title_repeated_as_script", codes)

    def test_blocks_generic_hook_even_with_generated_media(self) -> None:
        report = self.service.evaluate_scenes(
            [
                scene(
                    0,
                    "hook",
                    "Why does ₹50,000 feel gone by day 20?",
                    "RiskCard",
                    phases=["hook"],
                    duration=5,
                )
            ]
        )

        self.assertFalse(report.passed)
        self.assertIn("generic_hook_visual", {issue.code for issue in report.blocking_issues})

    def test_passes_strong_archetype_package(self) -> None:
        scenes = [
            scene(0, "hook", "₹50,000 lands. EMI and rent attack before day 20.", "MoneyFlowDiagram", ["intro", "drain", "remainder"], 8),
            scene(1, "body", "Rent, food apps, shopping, and subscriptions absorb the raise before savings grows.", "LifestyleCreepVisualizer", ["income_base", "raise_arrives", "expenses_follow", "gap_revealed"], 44),
            scene(2, "body", "A medical bill hits, but the emergency buffer blocks credit card debt.", "EmergencyFundVisualizer", ["boring_buffer", "shock_focus", "debt_prevention", "plan_survives"], 38),
            scene(3, "outro", "Track the leak, protect the buffer, cut fixed pressure, and start this month.", "OutroRecapVisualizer", ["track", "protect", "reduce_debt", "start"], 18),
        ]

        report = self.service.evaluate_scenes(scenes, project={"working_title": "Salary video"})

        self.assertTrue(report.passed)
        self.assertGreaterEqual(report.score, 80)
        self.assertEqual(report.blocking_issues, [])

    def test_blocks_long_body_scene_with_too_few_visual_moments(self) -> None:
        report = self.service.evaluate_scenes(
            [
                scene(
                    2,
                    "body",
                    "Your salary and expenses need a simple budget before the month begins.",
                    "MoneyFlowDiagram",
                    phases=["intro", "intro"],
                    duration=45,
                )
            ]
        )

        self.assertFalse(report.passed)
        self.assertIn("insufficient_perceptual_moments", {issue.code for issue in report.blocking_issues})


class ProfessionalSceneAcceptanceRouteTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.app = create_app(
            {
                "TESTING": True,
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

    def test_scene_approval_blocks_professional_qa_failures(self) -> None:
        with self.app.app_context():
            repo = ProjectRepository()
            project_id = repo.create_project("Why your salary disappears before month end")
            script_id = repo.create_script_version(project_id, {}, {}, [], "", [], {}, "test")
            repo.update_project(project_id, state="scene_review")
            repo.replace_scenes(
                project_id,
                script_id,
                [
                    {
                        "scene_order": 0,
                        "kind": "hook",
                        "narration_text": "Why does ₹50,000 feel gone by day 20?",
                        "visual_type": "RiskCard",
                        "visual_plan_json": scene(0, "hook", "Why does ₹50,000 feel gone by day 20?", "RiskCard", ["hook"], 5)["visual_plan_json"],
                    },
                    {
                        "scene_order": 1,
                        "kind": "body",
                        "narration_text": "The topic is Why your salary disappears before month end. The scene still needs one concrete mechanism.",
                        "visual_type": "ConceptCard",
                        "visual_plan_json": scene(1, "body", "bad", "ConceptCard", ["card"], 35)["visual_plan_json"],
                    },
                ],
            )
            for row in get_db().execute("SELECT id, scene_order FROM scenes WHERE video_project_id = ?", (project_id,)).fetchall():
                repo.update_scene(
                    row["id"],
                    audio_path=f"/tmp/scene-{row['scene_order']:02d}.wav",
                    visual_path=f"/tmp/scene-{row['scene_order']:02d}.mp4",
                    visual_source="remotion_scene_builder",
                    audio_duration_sec=35.0 if row["scene_order"] else 5.0,
                    status="completed",
                )

        response = self.client.post(f"/projects/{project_id}/scene-review/approve", follow_redirects=True)
        body = response.get_data(as_text=True)

        self.assertIn("Professional scene QA failed", body)
        with self.app.app_context():
            project = get_db().execute("SELECT state FROM video_projects WHERE id = ?", (project_id,)).fetchone()
        self.assertEqual(project["state"], "scene_review")


if __name__ == "__main__":
    unittest.main()
