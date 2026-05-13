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

    def test_risk_return_mechanism_uses_risk_return_visualizer_even_from_split_plan(self) -> None:
        section = {
            "text": (
                "Risk and return are connected. An FD may offer around 6% and feel calm. "
                "Equity can offer higher long-term growth. The price is volatility. "
                "Choose risk you can stay with."
            ),
            "concept_type": "risk_return",
            "visual_plan": [
                {
                    "concept": {"concept": "Risk vs Return", "type": "comparison"},
                    "visual": {"pattern": "SplitComparison", "data": {"mechanism": "risk_return"}},
                    "beats": {
                        "beats": [
                            {"component": "StatCard", "text": "FD feels calm"},
                            {"component": "SplitComparison", "text": "Risk vs Return"},
                            {"component": "HighlightText", "text": "Choose risk deliberately"},
                        ]
                    },
                }
            ],
        }

        result = self.expander.expand_section(section)
        beats = result["visual_plan"][0]["beats"]["beats"]

        self.assertTrue(any(beat.get("component") == "RiskReturnVisualizer" for beat in beats))
        self.assertFalse(any(beat.get("component") == "SplitComparison" for beat in beats))

    def test_phase_based_primary_mechanism_is_not_expanded_into_repeated_loops(self) -> None:
        flow_data = {
            "source": {"label": "Salary", "value": "₹50,000", "amount": 50000},
            "flows": [{"label": "Rent", "value": "₹15,000", "amount": 15000, "color": "red", "order": 1}],
            "remainder": {"value": "₹35,000", "amount": 35000, "is_dangerous": False},
        }
        section = {
            "text": (
                "You earn ₹50,000. Rent starts. EMI starts. Groceries start. "
                "The money path becomes visible. Savings shrink slowly. Salary drain becomes clear."
            ),
            "concept_type": "salary_drain",
            "story_state": {"active_objects": ["phone_account"]},
            "visual_plan": [
                {
                    "concept": {"concept": "Salary Drain", "type": "salary_drain"},
                    "visual": {"pattern": "MoneyFlowDiagram", "data": flow_data},
                    "beats": {
                        "beats": [
                            {"component": "MoneyFlowDiagram", "text": "₹50,000", "beat_phase": "intro", "data": {**flow_data, "active_phase": "intro"}},
                            {"component": "MoneyFlowDiagram", "text": "Where salary goes", "beat_phase": "drain", "data": {**flow_data, "active_phase": "drain"}},
                            {"component": "MoneyFlowDiagram", "text": "₹35,000 left", "beat_phase": "remainder", "data": {**flow_data, "active_phase": "remainder"}},
                        ]
                    },
                }
            ],
        }

        result = self.expander.expand_section(section)
        beats = result["visual_plan"][0]["beats"]["beats"]

        self.assertEqual(len(beats), 3)
        self.assertEqual([beat["beat_phase"] for beat in beats], ["intro", "drain", "remainder"])

    def test_visual_action_graph_expands_primary_plan_into_micro_beats(self) -> None:
        flow_data = {
            "source": {"label": "Salary", "value": "₹50,000", "amount": 50000},
            "flows": [
                {"label": "EMI", "value": "₹18,000", "amount": 18000, "color": "red", "order": 1},
                {"label": "Rent", "value": "₹12,000", "amount": 12000, "color": "orange", "order": 2},
            ],
            "remainder": {"value": "₹20,000", "amount": 20000, "is_dangerous": False},
        }
        section = {
            "text": "Salary lands. EMI leaves. Rent leaves. Balance remains.",
            "concept_type": "salary_drain",
            "visual_action_graph": {
                "source": "visual_action_graph_v1",
                "primary_concept": {"key": "salary_drain"},
                "actions": [
                    {
                        "id": "act:salary",
                        "action": "salary_arrives",
                        "semantic_role": "salary_income",
                        "motion": "credit_in",
                        "intent": "establish_source",
                        "sequence_index": 0,
                        "value": {"display_value": "₹50,000", "amount": 50000},
                    },
                    {
                        "id": "act:emi",
                        "action": "expense_drains",
                        "semantic_role": "emi_payment",
                        "motion": "collision_drain",
                        "intent": "show_outflow",
                        "relationship_id": "rel:emi",
                        "sequence_index": 1,
                        "value": {"display_value": "₹18,000", "amount": 18000},
                    },
                    {
                        "id": "act:rent",
                        "action": "expense_drains",
                        "semantic_role": "rent_expense",
                        "motion": "collision_drain",
                        "intent": "show_outflow",
                        "relationship_id": "rel:rent",
                        "sequence_index": 2,
                        "value": {"display_value": "₹12,000", "amount": 12000},
                    },
                    {
                        "id": "act:left",
                        "action": "balance_revealed",
                        "semantic_role": "remaining_balance",
                        "motion": "reveal_survivor",
                        "intent": "show_consequence",
                        "sequence_index": 3,
                        "value": {"display_value": "₹20,000", "amount": 20000},
                    },
                ],
                "edges": [],
            },
            "visual_plan": [
                {
                    "concept": {"concept": "Salary Drain", "type": "salary_drain"},
                    "visual": {"pattern": "MoneyFlowDiagram", "data": flow_data},
                    "beats": {
                        "beats": [
                            {"component": "MoneyFlowDiagram", "text": "₹50,000", "beat_phase": "intro", "data": {**flow_data, "active_phase": "intro"}},
                            {"component": "MoneyFlowDiagram", "text": "Where salary goes", "beat_phase": "drain", "data": {**flow_data, "active_phase": "drain"}},
                            {"component": "MoneyFlowDiagram", "text": "₹20,000 left", "beat_phase": "remainder", "data": {**flow_data, "active_phase": "remainder"}},
                        ]
                    },
                }
            ],
        }

        result = self.expander.expand_section(section)
        beats = result["visual_plan"][0]["beats"]["beats"]

        self.assertEqual(len(beats), 4)
        self.assertEqual([beat["beat_phase"] for beat in beats], ["intro", "drain", "drain", "remainder"])
        self.assertEqual([beat["data"]["active_action"]["action"] for beat in beats], ["salary_arrives", "expense_drains", "expense_drains", "balance_revealed"])
        self.assertEqual(beats[1]["data"]["action_choreography"]["window"], {"start_frame": 18, "end_frame": 52})
        self.assertEqual(beats[2]["data"]["action_choreography"]["overlap_group"], "overlapping_outflows")

    def test_visual_action_graph_sip_beats_preserve_growth_choreography(self) -> None:
        sip_data = {
            "monthly_sip": {"value": "₹5,000", "amount": 5000},
            "duration_years": 20,
            "annual_return_rate": 12,
            "total_invested": 1200000,
            "final_corpus": 5000000,
        }
        section = {
            "text": "A SIP starts, returns activate, time passes, and corpus appears.",
            "concept_type": "sip_growth",
            "visual_action_graph": {
                "source": "visual_action_graph_v1",
                "primary_concept": {"key": "sip_growth"},
                "actions": [
                    {"id": "act:sip", "action": "contribution_starts", "semantic_role": "monthly_sip", "motion": "repeat_deposit", "intent": "establish_contribution", "sequence_index": 0, "value": {"display_value": "₹5,000", "amount": 5000}},
                    {"id": "act:rate", "action": "return_rate_activates", "semantic_role": "annual_return_rate", "motion": "growth_curve_pull", "intent": "show_growth_force", "sequence_index": 1, "value": {"display_value": "12%", "amount": 12}},
                    {"id": "act:time", "action": "time_extends", "semantic_role": "time_period", "motion": "timeline_expand", "intent": "show_duration", "sequence_index": 2, "value": {"display_value": "20 years", "amount": 20}},
                    {"id": "act:invested", "action": "contributions_accumulate", "semantic_role": "total_contribution", "motion": "stacking_accumulation", "intent": "show_principal_base", "sequence_index": 3, "value": {"display_value": "₹12 lakh", "amount": 1200000}},
                    {"id": "act:corpus", "action": "corpus_revealed", "semantic_role": "target_corpus", "motion": "compound_reveal", "intent": "show_growth_result", "sequence_index": 4, "value": {"display_value": "₹50 lakh", "amount": 5000000}},
                ],
                "edges": [],
            },
            "visual_plan": [
                {
                    "concept": {"concept": "SIP Growth", "type": "sip_growth"},
                    "visual": {"pattern": "SIPGrowthEngine", "data": sip_data},
                    "beats": {
                        "beats": [
                            {"component": "SIPGrowthEngine", "text": "₹5,000", "beat_phase": "contribution", "data": {**sip_data, "active_phase": "contribution"}},
                            {"component": "SIPGrowthEngine", "text": "Compounding engine", "beat_phase": "growth", "data": {**sip_data, "active_phase": "growth"}},
                            {"component": "SIPGrowthEngine", "text": "₹50 lakh", "beat_phase": "corpus", "data": {**sip_data, "active_phase": "corpus"}},
                        ]
                    },
                }
            ],
        }

        result = self.expander.expand_section(section)
        beats = result["visual_plan"][0]["beats"]["beats"]

        self.assertEqual(len(beats), 5)
        self.assertEqual([beat["data"]["active_action"]["action"] for beat in beats], ["contribution_starts", "return_rate_activates", "time_extends", "contributions_accumulate", "corpus_revealed"])
        self.assertEqual(beats[-1]["beat_phase"], "corpus")
        self.assertEqual(beats[1]["data"]["action_choreography"]["overlap_group"], "compound_growth")


if __name__ == "__main__":
    unittest.main()
