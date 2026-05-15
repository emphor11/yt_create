from __future__ import annotations

from typing import Any


class RenderStructuredBeatNormalizer:
    """Normalizes structured visual beats using the legacy render rules."""

    def __init__(self, ops: Any) -> None:
        self.ops = ops

    def normalize(self, beat: dict[str, Any]) -> dict[str, Any]:
        ops = self.ops
        raw_intent = str(beat.get("intent") or "").strip().upper()
        raw_pattern = str(beat.get("pattern") or "").strip().upper()
        context = ops._beat_context(beat)
        visual_logic_object = ops._coerce_visual_logic_object(beat, context)
        classified_intent = ops._classified_intent_for_beat(beat, context, visual_logic_object)
        if not ops._logic_can_reach_render(visual_logic_object, beat):
            visual_logic_object = ops._regenerate_logic_from_context(context, {**beat, "classified_intent": classified_intent})
        logic_valid = ops._typed_visual_logic_is_valid(visual_logic_object)
        explicit_invalid_object = isinstance(beat.get("visual_logic"), dict) and not logic_valid
        force_emphasis = False
        raw_visual_logic_text = ops._visual_logic_to_text(visual_logic_object)
        if raw_intent == "CONTEXT" or raw_pattern == "CONTEXT":
            visual_logic = ops._visual_logic_to_text(beat.get("visual_logic") or beat.get("content") or beat.get("caption") or context or "finance stress")
        else:
            visual_logic = ops._visual_logic_to_text(visual_logic_object) if logic_valid else ops._visual_logic_to_text(ops._contextual_visual_logic_object(context, beat))
        intent = raw_intent if raw_intent in ops.INTENT_PATTERN_MAP else ops._infer_intent(raw_pattern, visual_logic)
        pattern = raw_pattern if raw_pattern in ops._all_patterns() else ops._pattern_for_intent(intent, visual_logic)
        logic_type = ops._logic_type(visual_logic_object)
        if logic_type in ops.LOGIC_TYPE_TO_PATTERN and logic_valid and raw_intent != "HOOK":
            pattern = ops.LOGIC_TYPE_TO_PATTERN[logic_type]
            intent = "EMPHASIS" if logic_type == "emphasis" else ("COMPARISON" if pattern == "COMPARISON" else "EXPLANATION")
        if pattern not in ops.INTENT_PATTERN_MAP[intent]:
            pattern = ops._pattern_for_intent(intent, visual_logic)
        if (
            (False if raw_intent == "CONTEXT" or raw_pattern == "CONTEXT" else explicit_invalid_object)
            or (
                raw_intent not in {"CONTEXT"}
                and raw_pattern != "CONTEXT"
                and not isinstance(beat.get("visual_logic"), dict)
                and str(beat.get("visual_logic") or "").strip()
                and not logic_valid
                and not context.strip()
            )
            or (not logic_valid and intent != "CONTEXT" and pattern != "CONTEXT")
            or (raw_intent == "DATA" and raw_pattern == "GROWTH" and not ops._has_chart_data(beat, raw_visual_logic_text))
            or not ops._visual_logic_relevant_to_context(visual_logic_object, context)
            or not ops._pattern_has_required_concrete_data(intent, pattern, beat, visual_logic)
            or not ops._passes_visual_gate(intent, pattern, visual_logic, beat)
        ):
            visual_logic_object = ops._safe_emphasis_logic_object(context) if not context.strip() else ops._regenerate_logic_from_context(context, {**beat, "classified_intent": classified_intent})
            visual_logic = ops._visual_logic_to_text(visual_logic_object)
            logic_type = ops._logic_type(visual_logic_object)
            intent = "COMPARISON" if logic_type == "comparison" else "EXPLANATION"
            pattern = ops.LOGIC_TYPE_TO_PATTERN.get(logic_type, "MONEY_FLOW")
            if raw_intent in {"HOOK", "EMPHASIS"} and (explicit_invalid_object or not context.strip()):
                intent = "EMPHASIS"
                pattern = "EMPHASIS"
                force_emphasis = True
            if not context.strip():
                intent = "EMPHASIS"
                pattern = "EMPHASIS"
                force_emphasis = True

        intent, pattern, component, visual_logic_object = ops._enforce_classified_render_contract(
            classified_intent,
            intent,
            pattern,
            component="",
            visual_logic_object=visual_logic_object,
            context=context,
        )
        visual_logic = ops._visual_logic_to_text(visual_logic_object)
        component = ops._derive_component(intent, pattern, beat, visual_logic)
        intent, pattern, component, visual_logic_object = ops._enforce_classified_render_contract(
            classified_intent,
            intent,
            pattern,
            component,
            visual_logic_object,
            context,
        )
        visual_logic = ops._visual_logic_to_text(visual_logic_object)
        if raw_intent == "HOOK" and component == "FlowDiagram":
            intent = "EMPHASIS"
            pattern = "EMPHASIS"
            component = "StatExplosion"
        animation_intent = ops._normalize_animation_intent(beat.get("animation_intent"))
        duration = ops._structured_duration(intent, beat)
        caption = ops._repair_caption(
            str(beat.get("caption") or (beat.get("props") or {}).get("caption") or ""),
            visual_logic,
            str(beat.get("narration") or ""),
        )
        props = ops._repair_props(component, pattern, visual_logic, caption, beat)
        if not ops._props_pass_visual_gate(component, pattern, visual_logic, props):
            if not force_emphasis:
                visual_logic_object = visual_logic_object if ops._logic_can_reach_render(visual_logic_object, beat) else ops._regenerate_logic_from_context(context, {**beat, "classified_intent": classified_intent})
                visual_logic = ops._visual_logic_to_text(visual_logic_object)
                intent = "COMPARISON" if ops._logic_type(visual_logic_object) == "comparison" else "EXPLANATION"
                pattern = ops.LOGIC_TYPE_TO_PATTERN.get(ops._logic_type(visual_logic_object), "MONEY_FLOW")
                if raw_intent == "HOOK":
                    intent = "EMPHASIS"
                    pattern = "EMPHASIS"
                intent, pattern, component, visual_logic_object = ops._enforce_classified_render_contract(
                    classified_intent,
                    intent,
                    pattern,
                    component,
                    visual_logic_object,
                    context,
                )
                visual_logic = ops._visual_logic_to_text(visual_logic_object)
                component = ops._derive_component(intent, pattern, beat, visual_logic)
                intent, pattern, component, visual_logic_object = ops._enforce_classified_render_contract(
                    classified_intent,
                    intent,
                    pattern,
                    component,
                    visual_logic_object,
                    context,
                )
                visual_logic = ops._visual_logic_to_text(visual_logic_object)
                if raw_intent == "HOOK" and component == "FlowDiagram":
                    component = "StatExplosion"
                props = ops._regenerate_props(component, pattern, visual_logic, caption, context, beat)
        if not ops._props_pass_visual_gate(component, pattern, visual_logic, props):
            intent, pattern, component, visual_logic_object = ops._fallback_for_classified_intent(classified_intent, context)
            visual_logic = ops._visual_logic_to_text(visual_logic_object)
            caption = ops._repair_caption("", visual_logic, context)
            props = (
                ops._safe_emphasis_props(visual_logic, caption)
                if component == "StatExplosion"
                else ops._regenerate_props(component, pattern, visual_logic, caption, context, {**beat, "props": {}})
            )
        animation_spec = ops.ANIMATION_MAP[animation_intent]
        if component == "FlowDiagram":
            props = ops._polish_flow_display_props(props, visual_logic)
            props["animationIntent"] = animation_intent
            props["animationSpec"] = animation_spec
        props["durationSec"] = duration
        return {
            **beat,
            "intent": intent,
            "pattern": pattern,
            "component": component,
            "visual_logic": visual_logic_object,
            "visual_logic_text": visual_logic,
            "caption": caption,
            "animation_intent": animation_intent,
            "animation_spec": animation_spec,
            "classified_intent": classified_intent,
            "estimated_duration_sec": duration,
            "props": props,
        }

    def kill_switch_beat(self, normalized: dict[str, Any]) -> dict[str, Any]:
        ops = self.ops
        context = ops._beat_context(normalized)
        visual_logic_object = ops._safe_emphasis_logic_object(context)
        visual_logic_text = ops._visual_logic_to_text(visual_logic_object)
        caption = ops._repair_caption("", visual_logic_text, context)
        props = ops._safe_emphasis_props(visual_logic_text, caption)
        props["durationSec"] = normalized.get("estimated_duration_sec") or 2.5
        return {
            **normalized,
            "intent": "EMPHASIS",
            "pattern": "EMPHASIS",
            "component": "StatExplosion",
            "visual_logic": visual_logic_object,
            "visual_logic_text": visual_logic_text,
            "caption": caption,
            "props": props,
        }
