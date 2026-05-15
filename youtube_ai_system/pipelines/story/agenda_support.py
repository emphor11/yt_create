from __future__ import annotations

from typing import Any

from .constants import CONCEPT_PRIORITY


class StoryAgendaSupportMixin:
    def agenda_from_top_concepts(self, sections: list[dict[str, Any]]) -> list[str]:
        ranked: list[tuple[float, int, str]] = []
        for section in sections:
            score = float((section.get("weight") or {}).get("score") or 0.0)
            strongest = (section.get("concepts") or [None])[0]
            if strongest:
                concept_text = str(strongest.get("concept") or "").strip()
                if concept_text:
                    concept_type = str(strongest.get("type") or "")
                    ranked.append((score, CONCEPT_PRIORITY.get(concept_type, 0), concept_text))
                    continue
            visual_plan = section.get("visual_plan") or []
            if visual_plan:
                visual_concept = str((visual_plan[0].get("concept") or {}).get("concept") or "").strip()
                visual_type = str((visual_plan[0].get("concept") or {}).get("type") or "")
                if visual_concept:
                    ranked.append((score, CONCEPT_PRIORITY.get(visual_type, 0), visual_concept))
        ranked.sort(key=lambda item: (item[1], item[0], len(item[2].split())), reverse=True)
        agenda: list[str] = []
        seen: set[str] = set()
        for _, _, concept_text in ranked:
            key = concept_text.lower()
            if key in seen:
                continue
            seen.add(key)
            agenda.append(concept_text)
            if len(agenda) == 3:
                break
        return agenda
