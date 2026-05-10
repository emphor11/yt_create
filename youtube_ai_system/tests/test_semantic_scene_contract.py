import unittest

from youtube_ai_system.services.finance_concept_extractor import FinanceConceptExtractor
from youtube_ai_system.services.semantic_scene_contract import SemanticSceneContractExtractor


class SemanticSceneContractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.finance = FinanceConceptExtractor()
        self.semantic = SemanticSceneContractExtractor()

    def contract_for(self, text: str, dominant_entity: str = "money", idea_type: str = "risk") -> dict:
        finance_concept = self.finance.extract(
            {
                "combined_text": text,
                "dominant_entity": dominant_entity,
                "idea_type": idea_type,
            }
        )
        return self.semantic.extract_dict(
            {"text": text, "dominant_entity": dominant_entity, "idea_type": idea_type},
            {
                "concept_name": finance_concept.concept_name,
                "concept_type": finance_concept.concept_type,
                "primary_entity": finance_concept.primary_entity,
                "action": finance_concept.action,
                "start_value": finance_concept.start_value,
                "end_value": finance_concept.end_value,
                "percentage": finance_concept.percentage,
                "time_period": finance_concept.time_period,
                "agent": finance_concept.agent,
                "victim": finance_concept.victim,
                "confidence": finance_concept.confidence,
                "numeric_facts": finance_concept.numeric_facts or [],
                "concept_policy": finance_concept.concept_policy or {},
            },
            scene_id="test_scene",
        )

    def test_salary_drain_contract_has_entities_and_consumption_relationships(self) -> None:
        contract = self.contract_for(
            "Your ₹50,000 salary lands. Then ₹18,000 goes to EMI. ₹12,000 goes to rent. Only ₹6,000 is left.",
            dominant_entity="salary",
            idea_type="risk",
        )

        roles = {entity["role"] for entity in contract["entities"]}
        relationship_types = {relationship["type"] for relationship in contract["relationships"]}

        self.assertEqual(contract["primary_concept"]["key"], "salary_drain")
        self.assertIn("salary_income", roles)
        self.assertIn("emi_payment", roles)
        self.assertIn("rent_expense", roles)
        self.assertIn("remaining_balance", roles)
        self.assertIn("consumed_by", relationship_types)
        self.assertIn("leaves_remainder", relationship_types)

    def test_sip_contract_preserves_investment_semantics(self) -> None:
        contract = self.contract_for(
            "A ₹5,000 SIP at 12% annual return over 20 years means you invest about ₹12 lakh from your pocket and it can become nearly ₹50 lakh.",
            dominant_entity="investment",
            idea_type="growth",
        )

        roles = {entity["role"] for entity in contract["entities"]}
        relationship_types = {relationship["type"] for relationship in contract["relationships"]}

        self.assertEqual(contract["primary_concept"]["key"], "sip_growth")
        self.assertIn("monthly_sip", roles)
        self.assertIn("annual_return_rate", roles)
        self.assertIn("time_period", roles)
        self.assertIn("total_contribution", roles)
        self.assertIn("target_corpus", roles)
        self.assertIn("compounds_to", relationship_types)


if __name__ == "__main__":
    unittest.main()
