from __future__ import annotations

import re
from typing import Any

from .finance_concept_extractor import FinanceConceptExtractor
from .idea_grouper import IdeaGrouper
from .run_log import RunLogger
from .story_intelligence_engine import StoryIntelligenceEngine
from .visual_logic_engine import map_concept_to_visual
from .visual_beat_expander import VisualBeatExpander
from .visual_director import VisualDirector, visual_director_input_from_section
from .visual_scene_normalizer import VisualSceneNormalizer
from .visual_story_engine import VisualStoryEngine

CONCEPT_PRIORITY = {
    "numeric": 5,
    "risk": 4,
    "comparison": 3,
    "growth": 2,
    "definition": 1,
}

FINANCIAL_NUMBER_KEYWORDS = {
    "salary",
    "interest",
    "payment",
    "bill",
    "amount",
    "balance",
    "debt",
    "cost",
    "loss",
    "leak",
    "spent",
    "save",
    "saved",
    "savings",
    "principal",
    "income",
    "emi",
    "return",
    "returns",
}


class StoryPipeline:
    def __init__(
        self,
        story_intelligence: StoryIntelligenceEngine | None = None,
        idea_grouper: IdeaGrouper | None = None,
        finance_concept_extractor: FinanceConceptExtractor | None = None,
        visual_director: VisualDirector | None = None,
        visual_scene_normalizer: VisualSceneNormalizer | None = None,
        visual_beat_expander: VisualBeatExpander | None = None,
        visual_story_engine: VisualStoryEngine | None = None,
        logger: RunLogger | None = None,
    ) -> None:
        self.story_intelligence = story_intelligence or StoryIntelligenceEngine()
        self.idea_grouper = idea_grouper or IdeaGrouper()
        self.finance_concept_extractor = finance_concept_extractor or FinanceConceptExtractor()
        self.visual_director = visual_director or VisualDirector()
        self.visual_scene_normalizer = visual_scene_normalizer or VisualSceneNormalizer()
        self.visual_beat_expander = visual_beat_expander or VisualBeatExpander()
        self.visual_story_engine = visual_story_engine or VisualStoryEngine()
        self.logger = logger or RunLogger()

    def build_story_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        planning_payload = self.group_payload_for_story_plan(payload)
        story_plan = self.story_plan_from_idea_groups(planning_payload)
        story_plan = self.attach_visual_scene_contract(story_plan)
        story_plan = self.attach_section_concepts(story_plan)
        story_plan = self.attach_section_narrative_arc(story_plan)
        story_plan = self.attach_visual_story(story_plan)
        story_plan = self.attach_section_visual_plan(story_plan)
        return story_plan

    def group_sentences_into_sections(self, sentences: list[str]) -> list[str]:
        cleaned = [self._normalize_text(sentence) for sentence in sentences if self._normalize_text(sentence)]
        if not cleaned:
            return []

        groups: list[list[str]] = []
        index = 0

        while index < len(cleaned):
            current = [cleaned[index]]
            index += 1

            if index < len(cleaned):
                current.append(cleaned[index])
                index += 1

            if index < len(cleaned):
                next_sentence = cleaned[index]
                if (
                    len(current) < 3
                    and self._section_word_count(current) < 8
                    and not self._sentence_starts_new_section(next_sentence)
                    and self._shares_topic_with_current(current, next_sentence)
                    and self._section_word_count(current + [next_sentence]) <= 20
                ):
                    current.append(next_sentence)
                    index += 1

            groups.append(current)

        groups = self._merge_short_sections(groups)
        return [" ".join(group) for group in groups if group]

    def group_payload_for_story_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        hook = dict(payload.get("hook") or {})
        grouped_scenes: list[dict[str, Any]] = []
        for scene in payload.get("scenes") or []:
            visual_scene_source = self._visual_scene_source(scene)
            if visual_scene_source:
                combined_text = self._normalize_text(str(scene.get("narration") or ""))
                if combined_text:
                    grouped_scenes.append(
                        {
                            "narration": combined_text,
                            "idea_group_id": f"idea_{len(grouped_scenes):02d}",
                            "dominant_entity": "money",
                            "idea_type": str(visual_scene_source.get("mechanism") or scene.get("idea_type") or "emphasis"),
                            "has_numbers": bool(re.search(r"₹|%|\d+", combined_text)),
                            "has_comparison": bool(
                                re.search(r"\bvs\b|\bversus\b|\bbut\b|\bhowever\b|\binstead\b", combined_text, re.IGNORECASE)
                            ),
                            "has_causation": bool(
                                re.search(
                                    r"\bbecause\b|\bso\b|\btherefore\b|\bleads to\b|\bresults in\b",
                                    combined_text,
                                    re.IGNORECASE,
                                )
                            ),
                            "visual_scene": visual_scene_source,
                        }
                    )
                continue
            raw_sentences = self._split_story_sentences(str(scene.get("narration") or ""))
            body_sentences = [sentence for sentence in raw_sentences if self._keep_story_sentence(sentence)]
            if len(body_sentences) < 2:
                body_sentences = [sentence for sentence in raw_sentences if self._keep_story_sentence(sentence, allow_short=True)]

            scene_groups = self.idea_grouped_scenes(body_sentences)
            if not scene_groups:
                combined_text = self._normalize_text(" ".join(body_sentences))
                scene_groups = (
                    [
                        {
                            "narration": combined_text,
                            "idea_group_id": f"idea_{len(grouped_scenes):02d}",
                            "dominant_entity": "money",
                            "idea_type": "emphasis",
                            "has_numbers": bool(re.search(r"₹|%|\d+", combined_text)),
                            "has_comparison": bool(
                                re.search(r"\bvs\b|\bversus\b|\bbut\b|\bhowever\b|\binstead\b", combined_text, re.IGNORECASE)
                            ),
                            "has_causation": bool(
                                re.search(
                                    r"\bbecause\b|\bso\b|\btherefore\b|\bleads to\b|\bresults in\b",
                                    combined_text,
                                    re.IGNORECASE,
                                )
                            ),
                        }
                    ]
                    if combined_text
                    else []
                )
            for scene_group in scene_groups:
                scene_group["idea_group_id"] = f"idea_{len(grouped_scenes):02d}"
                grouped_scenes.append(scene_group)

        return {
            "hook": hook,
            "scenes": grouped_scenes,
            "outro": {"narration": ""},
        }

    def idea_grouped_scenes(self, body_sentences: list[str]) -> list[dict[str, Any]]:
        narration_text = " ".join(sentence.strip() for sentence in body_sentences if sentence.strip())
        if not narration_text.strip():
            return []

        idea_groups = self.idea_grouper.group(narration_text)
        if not idea_groups:
            return []

        grouped_scenes: list[dict[str, Any]] = []
        for group in idea_groups:
            combined_text = self._normalize_text(group.combined_text)
            if not combined_text:
                continue
            grouped_scenes.append(
                {
                    "narration": combined_text,
                    "idea_group_id": group.group_id,
                    "dominant_entity": group.dominant_entity,
                    "idea_type": group.idea_type,
                    "has_numbers": group.has_numbers,
                    "has_comparison": group.has_comparison,
                    "has_causation": group.has_causation,
                }
            )
        return grouped_scenes

    def _visual_scene_source(self, scene: dict[str, Any]) -> dict[str, Any]:
        visual_scene = scene.get("visual_scene")
        if isinstance(visual_scene, dict):
            return dict(visual_scene)
        source: dict[str, Any] = {}
        for key in ("visual_intent", "visual_beats", "numbers", "emotion", "mechanism"):
            if key in scene:
                source[key] = scene[key]
        if source:
            source.setdefault("narration", scene.get("narration") or scene.get("text") or "")
        return source

    def story_plan_from_idea_groups(self, payload: dict[str, Any]) -> dict[str, Any]:
        hook_payload = payload.get("hook") or {}
        hook_text = str(hook_payload.get("narration") or "").strip()
        sections: list[dict[str, Any]] = []

        for scene in payload.get("scenes") or []:
            if not isinstance(scene, dict):
                continue
            text = self._normalize_text(str(scene.get("narration") or scene.get("narration_text") or ""))
            if not text:
                continue
            section_type = self.story_intelligence._classify_sentence(text)
            sections.append(
                {
                    "type": section_type,
                    "text": text,
                    "weight": self.story_intelligence._weight_for(section_type),
                    "idea_group_id": scene.get("idea_group_id"),
                    "dominant_entity": scene.get("dominant_entity") or "money",
                    "idea_type": scene.get("idea_type") or "emphasis",
                    "has_numbers": bool(scene.get("has_numbers")),
                    "has_comparison": bool(scene.get("has_comparison")),
                    "has_causation": bool(scene.get("has_causation")),
                    "visual_scene": scene.get("visual_scene") if isinstance(scene.get("visual_scene"), dict) else None,
                }
            )

        if len(sections) < 2 and hook_text:
            hook_section_type = self.story_intelligence._classify_sentence(hook_text)
            sections.insert(
                0,
                {
                    "type": hook_section_type,
                    "text": self._normalize_text(hook_text),
                    "weight": self.story_intelligence._weight_for(hook_section_type),
                    "idea_group_id": "idea_hook",
                    "dominant_entity": "money",
                    "idea_type": "emphasis",
                    "has_numbers": bool(re.search(r"₹|%|\d+", hook_text)),
                    "has_comparison": bool(re.search(r"\bvs\b|\bversus\b|\bbut\b|\bhowever\b|\binstead\b", hook_text, re.IGNORECASE)),
                    "has_causation": bool(
                        re.search(
                            r"\bbecause\b|\bso\b|\btherefore\b|\bleads to\b|\bresults in\b",
                            hook_text,
                            re.IGNORECASE,
                        )
                    ),
                },
            )

        sections = self.story_intelligence._ensure_section_progression(sections)
        sections = self.story_intelligence._stable_sort_sections_by_stage(sections)
        hook = self.story_intelligence._clean_hook_text(hook_text)
        hook = self.story_intelligence._ensure_distinct_hook(hook, sections)
        self.story_intelligence._validate_minimum_sections(sections)
        self._warn_on_section_flow(sections)

        hook_type = self.story_intelligence._classify_hook_type(hook)
        return {
            "hook": hook,
            "hook_type": hook_type,
            "arc_type": self.story_intelligence._classify_arc_type(sections, hook_type),
            "agenda": [],
            "sections": sections,
        }

    def attach_visual_scene_contract(self, story_plan: dict[str, Any]) -> dict[str, Any]:
        sections = story_plan.get("sections") or []
        story_plan["sections"] = [
            self.visual_scene_normalizer.inject_into_section(section, index)
            for index, section in enumerate(sections)
        ]
        return story_plan

    def attach_section_concepts(self, story_plan: dict[str, Any]) -> dict[str, Any]:
        sections = story_plan.get("sections") or []
        for section in sections:
            concepts: list[dict[str, str]] = []
            seen: set[tuple[str, str]] = set()
            finance_concept = self.finance_concept_extractor.extract(
                {
                    "combined_text": str(section.get("text") or ""),
                    "dominant_entity": str(section.get("dominant_entity") or "money"),
                    "idea_type": str(section.get("idea_type") or "emphasis"),
                }
            )
            section["finance_concept"] = {
                "concept_name": finance_concept.concept_name,
                "concept_type": finance_concept.concept_type,
                "primary_entity": finance_concept.primary_entity,
                "action": finance_concept.action,
                "start_value": finance_concept.start_value,
                "end_value": finance_concept.end_value,
                "percentage": finance_concept.percentage,
                "time_period": finance_concept.time_period,
                "agent": finance_concept.agent,
                "victim": finance_concept.victim,
                "confidence": finance_concept.confidence,
            }
            concept = finance_concept.concept_name if finance_concept.concept_name != "Unknown" else None
            concept_type = finance_concept.concept_type
            if concept:
                key = (str(concept), str(concept_type))
                if key not in seen:
                    seen.add(key)
                    concepts.append({"concept": str(concept), "type": str(concept_type)})
            concepts.sort(
                key=lambda item: (
                    CONCEPT_PRIORITY.get(item.get("type", ""), 0),
                    len(str(item.get("concept") or "").split()),
                ),
                reverse=True,
            )
            section["concepts"] = concepts
        story_plan["agenda"] = self.agenda_from_top_concepts(sections)
        return story_plan

    def attach_section_narrative_arc(self, story_plan: dict[str, Any]) -> dict[str, Any]:
        sections = story_plan.get("sections") or []
        for section in sections:
            arc = self._narrative_arc_for_section(section)
            section["narrative_arc"] = arc
            section["visual_type"] = arc.get("visual_type") or "concept"
            section["state"] = self._state_from_narrative_arc(arc)
        return story_plan

    def attach_visual_story(self, story_plan: dict[str, Any]) -> dict[str, Any]:
        return self.visual_story_engine.attach_visual_story(story_plan)

    def attach_section_visual_plan(self, story_plan: dict[str, Any]) -> dict[str, Any]:
        sections = story_plan.get("sections") or []
        preceding_concept_type: str | None = None
        total_sections = max(len(sections), 1)
        for index, section in enumerate(sections):
            if "narrative_arc" not in section:
                section["narrative_arc"] = self._narrative_arc_for_section(section)
            section_position = self._section_position(index, total_sections)
            director_input = visual_director_input_from_section(section, section_position, preceding_concept_type)
            directed_plan = None
            try:
                directed_plan = self.visual_director.direct(director_input)
            except Exception as exc:
                self._log_visual_director("failed", str(exc))

            if directed_plan and directed_plan.is_valid() and not directed_plan.fallback_reason:
                section["visual_plan"] = [directed_plan.to_visual_plan_item()]
                section["direction"] = directed_plan.direction.to_dict()
                section["theme"] = dict(directed_plan.theme)
                section["concept_type"] = directed_plan.concept_type
                section["visual_mode"] = directed_plan.visual_mode
                section["cinematic_intent"] = dict(directed_plan.cinematic_intent)
                section["visual_story"] = dict(story_plan.get("visual_story") or section.get("visual_story") or {})
                section["story_state"] = dict(section.get("story_state") or {})
                if directed_plan.fallback_reason:
                    self._log_visual_director("fallback", directed_plan.fallback_reason)
            else:
                if directed_plan and directed_plan.fallback_reason:
                    self._log_visual_director("fallback", directed_plan.fallback_reason)
                old_plan = self._old_visual_plan(section)
                if old_plan:
                    section["visual_plan"] = [old_plan]
                else:
                    fallback_text = self._short_visual_text(str(section.get("text") or "Core idea"))
                    section["visual_plan"] = [
                        {
                            "concept": {"concept": fallback_text, "type": "definition"},
                            "visual": {"pattern": "StatCard", "data": {"title": fallback_text.upper()}},
                            "beats": {"beats": [{"component": "StatCard", "text": fallback_text}]},
                        }
                    ]
                section["direction"] = None
                section["theme"] = {}
                section["concept_type"] = str(section.get("idea_type") or "emphasis")
                section.pop("visual_mode", None)
                section.pop("cinematic_intent", None)
            self.visual_story_engine.enrich_section_from_visual_plan(
                section,
                dict(story_plan.get("visual_story") or section.get("visual_story") or {}),
            )
            sections[index] = self.visual_beat_expander.expand_section(section)
            preceding_concept_type = directed_plan.concept_type if directed_plan else director_input.concept_type
        return story_plan

    def _log_visual_director(self, status: str, message: str) -> None:
        try:
            self.logger.log("visual_director", status, message)
        except Exception:
            pass

    def _old_visual_plan(self, section: dict[str, Any]) -> dict[str, Any] | None:
        candidate = {
            "concept": self._primary_visual_concept(section),
            "visual": self._visual_from_narrative_arc(section),
            "beats": {"beats": self._sentence_aligned_beats(section)},
        }
        return self.safe_visual_item(candidate)

    def _section_position(self, index: int, total_sections: int) -> str:
        if index == 0:
            return "hook"
        if index <= max(1, total_sections // 3):
            return "early"
        if index >= total_sections - 1:
            return "outro"
        if index >= max(1, int(total_sections * 0.7)):
            return "late"
        return "middle"

    def safe_visual_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        if self._is_valid_visual_item(item):
            return item
        return None

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

    def numeric_visual_plan(self, text: str) -> dict[str, Any] | None:
        numeric_phrases = self.numeric_phrases(text)
        if not self._numeric_visual_allowed(text, numeric_phrases):
            return None
        if len(numeric_phrases) >= 2:
            strongest = numeric_phrases[-1]
            return {
                "concept": {"concept": strongest, "type": "numeric"},
                "visual": {
                    "pattern": "NumericComparison",
                    "data": {"values": numeric_phrases[:3]},
                },
                "beats": {
                    "beats": self._numeric_beats(numeric_phrases[:3], strongest),
                },
            }
        strongest = numeric_phrases[0]
        return {
            "concept": {"concept": strongest, "type": "numeric"},
            "visual": {
                "pattern": "NumericComparison",
                "data": {"values": [strongest]},
            },
            "beats": {
                "beats": [{"component": "StatCard", "text": strongest}],
            },
        }

    def numeric_phrases(self, text: str) -> list[str]:
        if not re.search(r"(₹|Rs\.?\s*|\d|%)", text, flags=re.IGNORECASE):
            return []
        pattern = r"(?:₹\s*|Rs\.?\s*)?\d[\d,]*(?:\.\d+)?\s*(?:%|years?|months?|lakhs?)?"
        matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
        phrases: list[str] = []
        for match in matches:
            token = " ".join(match.group(0).strip().split())
            if not token or not re.search(r"\d", token):
                continue
            if not self._is_financial_number(text, token, match.start(), match.end()):
                continue
            label = self._numeric_label(text, match.start(), match.end())
            phrase = f"{token} {label}".strip() if label else token
            phrases.append(" ".join(phrase.split()))
        return self._unique_beat_values(phrases, phrases[-1] if phrases else "")

    def _warn_on_section_flow(self, sections: list[dict[str, Any]]) -> None:
        try:
            self.story_intelligence._validate_section_flow(sections)
        except ValueError as exc:
            self.logger.log("story_planning", "warning", str(exc))

    def _narrative_arc_for_section(self, section: dict[str, Any]) -> dict[str, Any]:
        text = str(section.get("text") or "")
        finance_concept = dict(section.get("finance_concept") or {})
        concept = self._primary_visual_concept(section)
        concept_name = str(concept.get("concept") or finance_concept.get("concept_name") or "Money Change").strip()
        concept_type = str(concept.get("type") or finance_concept.get("concept_type") or "definition").strip()
        numeric_phrases = self.numeric_phrases(text)
        start_value = str(finance_concept.get("start_value") or (numeric_phrases[0] if numeric_phrases else "")).strip()
        end_value = str(finance_concept.get("end_value") or (numeric_phrases[-1] if len(numeric_phrases) > 1 else "")).strip()
        start_value = self._visual_state_value(start_value)
        end_value = self._visual_state_value(end_value)
        rate = self._rate_value(finance_concept, numeric_phrases)
        visual_type = self._visual_type_for_section(section, concept_type, numeric_phrases, rate)
        process = self._arc_process(finance_concept, text, rate)

        return {
            "visual_type": visual_type,
            "visual_pattern": self._semantic_visual_pattern(visual_type, concept_name),
            "render_pattern": self._render_pattern_for_visual_type(visual_type, concept_type),
            "story_goal": self._story_goal(concept_name, start_value, process, end_value or rate),
            "start_state": start_value,
            "process": process,
            "end_state": end_value,
            "rate": rate,
            "punch": self._arc_punch(text, concept_name),
            "numeric_values": numeric_phrases[:3],
            "has_causation": bool(section.get("has_causation")),
            "has_comparison": bool(section.get("has_comparison")),
        }

    def _primary_visual_concept(self, section: dict[str, Any]) -> dict[str, str]:
        concepts = section.get("concepts") or []
        if concepts:
            concept = dict(concepts[0])
            concept_text = str(concept.get("concept") or "Money Change")
            if concept_text == "Money Change":
                inferred = self._concept_from_section_text(str(section.get("text") or ""))
                if inferred:
                    return inferred
            return {
                "concept": concept_text,
                "type": str(concept.get("type") or "definition"),
            }
        finance_concept = dict(section.get("finance_concept") or {})
        concept_name = str(finance_concept.get("concept_name") or "Money Change").strip()
        concept_type = str(finance_concept.get("concept_type") or "definition").strip()
        if concept_name in {"Unknown", "Money Change"}:
            inferred = self._concept_from_section_text(str(section.get("text") or ""))
            if inferred:
                return inferred
        return {"concept": concept_name if concept_name != "Unknown" else "Money Change", "type": concept_type}

    def _concept_from_section_text(self, text: str) -> dict[str, str] | None:
        lowered = text.lower()
        if "salary" in lowered and any(token in lowered for token in ("vanish", "disappear", "gone", "drain", "left")):
            return {"concept": "Salary Depletion", "type": "risk"}
        if "emi" in lowered:
            return {"concept": "EMI Pressure", "type": "risk"}
        if "debt" in lowered and "interest" in lowered:
            return {"concept": "Debt Trap", "type": "risk"}
        if "inflation" in lowered:
            return {"concept": "Inflation Erosion", "type": "risk"}
        if "sip" in lowered or "compound" in lowered:
            return {"concept": "Compounding Growth", "type": "growth"}
        return None

    def _visual_from_narrative_arc(self, section: dict[str, Any]) -> dict[str, Any]:
        arc = dict(section.get("narrative_arc") or {})
        concept = self._primary_visual_concept(section)
        render_pattern = str(arc.get("render_pattern") or "").strip()
        if render_pattern == "NumericComparison":
            values = [value for value in arc.get("numeric_values") or [] if str(value).strip()]
            if not values:
                values = [value for value in (arc.get("start_state"), arc.get("rate"), arc.get("end_state")) if str(value or "").strip()]
            if not values:
                return {"pattern": "ConceptCard", "data": {"title": str(concept.get("concept") or "Money Change").upper()}}
            return {"pattern": "NumericComparison", "data": {"values": values}}

        try:
            visual = map_concept_to_visual(concept)
        except (ValueError, TypeError):
            visual = {"pattern": "ConceptCard", "data": {"title": str(concept.get("concept") or "Money Change").upper()}}
        if render_pattern:
            visual["pattern"] = render_pattern
            visual["data"] = self._data_for_render_pattern(render_pattern, concept, arc, visual.get("data") or {})
        return visual

    def _beats_from_narrative_arc(self, section: dict[str, Any]) -> list[dict[str, Any]]:
        arc = dict(section.get("narrative_arc") or {})
        concept = self._primary_visual_concept(section)
        concept_name = str(concept.get("concept") or "Money Change")
        concept_type = str(concept.get("type") or "definition")
        visual_props = self._visual_props_for_arc(section, arc, concept)
        values = [str(value).strip() for value in arc.get("numeric_values") or [] if str(value).strip()]
        start_state = str(arc.get("start_state") or "").strip()
        end_state = str(arc.get("end_state") or "").strip()
        rate = str(arc.get("rate") or "").strip()
        process = str(arc.get("process") or "").strip()
        punch = str(arc.get("punch") or concept_name).strip()

        if values:
            beats = self._numeric_beats(values, values[-1])
            if visual_props.get("nodes") and len(values) >= 2:
                beats.insert(
                    1,
                    {
                        "component": "FlowBar",
                        "text": self._short_visual_text(str(visual_props.get("title") or "Money flow")),
                        "subtext": "money movement",
                        "props": visual_props,
                    },
                )
            if punch:
                beats.append({"component": "HighlightText", "text": self._short_visual_text(punch), "props": {"title": punch, "subtitle": concept_name}})
            return [beat for beat in beats if self._is_valid_beat(beat)][:6]

        if concept_type == "comparison" or arc.get("has_comparison"):
            beats = [
                {"component": "ConceptCard", "text": self._short_visual_text(concept_name), "props": {"title": concept_name, "subtitle": self._short_visual_text(process)}},
                {"component": "SplitComparison", "text": self._short_visual_text(process or concept_name), "props": visual_props},
                {"component": "HighlightText", "text": self._short_visual_text(punch), "props": {"title": punch, "subtitle": concept_name}},
            ]
            return [beat for beat in beats if self._is_valid_beat(beat)]

        if concept_type == "growth":
            beats = [
                {"component": "StatCard", "text": self._short_visual_text(start_state or "Start small"), "subtext": "start"},
                {"component": "GrowthChart", "text": self._short_visual_text(process or concept_name), "props": visual_props},
                {"component": "StatCard", "text": self._short_visual_text(end_state or "Growth builds"), "subtext": "result"},
                {"component": "HighlightText", "text": self._short_visual_text(punch), "props": {"title": punch, "subtitle": concept_name}},
            ]
            return [beat for beat in beats if self._is_valid_beat(beat)]

        if concept_type == "risk" or arc.get("has_causation"):
            middle_component = "BalanceBar" if visual_props.get("left") and visual_props.get("right") else "FlowBar"
            beats = [
                {"component": "StatCard" if start_state else "ConceptCard", "text": self._short_visual_text(start_state or concept_name), "props": {"title": concept_name, "subtitle": process}},
                {"component": middle_component, "text": self._short_visual_text(rate or process or "Pressure rises"), "props": visual_props},
                {"component": "FlowBar", "text": self._short_visual_text(end_state or "Money leaks"), "props": visual_props},
                {"component": "HighlightText", "text": self._short_visual_text(punch), "props": {"title": punch, "subtitle": concept_name}},
            ]
            return [beat for beat in beats if self._is_valid_beat(beat)]

        beats = [
            {"component": "ConceptCard", "text": self._short_visual_text(concept_name), "props": {"title": concept_name, "subtitle": self._short_visual_text(process)}},
            {"component": "FlowBar", "text": self._short_visual_text(process or "Money moves"), "props": visual_props},
            {"component": "HighlightText", "text": self._short_visual_text(punch), "props": {"title": punch, "subtitle": concept_name}},
        ]
        return [beat for beat in beats if self._is_valid_beat(beat)]

    def _sentence_aligned_beats(self, section: dict[str, Any]) -> list[dict[str, Any]]:
        beats = self._beats_from_narrative_arc(section)
        sentences = self._split_story_sentences(str(section.get("text") or ""))
        if not beats or not sentences:
            return beats

        aligned: list[dict[str, Any]] = []
        used_indices: set[int] = set()
        for index, beat in enumerate(beats):
            sentence_index = self._best_sentence_index_for_beat(beat, sentences, used_indices)
            used_indices.add(sentence_index)
            aligned_beat = dict(beat)
            aligned_beat["sentence_index"] = sentence_index
            aligned_beat["source_text"] = sentences[sentence_index]
            aligned.append(aligned_beat)
        return aligned

    def _best_sentence_index_for_beat(self, beat: dict[str, Any], sentences: list[str], used_indices: set[int]) -> int:
        beat_terms = self._beat_alignment_terms(beat)
        best_index = 0
        best_score = -1
        for index, sentence in enumerate(sentences):
            sentence_terms = self._alignment_terms(sentence)
            score = len(beat_terms.intersection(sentence_terms))
            if index not in used_indices:
                score += 0.25
            if score > best_score:
                best_score = score
                best_index = index
        if best_score <= 0:
            return min(len(sentences) - 1, len(used_indices))
        return best_index

    def _beat_alignment_terms(self, beat: dict[str, Any]) -> set[str]:
        parts = [str(beat.get("text") or ""), str(beat.get("subtext") or "")]
        props = beat.get("props") or {}
        if isinstance(props, dict):
            for key in ("title", "subtitle", "start", "end", "rate"):
                parts.append(str(props.get(key) or ""))
            for side_key in ("left", "right"):
                side = props.get(side_key)
                if isinstance(side, dict):
                    parts.append(str(side.get("label") or ""))
                    parts.append(str(side.get("value") or ""))
            nodes = props.get("nodes")
            if isinstance(nodes, list):
                for node in nodes:
                    if isinstance(node, dict):
                        parts.append(str(node.get("label") or ""))
                        parts.append(str(node.get("value") or ""))
                        parts.append(str(node.get("subtext") or ""))
        return self._alignment_terms(" ".join(parts))

    def _alignment_terms(self, text: str) -> set[str]:
        stopwords = {
            "the",
            "and",
            "your",
            "you",
            "are",
            "this",
            "that",
            "with",
            "from",
            "into",
            "then",
            "when",
            "almost",
        }
        aliases = {
            "emis": "emi",
            "expenses": "expense",
            "spends": "spending",
            "spent": "spending",
            "drains": "drain",
            "drain": "drain",
            "disappears": "disappear",
            "vanishes": "vanish",
            "leftover": "left",
        }
        terms: set[str] = set()
        for word in re.findall(r"[A-Za-z0-9₹%,.]+", str(text or "").lower()):
            cleaned = word.strip(".,")
            if not cleaned or cleaned in stopwords:
                continue
            terms.add(aliases.get(cleaned, cleaned))
        return terms

    def _visual_props_for_arc(
        self,
        section: dict[str, Any],
        arc: dict[str, Any],
        concept: dict[str, str],
    ) -> dict[str, Any]:
        text = str(section.get("text") or "")
        concept_name = str(concept.get("concept") or "Money Change").strip()
        visual_type = str(arc.get("visual_type") or "concept").strip()
        start_state = str(arc.get("start_state") or "").strip()
        process = str(arc.get("process") or "").strip()
        end_state = str(arc.get("end_state") or "").strip()
        rate = str(arc.get("rate") or "").strip()
        punch = str(arc.get("punch") or concept_name).strip()
        values = [str(value).strip() for value in arc.get("numeric_values") or [] if str(value).strip()]

        if visual_type == "comparison" or arc.get("has_comparison"):
            left, right = self._comparison_pair(text, start_state, end_state, concept_name)
            return {
                "title": self._short_visual_text(concept_name),
                "left": {"label": left},
                "right": {"label": right},
                "connector": "vs",
            }
        if visual_type == "growth":
            return {
                "title": self._short_visual_text(concept_name),
                "start": start_state or (values[0] if values else "Start"),
                "end": end_state or (values[-1] if values else punch),
                "rate": rate or process,
                "curve": "up",
            }
        if visual_type in {"balance_decay", "pressure"}:
            left_value = self._percent_from_text(rate or text) or 65
            return {
                "title": self._short_visual_text(concept_name),
                "left": {"label": self._balance_left_label(text), "value": left_value, "color": "#E63946"},
                "right": {"label": "leftover", "value": max(0, 100 - left_value), "color": "#2EC4B6"},
                "nodes": self._flow_nodes(values, start_state, process, end_state, punch, text),
            }
        return {
            "title": self._short_visual_text(concept_name if concept_name != "Money Change" else self._flow_title(text)),
            "nodes": self._flow_nodes(values, start_state, process, end_state, punch, text),
        }

    def _flow_nodes(
        self,
        values: list[str],
        start_state: str,
        process: str,
        end_state: str,
        punch: str,
        text: str,
    ) -> list[dict[str, str]]:
        if values:
            nodes = []
            labels = ["start", "cost", "result"]
            for index, value in enumerate(values[:4]):
                subtext = self._value_subtext(value)
                if not ("₹" in value or "%" in value or subtext):
                    continue
                nodes.append({"label": subtext or (labels[index] if index < len(labels) else "value"), "value": self._strip_value_label(value), "subtext": subtext})
            if len(nodes) >= 2:
                return nodes
        candidates = [
            ("salary", "Salary", start_state),
            ("emi", "EMI", process),
            ("rent", "Rent", ""),
            ("spending", "Lifestyle", process),
            ("expense", "Expenses", process),
            ("saving", "Savings", end_state),
            ("sip", "SIP", end_state),
            ("debt", "Debt", start_state),
            ("interest", "Interest", process),
        ]
        lowered = text.lower()
        nodes: list[dict[str, str]] = []
        for token, label, value in candidates:
            if token in lowered and label.lower() not in {node["label"].lower() for node in nodes}:
                nodes.append({"label": label, "value": self._strip_value_label(value) or "", "subtext": self._short_visual_text(value)})
            if len(nodes) >= 4:
                break
        if len(nodes) < 2:
            if "salary" in text.lower():
                return [
                    {"label": "Salary", "value": self._strip_value_label(start_state), "subtext": self._value_subtext(start_state)},
                    {"label": "EMI + rent", "value": "", "subtext": "fixed costs"},
                    {"label": "Lifestyle", "value": "", "subtext": "daily leaks"},
                    {"label": "Left", "value": self._strip_value_label(end_state), "subtext": "month-end reality"},
                ]
            nodes = [
                {"label": self._short_visual_text(start_state or "Start"), "value": self._strip_value_label(start_state), "subtext": self._value_subtext(start_state)},
                {"label": self._short_visual_text(process or "Change"), "value": self._strip_value_label(process), "subtext": self._value_subtext(process)},
                {"label": self._short_visual_text(end_state or punch or "Result"), "value": self._strip_value_label(end_state), "subtext": self._value_subtext(end_state)},
            ]
        return [node for node in nodes if str(node.get("label") or node.get("value") or "").strip()][:4]

    def _comparison_pair(self, text: str, start_state: str, end_state: str, concept_name: str) -> tuple[str, str]:
        lowered = text.lower()
        if " vs " in lowered:
            parts = re.split(r"\bvs\b|\bversus\b", text, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                return self._short_visual_text(parts[0]), self._short_visual_text(parts[1])
        if start_state and end_state:
            return self._short_visual_text(start_state), self._short_visual_text(end_state)
        if "before" in lowered and "after" in lowered:
            return "Before", "After"
        if "saving" in lowered and "spending" in lowered:
            return "Saving", "Spending"
        if "fd" in lowered and ("mutual" in lowered or "sip" in lowered):
            return "FD", "Mutual Fund"
        return "Before", self._short_visual_text(concept_name or "After")

    def _percent_from_text(self, text: str) -> int | None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", str(text or ""))
        if not match:
            return None
        return max(0, min(100, int(round(float(match.group(1))))))

    def _balance_left_label(self, text: str) -> str:
        lowered = text.lower()
        if "emi" in lowered:
            return "EMIs"
        if "debt" in lowered:
            return "debt pressure"
        if "rent" in lowered:
            return "fixed costs"
        return "money out"

    def _flow_title(self, text: str) -> str:
        lowered = text.lower()
        if "salary" in lowered:
            return "Where salary goes"
        if "emi" in lowered:
            return "EMI pressure"
        if "debt" in lowered:
            return "Debt flow"
        return "Money movement"

    def _visual_type_for_section(
        self,
        section: dict[str, Any],
        concept_type: str,
        numeric_phrases: list[str],
        rate: str,
    ) -> str:
        lowered = str(section.get("text") or "").lower()
        if "salary" in lowered and any(token in lowered for token in ("vanish", "disappear", "gone", "drain", "left")):
            return "money_flow"
        if concept_type == "comparison" or section.get("has_comparison"):
            return "comparison"
        if concept_type == "growth":
            return "growth"
        if (
            concept_type == "risk"
            and (numeric_phrases or rate)
            and any(token in lowered for token in ("debt", "interest", "minimum", "trap"))
        ):
            return "balance_decay"
        if numeric_phrases and rate:
            return "money_flow"
        if concept_type == "risk":
            return "pressure"
        if section.get("has_causation"):
            return "money_flow"
        return "concept"

    def _semantic_visual_pattern(self, visual_type: str, concept_name: str) -> str:
        lowered = concept_name.lower()
        if visual_type == "balance_decay" and ("debt" in lowered or "interest" in lowered):
            return "debt_growth_spiral"
        if visual_type == "balance_decay":
            return "balance_decay"
        if visual_type == "growth":
            return "growth_curve"
        if visual_type == "comparison":
            return "comparison_split"
        if visual_type == "money_flow":
            return "money_flow"
        if visual_type == "pressure":
            return "pressure_build"
        return "concept_focus"

    def _render_pattern_for_visual_type(self, visual_type: str, concept_type: str) -> str:
        if visual_type in {"balance_decay", "money_flow"}:
            return "NumericComparison"
        if visual_type == "comparison":
            return "SplitComparison"
        if visual_type == "growth":
            return "GrowthChart"
        if visual_type == "pressure":
            return "RiskCard"
        return {
            "risk": "RiskCard",
            "growth": "GrowthChart",
            "comparison": "SplitComparison",
            "process": "StepFlow",
            "definition": "ConceptCard",
        }.get(concept_type, "ConceptCard")

    def _data_for_render_pattern(
        self,
        pattern: str,
        concept: dict[str, str],
        arc: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        concept_name = str(concept.get("concept") or "Money Change")
        if pattern == "RiskCard":
            return {"title": concept_name.upper()}
        if pattern == "GrowthChart":
            return {
                "start": str(arc.get("start_state") or fallback.get("start") or ""),
                "end": str(arc.get("end_state") or concept_name),
                "curve": "up",
            }
        if pattern == "SplitComparison":
            return fallback if fallback else {"left": {"label": "Before"}, "right": {"label": concept_name}}
        if pattern == "StepFlow":
            steps = [value for value in (arc.get("start_state"), arc.get("process"), arc.get("end_state")) if str(value or "").strip()]
            return {"steps": steps or [concept_name]}
        return fallback if fallback else {"title": concept_name.upper()}

    def _state_from_narrative_arc(self, arc: dict[str, Any]) -> dict[str, str]:
        return {
            "money_in": str(arc.get("start_state") or ""),
            "money_out": str(arc.get("rate") or arc.get("process") or ""),
            "balance_change": str(arc.get("end_state") or arc.get("punch") or ""),
        }

    def _rate_value(self, finance_concept: dict[str, Any], numeric_phrases: list[str]) -> str:
        percentage = finance_concept.get("percentage")
        if percentage is not None:
            try:
                return f"{float(percentage):g}%"
            except (TypeError, ValueError):
                pass
        for phrase in numeric_phrases:
            if "%" in phrase:
                return phrase
        return ""

    def _visual_state_value(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if "₹" in text or "%" in text or text.lower().startswith("rs"):
            return text
        if self._value_subtext(text):
            return text
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            return ""
        return text

    def _arc_process(self, finance_concept: dict[str, Any], text: str, rate: str) -> str:
        action = str(finance_concept.get("action") or "").strip()
        lowered = text.lower()
        if "salary" in lowered and any(token in lowered for token in ("vanish", "disappear", "gone", "drain", "left")):
            return "Salary drains"
        if "emi" in lowered:
            return "EMI pressure"
        if rate and "interest" in lowered:
            return f"{rate} interest"
        if rate:
            return rate
        if action and action != "changes":
            return action
        if "inflation" in lowered:
            return "Inflation erodes"
        if "spending" in lowered or "expense" in lowered:
            return "Spending leaks"
        if "invest" in lowered or "sip" in lowered:
            return "Investment grows"
        return "Money changes"

    def _story_goal(self, concept_name: str, start_state: str, process: str, end_state: str) -> str:
        pieces = [piece for piece in (start_state, process, end_state) if piece]
        if pieces:
            return f"Show {concept_name}: {' -> '.join(pieces)}"
        return f"Show {concept_name}"

    def _arc_punch(self, text: str, concept_name: str) -> str:
        lowered = text.lower()
        if "debt" in lowered and "interest" in lowered:
            return "Paying to be broke"
        if "salary" in lowered and any(token in lowered for token in ("gone", "vanish", "disappear", "leak")):
            return "Salary disappears early"
        if "inflation" in lowered:
            return "Money loses power"
        if "compound" in lowered or "compounding" in lowered:
            return "Time does the work"
        if "fomo" in lowered:
            return "FOMO is expensive"
        return concept_name

    def _split_story_sentences(self, text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
        return [part.strip() for part in parts if part.strip()]

    def _sentence_starts_new_section(self, sentence: str) -> bool:
        lowered = sentence.lower().strip()
        if any(lowered.startswith(token) for token in ("but", "however", "so", "now", "because", "this means")):
            return True
        return len(sentence.split()) > 15

    def _keep_story_sentence(self, sentence: str, allow_short: bool = False) -> bool:
        lowered = sentence.lower().strip()
        if len(sentence.split()) < 6 and not allow_short:
            finance_short_tokens = (
                "debt",
                "credit",
                "interest",
                "salary",
                "lifestyle",
                "upgrade",
                "upgrades",
                "buy",
                "broke",
                "income",
                "expense",
                "expenses",
                "spending",
                "savings",
                "investment",
                "inflation",
                "budget",
                "fund",
                "payment",
                "trap",
                "risk",
                "wealth",
                "tax",
            )
            if not re.search(r"₹|%|\d+", sentence) and not any(token in lowered for token in finance_short_tokens):
                return False
        if any(phrase in lowered for phrase in ("for instance", "let's", "we've all", "you know")):
            return False
        return True

    def _normalize_text(self, text: str) -> str:
        return " ".join(str(text or "").strip().split())

    def _shares_topic_with_current(self, current: list[str], next_sentence: str) -> bool:
        if not next_sentence:
            return False
        current_terms = self._topic_terms(" ".join(current))
        next_terms = self._topic_terms(next_sentence)
        return bool(current_terms.intersection(next_terms))

    def _topic_terms(self, text: str) -> set[str]:
        keywords = {
            "debt",
            "credit",
            "payment",
            "minimum",
            "interest",
            "inflation",
            "savings",
            "investment",
            "returns",
            "budget",
            "budgeting",
            "income",
            "fund",
            "loan",
            "emi",
            "sip",
            "trap",
            "risk",
        }
        return {word for word in re.findall(r"[a-z]+", text.lower()) if word in keywords}

    def _section_word_count(self, section: list[str]) -> int:
        return len(" ".join(section).split())

    def _merge_short_sections(self, groups: list[list[str]]) -> list[list[str]]:
        merged: list[list[str]] = []
        index = 0
        while index < len(groups):
            current = list(groups[index])
            next_group = groups[index + 1] if index + 1 < len(groups) else None
            if (
                self._section_word_count(current) < 8
                and next_group is not None
                and self._can_merge_short_sections(current, next_group)
            ):
                current.extend(groups[index + 1])
                index += 1
            merged.append(current)
            index += 1
        return merged

    def _can_merge_short_sections(self, current: list[str], next_group: list[str]) -> bool:
        current_text = " ".join(current)
        next_text = " ".join(next_group)
        current_terms = self._topic_terms(current_text)
        next_terms = self._topic_terms(next_text)
        if current_terms and next_terms:
            return True
        return bool(current_terms.intersection(next_terms))

    def _unique_beat_values(self, values: list[str], strongest: str) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not value.strip():
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(value)
        if strongest.strip() and strongest.lower() not in seen:
            unique.append(strongest)
        return unique[:3]

    def _is_financial_number(self, text: str, token: str, start: int, end: int) -> bool:
        if "₹" in token or "%" in token or token.lower().startswith("rs"):
            return True
        trailing = text[end : min(len(text), end + 2)].lower()
        if trailing.startswith("s"):
            return False
        before_words = re.findall(r"[a-z]+", text[max(0, start - 24) : start].lower())
        after_words = re.findall(r"[a-z]+", text[end : min(len(text), end + 24)].lower())
        if any(word in {"day", "days", "age", "aged", "year", "years"} for word in before_words[-2:]):
            return False
        if any(word in {"day", "days"} for word in after_words[:2]):
            return False
        if any(word in FINANCIAL_NUMBER_KEYWORDS for word in after_words[:4]):
            return True
        if any(word in FINANCIAL_NUMBER_KEYWORDS for word in before_words[-2:]):
            return True
        return False

    def _numeric_label(self, text: str, start: int, end: int) -> str:
        before_words = re.findall(r"[a-z]+", text[max(0, start - 40) : start].lower())
        after_words = re.findall(r"[a-z]+", text[end : min(len(text), end + 40)].lower())
        keywords = {
            "interest": "interest",
            "bill": "bill",
            "balance": "balance",
            "debt": "debt",
            "payment": "payment",
            "salary": "salary",
            "return": "return",
            "returns": "returns",
            "cost": "cost",
            "emi": "emi",
            "principal": "principal",
            "minimum": "payment",
            "due": "payment",
            "leak": "leak",
            "lost": "lost",
            "wasted": "wasted",
            "waste": "wasted",
        }
        for word in after_words[:5]:
            if word in keywords:
                return keywords[word]
        for word in reversed(before_words[-5:]):
            if word in keywords:
                return keywords[word]
        impact = self._numeric_impact_label(text)
        if impact:
            return impact
        return ""

    def _numeric_impact_label(self, text: str) -> str:
        lowered = text.lower()
        if "interest" in lowered:
            return "interest"
        if any(token in lowered for token in ("leak", "leaks")):
            return "leak"
        if any(token in lowered for token in ("lost", "lose", "loss")):
            return "lost"
        if any(token in lowered for token in ("wasted", "waste")):
            return "wasted"
        if "cost" in lowered:
            return "cost"
        return ""

    def _numeric_beats(self, numeric_phrases: list[str], strongest: str) -> list[dict[str, Any]]:
        values = self._unique_beat_values(numeric_phrases, strongest)
        calculation = self._calculation_from_values(values)
        if calculation:
            beats: list[dict[str, Any]] = [
                {"component": "StatCard", "text": values[0], "subtext": self._value_subtext(values[0])},
            ]
            if calculation["rate"]:
                beats.append({"component": "StatCard", "text": calculation["rate"], "subtext": "rate"})
            beats.append(
                {
                    "component": "CalculationStrip",
                    "text": calculation["text"],
                    "steps": calculation["steps"],
                }
            )
            beats.append({"component": "StatCard", "text": calculation["result"], "subtext": self._value_subtext(calculation["result"])})
            return beats
        if len(values) == 2:
            return [
                {"component": "StatCard", "text": values[0], "subtext": self._value_subtext(values[0])},
                {"component": "FlowBar", "text": values[1], "subtext": self._value_subtext(values[1])},
            ]
        if len(values) >= 3:
            return [
                {"component": "StatCard", "text": values[0], "subtext": self._value_subtext(values[0])},
                {"component": "FlowBar", "text": values[1], "subtext": self._value_subtext(values[1])},
                {"component": "StatCard", "text": values[2], "subtext": self._value_subtext(values[2])},
            ]
        return (
            [{"component": "StatCard", "text": values[0], "subtext": self._value_subtext(values[0])}]
            if values
            else [{"component": "StatCard", "text": strongest}]
        )

    def _calculation_from_values(self, values: list[str]) -> dict[str, Any] | None:
        if len(values) < 2:
            return None
        money_values = [value for value in values if "₹" in value or value.lower().startswith("rs")]
        rate_values = [value for value in values if "%" in value]
        if not money_values or not rate_values:
            return None
        base = money_values[0]
        rate = rate_values[0]
        result = money_values[-1] if len(money_values) > 1 else ""
        if not result or result == base:
            estimated = self._estimated_rate_result(base, rate)
            if not estimated:
                return None
            result = estimated
        text = f"{self._strip_value_label(base)} x {self._strip_value_label(rate)} = {self._strip_value_label(result)}"
        return {
            "text": text,
            "rate": rate,
            "result": result,
            "steps": [
                {"label": self._value_subtext(base) or "Amount", "value": self._strip_value_label(base)},
                {"label": self._value_subtext(rate) or "Rate", "value": self._strip_value_label(rate), "operation": "x"},
                {"label": self._value_subtext(result) or "Cost", "value": self._strip_value_label(result), "operation": "="},
            ],
        }

    def _estimated_rate_result(self, base: str, rate: str) -> str:
        base_number = self._numeric_amount(base)
        rate_number = self._numeric_amount(rate)
        if base_number is None or rate_number is None or "%" not in rate:
            return ""
        result = base_number * rate_number / 100
        return self._format_rupee_amount(result)

    def _numeric_amount(self, value: str) -> float | None:
        cleaned = re.sub(r"[^\d.]", "", value)
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _format_rupee_amount(self, amount: float) -> str:
        rounded = int(round(amount))
        digits = str(rounded)
        if len(digits) <= 3:
            grouped = digits
        else:
            grouped = digits[-3:]
            digits = digits[:-3]
            while digits:
                grouped = digits[-2:] + "," + grouped
                digits = digits[:-2]
        return f"₹{grouped}"

    def _strip_value_label(self, value: str) -> str:
        parts = str(value or "").split()
        if not parts:
            return ""
        if re.search(r"₹|%|\d", parts[0]):
            return parts[0]
        return str(value or "").strip()

    def _value_subtext(self, value: str) -> str:
        parts = str(value or "").split()
        if len(parts) <= 1:
            return ""
        return self._short_visual_text(" ".join(parts[1:]))

    def _short_visual_text(self, text: str) -> str:
        words = [word.strip(" ,.-") for word in str(text or "").split() if word.strip(" ,.-")]
        if not words:
            return ""
        return " ".join(words[:5])

    def _numeric_visual_allowed(self, text: str, numeric_phrases: list[str]) -> bool:
        if not numeric_phrases:
            return False
        lowered = text.lower()
        has_comparison = any(word in lowered for word in (" more ", " less ", " vs ", " versus "))
        has_transformation = any(word in lowered for word in (" increase", " increases", " reduce", " reduces", " grow", " grows "))
        if len(numeric_phrases) >= 2:
            return True
        return has_comparison or has_transformation

    def _is_valid_visual_item(self, item: dict[str, Any] | None) -> bool:
        if not item:
            return False
        visual = item.get("visual") or {}
        pattern = str(visual.get("pattern") or "").strip()
        data = visual.get("data") or {}
        if not pattern:
            return False
        if not isinstance(data, dict) or not data:
            return False
        if "title" in data and not str(data.get("title", "")).strip():
            return False
        if "values" in data and not [value for value in data.get("values") or [] if str(value).strip()]:
            return False
        beats = (item.get("beats") or {}).get("beats") or []
        if not beats:
            return False
        if any(not self._is_valid_beat(beat) for beat in beats):
            return False
        concept_text = str((item.get("concept") or {}).get("concept", "")).strip()
        if not concept_text:
            return False
        return True

    def _is_valid_beat(self, beat: dict[str, Any]) -> bool:
        if not isinstance(beat, dict):
            return False
        component = str(beat.get("component") or "").strip()
        beat_text = str(beat.get("text") or "").strip()
        steps = beat.get("steps") or []
        if not component:
            return False
        if component == "CalculationStrip" and self._valid_calculation_steps(steps):
            return True
        if not beat_text:
            return False
        lowered = beat_text.lower()
        fragment_starters = (
            "as soon",
            "we love",
            "the fact",
            "it is",
            "this is",
            "there are",
            "we have",
            "you know",
            "for the",
            "in the",
            "of the",
            "and the",
            "because",
            "which",
        )
        if any(lowered.startswith(fragment) for fragment in fragment_starters):
            return False
        if len(beat_text.split()) > 5:
            return False
        return True

    def _valid_calculation_steps(self, steps: Any) -> bool:
        if not isinstance(steps, list) or len(steps) < 2:
            return False
        for step in steps:
            if not isinstance(step, dict):
                return False
            if not str(step.get("label") or "").strip():
                return False
            if not str(step.get("value") or "").strip():
                return False
        return True
