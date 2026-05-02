import tempfile
import unittest
from pathlib import Path

from youtube_ai_system import create_app
from youtube_ai_system.db import close_db
from youtube_ai_system.services.script_service import ScriptService
from youtube_ai_system.services.story_pipeline import StoryPipeline


def _find_visual_keys(value, path="root"):
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            if path.startswith("root.story_plan"):
                found.extend(_find_visual_keys(child, f"{path}.{key}"))
                continue
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
        self.pipeline = StoryPipeline()

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

    def test_prompt_hook_contract_matches_validator(self) -> None:
        prompt = self.service._build_prompt("salary leaks", "young professionals")

        self.assertIn("Must pass this hook contract", prompt)
        self.assertIn("Why does your ₹50,000 salary feel gone by day 20?", prompt)
        self.assertIn("Avoid validator-weak hooks", prompt)

    def test_hook_refiner_rewrites_validator_weak_salary_hook(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {
                    "narration": (
                        "You are working hard, getting a decent salary. "
                        "Still, your bank account is almost empty by the 20th of every month."
                    ),
                    "duration": 10,
                },
                "scenes": [{"narration": "Lifestyle inflation quietly drains your salary every month."}],
                "outro": {"narration": "Track the leak before the month tracks you."},
            },
            "salary mistakes",
            "young professionals",
        )

        hook = payload["hook"]["narration"]
        self.assertEqual(hook, "Why does your salary feel gone by day 20?")
        self.assertEqual(self.service.validate_hook(payload["hook"]), [])

    def test_hook_refiner_preserves_already_valid_hook(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "Why does your ₹50,000 salary feel gone by day 20?", "duration": 6},
                "scenes": [{"narration": "Lifestyle inflation quietly drains your salary every month."}],
                "outro": {"narration": "Track the leak before the month tracks you."},
            },
            "salary mistakes",
            "young professionals",
        )

        self.assertEqual(payload["hook"]["narration"], "Why does your ₹50,000 salary feel gone by day 20?")

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

    def test_group_sentences_into_sections_pairs_simple_sequence(self) -> None:
        grouped = self.pipeline.group_sentences_into_sections(
            ["Sentence 1", "Sentence 2", "Sentence 3", "Sentence 4"]
        )
        self.assertEqual(grouped, ["Sentence 1 Sentence 2", "Sentence 3 Sentence 4"])

    def test_group_sentences_merges_short_section_with_next(self) -> None:
        grouped = self.pipeline.group_sentences_into_sections(
            [
                "Debt hurts families.",
                "Interest grows monthly.",
                "Budgeting works before income shocks.",
            ]
        )
        self.assertEqual(len(grouped), 1)
        self.assertGreaterEqual(len(grouped[0].split()), 8)

    def test_group_sentences_breaks_before_transition_starter(self) -> None:
        grouped = self.pipeline.group_sentences_into_sections(
            [
                "Debt hurts families badly.",
                "Interest grows every month.",
                "Because banks earn more from delay.",
                "Budgeting can reduce the damage.",
            ]
        )
        self.assertEqual(
            grouped,
            [
                "Debt hurts families badly. Interest grows every month.",
                "Because banks earn more from delay. Budgeting can reduce the damage.",
            ],
        )

    def test_group_payload_filters_short_and_filler_sentences_before_grouping(self) -> None:
        grouped_payload = self.pipeline.group_payload_for_story_plan(
            {
                "hook": {"narration": "Debt grows quietly.", "duration": 6},
                "scenes": [
                    {
                        "narration": (
                            "Let's start with the obvious. "
                            "Minimum payments often look completely harmless. "
                            "For instance, this is a common trap. "
                            "Interest charges keep growing every month."
                        )
                    }
                ],
                "outro": {"narration": "You know this already. Build a repayment plan this month."},
            }
        )
        narrations = [scene["narration"] for scene in grouped_payload["scenes"]]
        self.assertEqual(
            narrations,
            [
                (
                    "Minimum payments often look completely harmless. "
                    "Interest charges keep growing every month."
                ),
            ],
        )

    def test_group_payload_uses_idea_grouper_metadata(self) -> None:
        grouped_payload = self.pipeline.group_payload_for_story_plan(
            {
                "hook": {"narration": "Debt can quietly grow.", "duration": 6},
                "scenes": [
                    {
                        "narration": (
                            "Your salary rises every year. "
                            "But your expenses rise faster. "
                            "Another problem is credit card debt. "
                            "Because interest grows every month."
                        )
                    }
                ],
                "outro": {"narration": "Build better money systems."},
            }
        )
        scenes = grouped_payload["scenes"]
        self.assertGreaterEqual(len(scenes), 2)
        self.assertEqual(scenes[0]["dominant_entity"], "salary")
        self.assertIn(scenes[1]["dominant_entity"], {"credit", "debt"})
        self.assertIn("idea_group_id", scenes[0])
        self.assertIn("idea_type", scenes[0])
        self.assertIn("has_numbers", scenes[0])
        self.assertIn("has_comparison", scenes[0])
        self.assertIn("has_causation", scenes[0])

    def test_idea_grouper_keeps_complete_lifestyle_inflation_idea_together(self) -> None:
        grouped_payload = self.pipeline.group_payload_for_story_plan(
            {
                "hook": {"narration": "Raises can still leave you broke.", "duration": 6},
                "scenes": [
                    {
                        "narration": (
                            "As soon as we get a raise, we upgrade our lifestyle. "
                            "Whether it's a fancy phone or a new car. "
                            "Spending rises faster than savings. "
                            "That quietly slows wealth building."
                        )
                    }
                ],
                "outro": {"narration": "Keep the gap and invest the difference."},
            }
        )
        scenes = grouped_payload["scenes"]
        self.assertEqual(len(scenes), 1)
        self.assertIn("Spending rises faster than savings.", scenes[0]["narration"])
        self.assertIn("That quietly slows wealth building.", scenes[0]["narration"])

    def test_idea_grouper_splits_credit_card_and_emergency_fund_ideas(self) -> None:
        grouped_payload = self.pipeline.group_payload_for_story_plan(
            {
                "hook": {"narration": "Debt feels manageable until it isn't.", "duration": 6},
                "scenes": [
                    {
                        "narration": (
                            "Credit card debt grows fast when interest compounds every month. "
                            "Minimum payments keep the balance alive. "
                            "Without an emergency fund, one medical bill pushes you into debt. "
                            "A cash buffer protects your long-term investments."
                        )
                    }
                ],
                "outro": {"narration": "Fix the system before the next shock arrives."},
            }
        )
        scenes = grouped_payload["scenes"]
        self.assertEqual(len(scenes), 2)
        self.assertIn("Credit card debt grows fast", scenes[0]["narration"])
        self.assertIn("Without an emergency fund", scenes[1]["narration"])

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

    def test_story_sections_include_deterministic_concepts(self) -> None:
        samples = [
            {
                "topic": "Inflation",
                "angle": "saving value",
                "payload": {
                    "hook": {"narration": "Inflation can quietly damage your savings.", "duration": 6},
                    "scenes": [
                        {"narration": "Inflation makes your savings lose value.", "duration": 30},
                        {"narration": "Equity is risky while debt is stable.", "duration": 30},
                    ],
                    "outro": {"narration": "Investment growth protects your future.", "duration": 18},
                },
            },
            {
                "topic": "Debt",
                "angle": "avoid the trap",
                "payload": {
                    "hook": {"narration": "One minimum payment can keep debt alive for years.", "duration": 6},
                    "scenes": [
                        {"narration": "Paying minimum dues creates a debt trap.", "duration": 30},
                        {"narration": "Budgeting works before and after income shocks.", "duration": 30},
                    ],
                    "outro": {"narration": "Debt risk destroys financial freedom.", "duration": 18},
                },
            },
        ]

        for sample in samples:
            with self.subTest(topic=sample["topic"]):
                payload = self.service._normalize_payload(
                    sample["payload"],
                    sample["topic"],
                    sample["angle"],
                )
                sections = payload["story_plan"]["sections"]
                self.assertTrue(sections)
                self.assertTrue(all("concepts" in section for section in sections))
                self.assertTrue(all("visual_plan" in section for section in sections))
                self.assertTrue(all(isinstance(section["concepts"], list) for section in sections))
                self.assertTrue(all(isinstance(section["visual_plan"], list) for section in sections))
                self.assertTrue(any(section["concepts"] for section in sections))
                self.assertTrue(any(section["visual_plan"] for section in sections))
                for section in sections:
                    for concept in section["concepts"]:
                        self.assertTrue(concept["concept"])
                        self.assertLessEqual(len(concept["concept"].split()), 3)
                        self.assertNotEqual(concept["type"], "unknown")
                    for item in section["visual_plan"]:
                        self.assertIn("concept", item)
                        self.assertIn("visual", item)
                        self.assertIn("beats", item)

    def test_finance_concepts_are_strong_on_grouped_sections(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "Invisible leaks keep salaries stuck.", "duration": 6},
                "scenes": [
                    {
                        "narration": (
                            "As soon as we get a raise, we upgrade our lifestyle. "
                            "Spending rises faster than savings. "
                            "Credit card debt grows fast when interest compounds every month. "
                            "Minimum payments keep the balance alive."
                        ),
                        "duration": 30,
                    }
                ],
                "outro": {"narration": "Protect the gap before it disappears.", "duration": 18},
            },
            "Money leaks",
            "salary trap",
        )
        concepts = [section["concepts"][0]["concept"] for section in payload["story_plan"]["sections"] if section["concepts"]]
        self.assertIn("Lifestyle Inflation", concepts)
        self.assertIn("Debt Trap", concepts)

    def test_story_plan_uses_grouped_sections_before_engine(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "Debt can quietly take over your life.", "duration": 6},
                "scenes": [
                    {
                        "narration": (
                            "Paying minimum dues creates a debt trap. "
                            "Interest keeps growing every month. "
                            "But most people notice too late. "
                            "Debt risk destroys financial freedom."
                        ),
                        "duration": 30,
                    }
                ],
                "outro": {"narration": "Budgeting works before and after income shocks.", "duration": 18},
            },
            "Debt",
            "avoid the trap",
        )
        self.assertIn("story_plan", payload)
        self.assertEqual(len(payload["story_plan"]["sections"]), 2)
        self.assertEqual(
            [section["idea_group_id"] for section in payload["story_plan"]["sections"]],
            ["idea_hook", "idea_00"],
        )

    def test_numeric_visuals_enhance_concept_visuals_and_agenda_uses_top_concepts(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "A ₹50,000 balance can quietly explode.", "duration": 6},
                "scenes": [
                    {
                        "narration": (
                            "A ₹50,000 bill with a ₹2,000 minimum can create ₹15,000 interest. "
                            "Paying minimum dues creates a debt trap."
                        ),
                        "duration": 35,
                    },
                    {
                        "narration": "Inflation makes your savings lose value.",
                        "duration": 35,
                    },
                ],
                "outro": {"narration": "Investment growth protects your long-term financial freedom.", "duration": 18},
            },
            "Debt",
            "minimum payment trap",
        )
        sections = payload["story_plan"]["sections"]
        self.assertTrue(sections[0]["visual_plan"])
        self.assertEqual(sections[0]["visual_plan"][0]["concept"]["type"], "risk")
        unified_item = sections[0]["visual_plan"][0]
        self.assertEqual(unified_item["visual"]["pattern"], "NumericComparison")
        self.assertEqual(
            unified_item["visual"]["data"]["values"],
            ["₹50,000 bill", "₹2,000 payment", "₹15,000 interest"],
        )
        self.assertEqual(sections[0]["visual_type"], "balance_decay")
        self.assertIn("state", sections[0])
        self.assertTrue(sections[0]["narrative_arc"]["story_goal"])
        self.assertEqual(
            payload["story_plan"]["agenda"],
            ["Debt Trap", "Inflation Loss"],
        )

    def test_visual_plan_uses_section_narrative_arc_beats(self) -> None:
        story_plan = {
            "hook": "",
            "agenda": [],
            "sections": [
                {
                    "type": "explanation",
                    "text": "Credit card debt grows fast when interest compounds every month.",
                    "weight": {"level": "medium", "score": 0.55},
                    "concepts": [{"concept": "Debt Trap", "type": "risk"}],
                    "has_numbers": False,
                }
            ],
        }
        story_plan = self.pipeline.attach_section_narrative_arc(story_plan)
        planned = self.pipeline.attach_section_visual_plan(story_plan)
        section = planned["sections"][0]
        beats = planned["sections"][0]["visual_plan"][0]["beats"]["beats"]
        self.assertGreaterEqual(len(beats), 1)
        self.assertEqual(section["visual_type"], "pressure")
        self.assertEqual(section["visual_plan"][0]["visual"]["pattern"], "FlowDiagram")
        self.assertEqual(beats[0]["text"], "Swipe now")
        self.assertIn("source_text", beats[0])
        self.assertTrue(all("component" in beat for beat in beats))

    def test_numeric_arc_uses_calculation_steps_when_values_are_related(self) -> None:
        story_plan = {
            "hook": "",
            "agenda": [],
            "sections": [
                {
                    "type": "explanation",
                    "text": (
                        "A ₹1,00,000 credit card debt at 40% interest costs ₹40,000 every year. "
                        "Paying minimum dues creates a debt trap."
                    ),
                    "weight": {"level": "high", "score": 0.9},
                    "dominant_entity": "debt",
                    "idea_type": "risk",
                    "has_numbers": True,
                    "has_causation": True,
                }
            ],
        }
        story_plan = self.pipeline.attach_section_concepts(story_plan)
        story_plan = self.pipeline.attach_section_narrative_arc(story_plan)
        planned = self.pipeline.attach_section_visual_plan(story_plan)
        beats = planned["sections"][0]["visual_plan"][0]["beats"]["beats"]
        calculation = next(beat for beat in beats if beat["component"] == "CalculationStrip")

        self.assertEqual(planned["sections"][0]["visual_type"], "balance_decay")
        steps = calculation.get("steps") or calculation.get("data", {}).get("steps") or []
        self.assertIn(calculation["text"], {"₹1,00,000 x 40% = ₹40,000", "Interest beats payment"})
        self.assertTrue(steps)
        self.assertTrue(any(step.get("operation") in {"x", "+", "="} for step in steps[1:]))
        self.assertIn(beats[-1]["component"], {"HighlightText", "DebtSpiralVisualizer"})

    def test_section_flow_validation_logs_warning_without_failing_story_plan(self) -> None:
        class FakeLogger:
            def __init__(self) -> None:
                self.messages = []

            def log(self, stage_name, status, message, project_id=None) -> None:
                self.messages.append((stage_name, status, message, project_id))

        logger = FakeLogger()
        pipeline = StoryPipeline(logger=logger)

        def fail_section_flow(sections):
            raise ValueError("Story sections are out of order.")

        pipeline.story_intelligence._validate_section_flow = fail_section_flow
        story_plan = pipeline.story_plan_from_idea_groups(
            {
                "hook": {"narration": "Debt can quietly trap you.", "duration": 6},
                "scenes": [
                    {
                        "narration": "Paying minimum dues creates a debt trap.",
                        "idea_group_id": "idea_00",
                        "dominant_entity": "debt",
                        "idea_type": "risk",
                    },
                    {
                        "narration": "Budgeting can reduce the damage.",
                        "idea_group_id": "idea_01",
                        "dominant_entity": "budgeting",
                        "idea_type": "optimization",
                    },
                ],
            }
        )

        self.assertTrue(story_plan["sections"])
        self.assertEqual(logger.messages[0][0], "story_planning")
        self.assertEqual(logger.messages[0][1], "warning")
        self.assertIn("out of order", logger.messages[0][2])

    def test_invalid_numeric_candidate_falls_back_to_concept_visual(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "Minimum payments feel harmless.", "duration": 6},
                "scenes": [
                    {
                        "narration": "A minimum payment cycle can last 10 years.",
                        "duration": 35,
                    }
                ],
                "outro": {"narration": "Minimum payment cycles quietly extend debt.", "duration": 18},
            },
            "Debt",
            "minimum payment trap",
        )
        concept_section = payload["story_plan"]["sections"][1]
        self.assertEqual(concept_section["concepts"], [{"concept": "Debt Trap", "type": "risk"}])
        self.assertTrue(concept_section["visual_plan"])
        self.assertNotEqual(concept_section["visual_plan"][0]["concept"]["type"], "numeric")

    def test_invalid_visual_item_is_rejected_without_text_fallback(self) -> None:
        fallback = self.pipeline.safe_visual_item(
            {
                "concept": {"concept": "", "type": "numeric"},
                "visual": {"component": "StatCard", "props": {"title": ""}},
                "beats": {"beats": [{"component": "StatCard", "text": ""}]},
            }
        )
        self.assertIsNone(fallback)

    def test_invalid_visual_item_rejects_sentence_fragments(self) -> None:
        fallback = self.pipeline.safe_visual_item(
            {
                "concept": {"concept": "Debt Trap", "type": "risk"},
                "visual": {"pattern": "RiskCard", "data": {"title": "DEBT TRAP"}},
                "beats": {"beats": [{"component": "StatCard", "text": "as soon as"}]},
            }
        )
        self.assertIsNone(fallback)

    def test_agenda_uses_strongest_section_insights_when_concepts_missing(self) -> None:
        agenda = self.pipeline.agenda_from_top_concepts(
            [
                {
                    "weight": {"score": 0.9},
                    "concepts": [],
                    "visual_plan": [{"concept": {"concept": "Salary disappears early", "type": "fallback"}}],
                },
                {
                    "weight": {"score": 0.8},
                    "concepts": [],
                    "visual_plan": [{"concept": {"concept": "₹1,60,000 leak", "type": "numeric"}}],
                },
                {
                    "weight": {"score": 0.7},
                    "concepts": [],
                    "visual_plan": [{"concept": {"concept": "Automate savings", "type": "fallback"}}],
                },
            ]
        )
        self.assertEqual(agenda, ["₹1,60,000 leak", "Salary disappears early", "Automate savings"])

    def test_financial_number_filter_rejects_age_and_day_numbers(self) -> None:
        phrases = self.pipeline.numeric_phrases(
            "In your 20s, salary can vanish by day 12, and one card bill can break the month."
        )
        self.assertEqual(phrases, [])

    def test_numeric_labels_add_financial_meaning(self) -> None:
        phrases = self.pipeline.numeric_phrases(
            "A ₹8,00,000 salary can still leak ₹1,60,000 before you notice."
        )
        self.assertEqual(phrases, ["₹8,00,000 salary", "₹1,60,000 leak"])
