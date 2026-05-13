from __future__ import annotations

import unittest

from youtube_ai_system.services.cinematic_event_compiler import CinematicEventCompiler


class CinematicEventCompilerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.compiler = CinematicEventCompiler()

    def test_maps_narration_entities_to_ordered_visual_events(self) -> None:
        events = self.compiler.compile(
            "₹50,000 salary lands. Rent upgrade hits. Food delivery follows. Shopping and subscriptions pile up. Only ₹6,000 is left.",
            component="LifestyleCreepVisualizer",
            duration_seconds=48,
        )

        labels = [event["label"] for event in events]
        modes = [event["visual_mode"] for event in events]

        self.assertGreaterEqual(len(events), 5)
        self.assertIn("Salary", labels)
        self.assertIn("Rent", labels)
        self.assertIn("Food delivery", labels)
        self.assertIn("Shopping", labels)
        self.assertIn("Subscriptions", labels)
        self.assertIn("survivor_isolation", modes)
        self.assertEqual(events, sorted(events, key=lambda event: event["start_progress"]))

    def test_repetition_governor_breaks_three_identical_modes(self) -> None:
        events = self.compiler.compile(
            "The bill hits. Another unexpected repair hits. A hospital shock hits again. Then the buffer protects the plan.",
            component="EmergencyFundVisualizer",
            duration_seconds=42,
        )
        modes = [event["visual_mode"] for event in events]

        for index in range(len(modes) - 2):
            self.assertNotEqual(modes[index : index + 3], [modes[index]] * 3)

    def test_unknown_topic_still_gets_generic_event_sequence(self) -> None:
        events = self.compiler.compile(
            "A creator sells one course. Refunds arrive late. Platform fees reduce the payout. The real cash arrives two weeks later.",
            component="",
            duration_seconds=40,
        )

        self.assertGreaterEqual(len(events), 4)
        self.assertTrue(all(event["label"] for event in events))
        self.assertTrue(all(event["visual_mode"] for event in events))


if __name__ == "__main__":
    unittest.main()
