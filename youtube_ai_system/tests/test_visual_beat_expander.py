import unittest

from youtube_ai_system.services.visual_beat_expander import VisualBeatExpander


class VisualBeatExpanderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.expander = VisualBeatExpander()

    def test_story_state_beats_do_not_leak_internal_object_names(self) -> None:
        section = {
            "text": (
                "FOMO investing feels like action. A stock runs up, everyone talks about it, and you enter late. "
                "Then the price falls and panic starts. Real investing starts with understanding what you own."
            ),
            "concept_type": "fomo_risk",
            "story_state": {
                "active_objects": ["portfolio_grid"],
                "callback_to": "sip_jar",
                "visual_question": "What happens when emotion becomes the strategy?",
                "visual_answer": "emotion stops pretending to be a strategy",
                "state_change": {
                    "money": {"from": "", "to": "", "change_label": "state changes"},
                },
            },
            "visual_plan": [
                {
                    "concept": {"concept": "FOMO Risk", "type": "fomo_risk"},
                    "visual": {"pattern": "SplitComparison", "data": {"accent": "orange"}},
                    "beats": {
                        "beats": [
                            {"component": "StatCard", "text": "FOMO trade"},
                            {"component": "SplitComparison", "text": "Emotion vs understanding"},
                            {"component": "HighlightText", "text": "Do not buy what you cannot explain"},
                        ]
                    },
                }
            ],
        }

        result = self.expander.expand_section(section)
        texts = [
            str(beat.get("text") or "").lower()
            for beat in result["visual_plan"][0]["beats"]["beats"]
        ]
        combined = " | ".join(texts)

        self.assertNotIn("portfolio grid", combined)
        self.assertNotIn("sip jar", combined)
        self.assertNotIn("state changes", combined)
        self.assertIn("risk gets distributed", combined)

    def test_debt_expansion_preserves_spiral_component(self) -> None:
        debt_data = {
            "principal": {"value": "₹1,00,000", "amount": 100000},
            "monthly_interest": 3333,
            "balances": [{"month": month, "balance": 100000 + month * 400, "interest": 3333, "principal_paid": -333} for month in range(1, 13)],
        }
        section = {
            "text": (
                "A ₹1,00,000 credit card balance does not look scary at first. "
                "The bank says the minimum payment is only ₹3,000. "
                "At 40% annual interest, the monthly interest itself is around ₹3,300. "
                "The payment feels responsible. The interest is still winning."
            ),
            "concept_type": "debt_trap",
            "story_state": {
                "active_objects": ["debt_pressure"],
                "visual_question": "Why does paying not reduce the balance?",
                "visual_answer": "₹3,000 payment cannot beat ₹3,333 interest",
                "state_change": {"money": {"from": "₹1,00,000", "to": "₹1,04,000", "change_label": "interest keeps winning"}},
            },
            "visual_plan": [
                {
                    "concept": {"concept": "Debt Trap", "type": "debt_trap"},
                    "visual": {"pattern": "DebtSpiralVisualizer", "data": debt_data},
                    "beats": {
                        "beats": [
                            {"component": "StatCard", "text": "₹1,00,000 outstanding"},
                            {"component": "CalculationStrip", "text": "Interest cost", "data": {"steps": [{"label": "Interest", "value": "₹3,333"}]}},
                            {"component": "DebtSpiralVisualizer", "text": "Debt trap closes", "data": debt_data},
                        ]
                    },
                }
            ],
        }

        result = self.expander.expand_section(section)
        beats = result["visual_plan"][0]["beats"]["beats"]
        components = [beat.get("component") for beat in beats]
        phases = [beat.get("beat_phase") for beat in beats if beat.get("component") == "DebtSpiralVisualizer"]

        self.assertIn("DebtSpiralVisualizer", components)
        self.assertIn("spiral", phases)
        self.assertTrue(all(component != "CalculationStrip" for component in components))


if __name__ == "__main__":
    unittest.main()
