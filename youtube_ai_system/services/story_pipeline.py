from __future__ import annotations

from typing import Any

from ..pipelines.story import CONCEPT_PRIORITY, FINANCIAL_NUMBER_KEYWORDS, StoryGroupPayloadHelper, StoryPlanningSupportMixin
from .finance_concept_extractor import FinanceConceptExtractor
from .financial_governance import apply_concept_policy, scene_density_report
from .idea_grouper import IdeaGrouper
from .run_log import RunLogger
from .semantic_scene_contract import SemanticSceneContractExtractor
from .story_intelligence_engine import StoryIntelligenceEngine
from .visual_action_graph import VisualActionGraphBuilder
from .visual_beat_expander import VisualBeatExpander
from .visual_director import VisualDirector, visual_director_input_from_section
from .visual_event_sequence import VisualEventSequenceBuilder
from .visual_scene_normalizer import KNOWN_MECHANISMS, MECHANISM_ALIASES, VisualSceneNormalizer
from .visual_story_engine import VisualStoryEngine
from .scene_debug import SceneDebugTrace, confidence_for_finance_concept, stable_hash


class StoryPipeline(StoryPlanningSupportMixin):
    SCRIPT_MECHANISM_OVERRIDES = {
        "affordability_illusion",
        "payment_pain_reduction",
        "price_anchoring",
        "anchoring",
        "commitment_stacking",
        "cash_flow_squeeze",
        "delayed_consequence",
        "leverage",
        "opportunity_cost",
        "compounding",
        "liquidity_pressure",
        "emi_pressure",
        "lifestyle_inflation",
    }

    def __init__(
        self,
        story_intelligence: StoryIntelligenceEngine | None = None,
        idea_grouper: IdeaGrouper | None = None,
        finance_concept_extractor: FinanceConceptExtractor | None = None,
        visual_director: VisualDirector | None = None,
        visual_scene_normalizer: VisualSceneNormalizer | None = None,
        visual_beat_expander: VisualBeatExpander | None = None,
        visual_story_engine: VisualStoryEngine | None = None,
        semantic_contract_extractor: SemanticSceneContractExtractor | None = None,
        visual_action_graph_builder: VisualActionGraphBuilder | None = None,
        visual_event_sequence_builder: VisualEventSequenceBuilder | None = None,
        logger: RunLogger | None = None,
    ) -> None:
        self.story_intelligence = story_intelligence or StoryIntelligenceEngine()
        self.idea_grouper = idea_grouper or IdeaGrouper()
        self.finance_concept_extractor = finance_concept_extractor or FinanceConceptExtractor()
        self.visual_director = visual_director or VisualDirector()
        self.visual_scene_normalizer = visual_scene_normalizer or VisualSceneNormalizer()
        self.visual_beat_expander = visual_beat_expander or VisualBeatExpander()
        self.visual_story_engine = visual_story_engine or VisualStoryEngine()
        self.semantic_contract_extractor = semantic_contract_extractor or SemanticSceneContractExtractor()
        self.visual_action_graph_builder = visual_action_graph_builder or VisualActionGraphBuilder()
        self.visual_event_sequence_builder = visual_event_sequence_builder or VisualEventSequenceBuilder()
        self.logger = logger or RunLogger()
        self.group_payload_helper = StoryGroupPayloadHelper()

    def build_story_plan(self, payload: dict[str, Any], debug_trace: SceneDebugTrace | None = None) -> dict[str, Any]:
        planning_payload = self.group_payload_for_story_plan(payload)
        story_plan = self.story_plan_from_idea_groups(planning_payload)
        story_plan = self.attach_visual_scene_contract(story_plan, debug_trace=debug_trace)
        story_plan = self.attach_section_concepts(story_plan, debug_trace=debug_trace)
        story_plan = self.attach_section_narrative_arc(story_plan, debug_trace=debug_trace)
        story_plan = self.attach_visual_story(story_plan)
        story_plan = self.attach_section_visual_plan(story_plan, debug_trace=debug_trace)
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
                    record = self.group_payload_helper.group_record(
                        combined_text,
                        idea_group_id=f"idea_{len(grouped_scenes):02d}",
                        idea_type=str(visual_scene_source.get("mechanism") or scene.get("idea_type") or "emphasis"),
                        visual_scene=visual_scene_source,
                    )
                    record["preserve_order"] = True
                    record["source_scene_index"] = len(grouped_scenes)
                    grouped_scenes.append(record)
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
                        self.group_payload_helper.group_record(
                            combined_text,
                            idea_group_id=f"idea_{len(grouped_scenes):02d}",
                        )
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
        return self.group_payload_helper.visual_scene_source(scene)

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
                    "preserve_order": bool(scene.get("preserve_order")),
                    "source_scene_index": scene.get("source_scene_index"),
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
                    "has_numbers": self.group_payload_helper.has_numbers(hook_text),
                    "has_comparison": self.group_payload_helper.has_comparison(hook_text),
                    "has_causation": self.group_payload_helper.has_causation(hook_text),
                },
            )

        preserve_script_order = any(section.get("preserve_order") and isinstance(section.get("visual_scene"), dict) for section in sections)
        sections = self.story_intelligence._ensure_section_progression(sections)
        if not preserve_script_order:
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

    def attach_visual_scene_contract(self, story_plan: dict[str, Any], debug_trace: SceneDebugTrace | None = None) -> dict[str, Any]:
        sections = story_plan.get("sections") or []
        story_plan["sections"] = [
            self.visual_scene_normalizer.inject_into_section(section, index, debug_trace=debug_trace)
            for index, section in enumerate(sections)
        ]
        return story_plan

    def attach_section_concepts(self, story_plan: dict[str, Any], debug_trace: SceneDebugTrace | None = None) -> dict[str, Any]:
        sections = story_plan.get("sections") or []
        for section_index, section in enumerate(sections):
            concepts: list[dict[str, str]] = []
            seen: set[tuple[str, str]] = set()
            trusted_mechanism = self._trusted_script_mechanism(section)
            finance_concept = self.finance_concept_extractor.extract(
                {
                    "combined_text": str(section.get("text") or ""),
                    "dominant_entity": str(section.get("dominant_entity") or "money"),
                    "idea_type": str(section.get("idea_type") or "emphasis"),
                }
            )
            concept_name = finance_concept.concept_name
            concept_type = finance_concept.concept_type
            concept_confidence = finance_concept.confidence
            concept_policy = finance_concept.concept_policy or {}
            if trusted_mechanism:
                concept_type = trusted_mechanism
                concept_name = self._display_mechanism_name(trusted_mechanism)
                concept_confidence = max(float(concept_confidence or 0.0), 0.92)
                concept_policy = apply_concept_policy(trusted_mechanism, str(section.get("text") or ""), {})
                section["concept_type"] = trusted_mechanism
            section["finance_concept"] = {
                "concept_name": concept_name,
                "concept_type": concept_type,
                "primary_entity": finance_concept.primary_entity,
                "action": finance_concept.action,
                "start_value": finance_concept.start_value,
                "end_value": finance_concept.end_value,
                "percentage": finance_concept.percentage,
                "time_period": finance_concept.time_period,
                "agent": finance_concept.agent,
                "victim": finance_concept.victim,
                "confidence": concept_confidence,
                "numeric_facts": finance_concept.numeric_facts or [],
                "concept_policy": concept_policy,
            }
            if trusted_mechanism:
                section["finance_concept"]["source"] = "script_brief_scene_mechanism"
            section["semantic_scene"] = self.semantic_contract_extractor.extract_dict(
                section,
                section["finance_concept"],
                scene_id=str(section.get("idea_group_id") or f"section_{section_index}"),
            )
            section["visual_action_graph"] = self.visual_action_graph_builder.build_dict(section["semantic_scene"])
            section["visual_event_sequence"] = self.visual_event_sequence_builder.build_dict(section)
            concept = concept_name if concept_name != "Unknown" else None
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
            if debug_trace:
                score, reasons = confidence_for_finance_concept(section["finance_concept"])
                concept_id = f"concept:{section.get('idea_group_id') or len(debug_trace.data.get('confidence') or [])}:{concept_type}"
                debug_trace.snapshot("story_pipeline_post_classification", section, owner="story_pipeline")
                debug_trace.snapshot("semantic_scene_contract", section["semantic_scene"], owner="semantic_scene_contract")
                debug_trace.snapshot("visual_action_graph", section["visual_action_graph"], owner="visual_action_graph")
                debug_trace.snapshot("visual_event_sequence", section["visual_event_sequence"], owner="visual_event_sequence")
                debug_trace.ownership("semantic_scene", "semantic_scene_contract", section["semantic_scene"], "central semantic contract extracted from narration and finance concept")
                debug_trace.ownership("visual_action_graph", "visual_action_graph", section["visual_action_graph"], "action graph derived from SemanticSceneContract")
                debug_trace.ownership("visual_event_sequence", "visual_event_sequence", section["visual_event_sequence"], "renderer-facing perceptual event sequence derived from VisualActionGraph")
                debug_trace.ownership("concept_type", "story_pipeline", concept_type, "script mechanism override" if trusted_mechanism else "finance concept extraction")
                debug_trace.confidence("story_pipeline", "concept_type", concept_type, score, reasons)
                debug_trace.lineage_node(
                    concept_id,
                    "concept",
                    "story_pipeline",
                    concept_name,
                    section["finance_concept"],
                    owner="story_pipeline",
                    confidence=score,
                    source_ids=[f"mechanism:0:{section.get('mechanism') or section.get('idea_type') or ''}"],
                )
                debug_trace.lineage_edge(
                    f"mechanism:0:{section.get('mechanism') or section.get('idea_type') or ''}",
                    concept_id,
                    "concept_selected_from_finance_extractor",
                )
                debug_trace.determinism("story_pipeline_classification", section.get("text"), section["finance_concept"])
        story_plan["agenda"] = self.agenda_from_top_concepts(sections)
        return story_plan

    def _trusted_script_mechanism(self, section: dict[str, Any]) -> str:
        """Trust mechanisms carried by generated ScriptBrief scenes, not stale DB visual scenes."""
        mechanism_source = str(section.get("mechanism_source") or "").strip()
        if mechanism_source and mechanism_source not in {"explicit_section", "explicit_visual_scene"}:
            return ""
        for key in ("mechanism", "idea_type"):
            mechanism = self._canonical_mechanism(section.get(key))
            if mechanism in self.SCRIPT_MECHANISM_OVERRIDES:
                return mechanism
        return ""

    def _canonical_mechanism(self, value: Any) -> str:
        mechanism = str(value or "").strip().lower()
        alias_map = {key: target for key, target in MECHANISM_ALIASES.items() if key != "tax_drain"}
        mechanism = alias_map.get(mechanism, mechanism)
        return mechanism if mechanism in KNOWN_MECHANISMS and mechanism != "definition" else ""

    def _display_mechanism_name(self, mechanism: str) -> str:
        return {
            "affordability_illusion": "Affordability Illusion",
            "payment_pain_reduction": "Payment Pain Reduction",
            "price_anchoring": "Price Anchoring",
            "anchoring": "Anchoring",
            "commitment_stacking": "Commitment Stacking",
            "cash_flow_squeeze": "Cash Flow Squeeze",
            "delayed_consequence": "Delayed Consequence",
            "leverage": "Leverage",
            "opportunity_cost": "Opportunity Cost",
            "compounding": "Compounding",
            "liquidity_pressure": "Liquidity Pressure",
            "emi_pressure": "EMI Pressure",
            "lifestyle_inflation": "Lifestyle Inflation",
        }.get(mechanism, mechanism.replace("_", " ").title())

    def attach_section_narrative_arc(self, story_plan: dict[str, Any], debug_trace: SceneDebugTrace | None = None) -> dict[str, Any]:
        sections = story_plan.get("sections") or []
        for section in sections:
            arc = self._narrative_arc_for_section(section)
            section["narrative_arc"] = arc
            section["visual_type"] = arc.get("visual_type") or "concept"
            section["state"] = self._state_from_narrative_arc(arc)
            if debug_trace:
                policy = apply_concept_policy(str(section.get("concept_type") or (section.get("visual_scene") or {}).get("mechanism") or ""), str(section.get("text") or ""), section.get("finance_concept") or {})
                debug_trace.data["concept_policy"] = policy
                debug_trace.data["scene_density"] = scene_density_report(section)
                debug_trace.snapshot("story_pipeline_post_narrative_arc", section, owner="story_pipeline")
        return story_plan

    def attach_visual_story(self, story_plan: dict[str, Any]) -> dict[str, Any]:
        return self.visual_story_engine.attach_visual_story(story_plan)

    def attach_section_visual_plan(self, story_plan: dict[str, Any], debug_trace: SceneDebugTrace | None = None) -> dict[str, Any]:
        sections = story_plan.get("sections") or []
        preceding_concept_type: str | None = None
        total_sections = max(len(sections), 1)
        for index, section in enumerate(sections):
            if "narrative_arc" not in section:
                section["narrative_arc"] = self._narrative_arc_for_section(section)
            section_position = self._section_position(index, total_sections)
            director_input = visual_director_input_from_section(section, section_position, preceding_concept_type)
            if debug_trace:
                debug_trace.snapshot("visual_director_pre", {"section": section, "director_input": director_input}, owner="story_pipeline")
                debug_trace.event(
                    "visual_director",
                    "starting",
                    {"input_hash": stable_hash(director_input), "concept_type": director_input.concept_type},
                )
            directed_plan = None
            try:
                directed_plan = self.visual_director.direct(director_input)
            except Exception as exc:
                self._log_visual_director("failed", str(exc))
                if debug_trace:
                    debug_trace.error("visual_director", str(exc), {"director_input": director_input})

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
                    if debug_trace:
                        debug_trace.fallback(
                            "visual_director",
                            "DirectedPlan.fallback_reason",
                            directed_plan.fallback_reason,
                            director_input,
                            directed_plan.to_visual_plan_item(),
                        )
                old_plan = self._old_visual_plan(section)
                if old_plan:
                    section["visual_plan"] = [old_plan]
                    if debug_trace:
                        debug_trace.fallback("visual_director", "old_visual_plan", "director invalid or fallback plan", director_input, old_plan)
                else:
                    fallback_text = self._short_visual_text(str(section.get("text") or "Core message"))
                    section["visual_plan"] = [
                        {
                            "concept": {"concept": fallback_text, "type": "definition"},
                            "visual": {"pattern": "StatCard", "data": {"title": fallback_text.upper()}},
                            "beats": {"beats": [{"component": "StatCard", "text": fallback_text}]},
                        }
                    ]
                    if debug_trace:
                        debug_trace.fallback("visual_director", "stat_card_definition", "director invalid and no old visual plan", director_input, section["visual_plan"][0])
                section["direction"] = None
                section["theme"] = {}
                section["concept_type"] = str(section.get("idea_type") or "emphasis")
                section.pop("visual_mode", None)
                section.pop("cinematic_intent", None)
            if debug_trace and directed_plan:
                plan_item = directed_plan.to_visual_plan_item()
                debug_trace.snapshot("visual_director_post", {"section": section, "directed_plan": plan_item}, owner="visual_director")
                debug_trace.ownership("visual_plan", "visual_director", section.get("visual_plan"), "director selected visual plan")
                debug_trace.ownership("pattern", "visual_director", plan_item.get("visual", {}).get("pattern"), "director selected pattern")
                debug_trace.ownership("data", "visual_director", plan_item.get("visual", {}).get("data"), "director generated component data")
                debug_trace.ownership("beats", "visual_director", plan_item.get("beats", {}).get("beats"), "director generated beats")
                debug_trace.confidence(
                    "visual_director",
                    "concept_type",
                    directed_plan.concept_type,
                    0.45 if directed_plan.fallback_reason else min(max(float(director_input.confidence or 0.65), 0.55), 0.98),
                    ["director fallback"] if directed_plan.fallback_reason else ["director input confidence", "valid directed plan"],
                )
                plan_id = f"director_plan:{index}:{directed_plan.pattern}"
                debug_trace.lineage_node(
                    plan_id,
                    "director_plan",
                    "visual_director",
                    directed_plan.pattern,
                    plan_item,
                    owner="visual_director",
                    confidence=None if directed_plan.fallback_reason else min(max(float(director_input.confidence or 0.65), 0.55), 0.98),
                    source_ids=[f"concept:{section.get('idea_group_id') or index}:{directed_plan.concept_type}"],
                )
                debug_trace.lineage_edge(f"concept:{section.get('idea_group_id') or index}:{directed_plan.concept_type}", plan_id, "visual_director_plan_from_concept")
                debug_trace.determinism("visual_director", director_input, plan_item)
            self.visual_story_engine.enrich_section_from_visual_plan(
                section,
                dict(story_plan.get("visual_story") or section.get("visual_story") or {}),
            )
            before_expansion = dict(section)
            sections[index] = self.visual_beat_expander.expand_section(section, debug_trace=debug_trace)
            if debug_trace:
                debug_trace.diff("beat_expansion", before_expansion, sections[index])
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
