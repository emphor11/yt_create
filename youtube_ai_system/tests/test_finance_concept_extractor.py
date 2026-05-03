import unittest

from youtube_ai_system.services.finance_concept_extractor import FinanceConceptExtractor


class FinanceConceptExtractorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.extractor = FinanceConceptExtractor()

    def test_maps_lifestyle_inflation_with_structure(self) -> None:
        result = self.extractor.extract(
            {
                "combined_text": "As soon as we get a raise, we upgrade our lifestyle and spending rises faster than savings.",
                "dominant_entity": "salary",
                "idea_type": "risk",
            }
        )
        self.assertEqual(result.concept_name, "Lifestyle Inflation")
        self.assertEqual(result.concept_type, "risk")
        self.assertEqual(result.primary_entity, "salary")
        self.assertGreaterEqual(result.confidence, 0.9)

    def test_maps_debt_trap_with_numeric_context(self) -> None:
        result = self.extractor.extract(
            {
                "combined_text": "Credit card debt grows fast when minimum payments only cover interest on a ₹50,000 balance.",
                "dominant_entity": "debt",
                "idea_type": "risk",
            }
        )
        self.assertEqual(result.concept_name, "Debt Trap")
        self.assertEqual(result.concept_type, "risk")
        self.assertEqual(result.start_value, "₹50,000")

    def test_maps_emi_pressure_before_generic_debt(self) -> None:
        result = self.extractor.extract(
            {
                "combined_text": (
                    "One EMI feels harmless. Then a phone EMI joins it. Then a bike EMI joins it. "
                    "Suddenly ₹18,000 leaves before the month begins."
                ),
                "dominant_entity": "emi",
                "idea_type": "risk",
            }
        )

        self.assertEqual(result.concept_name, "EMI Pressure")
        self.assertEqual(result.concept_type, "risk")

    def test_maps_sip_growth_before_generic_compounding(self) -> None:
        result = self.extractor.extract(
            {
                "combined_text": "A ₹5,000 SIP compounds at 12% for 20 years and creates a larger corpus.",
                "dominant_entity": "investment",
                "idea_type": "growth",
            }
        )

        self.assertEqual(result.concept_name, "SIP Growth")
        self.assertEqual(result.concept_type, "growth")

    def test_maps_expense_leakage(self) -> None:
        result = self.extractor.extract(
            {
                "combined_text": "Subscriptions and unnecessary spending quietly leak money every month.",
                "dominant_entity": "expense",
                "idea_type": "risk",
            }
        )
        self.assertEqual(result.concept_name, "Expense Leakage")
        self.assertEqual(result.concept_type, "risk")

    def test_maps_emergency_fund(self) -> None:
        result = self.extractor.extract(
            {
                "combined_text": "Without an emergency fund, one medical surprise can push you into debt.",
                "dominant_entity": "savings",
                "idea_type": "risk",
            }
        )
        self.assertEqual(result.concept_name, "Emergency Fund")
        self.assertEqual(result.concept_type, "definition")

    def test_numeric_pattern_extracts_structured_fallback(self) -> None:
        result = self.extractor.extract(
            {
                "combined_text": "A ₹6 lakh salary can become ₹60,000 lost every year.",
                "dominant_entity": "salary",
                "idea_type": "risk",
            }
        )
        self.assertIsNotNone(result.start_value)
        self.assertIsNotNone(result.end_value)
        self.assertGreaterEqual(result.confidence, 0.6)


if __name__ == "__main__":
    unittest.main()
