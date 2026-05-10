import unittest

from youtube_ai_system.services.finance_concept_extractor import FinanceConceptExtractor
from youtube_ai_system.services.financial_governance import repetition_report, numeric_role_map
from youtube_ai_system.services.scene_debug import SceneDebugTrace
from youtube_ai_system.services.visual_director import VisualDirector, VisualDirectorInput


def director_input(narration: str) -> VisualDirectorInput:
    return VisualDirectorInput(
        concept_type="lifestyle_inflation",
        concept_name="Lifestyle Inflation",
        primary_entity="salary",
        action="changes",
        start_value="₹50,000",
        end_value="₹30,000",
        percentage=None,
        time_period=None,
        confidence=0.9,
        narration_text=narration,
        idea_type="risk",
        has_numbers=True,
        section_position="middle",
        preceding_concept_type=None,
    )


class FinancialGovernanceTestCase(unittest.TestCase):
    def test_numeric_provenance_classifies_salary_raise_roles(self) -> None:
        facts = numeric_role_map(
            "Your salary rises from ₹50,000 to ₹80,000. The extra ₹30,000 never reaches savings.",
            scene_id="scene1",
        )["facts"]

        roles = {fact["role"]: fact["raw"] for fact in facts}

        self.assertEqual(roles["start_income"], "₹50,000")
        self.assertEqual(roles["end_income"], "₹80,000")
        self.assertEqual(roles["raise_delta"], "₹30,000")

    def test_finance_extractor_does_not_treat_raise_delta_as_end_income(self) -> None:
        result = FinanceConceptExtractor().extract(
            {
                "combined_text": (
                    "Your salary rises from ₹50,000 to ₹80,000. "
                    "The extra ₹30,000 never reaches savings. Lifestyle inflation absorbs the raise."
                ),
                "dominant_entity": "salary",
                "idea_type": "risk",
            }
        )

        self.assertEqual(result.concept_name, "Lifestyle Inflation")
        self.assertEqual(result.start_value, "₹50,000")
        self.assertEqual(result.end_value, "₹80,000")
        self.assertEqual(result.agent, "lifestyle")

    def test_visual_director_uses_spoken_income_range_not_synthetic_income(self) -> None:
        narration = "Your salary rises from ₹50,000 to ₹80,000. The extra ₹30,000 never reaches savings."
        result = VisualDirector().direct(director_input(narration))

        self.assertEqual(result.data["start_income"]["value"], "₹50,000")
        self.assertEqual(result.data["end_income"]["value"], "₹80,000")
        self.assertEqual(result.data["raise"]["value"], "₹30,000")
        self.assertNotIn("₹72,500", str(result.data))
        self.assertTrue(result.data["old_spending"]["derived"])
        self.assertTrue(result.data["old_spending"]["derived_from"])

    def test_validator_flags_unspoken_visual_number_and_scene_density(self) -> None:
        narration = (
            "Your salary rises from ₹50,000 to ₹80,000. At first, it feels like progress. "
            "Then rent upgrades. Food apps expand. Weekend plans expand. Shopping expands. "
            "The extra ₹30,000 never reaches savings. Lifestyle absorbs the raise. "
            "The problem is not earning more. The problem is giving every raise a new expense. "
            "Nothing feels irresponsible. A better house feels deserved. Better food feels normal. "
            "A nicer phone feels earned. Savings stay flat. The gap is lifestyle inflation."
        )
        trace = SceneDebugTrace(scene_id="scene_1", scene_order=1, narration=narration)
        scene = {
            "narration": narration,
            "concept_type": "lifestyle_inflation",
            "pattern": "LifestyleCreepVisualizer",
            "duration": 51.0,
            "data": {"end_income": {"value": "₹72,500", "amount": 72500}},
            "beats": [
                {"component": "LifestyleCreepVisualizer", "start_time": 0, "end_time": 12, "data": {"end_income": {"value": "₹72,500"}}},
                {"component": "LifestyleCreepVisualizer", "start_time": 12, "end_time": 24, "data": {}},
                {"component": "LifestyleCreepVisualizer", "start_time": 24, "end_time": 38, "data": {}},
                {"component": "LifestyleCreepVisualizer", "start_time": 38, "end_time": 51, "data": {}},
            ],
        }

        trace.validate_scene(scene)
        codes = {warning.get("payload", {}).get("code") for warning in trace.data["warnings"]}

        self.assertIn("unspoken_visual_number", codes)
        self.assertIn("too_few_beats_for_duration", codes)
        self.assertIn("scene_too_dense", codes)

    def test_repetition_report_flags_repeated_meta_philosophy(self) -> None:
        report = repetition_report(
            [
                {"narration": "The viewer can see the money system, not just hear generic advice."},
                {"narration": "Every rupee has a job inside the money system."},
                {"narration": "The money system appears again as generic advice."},
            ]
        )

        self.assertEqual(report["status"], "warning")
        self.assertIn("money system", report["banned_repeats"])


if __name__ == "__main__":
    unittest.main()
