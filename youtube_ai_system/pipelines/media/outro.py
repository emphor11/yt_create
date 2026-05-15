from __future__ import annotations

import re

from .text_signals import SceneTextSignalResolver


class OutroSectionBuilder:
    """Builds the deterministic outro recap section used by the scene renderer."""

    def __init__(self, text_signals: SceneTextSignalResolver | None = None) -> None:
        self.text_signals = text_signals or SceneTextSignalResolver()

    def section_intelligence(self, narration: str) -> dict:
        punch = self.punchline(narration)
        actions = self.actions(narration)
        outro_data = {"title": punch, "actions": actions, "punch": punch}
        visual_plan = [
            {
                "concept": {"concept": "Final Takeaway", "type": "outro"},
                "visual": {"pattern": "OutroRecapVisualizer", "data": outro_data},
                "beats": {
                    "beats": [
                        {
                            "component": "OutroRecapVisualizer",
                            "text": actions[0]["label"],
                            "emphasis": "normal",
                            "data": {**outro_data, "active_action": actions[0]},
                        },
                        {
                            "component": "OutroRecapVisualizer",
                            "text": "Build the system",
                            "emphasis": "subtle",
                            "data": outro_data,
                        },
                        {
                            "component": "OutroRecapVisualizer",
                            "text": punch,
                            "emphasis": "hero",
                            "data": outro_data,
                        },
                    ]
                },
            }
        ]
        return {
            "type": "optimization",
            "text": narration,
            "weight": self.text_signals.weight_for_scene_kind("outro"),
            "visual_plan": visual_plan,
            "finance_concept": {"concept_name": "Final Takeaway", "concept_type": "outro"},
            "narrative_arc": {"visual_type": "recap", "story_goal": punch},
            "visual_story": {},
            "story_state": {},
            "direction": {"emotional_arc": {"opening": "aware", "closing": "confidence"}, "scene_position": "outro", "accent": "positive"},
            "visual_mode": "graphic_recap",
            "cinematic_intent": {"visual_mode": "graphic_recap", "overlay_text": punch, "scene_role": "outro"},
            "concept_type": "outro",
            "theme": {},
            "state": {},
            "visual_type": "recap",
            "dominant_entity": "money",
            "idea_type": "process",
            "has_numbers": bool(re.search(r"₹|Rs\.?\s*|\d+|%", narration, re.IGNORECASE)),
            "has_comparison": False,
            "has_causation": False,
            "visual_scene": {
                "scene_id": "outro",
                "narration": narration,
                "visual_intent": "Show final recap and practical takeaway",
                "visual_beats": [action["label"] for action in actions],
                "numbers": [],
                "emotion": "confidence",
                "mechanism": "definition",
            },
        }

    def actions(self, narration: str) -> list[dict[str, object]]:
        lowered = narration.lower()
        candidates = [
            ("track", "Track the leak", "TRACK", ["track", "notice", "write", "budget", "spending", "expenses"], "#4361EE"),
            ("protect", "Protect the buffer", "PROTECT", ["protect", "emergency", "buffer", "savings", "fund"], "#2EC4B6"),
            ("reduce_debt", "Cut fixed pressure", "CUT DEBT", ["debt", "emi", "loan", "credit card", "avoid"], "#FF9F1C"),
            ("invest", "Invest consistently", "INVEST", ["invest", "sip", "compound", "long term", "wealth"], "#2EC4B6"),
            ("start", "Start this month", "START", ["start", "today", "this month", "small", "next salary"], "#FF9F1C"),
        ]
        actions = []
        for action_id, label, short_label, keywords, color in candidates:
            if any(keyword in lowered for keyword in keywords):
                actions.append({"id": action_id, "label": label, "shortLabel": short_label, "keywords": keywords, "color": color})
        if len(actions) < 4:
            for action_id, label, short_label, keywords, color in candidates:
                if not any(action["id"] == action_id for action in actions):
                    actions.append({"id": action_id, "label": label, "shortLabel": short_label, "keywords": keywords, "color": color})
                if len(actions) >= 5:
                    break
        return actions[:6]

    def punchline(self, narration: str) -> str:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", narration) if part.strip()]
        if sentences:
            return sentences[-1].rstrip(".!?")
        return "Build the system before the next month starts"
