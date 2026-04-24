import tempfile
import unittest
from pathlib import Path

from youtube_ai_system import create_app
from youtube_ai_system.db import close_db
from youtube_ai_system.services.script_service import ScriptService
from youtube_ai_system.services.story_intelligence_engine import StoryIntelligenceEngine


class StoryIntelligenceRefinementTestCase(unittest.TestCase):
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
        self.engine = StoryIntelligenceEngine()
        self.service = ScriptService()

    def tearDown(self) -> None:
        close_db()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def test_story_plan_uses_clean_hook_and_structured_weights(self) -> None:
        plan = self.engine.plan(
            (
                "Most people invest before they can survive one bad month. "
                "Without cash, one hospital bill becomes debt. "
                "An emergency fund buys time when income stops. "
                "Build survival before chasing returns."
            )
        )
        self.assertNotIn("real story starts", plan["hook"].lower())
        self.assertIn(plan["sections"][0]["type"], {"problem", "mistake"})
        self.assertGreaterEqual(len(plan["sections"]), 2)
        for section in plan["sections"]:
            self.assertIsInstance(section["weight"], dict)
            self.assertIn(section["weight"]["level"], {"low", "medium", "high"})
            self.assertGreaterEqual(section["weight"]["score"], 0)
            self.assertLessEqual(section["weight"]["score"], 1)

    def test_agenda_is_two_to_four_words_without_filler_prefixes(self) -> None:
        plan = self.engine.plan(
            (
                "A raise can make you feel rich and still keep you broke. "
                "Your expenses rise faster than your peace of mind. "
                "The fix is raising investments before lifestyle catches up. "
                "Automate the gap before spending expands."
            )
        )
        self.assertTrue(plan["agenda"])
        for item in plan["agenda"]:
            self.assertGreaterEqual(len(item.split()), 2)
            self.assertLessEqual(len(item.split()), 4)
            self.assertNotIn(item.split()[0].lower(), {"where", "how", "why"})

    def test_duplicate_hook_is_rephrased_and_contradiction_arc_wins(self) -> None:
        plan = self.engine.plan(
            (
                "Your salary looks bigger but still feels broken. "
                "Your salary looks bigger but still feels broken. "
                "Do this: automate saving before spending starts."
            )
        )
        self.assertNotEqual(plan["hook"].strip().rstrip(".!?").lower(), plan["sections"][0]["text"].strip().rstrip(".!?").lower())
        self.assertEqual(plan["arc_type"], "contradiction_arc")
        self.assertIn(plan["sections"][-1]["type"], {"decision", "optimization"})

    def test_plan_from_payload_keeps_single_idea_sections(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "Minimum payment is how small debt stays with you for years.", "duration": 6},
                "scenes": [
                    {"narration": "Interest keeps compounding when you delay the real payment.", "duration": 31},
                ],
                "outro": {"narration": "Cheap convenience becomes expensive silence.", "duration": 16},
            },
            "Credit cards",
            "minimum payment trap",
        )
        plan = payload["story_plan"]
        self.assertGreaterEqual(len(plan["sections"]), 2)
        self.assertIn(plan["sections"][0]["type"], {"problem", "mistake"})
        self.assertTrue(all(". " not in section["text"] for section in plan["sections"]))
