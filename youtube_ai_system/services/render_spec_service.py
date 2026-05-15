from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts.rendering import RenderSpec
from ..pipelines.rendering import (
    ABSTRACT_VISUAL_WORDS,
    ANIMATION_MAP,
    BEAT_TO_COMPOSITION,
    BasicRenderSpecFactory,
    DURATION_BY_INTENT,
    FLOW_PATTERNS,
    GENERIC_VISUAL_WORDS,
    INTENT_PATTERN_MAP,
    LegacyFlowSpecFactory,
    LegacyFlowStageBuilder,
    LOGIC_TYPE_TO_PATTERN,
    RenderLogicParser,
    RenderBrollResolver,
    RenderCaptionBuilder,
    RenderChartDataExtractor,
    RenderClassifiedContract,
    RenderContextGate,
    RenderContextualLogicBuilder,
    RenderDataRequirementGate,
    RenderEmphasisBuilder,
    RenderFlowHelpers,
    RenderFlowLabelHelper,
    RenderFlowPropsBuilder,
    RenderLogicRepair,
    RenderLogicTextFormatter,
    RenderLogicValidator,
    RenderNarrationLogicBuilder,
    RenderNumberUtils,
    RenderPatternSelector,
    RenderPropsBuilder,
    RenderPropsGate,
    RenderSplitHelpers,
    RenderSpecDispatcher,
    RenderStructuredBeatNormalizer,
    RenderTextUtils,
    RenderValueDeriver,
    RenderVisualGate,
    VALID_COMPONENTS,
    VALID_NODE_ROLES,
    VISUAL_LOGIC_SCHEMA,
)


class RenderSpecService:
    """Maps script-friendly scene fields to deterministic Remotion template props."""

    def __init__(self) -> None:
        self.basic_specs = BasicRenderSpecFactory()
        self.broll_resolver = RenderBrollResolver()
        self.chart_data = RenderChartDataExtractor()
        self.flow_helpers = RenderFlowHelpers()
        self.number_utils = RenderNumberUtils()
        self.flow_labels = RenderFlowLabelHelper(self.number_utils)
        self.classified_contract = RenderClassifiedContract()
        self.logic_repair = RenderLogicRepair()
        self.logic_text = RenderLogicTextFormatter(self.flow_labels)
        self.text_utils = RenderTextUtils()
        self.split_helpers = RenderSplitHelpers(self.text_utils)
        self.caption_builder = RenderCaptionBuilder(text_utils=self.text_utils, flow_labels=self.flow_labels)
        self.value_deriver = RenderValueDeriver(self.number_utils)
        self.narration_logic = RenderNarrationLogicBuilder(
            number_utils=self.number_utils,
            text_utils=self.text_utils,
            value_deriver=self.value_deriver,
        )
        self.contextual_logic = RenderContextualLogicBuilder(
            amount_with_label=self._amount_with_label,
            classify_intent=self.classifyIntent,
            concrete_fallback_logic=self._concrete_fallback_logic,
            derived_rupee=self._derived_rupee,
            fallback_numeric_flow=self._fallback_numeric_flow,
            first_numeric_value=self._first_numeric_value,
            inflation_output=self._inflation_output,
            logic_from_classified_intent=self._logic_from_classified_intent,
            money_tokens=self._money_tokens,
            minimal_narration_flow=self._minimal_narration_flow,
            percent_tokens=self._percent_tokens,
            string_visual_logic_to_object=self._string_visual_logic_to_object,
            typed_visual_logic_is_valid=self._typed_visual_logic_is_valid,
        )
        self.legacy_flow_stages = LegacyFlowStageBuilder(
            flow_helpers=self.flow_helpers,
            number_utils=self.number_utils,
            value_deriver=self.value_deriver,
        )
        self.legacy_flow_specs = LegacyFlowSpecFactory(self)
        self.context_gate = RenderContextGate(self.number_utils)
        self.visual_gate = RenderVisualGate(
            abstract_visual_words=self.ABSTRACT_VISUAL_WORDS,
            generic_visual_words=self.GENERIC_VISUAL_WORDS,
            number_utils=self.number_utils,
        )
        self.logic_parser = RenderLogicParser(
            is_abstract_visual_logic=self._is_abstract_visual_logic,
            numbers_respect_context=self._numbers_respect_context,
            has_number=self._has_number,
        )
        self.flow_props_builder = RenderFlowPropsBuilder(
            flow_helpers=self.flow_helpers,
            flow_labels=self.flow_labels,
            text_utils=self.text_utils,
            visual_gate=self.visual_gate,
        )
        self.props_builder = RenderPropsBuilder(
            chart_data=self.chart_data,
            flow_labels=self.flow_labels,
            flow_props=self.flow_props_builder,
            split_helpers=self.split_helpers,
            text_utils=self.text_utils,
            visual_gate=self.visual_gate,
        )
        self.props_gate = RenderPropsGate(self.visual_gate)
        self.emphasis_builder = RenderEmphasisBuilder(
            text_utils=self.text_utils,
            visual_gate=self.visual_gate,
        )
        self.logic_validator = RenderLogicValidator(
            self.VISUAL_LOGIC_SCHEMA,
            context_gate=self.context_gate,
            logic_text=self.logic_text,
            visual_gate=self.visual_gate,
        )
        self.data_requirements = RenderDataRequirementGate(
            flow_patterns=self.FLOW_PATTERNS,
            chart_data=self.chart_data,
            visual_gate=self.visual_gate,
        )
        self.pattern_selector = RenderPatternSelector(
            intent_pattern_map=self.INTENT_PATTERN_MAP,
            flow_patterns=self.FLOW_PATTERNS,
            duration_by_intent=self.DURATION_BY_INTENT,
            animation_map=self.ANIMATION_MAP,
        )
        self.structured_normalizer = RenderStructuredBeatNormalizer(self)
        self.spec_dispatcher = RenderSpecDispatcher(self)

    INTENT_PATTERN_MAP = INTENT_PATTERN_MAP
    DURATION_BY_INTENT = DURATION_BY_INTENT
    ANIMATION_MAP = ANIMATION_MAP
    VISUAL_LOGIC_SCHEMA = VISUAL_LOGIC_SCHEMA
    LOGIC_TYPE_TO_PATTERN = LOGIC_TYPE_TO_PATTERN
    FLOW_PATTERNS = FLOW_PATTERNS
    VALID_COMPONENTS = VALID_COMPONENTS
    VALID_NODE_ROLES = VALID_NODE_ROLES
    ABSTRACT_VISUAL_WORDS = ABSTRACT_VISUAL_WORDS
    GENERIC_VISUAL_WORDS = GENERIC_VISUAL_WORDS
    BEAT_TO_COMPOSITION = BEAT_TO_COMPOSITION

    def scene_spec(
        self,
        scene: dict[str, Any],
        duration_sec: float,
        source_asset_path: Path | None = None,
    ) -> RenderSpec:
        return self.spec_dispatcher.scene_spec(scene, duration_sec, source_asset_path=source_asset_path)

    def beat_spec(
        self,
        beat: dict[str, Any],
        source_asset_path: Path | None = None,
    ) -> RenderSpec:
        return self.spec_dispatcher.beat_spec(beat, source_asset_path=source_asset_path)

    def beat_requires_source_asset(self, beat: dict[str, Any]) -> bool:
        return self.broll_resolver.beat_requires_source_asset(
            beat,
            is_structured_beat=self._is_structured_beat,
            normalize_structured_beat=self.normalize_structured_beat,
        )

    def broll_query_for_beat(self, beat: dict[str, Any]) -> str:
        return self.broll_resolver.broll_query_for_beat(
            beat,
            is_structured_beat=self._is_structured_beat,
            normalize_structured_beat=self.normalize_structured_beat,
        )

    def classifyIntent(self, narration: str) -> str:
        return self.classified_contract.classify_intent(
            narration,
            has_money_tokens=lambda text: bool(self._money_tokens(text)),
        )

    def deriveFromNarration(self, narration: str, preferred_pattern: str = "", classified_intent: str = "") -> dict[str, Any]:
        classified_intent = (classified_intent or self.classifyIntent(narration)).strip().upper()
        logic = self._logic_from_classified_intent(narration, classified_intent, {"pattern": preferred_pattern} if preferred_pattern else None)
        if preferred_pattern:
            preferred_pattern = preferred_pattern.strip().upper()
            coerced = self._coerce_logic_to_pattern(logic, narration, preferred_pattern)
            if self._typed_visual_logic_is_valid(coerced) and self._visual_logic_relevant_to_context(coerced, narration):
                return coerced
        return logic

    def _logic_from_classified_intent(self, narration: str, classified_intent: str, beat: dict[str, Any] | None = None) -> dict[str, Any]:
        if classified_intent == "EMPHASIS":
            return self._emphasis_logic_from_narration(narration)
        if classified_intent == "COMPARISON":
            return self._comparison_logic_from_narration(narration)
        if classified_intent == "DECAY":
            return self._decay_flow_from_narration(narration)
        return self._flow_logic_from_narration(narration, beat)

    def validateRelevance(self, beat: dict[str, Any], narration: str) -> bool:
        context = narration or self._beat_context(beat)
        logic = self._coerce_visual_logic_object(beat, context)
        return bool(
            logic
            and self._typed_visual_logic_is_valid(logic)
            and self._visual_logic_relevant_to_context(logic, context)
        )

    def normalize_structured_beat(self, beat: dict[str, Any]) -> dict[str, Any]:
        return self.structured_normalizer.normalize(beat)

    def _regenerate_logic_from_context(self, context: str, beat: dict[str, Any] | None = None) -> dict[str, Any]:
        classified_intent = str((beat or {}).get("classified_intent") or self.classifyIntent(context)).upper()
        logic = self._logic_from_classified_intent(context, classified_intent, beat)
        if self._logic_can_reach_render(logic, beat or {}):
            return logic
        transformed = self._transformation_logic_to_flow(logic)
        if self._logic_can_reach_render(transformed, beat or {}):
            return transformed
        if context.strip():
            return self._minimal_narration_flow(context, classified_intent)
        return self._fallback_numeric_flow()

    def _minimal_narration_flow(self, context: str, classified_intent: str = "") -> dict[str, Any]:
        return self.narration_logic.minimal_narration_flow(context)

    def _transformation_logic_to_flow(self, visual_logic: Any) -> dict[str, Any] | None:
        return self.narration_logic.transformation_logic_to_flow(visual_logic)

    def _logic_can_reach_render(self, visual_logic: Any, beat: dict[str, Any]) -> bool:
        return self.logic_validator.logic_can_reach_render(visual_logic, beat)

    def _classified_intent_for_beat(self, beat: dict[str, Any], context: str, visual_logic: Any) -> str:
        return self.classified_contract.classified_intent_for_beat(
            beat,
            context,
            visual_logic,
            classify_intent=self.classifyIntent,
            logic_type=self._logic_type,
        )

    def _enforce_classified_render_contract(
        self,
        classified_intent: str,
        intent: str,
        pattern: str,
        component: str,
        visual_logic_object: Any,
        context: str,
    ) -> tuple[str, str, str, dict[str, Any]]:
        return self.classified_contract.enforce_render_contract(
            classified_intent,
            intent,
            pattern,
            component,
            visual_logic_object,
            context,
            logic_type=self._logic_type,
            logic_from_intent=lambda narration, classified: self._logic_from_classified_intent(narration, classified),
        )

    def _fallback_for_classified_intent(self, classified_intent: str, context: str) -> tuple[str, str, str, dict[str, Any]]:
        return self.classified_contract.fallback_for_classified_intent(
            classified_intent,
            context,
            logic_from_intent=lambda narration, classified: self._logic_from_classified_intent(narration, classified),
        )

    def _structured_beat_spec(self, beat: dict[str, Any], source_asset_path: Path | None = None) -> RenderSpec:
        return self.spec_dispatcher.structured_beat_spec(beat, source_asset_path=source_asset_path)

    def _legacy_flow_diagram_spec(self, beat: dict[str, Any], duration_sec: float, color: str) -> RenderSpec:
        return self.legacy_flow_specs.flow_diagram_spec(beat, duration_sec, color)

    def _beat_flow_stages(self, beat: dict[str, Any], concept: dict[str, Any], narration: str) -> list[dict[str, str]]:
        return self.legacy_flow_stages.beat_flow_stages(beat, concept, narration)

    def _concept_flow_stages(self, concept: dict[str, Any], narration: str) -> list[dict[str, str]]:
        return self.legacy_flow_stages.concept_flow_stages(concept, narration)

    def transition_spec(self, duration_sec: float = 0.5) -> RenderSpec:
        return self.basic_specs.transition(duration_sec)

    def intro_spec(self, title: str, duration_sec: float = 3.0) -> RenderSpec:
        return self.basic_specs.intro(title, duration_sec)

    def end_card_spec(self, next_title: str = "", duration_sec: float = 5.0) -> RenderSpec:
        return self.basic_specs.end_card(next_title, duration_sec)

    def thumbnail_spec(self, title: str, variant: int = 1) -> RenderSpec:
        dominant = self._dominant_phrase(title)
        return self.basic_specs.thumbnail(
            title,
            dominant,
            self._short_overlay(title.replace(dominant, ""), 4),
            variant,
        )

    def _stat_reveal_spec(self, instruction: str, duration_sec: float) -> RenderSpec:
        return self.spec_dispatcher.stat_reveal_spec(instruction, duration_sec)

    def _graph_spec(self, instruction: str, duration_sec: float) -> RenderSpec:
        return self.spec_dispatcher.graph_spec(instruction, duration_sec)

    def _is_structured_beat(self, beat: dict[str, Any]) -> bool:
        return any(key in beat for key in ("intent", "pattern", "props", "visual_logic", "animation_intent"))

    def _all_patterns(self) -> set[str]:
        return self.pattern_selector.all_patterns()

    def _infer_intent(self, pattern: str, visual_logic: str) -> str:
        return self.pattern_selector.infer_intent(pattern, visual_logic)

    def _pattern_for_intent(self, intent: str, visual_logic: str) -> str:
        return self.pattern_selector.pattern_for_intent(intent, visual_logic)

    def _derive_component(self, intent: str, pattern: str, beat: dict[str, Any], visual_logic: str) -> str:
        return self.pattern_selector.derive_component(
            intent,
            pattern,
            beat,
            visual_logic,
            has_chart_data=self._has_chart_data,
        )

    def _has_chart_data(self, beat: dict[str, Any], visual_logic: str) -> bool:
        return self.data_requirements.has_chart_data(beat, visual_logic)

    def _pattern_has_required_concrete_data(self, intent: str, pattern: str, beat: dict[str, Any], visual_logic: str) -> bool:
        return self.data_requirements.pattern_has_required_concrete_data(intent, pattern, beat, visual_logic)

    def _emphasis_component(self, text: str) -> str:
        return self.pattern_selector.emphasis_component(text)

    def _normalize_animation_intent(self, value: Any) -> str:
        return self.pattern_selector.normalize_animation_intent(value)

    def _structured_duration(self, intent: str, beat: dict[str, Any]) -> float:
        return self.pattern_selector.structured_duration(intent, beat)

    def _repair_caption(self, caption: str, visual_logic: str, narration: str = "") -> str:
        return self.caption_builder.repair_caption(caption, visual_logic, narration)

    def _beat_context(self, beat: dict[str, Any]) -> str:
        return self.caption_builder.beat_context(beat)

    def _logic_type(self, visual_logic: Any) -> str:
        return self.logic_validator.logic_type(visual_logic)

    def _coerce_visual_logic_object(self, beat: dict[str, Any], context: str) -> dict[str, Any] | None:
        raw = beat.get("visual_logic")
        if isinstance(raw, dict):
            return raw
        candidates = [raw, beat.get("content"), beat.get("caption")]
        props = beat.get("props") if isinstance(beat.get("props"), dict) else {}
        if props.get("leftContent") and props.get("rightContent"):
            candidates.append(f"{props.get('leftContent')} vs {props.get('rightContent')}")
        nodes = props.get("nodes")
        if isinstance(nodes, list):
            labels = [
                str(node.get("label") if isinstance(node, dict) else node)
                for node in nodes
                if str(node.get("label") if isinstance(node, dict) else node).strip()
            ]
            if labels:
                candidates.append(" -> ".join(labels))
        for candidate in candidates:
            logic = self._string_visual_logic_to_object(str(candidate or ""), context)
            if logic and self._typed_visual_logic_is_valid(logic):
                return logic
        return None

    def _string_visual_logic_to_object(self, text: str, context: str = "") -> dict[str, Any] | None:
        return self.logic_parser.string_visual_logic_to_object(text, context)

    def _typed_visual_logic_is_valid(self, visual_logic: Any) -> bool:
        return self.logic_validator.typed_visual_logic_is_valid(visual_logic)

    def _flow_semantically_valid(self, visual_logic: dict[str, Any]) -> bool:
        return self.logic_validator.flow_semantically_valid(visual_logic)

    def _visual_logic_relevant_to_context(self, visual_logic: Any, context: str) -> bool:
        logic_text = self._visual_logic_to_text(visual_logic)
        return self.context_gate.visual_logic_relevant_to_context(
            visual_logic,
            context,
            logic_text=logic_text,
            logic_type=self._logic_type(visual_logic),
        )

    def _comparison_units_match(self, visual_logic: Any) -> bool:
        return self.context_gate.comparison_units_match(visual_logic)

    def _dominant_unit(self, text: str) -> str:
        return self.context_gate.dominant_unit(text)

    def _numbers_allowed_by_context(self, logic_numbers: set[str], context_numbers: set[str], context: str) -> bool:
        return self.context_gate.numbers_allowed_by_context(logic_numbers, context_numbers, context)

    def _strict_contextual_number_allowlist(self, context: str) -> set[str]:
        return self.context_gate.strict_contextual_number_allowlist(context)

    def _derived_context_number_tokens(self, context: str) -> set[str]:
        return self.context_gate.derived_context_number_tokens(context, inflation_output=self._inflation_output)

    def _meaningful_keywords(self, text: str) -> set[str]:
        return self.context_gate.meaningful_keywords(text)

    def _visual_logic_to_text(self, visual_logic: Any) -> str:
        return self.logic_text.visual_logic_to_text(visual_logic, logic_type=self._logic_type(visual_logic))

    def _repair_visual_logic(self, visual_logic: Any, beat: dict[str, Any], context: str = "") -> str:
        return self.logic_repair.repair_visual_logic(
            self._visual_logic_to_text(visual_logic),
            beat,
            context,
            numbers_respect_context=self._numbers_respect_context,
            is_concrete_visual_logic=self._is_concrete_visual_logic,
            has_visual_structure=self._has_visual_structure,
            contextual_visual_logic=self._contextual_visual_logic,
            beat_context=self._beat_context,
        )

    def _contextual_visual_logic(self, context: str, beat: dict[str, Any] | None = None) -> str:
        return self._visual_logic_to_text(self._contextual_visual_logic_object(context, beat))

    def _contextual_visual_logic_object(self, context: str, beat: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.contextual_logic.contextual_visual_logic_object(context, beat)

    def _emphasis_logic_from_narration(self, narration: str) -> dict[str, Any]:
        return self.narration_logic.emphasis_logic_from_narration(narration)

    def _comparison_logic_from_narration(self, narration: str) -> dict[str, Any]:
        return self.narration_logic.comparison_logic_from_narration(narration)

    def _flow_logic_from_narration(self, narration: str, beat: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.narration_logic.flow_logic_from_narration(narration, beat)

    def _decay_flow_from_narration(self, narration: str) -> dict[str, Any]:
        return self.narration_logic.decay_flow_from_narration(narration)

    def _contextual_visual_logic_object_without_classification(self, context: str) -> dict[str, Any]:
        return self.narration_logic.contextual_visual_logic_object_without_classification(context)

    def _coerce_logic_to_pattern(self, logic: dict[str, Any], context: str, preferred_pattern: str) -> dict[str, Any]:
        return self.narration_logic.coerce_logic_to_pattern(logic, context, preferred_pattern)

    def _amount_with_label(self, amount: str, label: str) -> str:
        return self.value_deriver.amount_with_label(amount, label)

    def _safe_emphasis_logic_object(self, context: str) -> dict[str, Any]:
        logic = self._contextual_visual_logic_object(context, None)
        if self._logic_can_reach_render(logic, {"intent": "EMPHASIS"}):
            return logic
        return self._fallback_numeric_flow()

    def _fallback_numeric_flow(self) -> dict[str, Any]:
        return self.narration_logic.fallback_numeric_flow()

    def _inflation_output(self, principal: str, rate: str) -> str:
        return self.value_deriver.inflation_output(principal, rate)

    def _derived_rupee(self, amount: str, multiplier: float, label: str) -> str:
        return self.value_deriver.derived_rupee(amount, multiplier, label)

    def _first_numeric_value(self, text: str) -> float:
        return self.number_utils.first_numeric_value(text)

    def _format_rupees(self, value: float) -> str:
        return self.number_utils.format_rupees(value)

    def _concrete_fallback_logic(self, beat: dict[str, Any]) -> str:
        return self.emphasis_builder.concrete_fallback_logic(beat)

    def _is_concrete_visual_logic(self, text: str) -> bool:
        return self.visual_gate.is_concrete_visual_logic(text)

    def _is_abstract_visual_logic(self, text: str) -> bool:
        return self.visual_gate.is_abstract_visual_logic(text)

    def _contains_generic_visual_words(self, text: str) -> bool:
        return self.visual_gate.contains_generic_visual_words(text)

    def _has_number(self, text: str) -> bool:
        return self.visual_gate.has_number(text)

    def _numbers_respect_context(self, candidate: str, context: str) -> bool:
        return self.context_gate.numbers_respect_context(candidate, context)

    def _has_visual_structure(self, text: str) -> bool:
        return self.visual_gate.has_visual_structure(text)

    def _has_impact(self, text: str) -> bool:
        return self.visual_gate.has_impact(text)

    def _passes_text_gate(self, text: str) -> bool:
        return self.visual_gate.passes_text_gate(text)

    def _passes_visual_gate(self, intent: str, pattern: str, visual_logic: str, beat: dict[str, Any]) -> bool:
        return self.props_gate.passes_visual_gate(intent, pattern, visual_logic)

    def _props_pass_visual_gate(self, component: str, pattern: str, visual_logic: str, props: dict[str, Any]) -> bool:
        return self.props_gate.props_pass_visual_gate(component, pattern, visual_logic, props)

    def _regenerate_props(
        self,
        component: str,
        pattern: str,
        visual_logic: str,
        caption: str,
        context: str,
        beat: dict[str, Any],
    ) -> dict[str, Any]:
        return self.props_builder.regenerate_props(
            component,
            pattern,
            visual_logic,
            caption,
            context,
            beat,
            contextual_visual_logic=self._contextual_visual_logic,
            safe_emphasis_logic=self._safe_emphasis_logic,
            safe_emphasis_props=self._safe_emphasis_props,
        )

    def _safe_emphasis_logic(self, context: str) -> str:
        logic = self._visual_logic_to_text(self._safe_emphasis_logic_object(context))
        if self._passes_text_gate(logic):
            return logic
        return "76% can't save ₹5,000"

    def _safe_emphasis_props(self, visual_logic: str, caption: str) -> dict[str, Any]:
        return self.emphasis_builder.safe_emphasis_props(visual_logic, caption)

    def _kill_switch_beat(self, normalized: dict[str, Any]) -> dict[str, Any]:
        return self.structured_normalizer.kill_switch_beat(normalized)

    def _repair_props(
        self,
        component: str,
        pattern: str,
        visual_logic: str,
        caption: str,
        beat: dict[str, Any],
    ) -> dict[str, Any]:
        return self.props_builder.repair_props(component, pattern, visual_logic, caption, beat)

    def _flow_props(
        self,
        pattern: str,
        visual_logic: str,
        caption: str,
        raw_props: dict[str, Any],
        color: str,
        beat: dict[str, Any],
    ) -> dict[str, Any]:
        return self.flow_props_builder.flow_props(pattern, visual_logic, caption, raw_props, color, beat)

    def _polish_flow_display_props(self, props: dict[str, Any], visual_logic: str) -> dict[str, Any]:
        return self.flow_props_builder.polish_flow_display_props(props, visual_logic)

    def _flow_mode(self, pattern: str, value: Any) -> str:
        return self.flow_props_builder.flow_mode(pattern, value)

    def _flow_layout(self, mode: str, value: Any) -> str:
        return self.flow_props_builder.flow_layout(mode, value)

    def _flow_nodes(self, raw_nodes: Any, visual_logic: str, pattern: str) -> list[dict[str, Any]]:
        return self.flow_props_builder.flow_nodes(raw_nodes, visual_logic, pattern)

    def _fallback_node_label(self, visual_logic: str, index: int, pattern: str) -> str:
        return self.flow_props_builder.fallback_node_label(visual_logic, index, pattern)

    def _fallback_flow_nodes(self, visual_logic: str, pattern: str) -> list[dict[str, Any]]:
        return self.flow_props_builder.fallback_flow_nodes(visual_logic, pattern)

    def _node_style(self, role: str, label: str, pattern: str = "") -> dict[str, str]:
        return self.flow_props_builder.node_style(role, label, pattern)

    def _flow_connections(self, raw_connections: Any, nodes: list[dict[str, Any]], mode: str) -> list[dict[str, str]]:
        return self.flow_helpers.flow_connections(raw_connections, nodes, mode)

    def _default_node_role(self, index: int, total: int) -> str:
        return self.flow_helpers.default_node_role(index, total)

    def _safe_id(self, value: str, index: int) -> str:
        return self.flow_helpers.safe_id(value, index)

    def _dominant_phrase(self, text: str) -> str:
        return self.text_utils.dominant_phrase(text)

    def _short_overlay(self, text: str, max_words: int) -> str:
        return self.text_utils.short_overlay(text, max_words)

    def _sentiment(self, text: str) -> str:
        return self.text_utils.sentiment(text)

    def _looks_like_line_chart(self, text: str) -> bool:
        return self.text_utils.looks_like_line_chart(text)

    def _chart_color(self, text: str) -> str:
        return self.text_utils.chart_color(text)

    def _kicker(self, text: str) -> str:
        return self.text_utils.kicker(text)

    def _unit_label(self, text: str) -> str:
        return self.text_utils.unit_label(text)

    def _money_tokens(self, text: str) -> list[str]:
        return self.number_utils.money_tokens(text)

    def _percent_tokens(self, text: str) -> list[str]:
        return self.number_utils.percent_tokens(text)

    def _numeric_values(self, text: str) -> list[float]:
        return self.number_utils.numeric_values(text)

    def _extract_data_points(self, text: str) -> list[dict[str, float | str]]:
        return self.chart_data.extract_data_points(text)

    def _extract_data_section(self, text: str) -> str:
        return self.chart_data.extract_data_section(text)

    def _extract_named_field(self, text: str, field: str) -> str:
        return self.text_utils.extract_named_field(text, field)

    def _extract_color(self, text: str) -> str:
        return self.text_utils.extract_color(text)

    def _beat_color(self, value: Any) -> str:
        return self.text_utils.beat_color(value)

    def _parse_split(self, content: str, caption: str) -> tuple[str, str, str, str]:
        return self.text_utils.parse_split(content, caption)

    def _concrete_split_from_logic(self, visual_logic: str, caption: str) -> tuple[str, str]:
        return self.split_helpers.concrete_split_from_logic(visual_logic, caption)

    def _extract_split_label(self, content: str) -> str:
        return self.text_utils.extract_split_label(content)

    def _humanize_split_label(self, label: str, content: str) -> str:
        return self.split_helpers.humanize_split_label(label, content)

    def _humanize_money_phrase(self, text: str) -> str:
        return self.flow_labels.humanize_money_phrase(text)

    def _complete_caption(self, caption: str) -> str:
        return self.flow_labels.complete_caption(caption)

    def _color_for_label(self, label: str) -> str:
        return self.flow_labels.color_for_label(label)

    def _is_loss_result(self, text: str) -> bool:
        return self.flow_labels.is_loss_result(text)

    def _looks_like_outro_loss(self, text: str) -> bool:
        return self.flow_labels.looks_like_outro_loss(text)

    def _monthly_punchline_source(self, label: str) -> str:
        return self.flow_props_builder.monthly_punchline_source(label)

    def _short_money(self, text: str) -> str:
        return self.flow_props_builder.short_money(text)
