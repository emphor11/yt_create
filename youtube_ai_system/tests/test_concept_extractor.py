import unittest

from youtube_ai_system.services.concept_extractor import extract, extract_all


class ConceptExtractorTestCase(unittest.TestCase):
    def test_extract_cause_effect_concept(self) -> None:
        result = extract("Inflation makes your savings lose value")
        self.assertEqual(result["concept"], "Inflation Loss")
        self.assertEqual(result["type"], "cause_effect")
        self.assertGreaterEqual(result["confidence"], 0.9)

    def test_extract_comparison_concept(self) -> None:
        result = extract("Equity is risky while debt is stable")
        self.assertEqual(result["concept"], "Equity vs Debt")
        self.assertEqual(result["type"], "comparison")
        self.assertGreaterEqual(result["confidence"], 0.9)

    def test_extract_risk_concept(self) -> None:
        result = extract("Paying minimum dues creates a debt trap")
        self.assertEqual(result["concept"], "Debt Trap")
        self.assertEqual(result["type"], "risk")
        self.assertGreaterEqual(result["confidence"], 0.9)

    def test_extract_consequence_based_interest_loss(self) -> None:
        result = extract("Banks make money from the interest cost you pay")
        self.assertEqual(result["concept"], "Interest Loss")
        self.assertEqual(result["type"], "risk")

    def test_extract_before_after_concept(self) -> None:
        result = extract("Budgeting works before and after income shocks")
        self.assertEqual(result["concept"], "Budgeting Impact")
        self.assertEqual(result["type"], "before_after")
        self.assertGreaterEqual(result["confidence"], 0.6)

    def test_extract_growth_concept(self) -> None:
        result = extract("If you invest monthly, your money grows over time")
        self.assertEqual(result["concept"], "Investment Growth")
        self.assertEqual(result["type"], "growth")
        self.assertGreaterEqual(result["confidence"], 0.9)

    def test_extract_unknown_for_low_confidence_sentence(self) -> None:
        result = extract("This helps you manage money better")
        self.assertIsNone(result["concept"])
        self.assertEqual(result["type"], "unknown")
        self.assertLess(result["confidence"], 0.6)

    def test_extract_rejects_generic_opening_phrase(self) -> None:
        result = extract("We've all been there with our credit cards")
        self.assertIsNone(result["concept"])
        self.assertEqual(result["type"], "unknown")

    def test_extract_minimum_payment_cycle_from_credit_card_sentence(self) -> None:
        result = extract("When you pay just the minimum on your credit card.")
        self.assertEqual(result["concept"], "Minimum Payment Cycle")
        self.assertEqual(result["type"], "definition")

    def test_extract_all_supports_two_concepts_max(self) -> None:
        result = extract_all("Inflation makes savings lose value and returns grow over time")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["concept"], "Inflation Loss")
        self.assertEqual(result[0]["type"], "cause_effect")
        self.assertEqual(result[1]["concept"], "Returns Growth")
        self.assertEqual(result[1]["type"], "growth")

    def test_growth_concepts_are_normalized(self) -> None:
        result = extract("Investment returns growth matters over time")
        self.assertEqual(result["concept"], "Investment Growth")
        self.assertEqual(result["type"], "growth")

    def test_risk_concepts_are_normalized(self) -> None:
        result = extract("Debt can destroy stability")
        self.assertEqual(result["concept"], "Debt Risk")
        self.assertEqual(result["type"], "risk")
        self.assertGreaterEqual(result["confidence"], 0.8)


if __name__ == "__main__":
    unittest.main()
