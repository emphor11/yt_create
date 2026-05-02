import tempfile
import unittest
from pathlib import Path

from youtube_ai_system import create_app
from youtube_ai_system.db import close_db
from youtube_ai_system.services.scene_builder import build_scenes
from youtube_ai_system.services.scene_builder import COMPONENT_DURATION_WEIGHTS, PATTERN_PRIORITY


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
        self.assertEqual(scene["duration"], scene["total_duration"])
        self.assertGreaterEqual(len(scene["beats"]), 2)
        self.assertEqual(scene["beats"][0]["component"], "StatCard")
        self.assertIn(scene["beats"][-1]["text"], {"Debt Trap", "Interest grows Debt Trap"})
        self.assertEqual(scene["beats"][0]["start_time"], 0.0)
        self.assertEqual(scene["beats"][-1]["emphasis"], "hero")
        self.assertEqual(scene["beats"][-1]["end_time"], scene["duration"])

    def test_pattern_priority_has_no_downgraded_chart_duplicates_and_weights_exist(self) -> None:
        self.assertEqual(PATTERN_PRIORITY["GrowthChart"], 6)
        self.assertEqual(PATTERN_PRIORITY["SplitComparison"], 6)
        self.assertEqual(COMPONENT_DURATION_WEIGHTS["FlowDiagram"], 1.6)
        self.assertEqual(COMPONENT_DURATION_WEIGHTS["BalanceBar"], 1.5)

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

    def test_equal_audio_split_respects_minimum_duration(self) -> None:
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
        self.assertGreaterEqual(beat["end_time"] - beat["start_time"], 1.2)

    def test_equal_audio_split_gives_same_duration_per_beat(self) -> None:
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
        second_audio_duration = scene["audio_duration"] - scene["beats"][1]["start_time"]
        self.assertAlmostEqual(second_audio_duration, first_duration, places=1)
        self.assertEqual(scene["beats"][1]["end_time"], scene["duration"])
        self.assertEqual(scene["beats"][1]["emphasis"], "hero")

    def test_component_weighted_timing_gives_calculation_more_time(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "A ₹1,00,000 card bill at 40% interest creates ₹40,000 cost.",
                    "audio_file": str((Path(self.temp_dir.name) / "storage" / "audio" / "dummy.wav").resolve()),
                    "audio_duration": 12.0,
                    "weight": {"level": "high", "score": 0.9},
                    "visual_plan": [
                        {
                            "beats": {
                                "beats": [
                                    {"component": "StatCard", "text": "₹1,00,000 debt"},
                                    {"component": "CalculationStrip", "text": "₹1,00,000 x 40% = ₹40,000"},
                                    {"component": "StatCard", "text": "₹40,000 cost"},
                                ]
                            }
                        }
                    ],
                }
            ]
        )

        beats = result["scenes"][0]["beats"]
        stat_duration = beats[0]["end_time"] - beats[0]["start_time"]
        calculation_duration = beats[1]["end_time"] - beats[1]["start_time"]
        self.assertGreater(calculation_duration, stat_duration)
        self.assertEqual(beats[1]["emphasis"], "subtle")
        self.assertEqual(beats[-1]["emphasis"], "hero")

    def test_scene_builder_merges_all_visual_plan_beats_and_prefers_numeric_contract(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "Credit card debt at 40% interest means ₹1,00,000 becomes ₹1,40,000 in one year.",
                    "audio_file": str((Path(self.temp_dir.name) / "storage" / "audio" / "dummy.wav").resolve()),
                    "audio_duration": 12.0,
                    "weight": {"level": "high", "score": 0.9},
                    "finance_concept": {
                        "start_value": "₹1,00,000",
                        "end_value": "₹1,40,000",
                        "percentage": 40.0,
                    },
                    "narrative_arc": {
                        "visual_type": "balance_decay",
                        "rate": "40%",
                        "start_state": "₹1,00,000",
                        "end_state": "₹1,40,000",
                    },
                    "visual_plan": [
                        {
                            "concept": {"concept": "Debt Trap", "type": "risk"},
                            "visual": {"pattern": "RiskCard", "data": {"title": "DEBT TRAP"}},
                            "beats": {
                                "beats": [
                                    {"component": "FlowBar", "text": "Debt Trap"},
                                ]
                            },
                        },
                        {
                            "concept": {"concept": "40% interest", "type": "numeric"},
                            "visual": {
                                "pattern": "NumericComparison",
                                "data": {"values": ["₹1,00,000", "40%", "₹1,40,000"]},
                            },
                            "beats": {
                                "beats": [
                                    {"component": "StatCard", "text": "₹1,00,000"},
                                    {"component": "CalculationStrip", "text": "₹1,00,000 x 40% = ₹1,40,000"},
                                    {"component": "StatCard", "text": "₹1,40,000"},
                                ]
                            },
                        },
                    ],
                }
            ]
        )

        scene = result["scenes"][0]
        self.assertEqual(scene["pattern"], "NumericComparison")
        self.assertEqual(scene["data"]["values"], ["₹1,00,000", "40%", "₹1,40,000"])
        self.assertEqual(scene["data"]["rate"], "40%")
        self.assertEqual(scene["data"]["visual_type"], "balance_decay")
        self.assertIn("Debt Trap", [beat["text"] for beat in scene["beats"]])
        self.assertIn("₹1,40,000", [beat["text"] for beat in scene["beats"]])

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

    def test_timing_stays_deterministic_with_equal_audio_split(self) -> None:
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
        self.assertEqual(first_beats[-1]["end_time"], first["scenes"][0]["duration"])

    def test_sentence_aligned_beats_follow_sentence_word_timing(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "Salary hits account. EMI and rent take most of the monthly income.",
                    "audio_file": str((Path(self.temp_dir.name) / "storage" / "audio" / "dummy.wav").resolve()),
                    "audio_duration": 12.0,
                    "weight": {"level": "medium", "score": 0.5},
                    "visual_plan": [
                        {
                            "beats": {
                                "beats": [
                                    {
                                        "component": "StatCard",
                                        "text": "Salary",
                                        "source_text": "Salary hits account.",
                                        "sentence_index": 0,
                                    },
                                    {
                                        "component": "BalanceBar",
                                        "text": "EMI pressure",
                                        "source_text": "EMI and rent take most of the monthly income.",
                                        "sentence_index": 1,
                                    },
                                ]
                            }
                        }
                    ],
                }
            ]
        )

        beats = result["scenes"][0]["beats"]
        self.assertEqual(beats[0]["source_text"], "Salary hits account.")
        self.assertEqual(beats[1]["sentence_index"], 1)
        self.assertAlmostEqual(beats[0]["end_time"], 3.0, places=1)
        self.assertAlmostEqual(beats[1]["start_time"], 3.0, places=1)
        self.assertEqual(beats[1]["end_time"], 12.4)

    def test_too_many_beats_merges_last_two_for_minimum_duration(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "Debt pressure rises fast when interest compounds every month.",
                    "audio_file": str((Path(self.temp_dir.name) / "storage" / "audio" / "dummy.wav").resolve()),
                    "audio_duration": 4.0,
                    "weight": {"level": "medium", "score": 0.5},
                    "visual_plan": [
                        {
                            "beats": {
                                "beats": [
                                    {"component": "ConceptCard", "text": "Borrow money"},
                                    {"component": "FlowBar", "text": "Interest starts"},
                                    {"component": "FlowBar", "text": "Payments continue"},
                                    {"component": "RiskCard", "text": "Pressure rises"},
                                ]
                            }
                        }
                    ],
                }
            ]
        )
        scene = result["scenes"][0]
        self.assertEqual(len(scene["beats"]), 3)
        for beat in scene["beats"]:
            self.assertGreaterEqual(beat["end_time"] - beat["start_time"], 1.2)

    def test_scene_builder_preserves_directed_scene_fields_and_beat_data(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "My ₹50,000 salary disappears every month. EMI takes ₹18,000 and only ₹3,000 is left.",
                    "audio_file": str((Path(self.temp_dir.name) / "storage" / "audio" / "dummy.wav").resolve()),
                    "audio_duration": 6.0,
                    "concept_type": "salary_drain",
                    "direction": {"emotional_arc": {"opening": "comfort", "closing": "anxiety"}},
                    "theme": {"background": "#0A0A14"},
                    "visual_plan": [
                        {
                            "concept": {"concept": "Salary Drain", "type": "salary_drain"},
                            "visual": {
                                "pattern": "MoneyFlowDiagram",
                                "data": {
                                    "source": {"label": "Salary", "value": "₹50,000", "amount": 50000},
                                    "flows": [{"label": "EMI", "value": "₹18,000", "amount": 18000, "color": "red", "order": 1}],
                                    "remainder": {"value": "₹3,000", "amount": 3000, "is_dangerous": True},
                                },
                            },
                            "beats": {
                                "beats": [
                                    {"component": "StatCard", "text": "₹50,000", "data": {"label": "Salary"}},
                                    {
                                        "component": "MoneyFlowDiagram",
                                        "text": "Where salary goes",
                                        "data": {
                                            "source": {"label": "Salary", "value": "₹50,000", "amount": 50000},
                                            "flows": [{"label": "EMI", "value": "₹18,000", "amount": 18000, "color": "red", "order": 1}],
                                            "remainder": {"value": "₹3,000", "amount": 3000, "is_dangerous": True},
                                        },
                                    },
                                ]
                            },
                        }
                    ],
                }
            ]
        )
        scene = result["scenes"][0]
        self.assertEqual(scene["concept_type"], "salary_drain")
        self.assertEqual(scene["direction"]["emotional_arc"]["closing"], "anxiety")
        self.assertEqual(scene["theme"]["background"], "#0A0A14")
        self.assertEqual(scene["beats"][1]["data"]["remainder"]["amount"], 3000)
        self.assertEqual(scene["beats"][-1]["end_time"], scene["duration"])

    def test_scene_builder_preserves_directed_data_through_cleaning_and_timing(self) -> None:
        flow_data = {
            "source": {"label": "Salary", "value": "₹50,000", "amount": 50000},
            "flows": [{"label": "EMI", "value": "₹18,000", "amount": 18000, "color": "red", "order": 1}],
            "remainder": {"value": "₹3,000", "amount": 3000, "is_dangerous": True},
        }
        result = build_scenes(
            [
                {
                    "text": "My ₹50,000 salary disappears every month. EMI takes ₹18,000 and only ₹3,000 is left.",
                    "audio_file": str((Path(self.temp_dir.name) / "storage" / "audio" / "dummy.wav").resolve()),
                    "audio_duration": 6.0,
                    "direction": {"emotional_arc": {"opening": "comfort", "closing": "anxiety"}},
                    "visual_plan": [
                        {
                            "concept": {"concept": "Salary Drain", "type": "salary_drain"},
                            "visual": {"pattern": "MoneyFlowDiagram", "data": flow_data},
                            "beats": {
                                "beats": [
                                    {"component": "StatCard", "text": "₹50,000", "data": {"primary_value": "₹50,000"}},
                                    {"component": "MoneyFlowDiagram", "text": "Where salary goes", "data": flow_data},
                                    {"component": "HighlightText", "text": "₹3,000 left", "data": {"primary_value": "₹3,000"}},
                                ]
                            },
                        }
                    ],
                }
            ]
        )

        flow_beat = next(beat for beat in result["scenes"][0]["beats"] if beat["component"] == "MoneyFlowDiagram")
        self.assertEqual(flow_beat["data"]["source"]["amount"], 50000)
        self.assertEqual(flow_beat["data"]["flows"][0]["label"], "EMI")

    def test_calculation_strip_contract_preserves_steps_when_inferred_from_beats(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "A loan calculation shows the monthly pressure clearly.",
                    "audio_file": str((Path(self.temp_dir.name) / "storage" / "audio" / "dummy.wav").resolve()),
                    "audio_duration": 6.0,
                    "visual_plan": [
                        {
                            "beats": {
                                "beats": [
                                    {"component": "StatCard", "text": "₹1,00,000"},
                                    {
                                        "component": "CalculationStrip",
                                        "text": "Interest cost",
                                        "data": {
                                            "steps": [
                                                {"label": "Loan", "value": "₹1,00,000"},
                                                {"label": "Rate", "value": "14%", "operation": "+"},
                                            ]
                                        },
                                    },
                                ]
                            }
                        }
                    ],
                }
            ]
        )

        scene = result["scenes"][0]
        self.assertEqual(scene["pattern"], "CalculationStrip")
        self.assertEqual(scene["data"]["steps"][0]["label"], "Loan")

    def test_fallback_text_does_not_recurse_on_punctuation_only_text(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "!!!",
                    "audio_file": str((Path(self.temp_dir.name) / "storage" / "audio" / "dummy.wav").resolve()),
                    "audio_duration": 3.0,
                    "visual_plan": [],
                }
            ]
        )

        self.assertEqual(result["scenes"][0]["concept"], "Core message")

    def test_directed_scene_duration_gets_tail_hold(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "My ₹50,000 salary disappears every month. EMI takes ₹18,000 and only ₹3,000 is left.",
                    "audio_file": str((Path(self.temp_dir.name) / "storage" / "audio" / "dummy.wav").resolve()),
                    "audio_duration": 6.0,
                    "visual_plan": [
                        {
                            "concept": {"concept": "Salary Drain", "type": "salary_drain"},
                            "visual": {
                                "pattern": "MoneyFlowDiagram",
                                "data": {
                                    "source": {"label": "Salary", "value": "₹50,000", "amount": 50000},
                                    "flows": [{"label": "EMI", "value": "₹18,000", "amount": 18000, "color": "red", "order": 1}],
                                    "remainder": {"value": "₹3,000", "amount": 3000, "is_dangerous": True},
                                },
                            },
                            "beats": {"beats": [{"component": "MoneyFlowDiagram", "text": "Where salary goes"}]},
                        }
                    ],
                }
            ]
        )

        self.assertEqual(result["scenes"][0]["duration"], 6.8)


if __name__ == "__main__":
    unittest.main()
