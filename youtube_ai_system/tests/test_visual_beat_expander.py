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


if __name__ == "__main__":
    unittest.main()
