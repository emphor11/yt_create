import unittest

from youtube_ai_system.services.story_pipeline import StoryPipeline
from youtube_ai_system.services.visual_story_engine import VisualStoryEngine


def make_section(concept_type: str, text: str, visual_data: dict | None = None) -> dict:
    section = {
        "text": text,
        "concept_type": concept_type,
        "finance_concept": {
            "concept_type": concept_type,
            "concept_name": concept_type.replace("_", " ").title(),
            "start_value": None,
            "end_value": None,
            "confidence": 0.9,
        },
    }
    if visual_data is not None:
        section["visual_plan"] = [
            {
                "concept": {"concept": concept_type.replace("_", " ").title(), "type": concept_type},
                "visual": {"pattern": "GrowthChart", "data": visual_data},
                "beats": {"beats": [{"component": "GrowthChart", "text": "Value path", "data": visual_data}]},
            }
        ]
    return section


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
        self.assertIn("salary_balance", result["visual_story"]["recurring_objects"])
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

        self.assertEqual(roles[0], "pressure")
        self.assertIn("pressure", roles)
        self.assertIn("mechanism", roles)
        self.assertEqual(roles[-1], "solution")

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

    def test_single_scene_role_uses_concept_not_index(self) -> None:
        result = VisualStoryEngine().attach_visual_story(
            {"sections": [make_section("emi_pressure", "One EMI feels harmless. Then ₹18,000 leaves.")]}
        )
        state = result["sections"][0]["story_state"]

        self.assertEqual(state["scene_role"], "pressure")
        self.assertEqual(state["protagonist_state"], "stressed")

    def test_single_scene_sip_is_solution_not_setup(self) -> None:
        result = VisualStoryEngine().attach_visual_story(
            {"sections": [make_section("sip_growth", "₹5,000 monthly SIP compounds at 12% interest.")]}
        )
        state = result["sections"][0]["story_state"]

        self.assertEqual(state["scene_role"], "solution")
        self.assertEqual(state["active_objects"], ["sip_jar"])

    def test_compound_interest_does_not_activate_debt_pressure(self) -> None:
        result = VisualStoryEngine().attach_visual_story(
            {
                "sections": [
                    make_section(
                        "sip_growth",
                        "₹5,000 monthly investment compounds over time. At 12% interest, corpus grows.",
                    )
                ]
            }
        )
        state = result["sections"][0]["story_state"]

        self.assertIn("sip_jar", state["active_objects"])
        self.assertNotIn("debt_pressure", state["active_objects"])
        self.assertEqual(state["visual_question"], "What changes when returns start earning returns?")

    def test_fomo_scene_uses_portfolio_not_sip_or_debt(self) -> None:
        result = VisualStoryEngine().attach_visual_story(
            {
                "sections": [
                    make_section(
                        "fomo_risk",
                        "FOMO investing feels like action. You enter late, the price falls, and panic starts.",
                    )
                ]
            }
        )
        state = result["sections"][0]["story_state"]

        self.assertEqual(state["active_objects"], ["portfolio_grid"])
        self.assertNotIn("sip_jar", state["active_objects"])
        self.assertNotIn("debt_pressure", state["active_objects"])
        self.assertEqual(state["visual_question"], "What happens when emotion becomes the strategy?")
        self.assertEqual(state["visual_answer"], "emotion stops pretending to be a strategy")

    def test_inflation_story_state_uses_directed_end_value_not_percentage(self) -> None:
        section = make_section(
            "inflation_erosion",
            "₹1,00,000 sits idle while prices rise at 7%. After 10 years, buying power halves.",
            {"start": "₹1,00,000", "end": "₹50,835", "rate": "7% for 10 years", "curve": "down"},
        )
        result = VisualStoryEngine().attach_visual_story({"sections": [section]})
        section = result["sections"][0]
        VisualStoryEngine().enrich_section_from_visual_plan(section, result["visual_story"])
        state = section["story_state"]

        self.assertEqual(state["state_change"]["money"]["from"], "₹1,00,000")
        self.assertEqual(state["state_change"]["money"]["to"], "₹50,835")
        self.assertEqual(state["visual_question"], "Why does the same balance buy less?")
        self.assertEqual(state["visual_answer"], "₹1,00,000 today buys like ₹50,835")
        self.assertNotIn("%", state["state_change"]["money"]["to"])

    def test_emi_question_is_concept_specific(self) -> None:
        result = VisualStoryEngine().attach_visual_story(
            {"sections": [make_section("emi_pressure", "One EMI feels harmless. Then phone and bike EMIs stack. ₹18,000 leaves.")]}
        )
        state = result["sections"][0]["story_state"]

        self.assertEqual(state["visual_question"], "How do small EMIs become one big leak?")
        self.assertEqual(state["state_change"]["money"]["change_label"], "₹18,000 leaves before the month begins")

    def test_recurring_objects_are_frequency_based(self) -> None:
        result = VisualStoryEngine().attach_visual_story(
            {
                "sections": [
                    make_section("salary_drain", "Salary goes to EMI."),
                    make_section("emi_pressure", "EMI stack grows."),
                    make_section("sip_growth", "SIP compounds."),
                ]
            }
        )
        recurring = result["visual_story"]["recurring_objects"]

        self.assertIn("salary_balance", recurring)
        self.assertNotIn("sip_jar", recurring)


if __name__ == "__main__":
    unittest.main()
