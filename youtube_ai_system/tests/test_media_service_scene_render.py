import tempfile
import unittest
import json
from pathlib import Path

from youtube_ai_system import create_app
from youtube_ai_system.db import close_db
from youtube_ai_system.services.media_service import MediaService


class MediaServiceSceneRenderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": root / "instance" / "database.db",
                "INSTANCE_PATH": root / "instance",
                "STORAGE_ROOT": root / "storage",
                "VOICE_MODE": "demo",
                "REMOTION_ENABLED": False,
            }
        )
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.service = MediaService()

    def tearDown(self) -> None:
        close_db()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def test_section_for_scene_render_passes_finance_intelligence_to_scene_builder(self) -> None:
        section = self.service._section_for_scene_render(
            {
                "kind": "body",
                "narration_text": "A ₹1,00,000 credit card debt at 40% interest costs ₹40,000 every year.",
                "visual_plan_json": '[{"concept":{"concept":"Debt Trap","type":"risk"},"visual":{"pattern":"RiskCard","data":{"title":"DEBT TRAP"}},"beats":{"beats":[{"component":"FlowBar","text":"Debt Trap"}]}}]',
            },
            12.0,
            Path(self.temp_dir.name) / "scene.wav",
        )

        self.assertEqual(section["dominant_entity"], "debt")
        self.assertEqual(section["idea_type"], "risk")
        self.assertTrue(section["has_numbers"])
        self.assertTrue(section["has_causation"])
        self.assertEqual(section["finance_concept"]["concept_name"], "Debt Trap")
        self.assertEqual(section["narrative_arc"]["visual_type"], "balance_decay")
        self.assertEqual(section["state"]["money_out"], "40%")
        self.assertEqual(section["visual_plan"][0]["visual"]["pattern"], "DebtSpiralVisualizer")
        self.assertTrue(section["visual_story"])
        self.assertTrue(section["story_state"])

    def test_section_for_scene_render_preserves_stored_visual_scene_contract(self) -> None:
        visual_scene = {
            "narration": "Income rises. Lifestyle rises with it. Savings stay stuck.",
            "visual_intent": "Show income rising, lifestyle absorbing it, and savings staying flat.",
            "visual_beats": ["Income rises", "Lifestyle rises", "Savings stay stuck"],
            "numbers": [],
            "emotion": "anxiety",
            "mechanism": "lifestyle_inflation",
        }
        section = self.service._section_for_scene_render(
            {
                "kind": "body",
                "narration_text": visual_scene["narration"],
                "visual_scene_json": json.dumps(visual_scene),
                "visual_plan_json": '[{"visual":{"pattern":"ConceptCard"},"beats":{"beats":[{"component":"ConceptCard","text":"Old stale plan"}]}}]',
            },
            10.0,
            Path(self.temp_dir.name) / "scene.wav",
        )

        self.assertEqual(section["visual_scene"]["mechanism"], "lifestyle_inflation")
        self.assertEqual(section["concept_type"], "lifestyle_inflation")
        self.assertNotEqual(section["visual_plan"][0]["beats"]["beats"][0]["text"], "Old stale plan")
        self.assertTrue(section["story_state"])

    def test_derived_visual_plan_uses_full_story_pipeline_fallback(self) -> None:
        section = self.service._section_intelligence_from_narration(
            "Salary can vanish by day 12 when spending leaks every week.",
            "body",
        )

        self.assertEqual(section["dominant_entity"], "salary")
        self.assertEqual(section["idea_type"], "decay")
        self.assertEqual(section["finance_concept"]["concept_name"], "Salary Drain")
        self.assertTrue(section["narrative_arc"])
        self.assertTrue(section["visual_plan"])
        self.assertTrue(section["visual_story"])
        self.assertTrue(section["story_state"])
        self.assertEqual(section["visual_type"], "money_flow")

    def test_format_number_uses_indian_finance_style(self) -> None:
        self.assertEqual(self.service._format_number(1000), "1,000")
        self.assertEqual(self.service._format_number(100000), "1L")
        self.assertEqual(self.service._format_number(250000), "2.5L")
        self.assertEqual(self.service._format_number(10000000), "1Cr")

    def test_normalize_beat_durations_sums_to_scene_duration(self) -> None:
        beats = self.service._normalize_beat_durations(
            [
                {"beat_index": 0, "estimated_duration_sec": 2},
                {"beat_index": 1, "estimated_duration_sec": 3},
                {"beat_index": 2, "estimated_duration_sec": 5},
            ],
            12.0,
        )

        self.assertEqual(round(sum(beat["estimated_duration_sec"] for beat in beats), 2), 12.0)
        self.assertEqual([beat["estimated_duration_sec"] for beat in beats], [2.4, 3.6, 6.0])


if __name__ == "__main__":
    unittest.main()
