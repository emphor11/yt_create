import unittest

from youtube_ai_system.services.visual_logic_engine import map_concept_to_visual


class VisualLogicEngineTestCase(unittest.TestCase):
    def test_maps_risk_to_risk_card(self) -> None:
        self.assertEqual(
            map_concept_to_visual({"concept": "Debt Trap", "type": "risk"}),
            {
                "component": "RiskCard",
                "props": {"title": "DEBT TRAP"},
            },
        )

    def test_maps_comparison_to_split_comparison(self) -> None:
        self.assertEqual(
            map_concept_to_visual({"concept": "Equity vs Debt", "type": "comparison"}),
            {
                "component": "SplitComparison",
                "props": {
                    "left": {"label": "Equity"},
                    "right": {"label": "Debt"},
                },
            },
        )

    def test_maps_definition_to_concept_card(self) -> None:
        self.assertEqual(
            map_concept_to_visual({"concept": "Inflation", "type": "definition"}),
            {
                "component": "ConceptCard",
                "props": {"title": "INFLATION"},
            },
        )

    def test_maps_process_to_step_flow(self) -> None:
        self.assertEqual(
            map_concept_to_visual({"concept": "Money Flow", "type": "process"}),
            {
                "component": "StepFlow",
                "props": {"steps": ["Money Flow"]},
            },
        )

    def test_maps_cause_effect_to_flow_bar(self) -> None:
        self.assertEqual(
            map_concept_to_visual({"concept": "Inflation", "type": "cause_effect"}),
            {
                "component": "FlowBar",
                "props": {"start_label": "Inflation", "end_label": ""},
            },
        )

    def test_maps_growth_to_growth_chart(self) -> None:
        self.assertEqual(
            map_concept_to_visual({"concept": "Investment Growth", "type": "growth"}),
            {
                "component": "GrowthChart",
                "props": {"start": "", "end": "Investment Growth", "curve": "up"},
            },
        )

    def test_maps_before_after_to_before_after_split(self) -> None:
        self.assertEqual(
            map_concept_to_visual({"concept": "Budgeting Impact", "type": "before_after"}),
            {
                "component": "BeforeAfterSplit",
                "props": {"before": "", "after": "Budgeting Impact"},
            },
        )

    def test_maps_paradox_to_risk_card(self) -> None:
        self.assertEqual(
            map_concept_to_visual({"concept": "Rich but Broke", "type": "paradox"}),
            {
                "component": "RiskCard",
                "props": {"title": "RICH BUT BROKE"},
            },
        )


if __name__ == "__main__":
    unittest.main()
