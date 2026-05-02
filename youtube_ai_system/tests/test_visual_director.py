import unittest

from youtube_ai_system.services.visual_director import VisualDirector, VisualDirectorInput
from youtube_ai_system.services.story_pipeline import StoryPipeline


def build_input(narration: str, concept_type: str = "definition", percentage: float | None = None, time_period: str | None = None) -> VisualDirectorInput:
    return VisualDirectorInput(
        concept_type=concept_type,
        concept_name=concept_type.replace("_", " ").title(),
        primary_entity="money",
        action="changes",
        start_value=None,
        end_value=None,
        percentage=percentage,
        time_period=time_period,
        confidence=0.9,
        narration_text=narration,
        idea_type="emphasis",
        has_numbers=True,
        section_position="middle",
        preceding_concept_type=None,
    )


class VisualDirectorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.director = VisualDirector()

    def test_money_flow_diagram_data_correctness(self) -> None:
        narration = (
            "My ₹50,000 salary disappears every month. EMI takes ₹18,000, rent takes ₹12,000, "
            "food takes ₹8,000, and only ₹3,000 is left by day 10."
        )
        result = self.director.direct(build_input(narration, "salary_drain"))

        self.assertEqual(result.pattern, "MoneyFlowDiagram")
        flow_beat = next(beat for beat in result.beats if beat.component == "MoneyFlowDiagram")
        data = flow_beat.data or {}

        self.assertEqual(data["source"]["amount"], 50000)
        flow_total = sum(flow["amount"] for flow in data["flows"])
        self.assertLess(abs(flow_total + data["remainder"]["amount"] - data["source"]["amount"]), 100)
        self.assertEqual(data["remainder"]["amount"], 3000)
        self.assertTrue(data["remainder"]["is_dangerous"])
        self.assertEqual(data["flows"][0]["label"], "EMI")
        self.assertEqual(data["flows"][0]["amount"], 18000)

    def test_debt_spiral_math_correctness(self) -> None:
        narration = "Credit card balance ₹1,00,000 at 40% interest. Minimum payment ₹3,000."
        result = self.director.direct(build_input(narration, "debt_trap", percentage=40.0))

        self.assertEqual(result.pattern, "DebtSpiralVisualizer")
        spiral_beat = next(beat for beat in result.beats if beat.component == "DebtSpiralVisualizer")
        data = spiral_beat.data or {}

        monthly_interest = 100000 * (0.40 / 12)
        self.assertAlmostEqual(data["monthly_interest"], monthly_interest, delta=10)
        self.assertTrue(data["is_trap"])
        self.assertGreater(data["month_12_balance"], 100000)

    def test_sip_growth_awe_ratio(self) -> None:
        narration = "Invest ₹5,000 per month in SIP at 12% returns for 20 years."
        result = self.director.direct(build_input(narration, "sip_growth", percentage=12.0, time_period="20 years"))

        self.assertEqual(result.pattern, "SIPGrowthEngine")
        sip_beat = next(beat for beat in result.beats if beat.component == "SIPGrowthEngine")
        data = sip_beat.data or {}

        expected_invested = 5000 * 12 * 20
        expected_corpus = 4994839
        self.assertAlmostEqual(data["total_invested"], expected_invested, delta=expected_invested * 0.01)
        self.assertAlmostEqual(data["final_corpus"], expected_corpus, delta=expected_corpus * 0.05)
        self.assertGreater(data["final_corpus"] / data["total_invested"], 4.0)

    def test_sip_growth_rate_floor_prevents_zero_rate_visual(self) -> None:
        narration = "Invest ₹5,000 per month in SIP at 0% returns for 20 years."
        result = self.director.direct(build_input(narration, "sip_growth", percentage=0.0, time_period="20 years"))

        sip_beat = next(beat for beat in result.beats if beat.component == "SIPGrowthEngine")
        data = sip_beat.data or {}

        self.assertEqual(data["annual_return_rate"], 1.0)
        self.assertGreater(data["final_corpus"], data["total_invested"])

    def test_money_mentions_excludes_age_and_time_units(self) -> None:
        narration = "I am 28 years old and I watched 20 minutes before I invest ₹5,000 per month in SIP."
        mentions = self.director._money_mentions(narration)

        self.assertEqual([mention["amount"] for mention in mentions], [5000])

    def test_directed_beats_use_data_without_duplicate_props(self) -> None:
        debt = self.director.direct(build_input("Credit card balance ₹1,00,000 at 40% interest. Minimum payment ₹3,000.", "debt_trap", percentage=40.0))
        calculation = next(beat for beat in debt.beats if beat.component == "CalculationStrip")
        sip = self.director.direct(build_input("Invest ₹5,000 per month in SIP at 12% returns for 20 years.", "sip_growth", percentage=12.0, time_period="20 years"))
        comparison = next(beat for beat in sip.beats if beat.component == "SplitComparison")

        self.assertIsNotNone(calculation.data)
        self.assertIsNone(calculation.props)
        self.assertIsNotNone(comparison.data)
        self.assertIsNone(comparison.props)

    def test_director_falls_back_when_directed_data_is_missing(self) -> None:
        result = self.director.direct(build_input("Debt can feel stressful without a payoff plan.", "debt_trap"))

        self.assertTrue(result.is_valid())
        self.assertNotEqual(result.pattern, "DebtSpiralVisualizer")
        self.assertEqual(result.pattern, "FlowDiagram")
        self.assertIsNone(result.fallback_reason)
        self.assertIn("Interest starts", [node["label"] for node in result.data["nodes"]])

    def test_director_does_not_invent_money_flow_numbers_for_generic_lifestyle(self) -> None:
        result = self.director.direct(build_input("You earn well. You spend well. Saving is a myth. Lifestyle inflation is real.", "lifestyle_inflation"))

        self.assertEqual(result.pattern, "FlowDiagram")
        self.assertNotIn("₹", str(result.data))
        self.assertEqual(result.data["nodes"][-1]["label"], "Savings stay stuck")

    def test_generic_inflation_visual_stays_qualitative_without_numbers(self) -> None:
        result = self.director.direct(build_input("Inflation is a slow poison. It eats into your savings. Without you even noticing.", "inflation_erosion"))

        self.assertEqual(result.pattern, "GrowthChart")
        self.assertNotIn("₹", str(result.data))
        self.assertEqual(result.data["start"], "Savings")

    def test_directed_beats_carry_sentence_metadata_for_sync(self) -> None:
        result = self.director.direct(
            build_input(
                "My ₹50,000 salary disappears every month. EMI takes ₹18,000. Only ₹3,000 is left by day 10.",
                "salary_drain",
            )
        )

        beat_payloads = [beat.to_dict() for beat in result.beats]
        self.assertTrue(all("source_text" in beat for beat in beat_payloads))
        self.assertEqual(beat_payloads[0]["sentence_index"], 0)
        self.assertEqual(beat_payloads[-1]["sentence_index"], 2)

    def test_story_pipeline_prefers_valid_directed_plan(self) -> None:
        section = {
            "text": (
                "My ₹50,000 salary disappears every month. EMI takes ₹18,000, rent takes ₹12,000, "
                "food takes ₹8,000, and only ₹3,000 is left by day 10."
            ),
            "dominant_entity": "money",
            "idea_type": "risk",
            "has_numbers": True,
            "has_comparison": False,
            "has_causation": False,
            "finance_concept": {
                "concept_name": "Salary Depletion",
                "concept_type": "risk",
                "primary_entity": "salary",
                "action": "drains",
                "start_value": "₹50,000",
                "end_value": "₹3,000",
                "percentage": None,
                "time_period": None,
                "confidence": 0.9,
            },
            "concepts": [{"concept": "Salary Depletion", "type": "risk"}],
            "narrative_arc": {},
        }

        result = StoryPipeline().attach_section_visual_plan({"sections": [section]})
        directed_section = result["sections"][0]
        visual = directed_section["visual_plan"][0]["visual"]

        self.assertEqual(directed_section["concept_type"], "salary_drain")
        self.assertEqual(directed_section["direction"]["emotional_arc"]["closing"], "anxiety")
        self.assertEqual(visual["pattern"], "MoneyFlowDiagram")
        self.assertEqual(visual["data"]["remainder"]["amount"], 3000)

    def test_major_finance_concepts_do_not_fall_back_to_concept_card(self) -> None:
        cases = [
            ("Lifestyle inflation is a silent killer. As salary increases, expenses rise on luxuries, not necessities.", "lifestyle_inflation", "FlowDiagram"),
            ("Inflation quietly erodes your purchasing power over 10 years.", "inflation_erosion", "GrowthChart"),
            ("Expense leakage from subscriptions and food apps eats your salary.", "expense_leakage", "FlowDiagram"),
            ("Emergency fund protects you when a medical bill hits.", "emergency_fund", "FlowDiagram"),
            ("Diversification spreads your investments across asset classes.", "diversification", "SplitComparison"),
            ("Risk and return move together in investing.", "risk_return", "SplitComparison"),
            ("Tax saving under 80C can reduce your tax bill.", "tax_saving", "SplitComparison"),
            ("FOMO investing is not investing. It is speculation. Do not put your life savings into something you don't understand.", "definition", "SplitComparison"),
        ]

        for narration, concept_type, expected_pattern in cases:
            with self.subTest(concept_type=concept_type):
                result = self.director.direct(build_input(narration, concept_type))
                self.assertEqual(result.pattern, expected_pattern)
                self.assertIsNone(result.fallback_reason)
                self.assertNotIn(result.pattern, {"ConceptCard", "StatCard"})

    def test_story_pipeline_uses_old_plan_when_director_returns_generic_fallback(self) -> None:
        section = {
            "text": "This is a simple money habit with no specific visual mechanism.",
            "dominant_entity": "money",
            "idea_type": "definition",
            "has_numbers": False,
            "has_comparison": False,
            "has_causation": False,
            "finance_concept": {
                "concept_name": "Unknown",
                "concept_type": "definition",
                "primary_entity": "money",
                "action": "noted",
                "start_value": None,
                "end_value": None,
                "percentage": None,
                "time_period": None,
                "confidence": 0.1,
            },
            "concepts": [{"concept": "Money Habit", "type": "definition"}],
            "narrative_arc": {},
        }

        result = StoryPipeline().attach_section_visual_plan({"sections": [section]})
        visual = result["sections"][0]["visual_plan"][0]["visual"]

        self.assertEqual(visual["pattern"], "ConceptCard")
        self.assertIsNone(result["sections"][0]["direction"])


if __name__ == "__main__":
    unittest.main()
