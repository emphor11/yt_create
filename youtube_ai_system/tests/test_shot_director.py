import unittest

from youtube_ai_system.services.shot_director import ShotDirector


class ShotDirectorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.director = ShotDirector()

    def test_money_flow_states_create_context_pressure_and_survivor_shots(self) -> None:
        beats = [
            self._beat("MoneyFlowDiagram", 0.0, 1.0, "salary_arrives", "centered_focus", "salary_income"),
            self._beat("MoneyFlowDiagram", 1.0, 2.0, "expense_drains", "pressure_cluster", "expense_group"),
            self._beat("MoneyFlowDiagram", 2.0, 4.0, "balance_revealed", "isolate_survivor", "remaining_balance"),
        ]

        sequence = self.director.build_sequence(beats)

        self.assertIsNotNone(sequence)
        self.assertEqual(
            [shot["shot_type"] for shot in sequence["shots"]],
            ["wide_context", "pressure_closeup", "survivor_isolation"],
        )
        self.assertEqual(sequence["shots"][1]["focus_target"], "expense_group")
        self.assertEqual(sequence["shots"][2]["framing_profile"], "isolated_hold")

    def test_sip_growth_states_create_momentum_and_reward_shots(self) -> None:
        beats = [
            self._beat("SIPGrowthEngine", 0.0, 1.0, "contribution_starts", "optimistic_seed", "monthly_sip"),
            self._beat("SIPGrowthEngine", 1.0, 2.0, "return_rate_activates", "growth_acceleration", "corpus_growth"),
            self._beat("SIPGrowthEngine", 2.0, 3.0, "contributions_accumulate", "layered_growth", "compounding_layers"),
            self._beat("SIPGrowthEngine", 3.0, 5.0, "corpus_revealed", "awe_reveal", "final_corpus"),
        ]

        sequence = self.director.build_sequence(beats)

        self.assertEqual(
            [shot["shot_type"] for shot in sequence["shots"]],
            ["wide_context", "upward_momentum", "focused_growth", "reward_hero"],
        )
        self.assertEqual(sequence["shots"][-1]["attention_weight"], 0.98)

    def test_non_finance_components_receive_generic_shots(self) -> None:
        beats = [
            {
                "component": "ConceptCard",
                "text": "Simple idea",
                "start_time": 0.0,
                "end_time": 2.0,
                "emphasis": "hero",
            }
        ]

        sequence = self.director.build_sequence(beats)
        attached = self.director.attach_to_beats(beats, sequence)

        self.assertIsNotNone(sequence)
        self.assertEqual(sequence["shots"][0]["shot_type"], "emotional_pause")
        self.assertEqual(sequence["shots"][0]["focus_target"], "active_beat")
        self.assertEqual(attached[0]["active_shot"]["shot_type"], "emotional_pause")
        self.assertNotIn("data", attached[0])

    def test_all_renderer_component_families_receive_shots(self) -> None:
        components = [
            "StatCard",
            "ConceptCard",
            "RiskCard",
            "CalculationStrip",
            "FlowDiagram",
            "BalanceBar",
            "SplitComparison",
            "StepFlow",
            "GrowthChart",
            "DebtSpiralVisualizer",
            "InflationErosionVisualizer",
            "LifestyleCreepVisualizer",
            "EMIStackVisualizer",
            "FOMOPriceCrashVisualizer",
            "PortfolioDiversificationVisualizer",
            "SmallLeaksAccumulator",
            "CinematicScene",
        ]
        beats = [
            {
                "component": component,
                "text": component,
                "start_time": float(index),
                "end_time": float(index + 1),
            }
            for index, component in enumerate(components)
        ]

        sequence = self.director.build_sequence(beats)
        attached = self.director.attach_to_beats(beats, sequence)

        self.assertEqual(sequence["shot_count"], len(components))
        self.assertTrue(all(shot["shot_type"] for shot in sequence["shots"]))
        self.assertTrue(all(beat.get("active_shot", {}).get("shot_type") for beat in attached))

    def test_shots_preserve_frame_windows(self) -> None:
        beats = [
            self._beat("SIPGrowthEngine", 0.25, 3.75, "corpus_revealed", "awe_reveal", "final_corpus"),
        ]

        sequence = self.director.build_sequence(beats)

        self.assertEqual(sequence["shots"][0]["start_frame"], 8)
        self.assertEqual(sequence["shots"][0]["end_frame"], 112)
        self.assertEqual(sequence["shots"][0]["composition_window"], {"start_frame": 8, "end_frame": 112})

    def test_attach_to_beats_propagates_active_shot(self) -> None:
        beats = [
            self._beat("MoneyFlowDiagram", 0.0, 1.0, "expense_drains", "pressure_cluster", "expense_group"),
        ]

        sequence = self.director.build_sequence(beats)
        attached = self.director.attach_to_beats(beats, sequence)

        self.assertEqual(attached[0]["active_shot"]["shot_type"], "pressure_closeup")
        self.assertEqual(attached[0]["data"]["active_shot"]["focus_target"], "expense_group")

    def _beat(
        self,
        component: str,
        start_time: float,
        end_time: float,
        action: str,
        state_type: str,
        focus_entity: str,
    ) -> dict:
        return {
            "component": component,
            "text": action,
            "start_time": start_time,
            "end_time": end_time,
            "data": {
                "active_action": {
                    "id": f"act:{action}:{focus_entity}",
                    "action": action,
                    "semantic_role": focus_entity,
                    "sequence_index": 0,
                }
            },
            "visual_state": {
                "state_type": state_type,
                "focus_entity": focus_entity,
                "overlap_group": "test_group",
            },
        }


if __name__ == "__main__":
    unittest.main()
