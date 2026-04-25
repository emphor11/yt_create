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

    def test_group_sentences_into_sections_pairs_simple_sequence(self) -> None:
        grouped = self.service.group_sentences_into_sections(
            ["Sentence 1", "Sentence 2", "Sentence 3", "Sentence 4"]
        )
        self.assertEqual(grouped, ["Sentence 1 Sentence 2", "Sentence 3 Sentence 4"])

    def test_group_sentences_merges_short_section_with_next(self) -> None:
        grouped = self.service.group_sentences_into_sections(
            [
                "Debt hurts families.",
                "Interest grows monthly.",
                "Budgeting works before income shocks.",
            ]
        )
        self.assertEqual(len(grouped), 1)
        self.assertGreaterEqual(len(grouped[0].split()), 8)

    def test_group_sentences_breaks_before_transition_starter(self) -> None:
        grouped = self.service.group_sentences_into_sections(
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
        grouped_payload = self.service._group_payload_for_story_plan(
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
                "Minimum payments often look completely harmless. Interest charges keep growing every month.",
                "Build a repayment plan this month.",
            ],
        )

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
                self.assertTrue(all(section["concepts"] for section in sections))
                self.assertTrue(all(section["visual_plan"] for section in sections))
                for section in sections:
                    for concept in section["concepts"]:
                        self.assertTrue(concept["concept"])
                        self.assertLessEqual(len(concept["concept"].split()), 3)
                        self.assertNotEqual(concept["type"], "unknown")
                    for item in section["visual_plan"]:
                        self.assertIn("concept", item)
                        self.assertIn("visual", item)
                        self.assertIn("beats", item)

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
        self.assertGreaterEqual(len(payload["story_plan"]["sections"]), 2)

    def test_numeric_visuals_override_generic_concepts_and_agenda_uses_top_concepts(self) -> None:
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
        self.assertEqual(sections[0]["visual_plan"][0]["concept"]["type"], "numeric")
        self.assertEqual(sections[0]["visual_plan"][0]["visual"]["pattern"], "NumericComparison")
        self.assertEqual(
            sections[0]["visual_plan"][0]["visual"]["data"]["values"],
            ["₹50,000 bill", "₹2,000 payment", "₹15,000 interest"],
        )
        self.assertEqual(
            payload["story_plan"]["agenda"],
            ["Debt Trap", "Investment Growth", "Inflation Loss"],
        )

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
        self.assertTrue(concept_section["concepts"])
        self.assertTrue(concept_section["visual_plan"])
        self.assertNotEqual(concept_section["visual_plan"][0]["concept"]["type"], "numeric")

    def test_invalid_visual_item_falls_back_to_concept_card(self) -> None:
        fallback = self.service._safe_visual_item(
            {
                "concept": {"concept": "", "type": "numeric"},
                "visual": {"component": "StatCard", "props": {"title": ""}},
                "beats": {"beats": [{"component": "StatCard", "text": ""}]},
            },
            "Minimum payments quietly extend debt.",
        )
        self.assertEqual(fallback["visual"]["pattern"], "ConceptCard")
        self.assertEqual(fallback["concept"]["type"], "fallback")
        self.assertEqual(fallback["beats"]["beats"][0]["text"], "Minimum payments stretch debt")

    def test_agenda_uses_strongest_section_insights_when_concepts_missing(self) -> None:
        agenda = self.service._agenda_from_top_concepts(
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
        phrases = self.service._numeric_phrases(
            "In your 20s, salary can vanish by day 12, and one card bill can break the month."
        )
        self.assertEqual(phrases, [])

    def test_numeric_labels_add_financial_meaning(self) -> None:
        phrases = self.service._numeric_phrases(
            "A ₹8,00,000 salary can still leak ₹1,60,000 before you notice."
        )
        self.assertEqual(phrases, ["₹8,00,000 salary", "₹1,60,000 leak"])
