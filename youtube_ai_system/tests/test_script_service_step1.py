import tempfile
import unittest
from pathlib import Path

from youtube_ai_system import create_app
from youtube_ai_system.db import close_db
from youtube_ai_system.services.script_service import ScriptService


def _find_visual_keys(value, path="root"):
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"visual_beats", "visual_instruction", "visual_type"}:
                found.append(f"{path}.{key}")
            found.extend(_find_visual_keys(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_find_visual_keys(child, f"{path}[{index}]"))
    return found


class ScriptServiceStep1TestCase(unittest.TestCase):
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
                "VOICE_MODE": "demo",
                "GROQ_API_KEY": None,
            }
        )
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.service = ScriptService()

    def tearDown(self) -> None:
        close_db()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def test_normalize_payload_removes_visual_fields_and_adds_story_plan(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {
                    "narration": "80% of Indians are broke by payday.",
                    "estimated_duration_sec": 6,
                    "visual_type": "motion_text",
                    "visual_instruction": "80% broke",
                    "visual_beats": [{"beat_type": "reaction_card"}],
                },
                "scenes": [
                    {
                        "kind": "body",
                        "scene_index": 1,
                        "narration": "Build an emergency fund before you invest.",
                        "estimated_duration_sec": 30,
                        "visual_type": "graph",
                        "visual_instruction": "fund chart",
                    }
                ],
                "outro": {
                    "narration": "Fix the system before you blame yourself.",
                    "estimated_duration_sec": 18,
                    "visual_type": "motion_text",
                },
            },
            "Emergency Fund",
            "stability first",
        )

        self.assertEqual(payload["hook"], {"narration": "80% of Indians are broke by payday.", "duration": 6})
        self.assertEqual(payload["scenes"][0]["duration"], 30)
        self.assertEqual(payload["outro"]["duration"], 18)
        self.assertIn("story_plan", payload)
        self.assertTrue(payload["story_plan"]["sections"])
        self.assertEqual(_find_visual_keys(payload), [])

    def test_scene_rows_store_no_visual_payload(self) -> None:
        payload = self.service._normalize_payload(
            self.service._demo_script("Saving money", "bad defaults"),
            "Saving money",
            "bad defaults",
        )

        rows = self.service.scene_rows_from_payload(payload)
        self.assertTrue(rows)
        self.assertTrue(all("visual_instruction" not in row for row in rows))
        self.assertTrue(all("visual_type" not in row for row in rows))
        self.assertTrue(all("visual_plan_json" not in row for row in rows))

    def test_three_sample_scripts_normalize_to_minimal_shape(self) -> None:
        samples = [
            (
                "Emergency fund",
                "why savings comes first",
                {
                    "hook": {"narration": "Most people invest before they can survive one bad month.", "duration": 6},
                    "scenes": [
                        {"narration": "Without cash, one hospital bill becomes debt.", "duration": 30},
                        {"narration": "An emergency fund buys time when income stops.", "duration": 28},
                    ],
                    "outro": {"narration": "Build survival before chasing returns.", "duration": 15},
                },
            ),
            (
                "Lifestyle inflation",
                "income growth trap",
                {
                    "hook": {"narration": "A raise can make you feel rich and still keep you broke.", "estimated_duration_sec": 6},
                    "scenes": [
                        {"narration_text": "Your expenses rise faster than your peace of mind.", "estimated_duration_sec": 32},
                        {"content": "The fix is raising investments before lifestyle catches up.", "estimated_duration_sec": 34},
                    ],
                    "outro": {"text": "Automate the gap before spending expands.", "estimated_duration_sec": 18},
                },
            ),
            (
                "Credit cards",
                "minimum payment trap",
                {
                    "hook": {"text": "Minimum payment is how small debt stays with you for years.", "duration": 6},
                    "scenes": [
                        {"narration": "Interest keeps compounding when you delay the real payment.", "duration": 31},
                    ],
                    "outro": {"narration": "Cheap convenience becomes expensive silence.", "duration": 16},
                },
            ),
        ]

        for topic, angle, raw in samples:
            with self.subTest(topic=topic):
                payload = self.service._normalize_payload(raw, topic, angle)
                self.assertEqual(_find_visual_keys(payload), [])
                self.assertIn("story_plan", payload)
                self.assertIn("hook", payload)
                self.assertIn("scenes", payload)
                self.assertIn("outro", payload)
                self.assertIsInstance(payload["hook"]["duration"], int)
                self.assertTrue(all("duration" in scene for scene in payload["scenes"]))
                self.assertIsInstance(payload["story_plan"]["agenda"], list)
