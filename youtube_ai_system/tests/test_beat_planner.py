import unittest

from youtube_ai_system.services.beat_planner import generate_beats


class BeatPlannerTestCase(unittest.TestCase):
    def test_risk_generates_three_beats_with_risk_card_at_end(self) -> None:
        result = generate_beats(
            {"concept": "Debt Trap", "type": "risk", "weight_level": "high"},
            "Paying minimum dues creates a debt trap",
        )
        self.assertEqual(
            result,
            {
                "beats": [
                    {"component": "StatCard", "text": "Minimum dues"},
                    {"component": "FlowBar", "text": "Interest grows"},
                    {"component": "RiskCard", "text": "Debt Trap"},
                ]
            },
        )

    def test_comparison_generates_split_comparison_at_end(self) -> None:
        result = generate_beats(
            {"concept": "Equity vs Debt", "type": "comparison", "weight_level": "high"},
            "Equity is risky while debt is stable",
        )
        self.assertEqual(
            result,
            {
                "beats": [
                    {"component": "ConceptCard", "text": "Equity"},
                    {"component": "ConceptCard", "text": "Debt"},
                    {"component": "SplitComparison", "text": "Equity vs Debt"},
                ]
            },
        )

    def test_cause_effect_generates_three_beats(self) -> None:
        result = generate_beats(
            {"concept": "Inflation", "type": "cause_effect", "weight_level": "high"},
            "Inflation makes your savings lose value",
        )
        self.assertEqual(len(result["beats"]), 2)
        self.assertEqual(result["beats"][0]["text"], "Inflation")
        self.assertEqual(result["beats"][-1]["text"], "Inflation")
        self.assertNotIn(result["beats"][0]["text"], {"Cause", "Process", "Context"})

    def test_growth_generates_three_beats(self) -> None:
        result = generate_beats(
            {"concept": "Investment Growth", "type": "growth", "weight_level": "high"},
            "₹5,000 can become ₹60,000 over 12 months",
        )
        self.assertEqual(len(result["beats"]), 3)
        self.assertEqual(result["beats"][0]["text"], "₹5,000")
        self.assertEqual(result["beats"][-1]["text"], "Investment Growth")

    def test_before_after_generates_three_beats(self) -> None:
        result = generate_beats(
            {"concept": "Budgeting Impact", "type": "before_after", "weight_level": "high"},
            "Budgeting works before and after income shocks",
        )
        self.assertEqual(len(result["beats"]), 3)
        self.assertEqual(result["beats"][0]["text"], "Budgeting")
        self.assertEqual(result["beats"][-1]["text"], "Budgeting Impact")

    def test_process_generates_single_step_flow(self) -> None:
        result = generate_beats(
            {"concept": "Money Flow", "type": "process", "weight_level": "low"},
            "First save money and then invest it",
        )
        self.assertEqual(
            result,
            {"beats": [{"component": "StepFlow", "text": "Money Flow"}]},
        )

    def test_definition_generates_two_beats(self) -> None:
        result = generate_beats(
            {"concept": "Inflation", "type": "definition", "weight_level": "medium"},
            "Inflation reduces buying power",
        )
        self.assertEqual(result, {"beats": [{"component": "ConceptCard", "text": "Inflation"}]})

    def test_paradox_generates_risk_card_at_end(self) -> None:
        result = generate_beats(
            {"concept": "Rich but Broke", "type": "paradox", "weight_level": "medium"},
            "You can feel rich but still stay broke",
        )
        self.assertEqual(
            result["beats"],
            [
                {"component": "ConceptCard", "text": "feel rich"},
                {"component": "RiskCard", "text": "Rich but Broke"},
            ],
        )

    def test_fallback_uses_single_concept_card_when_extraction_is_weak(self) -> None:
        result = generate_beats(
            {"concept": "Savings", "type": "definition", "weight_level": "low"},
            "Savings",
        )
        self.assertEqual(
            result,
            {"beats": [{"component": "ConceptCard", "text": "Savings"}]},
        )

    def test_medium_risk_uses_two_beats(self) -> None:
        result = generate_beats(
            {"concept": "Debt Trap", "type": "risk", "weight_level": "medium"},
            "Paying minimum dues creates a debt trap",
        )
        self.assertEqual(
            result,
            {
                "beats": [
                    {"component": "StatCard", "text": "Minimum dues"},
                    {"component": "RiskCard", "text": "Debt Trap"},
                ]
            },
        )

    def test_duplicate_beats_collapse_to_single_strong_beat(self) -> None:
        result = generate_beats(
            {"concept": "Savings", "type": "definition", "weight_level": "low"},
            "Savings",
        )
        self.assertEqual(result, {"beats": [{"component": "ConceptCard", "text": "Savings"}]})


if __name__ == "__main__":
    unittest.main()
