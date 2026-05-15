"""Hook validation policy for script approval."""

from __future__ import annotations

import re
from typing import Iterable


class HookValidator:
    def __init__(
        self,
        *,
        tension_keywords: Iterable[str],
        people_group_words: Iterable[str],
        negative_implication_words: Iterable[str],
    ) -> None:
        self.tension_keywords = tuple(tension_keywords)
        self.people_group_words = tuple(people_group_words)
        self.negative_implication_words = tuple(negative_implication_words)

    def validate(self, hook: dict) -> list[str]:
        errors: list[str] = []
        if float(hook.get("duration", hook.get("estimated_duration_sec", 0)) or 0) > 30:
            errors.append("Hook must be 30 seconds or under.")

        narration = str(hook.get("narration", "")).strip()
        narration_lower = narration.lower()
        word_count = len(narration.split())

        condition_a = any(keyword in narration_lower for keyword in self.tension_keywords)

        condition_b = False
        has_pct = "%" in narration
        large_numbers = [int(m) for m in re.findall(r"\d+", narration) if int(m) > 1000]
        has_large_number = len(large_numbers) > 0
        has_people_group = any(pg in narration_lower for pg in self.people_group_words)
        if (has_pct or has_large_number) and word_count <= 25 and has_people_group:
            condition_b = True

        condition_c = False
        has_rupee = "₹" in narration
        has_negative = any(nw in narration_lower for nw in self.negative_implication_words)
        if has_rupee and has_negative:
            condition_c = True

        if not (condition_a or condition_b or condition_c):
            guidance_lines = [
                "Hook must include a tension signal. Satisfy ANY ONE of these:",
                "  A) Include a tension keyword or question mark: " + ", ".join(sorted(self.tension_keywords)),
                "  B) Include a percentage or number > 1000 AND a people group word "
                + f"({', '.join(sorted(self.people_group_words))}) in under 25 words",
                "  C) Include ₹ symbol AND a negative implication word "
                + f"({', '.join(sorted(self.negative_implication_words))})",
            ]
            errors.append(" | ".join(guidance_lines))
        return errors

