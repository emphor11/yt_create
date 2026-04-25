import tempfile
import unittest
from pathlib import Path

from youtube_ai_system import create_app
from youtube_ai_system.db import close_db
from youtube_ai_system.services.scene_builder import build_scenes


class SceneBuilderTestCase(unittest.TestCase):
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
            }
        )
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self) -> None:
        close_db()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def test_build_scenes_creates_timed_beats_from_audio_duration(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "Paying minimum dues creates a debt trap.",
                    "weight": {"level": "high", "score": 0.9},
                    "visual_plan": [
                        {
                            "beats": {
                                "beats": [
                                    {"component": "StatCard", "text": "Minimum dues"},
                                    {"component": "FlowBar", "text": "Interest grows"},
                                    {"component": "RiskCard", "text": "Debt Trap"},
                                ]
                            }
                        }
                    ],
                }
            ]
        )

        self.assertEqual(len(result["scenes"]), 1)
        scene = result["scenes"][0]
        self.assertEqual(scene["concept"], "Debt Trap")
        self.assertEqual(scene["pattern"], "RiskCard")
        self.assertEqual(scene["data"], {"title": "DEBT TRAP"})
        self.assertTrue(Path(scene["audio_file"]).exists())
        self.assertGreater(scene["duration"], 0)
        self.assertEqual(len(scene["beats"]), 3)
        self.assertEqual(scene["beats"][0]["component"], "StatCard")
        self.assertEqual(scene["beats"][-1]["text"], "Debt Trap")
        self.assertEqual(scene["beats"][0]["start_time"], 0.0)
        self.assertEqual(scene["beats"][-1]["emphasis"], "hero")
        self.assertLessEqual(scene["beats"][-1]["end_time"], scene["duration"])

    def test_build_scenes_falls_back_to_single_concept_card_when_beats_missing(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "Inflation quietly reduces savings value.",
                    "weight": {"level": "medium", "score": 0.5},
                    "visual_plan": [],
                }
            ]
        )

        scene = result["scenes"][0]
        self.assertEqual(len(scene["beats"]), 2)
        self.assertEqual(scene["pattern"], "ConceptCard")
        self.assertEqual(scene["beats"][0]["text"], "Inflation quietly reduces")
        self.assertEqual(scene["beats"][-1]["emphasis"], "hero")

    def test_low_weight_shortens_beat_duration_within_limits(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "Budgeting works before and after income shocks.",
                    "weight": {"level": "low", "score": 0.4},
                    "visual_plan": [
                        {
                            "beats": {
                                "beats": [
                                    {"component": "ConceptCard", "text": "Before"},
                                    {"component": "BeforeAfterSplit", "text": "Budgeting Impact"},
                                ]
                            }
                        }
                    ],
                }
            ]
        )

        beat = result["scenes"][0]["beats"][0]
        self.assertGreaterEqual(beat["end_time"] - beat["start_time"], 0.6)
        self.assertLessEqual(beat["end_time"] - beat["start_time"], 2.5)

    def test_longer_final_beat_gets_more_time_than_short_intro_beat(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "A ₹8,00,000 salary can still leak ₹1,60,000 before you notice.",
                    "weight": {"level": "medium", "score": 0.5},
                    "visual_plan": [
                        {
                            "beats": {
                                "beats": [
                                    {"component": "StatCard", "text": "₹8,00,000 salary"},
                                    {"component": "StatCard", "text": "₹1,60,000 lost"},
                                ]
                            }
                        }
                    ],
                }
            ]
        )
        scene = result["scenes"][0]
        first_duration = scene["beats"][0]["end_time"] - scene["beats"][0]["start_time"]
        second_duration = scene["beats"][1]["end_time"] - scene["beats"][1]["start_time"]
        self.assertGreater(second_duration, first_duration)
        self.assertEqual(scene["beats"][1]["emphasis"], "hero")

    def test_single_existing_beat_expands_into_two_story_beats(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "In your 20s, salary can vanish by day 12, and one card bill can break the month.",
                    "weight": {"level": "medium", "score": 0.5},
                    "visual_plan": [
                        {
                            "beats": {
                                "beats": [
                                    {"component": "ConceptCard", "text": "Salary disappears early"},
                                ]
                            }
                        }
                    ],
                }
            ]
        )
        scene = result["scenes"][0]
        self.assertEqual(len(scene["beats"]), 2)
        self.assertEqual(scene["beats"][0]["text"], "Salary disappears early")
        self.assertEqual(scene["beats"][1]["text"], "Month feels broken")

    def test_clean_beat_text_rewrites_clipped_or_weak_phrases(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "Fix the system now, automate the ₹5,000, and next year stops feeling expensive.",
                    "weight": {"level": "high", "score": 0.9},
                    "visual_plan": [
                        {
                            "beats": {
                                "beats": [
                                    {"component": "ConceptCard", "text": "Fix the system"},
                                ]
                            }
                        }
                    ],
                }
            ]
        )
        scene = result["scenes"][0]
        self.assertEqual(scene["beats"][0]["text"], "Automate before you spend")
        self.assertEqual(scene["beats"][1]["text"], "Automate savings")

    def test_timing_variation_stays_deterministic_and_final_beat_is_longer(self) -> None:
        first = build_scenes(
            [
                {
                    "text": "A ₹8,00,000 salary can still leak ₹1,60,000 before you notice.",
                    "weight": {"level": "medium", "score": 0.5},
                    "visual_plan": [
                        {
                            "beats": {
                                "beats": [
                                    {"component": "StatCard", "text": "₹8,00,000 salary"},
                                    {"component": "CalculationStrip", "text": "₹1,60,000 leak"},
                                ]
                            }
                        }
                    ],
                }
            ]
        )
        second = build_scenes(
            [
                {
                    "text": "A ₹8,00,000 salary can still leak ₹1,60,000 before you notice.",
                    "weight": {"level": "medium", "score": 0.5},
                    "visual_plan": [
                        {
                            "beats": {
                                "beats": [
                                    {"component": "StatCard", "text": "₹8,00,000 salary"},
                                    {"component": "CalculationStrip", "text": "₹1,60,000 leak"},
                                ]
                            }
                        }
                    ],
                }
            ]
        )
        first_beats = first["scenes"][0]["beats"]
        second_beats = second["scenes"][0]["beats"]
        self.assertEqual(first_beats, second_beats)
        first_duration = first_beats[0]["end_time"] - first_beats[0]["start_time"]
        second_duration = first_beats[1]["end_time"] - first_beats[1]["start_time"]
        self.assertGreater(second_duration, first_duration)


if __name__ == "__main__":
    unittest.main()
