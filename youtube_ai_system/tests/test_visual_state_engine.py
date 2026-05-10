import unittest

from youtube_ai_system.services.visual_state_engine import VisualStateEngine


class VisualStateEngineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = VisualStateEngine()

    def test_salary_drain_creates_pressure_evolution_states(self) -> None:
        beats = [
            self._beat("₹50,000 Salary lands", 0.0, 1.0, "salary_arrives", "salary_income", "credit_in", "establish_source", "salary_drain"),
            self._beat("₹18,000 EMI", 1.0, 1.8, "expense_drains", "emi_payment", "collision_drain", "show_outflow", "overlapping_outflows"),
            self._beat("₹12,000 rent", 1.8, 2.7, "expense_drains", "rent_expense", "collision_drain", "show_outflow", "overlapping_outflows"),
            self._beat("₹6,000 left", 2.7, 4.0, "balance_revealed", "remaining_balance", "reveal_survivor", "show_consequence", "salary_drain"),
        ]

        sequence = self.engine.build_sequence(beats)

        self.assertIsNotNone(sequence)
        states = sequence["states"]
        self.assertEqual([state["state_type"] for state in states], ["centered_focus", "pressure_cluster", "isolate_survivor"])
        self.assertEqual(states[0]["focus_entity"], "salary_income")
        self.assertEqual(states[1]["focus_entity"], "expense_group")
        self.assertEqual(states[2]["focus_entity"], "remaining_balance")
        self.assertEqual(states[1]["frame_window"], {"start_frame": 30, "end_frame": 81})
        self.assertEqual(states[1]["derived_from_action"], "expense_drains")

    def test_sip_growth_creates_growth_state_progression(self) -> None:
        beats = [
            self._beat("₹5,000 monthly SIP", 0.0, 1.2, "contribution_starts", "monthly_sip", "repeat_deposit", "establish_contribution", "sip_growth"),
            self._beat("12% return activates", 1.2, 2.4, "return_rate_activates", "annual_return_rate", "growth_curve_pull", "show_growth_force", "compound_growth"),
            self._beat("20 years time expands", 2.4, 3.3, "time_extends", "time_period", "timeline_expand", "show_duration", "compound_growth"),
            self._beat("₹12 lakh invested", 3.3, 4.4, "contributions_accumulate", "total_contribution", "stacking_accumulation", "show_principal_base", "compound_growth"),
            self._beat("₹50 lakh corpus reveal", 4.4, 6.0, "corpus_revealed", "target_corpus", "compound_reveal", "show_growth_result", "compound_growth"),
        ]

        sequence = self.engine.build_sequence(beats)

        self.assertIsNotNone(sequence)
        states = sequence["states"]
        self.assertEqual([state["state_type"] for state in states], ["optimistic_seed", "growth_acceleration", "layered_growth", "awe_reveal"])
        self.assertEqual(states[1]["frame_window"], {"start_frame": 36, "end_frame": 99})
        self.assertEqual(states[-1]["emotional_posture"], "awe")
        self.assertEqual(states[-1]["transition_behavior"], "slow_reveal")

    def test_existing_scenes_without_action_metadata_preserve_old_behavior(self) -> None:
        beats = [
            {"component": "StatCard", "text": "Simple idea", "start_time": 0.0, "end_time": 2.0},
            {"component": "ConceptCard", "text": "Result", "start_time": 2.0, "end_time": 4.0},
        ]

        sequence = self.engine.build_sequence(beats)
        attached = self.engine.attach_to_beats(beats, sequence)

        self.assertIsNone(sequence)
        self.assertEqual(attached, beats)
        self.assertTrue(all("visual_state" not in beat for beat in attached))

    def test_visual_states_preserve_timed_frame_windows(self) -> None:
        beats = [
            self._beat("₹50,000 Salary lands", 0.25, 1.5, "salary_arrives", "salary_income", "credit_in", "establish_source", "salary_drain"),
            self._beat("₹6,000 left", 1.5, 3.75, "balance_revealed", "remaining_balance", "reveal_survivor", "show_consequence", "salary_drain"),
        ]

        sequence = self.engine.build_sequence(beats)

        self.assertEqual(sequence["states"][0]["frame_window"], {"start_frame": 8, "end_frame": 45})
        self.assertEqual(sequence["states"][1]["frame_window"], {"start_frame": 45, "end_frame": 112})

    def test_overlap_groups_propagate_to_states_and_attached_beats(self) -> None:
        beats = [
            self._beat("₹18,000 EMI", 0.0, 1.0, "expense_drains", "emi_payment", "collision_drain", "show_outflow", "overlapping_outflows"),
            self._beat("₹12,000 rent", 1.0, 2.0, "expense_drains", "rent_expense", "collision_drain", "show_outflow", "overlapping_outflows"),
        ]

        sequence = self.engine.build_sequence(beats)
        attached = self.engine.attach_to_beats(beats, sequence)

        self.assertEqual(sequence["states"][0]["overlap_group"], "overlapping_outflows")
        self.assertEqual(attached[0]["visual_state"]["overlap_group"], "overlapping_outflows")
        self.assertEqual(attached[1]["data"]["visual_state"]["state_type"], "pressure_cluster")

    def _beat(
        self,
        text: str,
        start_time: float,
        end_time: float,
        action: str,
        semantic_role: str,
        motion: str,
        intent: str,
        overlap_group: str,
    ) -> dict:
        return {
            "component": "MoneyFlowDiagram",
            "text": text,
            "start_time": start_time,
            "end_time": end_time,
            "data": {
                "active_action": {
                    "id": f"act:{action}:{semantic_role}",
                    "action": action,
                    "semantic_role": semantic_role,
                    "motion": motion,
                    "intent": intent,
                    "sequence_index": 0,
                },
                "action_choreography": {"overlap_group": overlap_group},
            },
            "semantic_timing": {
                "overlap_group": overlap_group,
                "relative_window": {"start_frame": 0, "end_frame": 30},
            },
        }


if __name__ == "__main__":
    unittest.main()
