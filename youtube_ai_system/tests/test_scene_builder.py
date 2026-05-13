import json
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
        self.assertEqual(PATTERN_PRIORITY["InflationErosionVisualizer"], 7)
        self.assertEqual(PATTERN_PRIORITY["LifestyleCreepVisualizer"], 7)
        self.assertEqual(COMPONENT_DURATION_WEIGHTS["FlowDiagram"], 1.6)
        self.assertEqual(COMPONENT_DURATION_WEIGHTS["LifestyleCreepVisualizer"], 2.4)
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

    def test_risk_return_split_comparison_upgrades_to_finance_visualizer(self) -> None:
        result = build_scenes(
            [
                {
                    "kind": "body",
                    "text": (
                        "Risk and return are connected. An FD may offer around 6% and feel calm. "
                        "Equity can offer higher long-term growth. The price is volatility."
                    ),
                    "concept_type": "risk_return",
                    "visual_plan": [
                        {
                            "concept": {"concept": "Risk vs Return", "type": "comparison"},
                            "visual": {
                                "pattern": "SplitComparison",
                                "data": {"left": {"label": "Risk"}, "right": {"label": "Return"}},
                            },
                            "beats": {
                                "beats": [
                                    {"component": "StatCard", "text": "6%"},
                                    {"component": "SplitComparison", "text": "Risk vs Return"},
                                    {"component": "HighlightText", "text": "Choose risk deliberately"},
                                ]
                            },
                        }
                    ],
                }
            ]
        )

        scene = result["scenes"][0]
        self.assertEqual(scene["pattern"], "RiskReturnVisualizer")
        self.assertEqual(scene["data"]["safe_asset"], "FD")
        self.assertEqual(scene["data"]["growth_asset"], "Equity")

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

    def test_semantic_timing_allocates_action_micro_beats_by_intent(self) -> None:
        visual_data = {
            "source": {"label": "Salary", "value": "₹50,000", "amount": 50000},
            "flows": [
                {"label": "EMI", "value": "₹18,000", "amount": 18000},
                {"label": "Rent", "value": "₹12,000", "amount": 12000},
            ],
            "remainder": {"value": "₹20,000", "amount": 20000},
        }
        action_beats = [
            self._action_beat("₹50,000 Salary lands", "intro", "salary_arrives", "credit_in", "establish_source", {"start_frame": 0, "end_frame": 30}, visual_data),
            self._action_beat("₹18,000 EMI", "drain", "expense_drains", "collision_drain", "show_outflow", {"start_frame": 18, "end_frame": 52}, visual_data),
            self._action_beat("₹12,000 rent", "drain", "expense_drains", "collision_drain", "show_outflow", {"start_frame": 36, "end_frame": 70}, visual_data),
            self._action_beat("₹20,000 left", "remainder", "balance_revealed", "reveal_survivor", "show_consequence", {"start_frame": 78, "end_frame": 112}, visual_data),
        ]

        result = build_scenes(
            [
                {
                    "text": "Salary lands. EMI drains. Rent drains. Balance survives.",
                    "audio_file": "/tmp/phase5.wav",
                    "audio_duration": 12.0,
                    "direction": {"emotional_arc": {"opening": "comfort", "closing": "anxiety"}},
                    "concept_type": "salary_drain",
                    "visual_plan": [
                        {
                            "concept": {"concept": "Salary Drain", "type": "salary_drain"},
                            "visual": {"pattern": "MoneyFlowDiagram", "data": visual_data},
                            "beats": {"beats": action_beats},
                        }
                    ],
                }
            ]
        )

        scene = result["scenes"][0]
        beats = scene["beats"]
        durations = [round(beat["end_time"] - beat["start_time"], 2) for beat in beats]

        self.assertEqual([beat["data"]["active_action"]["action"] for beat in beats], ["salary_arrives", "expense_drains", "expense_drains", "balance_revealed"])
        self.assertTrue(all(beat["semantic_timing"]["engine"] == "semantic_timing" for beat in beats))
        self.assertEqual([state["state_type"] for state in scene["visual_state_sequence"]["states"]], ["centered_focus", "pressure_cluster", "isolate_survivor"])
        self.assertTrue(all(beat["visual_state"]["source_beat_indices"] for beat in beats))
        self.assertEqual([shot["shot_type"] for shot in scene["shot_sequence"]["shots"]], ["wide_context", "pressure_closeup", "pressure_closeup", "survivor_isolation"])
        self.assertTrue(all(beat["active_shot"]["source_beat_indices"] for beat in beats))
        self.assertEqual(beats[1]["semantic_timing"]["pacing"], "overlap_intensify")
        self.assertEqual(beats[-1]["semantic_timing"]["pacing"], "reveal_hold")
        self.assertGreater(durations[-1], durations[1])
        self.assertEqual(beats[-1]["end_time"], 12.8)

    def test_non_action_beats_keep_existing_component_weighted_timing(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "Money habits change slowly.",
                    "audio_file": "/tmp/no-action.wav",
                    "audio_duration": 6.0,
                    "visual_plan": [
                        {
                            "beats": {
                                "beats": [
                                    {"component": "StatCard", "text": "Habit"},
                                    {"component": "FlowBar", "text": "Change"},
                                    {"component": "RiskCard", "text": "Result"},
                                ]
                            }
                        }
                    ],
                }
            ]
        )

        beats = result["scenes"][0]["beats"]

        self.assertTrue(all("semantic_timing" not in beat for beat in beats))

    def _action_beat(
        self,
        text: str,
        phase: str,
        action: str,
        motion: str,
        intent: str,
        window: dict,
        visual_data: dict,
    ) -> dict:
        return {
            "component": "MoneyFlowDiagram",
            "text": text,
            "beat_phase": phase,
            "data": {
                **visual_data,
                "active_phase": phase,
                "active_action": {
                    "id": f"act:{action}:{text}",
                    "action": action,
                    "semantic_role": action,
                    "motion": motion,
                    "intent": intent,
                    "sequence_index": 0,
                    "value": {"display_value": text.split()[0]},
                },
                "action_choreography": {
                    "unit": "relative_frames",
                    "window": window,
                    "motion": motion,
                    "overlap_group": "overlapping_outflows" if action == "expense_drains" else "salary_drain",
                },
            },
        }
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
                    "visual_mode": "layered_hybrid",
                    "visual_story": {
                        "protagonist": {"role": "young_salaried_professional", "visual_id": "protagonist_01"},
                        "recurring_objects": ["phone_account", "salary_balance"],
                    },
                    "story_state": {
                        "scene_role": "pressure",
                        "protagonist_state": "stressed",
                        "active_objects": ["phone_account", "salary_balance"],
                        "visual_question": "Where did the salary go?",
                        "visual_answer": "₹50,000 becomes ₹3,000",
                    },
                    "cinematic_intent": {
                        "visual_mode": "layered_hybrid",
                        "human_action": "person checking salary credit on phone",
                        "metaphor": "salary drains into fixed expenses before the month starts",
                        "overlay_text": "₹3,000 left",
                        "motion_treatment": "notification_stack",
                        "asset_query": "cinematic phone banking closeup",
                        "texture": "dark_documentary",
                    },
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
        self.assertEqual(scene["visual_mode"], "layered_hybrid")
        self.assertEqual(scene["cinematic_intent"]["asset_query"], "cinematic phone banking closeup")
        self.assertEqual(scene["visual_story"]["protagonist"]["visual_id"], "protagonist_01")
        self.assertEqual(scene["story_state"]["visual_question"], "Where did the salary go?")
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
        self.assertEqual(flow_beat["beat_role"], "process")

    def test_scene_visual_contract_uses_matching_beat_data_when_visual_data_missing(self) -> None:
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
                    "visual_plan": [
                        {
                            "concept": {"concept": "Salary Drain", "type": "salary_drain"},
                            "visual": {"pattern": "MoneyFlowDiagram", "data": {}},
                            "beats": {
                                "beats": [
                                    {"component": "StatCard", "text": "₹50,000"},
                                    {"component": "MoneyFlowDiagram", "text": "Where salary goes", "data": flow_data},
                                ]
                            },
                        }
                    ],
                }
            ]
        )

        scene = result["scenes"][0]
        self.assertEqual(scene["pattern"], "MoneyFlowDiagram")
        self.assertEqual(scene["data"]["source"]["amount"], 50000)
        self.assertEqual(scene["warnings"], [])

    def test_scene_builder_normalizes_json_string_beat_data(self) -> None:
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
                    "visual_plan": [
                        {
                            "concept": {"concept": "Salary Drain", "type": "salary_drain"},
                            "visual": {"pattern": "MoneyFlowDiagram"},
                            "beats": {
                                "beats": [
                                    {"component": "MoneyFlowDiagram", "text": "Where salary goes", "data": json.dumps(flow_data)},
                                ]
                            },
                        }
                    ],
                }
            ]
        )

        scene = result["scenes"][0]
        self.assertEqual(scene["data"]["remainder"]["amount"], 3000)
        self.assertEqual(scene["beats"][0]["data"]["source"]["value"], "₹50,000")
        self.assertIsInstance(scene["beats"][0]["data"], dict)
        self.assertEqual(scene["beats"][0]["beat_role"], "introduce")

    def test_enrich_data_does_not_overwrite_rich_visual_director_fields(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "Credit card debt at 40% interest creates pressure.",
                    "audio_file": str((Path(self.temp_dir.name) / "storage" / "audio" / "dummy.wav").resolve()),
                    "audio_duration": 6.0,
                    "finance_concept": {"end_value": "₹1,40,000", "percentage": 40.0},
                    "narrative_arc": {"rate": "40%", "visual_type": "balance_decay"},
                    "state": {"money_out": "40%", "balance_change": "Debt grows"},
                    "visual_plan": [
                        {
                            "concept": {"concept": "Debt Trap", "type": "risk"},
                            "visual": {
                                "pattern": "RiskCard",
                                "data": {
                                    "title": "DEBT TRAP",
                                    "subtitle": "Minimum payment fails",
                                    "value": "Still growing",
                                    "state": {"risk": "visible"},
                                    "visual_type": "custom_risk",
                                },
                            },
                            "beats": {"beats": [{"component": "RiskCard", "text": "Debt Trap"}]},
                        }
                    ],
                }
            ]
        )

        data = result["scenes"][0]["data"]
        self.assertEqual(data["subtitle"], "Minimum payment fails")
        self.assertEqual(data["value"], "Still growing")
        self.assertEqual(data["state"], {"risk": "visible"})
        self.assertEqual(data["visual_type"], "custom_risk")

    def test_scene_builder_warns_when_directed_component_data_is_incomplete(self) -> None:
        result = build_scenes(
            [
                {
                    "text": "My ₹50,000 salary disappears every month.",
                    "audio_file": str((Path(self.temp_dir.name) / "storage" / "audio" / "dummy.wav").resolve()),
                    "audio_duration": 4.0,
                    "visual_plan": [
                        {
                            "concept": {"concept": "Salary Drain", "type": "salary_drain"},
                            "visual": {"pattern": "MoneyFlowDiagram", "data": {"source": {"value": "₹50,000"}}},
                            "beats": {"beats": [{"component": "MoneyFlowDiagram", "text": "Where salary goes"}]},
                        }
                    ],
                }
            ]
        )

        self.assertTrue(any("MoneyFlowDiagram has no data dict" in warning for warning in result["scenes"][0]["warnings"]))

    def test_directed_mechanism_component_gets_majority_duration(self) -> None:
        debt_data = {
            "principal": {"value": "₹1,00,000", "amount": 100000},
            "annual_interest_rate": 40.0,
            "monthly_interest": 3333.0,
            "minimum_payment": 3000.0,
            "time_period_months": 12,
            "balances": [{"month": month, "balance": 100000 + month * 400, "interest": 3333, "principal_paid": -333} for month in range(1, 13)],
            "month_12_balance": 104000,
            "is_trap": True,
        }
        result = build_scenes(
            [
                {
                    "text": (
                        "A ₹1,00,000 credit card balance does not look scary at first. "
                        "At 40% annual interest, the monthly interest itself is around ₹3,300. "
                        "The payment feels responsible but the interest is still winning."
                    ),
                    "audio_file": str((Path(self.temp_dir.name) / "storage" / "audio" / "dummy.wav").resolve()),
                    "audio_duration": 12.0,
                    "direction": {"emotional_arc": {"opening": "false_security", "closing": "alarm"}},
                    "visual_plan": [
                        {
                            "concept": {"concept": "Debt Trap", "type": "debt_trap"},
                            "visual": {"pattern": "DebtSpiralVisualizer", "data": debt_data},
                            "beats": {
                                "beats": [
                                    {"component": "StatCard", "text": "₹1,00,000 outstanding"},
                                    {"component": "CalculationStrip", "text": "Interest beats payment", "data": {"steps": [{"label": "Interest", "value": "₹3,333"}]}},
                                    {"component": "DebtSpiralVisualizer", "text": "Debt trap closes", "data": debt_data},
                                    {"component": "HighlightText", "text": "Interest is winning"},
                                ]
                            },
                        }
                    ],
                }
            ]
        )

        scene = result["scenes"][0]
        spiral = next(beat for beat in scene["beats"] if beat["component"] == "DebtSpiralVisualizer")
        spiral_duration = spiral["end_time"] - spiral["start_time"]
        self.assertGreaterEqual(spiral_duration / scene["audio_duration"], 0.55)
        self.assertEqual(spiral["beat_role"], "process")

    def test_inflation_visualizer_contract_and_timing(self) -> None:
        visual_data = {
            "start": "₹1,00,000",
            "end": "₹50,835",
            "rate": "7% for 10 years",
            "years": 10,
            "curve": "down",
            "items": [{"name": "Groceries", "current": 5, "future": 3}],
        }
        result = build_scenes(
            [
                {
                    "text": "If ₹1,00,000 sits idle while prices rise at 7%, buying power keeps shrinking.",
                    "audio_file": str((Path(self.temp_dir.name) / "storage" / "audio" / "dummy.wav").resolve()),
                    "audio_duration": 8.0,
                    "direction": {"emotional_arc": {"opening": "false_security", "closing": "alarm"}},
                    "visual_plan": [
                        {
                            "concept": {"concept": "Inflation Erosion", "type": "inflation_erosion"},
                            "visual": {"pattern": "InflationErosionVisualizer", "data": visual_data},
                            "beats": {
                                "beats": [
                                    {"component": "StatCard", "text": "₹1,00,000 today"},
                                    {"component": "InflationErosionVisualizer", "text": "Purchasing power falls", "data": visual_data},
                                    {"component": "HighlightText", "text": "Same money buys less"},
                                ]
                            },
                        }
                    ],
                }
            ]
        )

        scene = result["scenes"][0]
        self.assertEqual(scene["pattern"], "InflationErosionVisualizer")
        erosion = next(beat for beat in scene["beats"] if beat["component"] == "InflationErosionVisualizer")
        self.assertEqual(erosion["data"]["end"], "₹50,835")
        self.assertGreaterEqual((erosion["end_time"] - erosion["start_time"]) / scene["audio_duration"], 0.55)
        self.assertEqual(scene["warnings"], [])

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

    def test_phase_based_mechanism_scene_has_no_text_beats(self) -> None:
        visual_data = {
            "source": {"label": "Salary", "value": "₹50,000", "amount": 50000},
            "flows": [{"label": "EMI", "value": "₹18,000", "amount": 18000, "color": "red", "order": 1}],
            "remainder": {"value": "₹3,000", "amount": 3000, "is_dangerous": True},
        }
        result = build_scenes(
            [
                {
                    "type": "body",
                    "text": "My ₹50,000 salary disappears every month. EMI takes ₹18,000 and only ₹3,000 is left.",
                    "audio_file": str((Path(self.temp_dir.name) / "storage" / "audio" / "dummy.wav").resolve()),
                    "audio_duration": 9.0,
                    "visual_plan": [
                        {
                            "concept": {"concept": "Salary Drain", "type": "salary_drain"},
                            "visual": {"pattern": "MoneyFlowDiagram", "data": visual_data},
                            "beats": {
                                "beats": [
                                    {"component": "MoneyFlowDiagram", "text": "₹50,000", "data": {**visual_data, "active_phase": "intro"}, "beat_phase": "intro"},
                                    {"component": "MoneyFlowDiagram", "text": "Where salary goes", "data": {**visual_data, "active_phase": "drain"}, "beat_phase": "drain"},
                                    {"component": "MoneyFlowDiagram", "text": "₹3,000 left", "data": {**visual_data, "active_phase": "remainder"}, "beat_phase": "remainder"},
                                ]
                            },
                        }
                    ],
                }
            ]
        )

        scene = result["scenes"][0]
        self.assertEqual([beat["component"] for beat in scene["beats"]], ["MoneyFlowDiagram", "MoneyFlowDiagram", "MoneyFlowDiagram"])
        self.assertEqual([beat["beat_phase"] for beat in scene["beats"]], ["intro", "drain", "remainder"])
        self.assertEqual(scene["warnings"], [])


if __name__ == "__main__":
    unittest.main()
