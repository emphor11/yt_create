import unittest

from youtube_ai_system.services.finance_concept_extractor import FinanceConceptExtractor
from youtube_ai_system.services.semantic_scene_contract import SemanticSceneContractExtractor
from youtube_ai_system.services.story_pipeline import StoryPipeline
from youtube_ai_system.services.visual_action_graph import VisualActionGraphBuilder


class VisualActionGraphTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.finance = FinanceConceptExtractor()
        self.semantic = SemanticSceneContractExtractor()
        self.builder = VisualActionGraphBuilder()

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

    def test_salary_drain_graph_turns_relationships_into_visual_actions(self) -> None:
        contract = self.contract_for(
            "Your ₹50,000 salary lands. Then ₹18,000 goes to EMI. ₹12,000 goes to rent. Only ₹6,000 is left.",
            dominant_entity="salary",
            idea_type="risk",
        )

        graph = self.builder.build_dict(contract)
        actions = graph["actions"]

        self.assertEqual(graph["source"], "visual_action_graph_v1")
        self.assertEqual(graph["primary_concept"]["key"], "salary_drain")
        self.assertIn("salary_arrives", [action["action"] for action in actions])
        self.assertEqual([action["action"] for action in actions].count("expense_drains"), 2)
        self.assertIn("balance_revealed", [action["action"] for action in actions])
        drain_actions = [action for action in actions if action["action"] == "expense_drains"]
        self.assertTrue(all(action["relationship_id"] for action in drain_actions))
        self.assertTrue(all(action["motion"] == "collision_drain" for action in drain_actions))
        self.assertEqual(len(graph["edges"]), len(actions) - 1)

    def test_sip_graph_exposes_action_level_growth_semantics(self) -> None:
        contract = self.contract_for(
            "A ₹5,000 SIP at 12% annual return over 20 years means you invest about ₹12 lakh from your pocket and it can become nearly ₹50 lakh.",
            dominant_entity="investment",
            idea_type="growth",
        )

        graph = self.builder.build_dict(contract)
        actions = {action["action"]: action for action in graph["actions"]}

        self.assertEqual(graph["primary_concept"]["key"], "sip_growth")
        self.assertIn("contribution_starts", actions)
        self.assertIn("contributions_accumulate", actions)
        self.assertIn("return_rate_activates", actions)
        self.assertIn("time_extends", actions)
        self.assertIn("corpus_revealed", actions)
        self.assertEqual(actions["contribution_starts"]["value"]["display_value"], "₹5,000")
        self.assertEqual(actions["corpus_revealed"]["value"]["display_value"], "₹50 lakh")
        self.assertEqual(actions["corpus_revealed"]["motion"], "compound_reveal")

    def test_story_pipeline_attaches_visual_action_graph_without_changing_visual_plan(self) -> None:
        section = {
            "text": "A ₹5,000 SIP at 12% annual return over 20 years can become nearly ₹50 lakh.",
            "dominant_entity": "investment",
            "idea_type": "growth",
            "has_numbers": True,
            "has_comparison": False,
            "has_causation": True,
            "visual_scene": {},
        }
        story_plan = {"hook": "", "agenda": [], "sections": [section]}

        story_plan = StoryPipeline().attach_section_concepts(story_plan)
        planned = StoryPipeline().attach_section_visual_plan(story_plan)
        planned_section = planned["sections"][0]

        self.assertEqual(planned_section["visual_action_graph"]["source"], "visual_action_graph_v1")
        self.assertTrue(planned_section["visual_action_graph"]["actions"])
        self.assertEqual(planned_section["visual_plan"][0]["visual"]["pattern"], "SIPGrowthEngine")
        self.assertNotIn("visual_action_graph", planned_section["visual_plan"][0]["visual"])

    def test_empty_semantic_contract_returns_warning_not_fallback_narration_parse(self) -> None:
        graph = self.builder.build_dict({"source": "semantic_scene_contract_v1", "scene_id": "empty", "primary_concept": {"key": "salary_drain"}})

        self.assertEqual(graph["actions"], [])
        self.assertEqual(graph["warnings"][0]["code"], "no_semantic_entities")


if __name__ == "__main__":
    unittest.main()
