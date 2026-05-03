import unittest

from youtube_ai_system.services.story_pipeline import StoryPipeline
from youtube_ai_system.services.visual_story_engine import VisualStoryEngine


class VisualStoryEngineTestCase(unittest.TestCase):
    def test_visual_story_engine_adds_story_world_and_section_states(self) -> None:
        story_plan = {
            "hook": "Why does your ₹50,000 salary feel gone by day 20?",
            "sections": [
                {"text": "Your ₹50,000 salary lands and feels powerful.", "concept_type": "salary_drain"},
                {"text": "Then ₹18,000 goes to EMI and rent follows.", "concept_type": "emi_pressure"},
                {"text": "Inflation makes the same balance buy less.", "concept_type": "inflation_erosion"},
                {"text": "A ₹5,000 SIP starts building a system.", "concept_type": "sip_growth"},
                {"text": "Diversification spreads risk across assets.", "concept_type": "diversification"},
            ],
        }

        result = VisualStoryEngine().attach_visual_story(story_plan)

        self.assertEqual(result["visual_story"]["protagonist"]["role"], "young_salaried_professional")
        self.assertEqual(result["visual_story"]["protagonist"]["visual_id"], "protagonist_01")
        self.assertIn("phone_account", result["visual_story"]["recurring_objects"])
        self.assertIn("emi_stack", result["visual_story"]["recurring_objects"])
        self.assertIn("inflation_basket", result["visual_story"]["recurring_objects"])
        self.assertIn("sip_jar", result["visual_story"]["recurring_objects"])
        self.assertIn("portfolio_grid", result["visual_story"]["recurring_objects"])
        self.assertTrue(all(section.get("story_state") for section in result["sections"]))

    def test_story_pipeline_threads_story_state_into_directed_visuals(self) -> None:
        payload = {
            "hook": {"narration": "Why does your ₹50,000 salary feel gone by day 20?"},
            "scenes": [
                {
                    "narration": (
                        "Your ₹50,000 salary lands and feels powerful for one day. "
                        "Then ₹18,000 goes to EMI. ₹12,000 goes to rent. "
                        "By day 20, only ₹6,000 is still breathing."
                    )
                },
                {
                    "narration": (
                        "A ₹5,000 SIP looks boring in the first month. "
                        "After 20 years, compounding does most of the work."
                    )
                },
            ],
            "outro": {"narration": "Track the leak before the month tracks you."},
        }

        result = StoryPipeline().build_story_plan(payload)
        sections = result["sections"]

        self.assertIn("visual_story", result)
        self.assertTrue(all("story_state" in section for section in sections))
        salary_section = next(section for section in sections if section.get("concept_type") == "salary_drain")
        visual = salary_section["visual_plan"][0]["visual"]
        self.assertIn("phone_account", salary_section["story_state"]["active_objects"])
        self.assertIn("salary_balance", salary_section["story_state"]["active_objects"])
        self.assertEqual(visual["data"]["story_state"]["visual_question"], "Where did the salary go?")
        self.assertEqual(visual["cinematic_intent"]["active_object"], "phone_account")

    def test_story_states_follow_progression(self) -> None:
        story_plan = {
            "sections": [
                {"text": "Salary lands.", "concept_type": "salary_drain"},
                {"text": "EMIs stack up.", "concept_type": "emi_pressure"},
                {"text": "Inflation erodes value.", "concept_type": "inflation_erosion"},
                {"text": "SIP creates discipline.", "concept_type": "sip_growth"},
            ],
        }

        result = VisualStoryEngine().attach_visual_story(story_plan)
        roles = [section["story_state"]["scene_role"] for section in result["sections"]]

        self.assertEqual(roles[0], "setup")
        self.assertIn("pressure", roles)
        self.assertIn("mechanism", roles)
        self.assertEqual(roles[-1], "resolution")

    def test_portfolio_story_answer_uses_portfolio_object_even_when_concept_is_risk_return(self) -> None:
        story_plan = {
            "sections": [
                {"text": "Risk and return matter.", "concept_type": "risk_return"},
                {"text": "Diversification spreads risk across assets. One fragile bet becomes a portfolio system.", "concept_type": "risk_return"},
            ],
        }

        result = VisualStoryEngine().attach_visual_story(story_plan)
        portfolio_section = result["sections"][1]

        self.assertIn("portfolio_grid", portfolio_section["story_state"]["active_objects"])
        self.assertEqual(
            portfolio_section["story_state"]["visual_answer"],
            "one fragile bet becomes a spread portfolio",
        )


if __name__ == "__main__":
    unittest.main()
