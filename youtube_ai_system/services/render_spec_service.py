from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RenderSpec:
    composition: str
    props: dict[str, Any]
    duration_sec: float
    source: str
    output_ext: str = ".mp4"
    source_asset_path: Path | None = None


class RenderSpecService:
    """Maps script-friendly scene fields to deterministic Remotion template props."""

    INTENT_PATTERN_MAP = {
        "HOOK": {"EMPHASIS", "CONTEXT"},
        "COMPARISON": {"COMPARISON"},
        "DATA": {"GROWTH", "COMPARISON"},
        "EXPLANATION": {"MONEY_FLOW", "VALUE_DECAY", "LOOP", "GROWTH"},
        "EMPHASIS": {"EMPHASIS"},
        "CONTEXT": {"CONTEXT"},
    }
    DURATION_BY_INTENT = {
        "HOOK": 2.5,
        "EMPHASIS": 2.5,
        "COMPARISON": 3.0,
        "DATA": 4.0,
        "EXPLANATION": 4.5,
        "CONTEXT": 3.0,
    }
    ANIMATION_MAP = {
        "reveal": {"type": "fade_sequence"},
        "progress": {"type": "line_draw"},
        "highlight": {"type": "pulse_node"},
        "transform": {"type": "scale_change"},
    }
    VISUAL_LOGIC_SCHEMA = {
        "decay": ("input", "factor", "output"),
        "flow": ("source", "process", "result"),
        "comparison": ("left", "right"),
        "growth": ("input", "rate", "output"),
        "emphasis": ("headline",),
    }
    LOGIC_TYPE_TO_PATTERN = {
        "decay": "VALUE_DECAY",
        "flow": "MONEY_FLOW",
        "comparison": "COMPARISON",
        "growth": "GROWTH",
        "emphasis": "EMPHASIS",
    }
    FLOW_PATTERNS = {"MONEY_FLOW", "VALUE_DECAY", "LOOP", "GROWTH"}
    VALID_COMPONENTS = {
        "FlowDiagram",
        "SplitComparison",
        "BarChart",
        "LineChart",
        "StatExplosion",
        "TextBurst",
        "ReactionCard",
        "BrollOverlay",
    }
    VALID_NODE_ROLES = {"source", "process", "modifier", "result", "actor", "sink"}
    ABSTRACT_VISUAL_WORDS = {
        "abstract",
        "chart",
        "contrast",
        "concept",
        "data",
        "display",
        "flow",
        "graph",
        "idea",
        "image",
        "juxtaposition",
        "narrative",
        "show",
        "split screen",
        "static image",
        "statistic",
        "stuff",
        "thing",
        "visual",
    }

    BEAT_TO_COMPOSITION = {
        "stat_explosion": "StatExplosion",
        "text_burst": "TextBurst",
        "chart": "BarChart",
        "split_comparison": "SplitComparison",
        "broll_caption": "BrollOverlay",
        "reaction_card": "ReactionCard",
        "graph": "BarChart",
        "broll": "BrollOverlay",
        "motion_text": "StatReveal",
    }

    def scene_spec(
        self,
        scene: dict[str, Any],
        duration_sec: float,
        source_asset_path: Path | None = None,
    ) -> RenderSpec:
        visual_type = str(scene.get("visual_type") or "motion_text").lower()
        narration = str(scene.get("narration_text") or "")
        instruction = str(scene.get("visual_instruction") or narration)

        if visual_type == "graph":
            return self._graph_spec(instruction, duration_sec)
        if visual_type == "broll":
            if source_asset_path is None:
                raise ValueError("BrollOverlay requires a Pexels/Pixabay source video path.")
            return RenderSpec(
                composition="BrollOverlay",
                props={
                    "videoPath": str(source_asset_path),
                    "overlayText": self._short_overlay(instruction or narration, 9),
                    "durationSec": duration_sec,
                    "brand": "YTCreate Finance",
                    "sentiment": self._sentiment(instruction or narration),
                },
                duration_sec=duration_sec,
                source="remotion_broll_overlay",
                source_asset_path=source_asset_path,
            )
        return self._stat_reveal_spec(instruction or narration, duration_sec)

    def beat_spec(
        self,
        beat: dict[str, Any],
        source_asset_path: Path | None = None,
    ) -> RenderSpec:
        if self._is_structured_beat(beat):
            return self._structured_beat_spec(beat, source_asset_path=source_asset_path)

        beat_type = str(beat.get("beat_type") or "text_burst").lower()
        content = str(beat.get("content") or "Money reality")
        caption = str(beat.get("caption") or "")
        color = self._beat_color(beat.get("color"))
        duration_sec = max(float(beat.get("estimated_duration_sec") or 3), 0.5)

        if beat_type == "motion_text":
            return self._stat_reveal_spec(f"{content} {caption}".strip(), duration_sec)
        if beat_type == "graph":
            spec = self._graph_spec(content, duration_sec)
            spec.props["animationSpeed"] = "fast"
            return spec
        if beat_type == "broll":
            beat_type = "broll_caption"

        if beat_type == "stat_explosion":
            return RenderSpec(
                composition="StatExplosion",
                props={"headline": content, "subtext": caption, "color": color, "durationSec": duration_sec},
                duration_sec=duration_sec,
                source="remotion_stat_explosion",
            )
        if beat_type == "text_burst":
            return RenderSpec(
                composition="TextBurst",
                props={"content": content, "color": color, "durationSec": duration_sec},
                duration_sec=duration_sec,
                source="remotion_text_burst",
            )
        if beat_type == "reaction_card":
            return RenderSpec(
                composition="ReactionCard",
                props={"content": content, "subtext": caption, "color": color, "durationSec": duration_sec},
                duration_sec=duration_sec,
                source="remotion_reaction_card",
            )
        if beat_type == "split_comparison":
            left_label, left_content, right_label, right_content = self._parse_split(content, caption)
            return RenderSpec(
                composition="SplitComparison",
                props={
                    "leftLabel": left_label,
                    "leftContent": left_content,
                    "rightLabel": right_label,
                    "rightContent": right_content,
                    "durationSec": duration_sec,
                },
                duration_sec=duration_sec,
                source="remotion_split_comparison",
            )
        if beat_type == "chart":
            spec = self._graph_spec(content, duration_sec)
            spec.props["animationSpeed"] = "fast"
            return spec
        if beat_type == "broll_caption":
            if source_asset_path is None:
                raise ValueError("BrollOverlay beat requires a Pexels/Pixabay source video path.")
            return RenderSpec(
                composition="BrollOverlay",
                props={
                    "videoPath": str(source_asset_path),
                    "overlayText": caption or self._short_overlay(content, 9),
                    "durationSec": duration_sec,
                    "brand": "10 Minute Finance",
                    "sentiment": self._sentiment(f"{content} {caption}"),
                },
                duration_sec=duration_sec,
                source="remotion_broll_overlay",
                source_asset_path=source_asset_path,
            )

        return self._stat_reveal_spec(content or caption, duration_sec)

    def beat_requires_source_asset(self, beat: dict[str, Any]) -> bool:
        if self._is_structured_beat(beat):
            return self.normalize_structured_beat(beat)["component"] == "BrollOverlay"
        beat_type = str(beat.get("beat_type") or "").lower()
        return beat_type in {"broll", "broll_caption"}

    def broll_query_for_beat(self, beat: dict[str, Any]) -> str:
        if self._is_structured_beat(beat):
            normalized = self.normalize_structured_beat(beat)
            props = normalized.get("props") or {}
            return str(
                props.get("query")
                or props.get("searchQuery")
                or normalized.get("visual_logic")
                or normalized.get("caption")
                or "finance stress"
            )
        return str(beat.get("content") or beat.get("caption") or "finance stress")

    def deriveFromNarration(self, narration: str, preferred_pattern: str = "") -> dict[str, Any]:
        logic = self._contextual_visual_logic_object(narration, {"pattern": preferred_pattern} if preferred_pattern else None)
        if preferred_pattern:
            preferred_pattern = preferred_pattern.strip().upper()
            coerced = self._coerce_logic_to_pattern(logic, narration, preferred_pattern)
            if self._typed_visual_logic_is_valid(coerced) and self._visual_logic_relevant_to_context(coerced, narration):
                return coerced
        return logic

    def validateRelevance(self, beat: dict[str, Any], narration: str) -> bool:
        context = narration or self._beat_context(beat)
        logic = self._coerce_visual_logic_object(beat, context)
        return bool(
            logic
            and self._typed_visual_logic_is_valid(logic)
            and self._visual_logic_relevant_to_context(logic, context)
        )

    def normalize_structured_beat(self, beat: dict[str, Any]) -> dict[str, Any]:
        raw_intent = str(beat.get("intent") or "").strip().upper()
        raw_pattern = str(beat.get("pattern") or "").strip().upper()
        context = self._beat_context(beat)
        visual_logic_object = self._coerce_visual_logic_object(beat, context)
        logic_valid = self._typed_visual_logic_is_valid(visual_logic_object)
        explicit_invalid_object = isinstance(beat.get("visual_logic"), dict) and not logic_valid
        force_emphasis = False
        raw_visual_logic_text = self._visual_logic_to_text(visual_logic_object)
        if raw_intent == "CONTEXT" or raw_pattern == "CONTEXT":
            visual_logic = self._visual_logic_to_text(beat.get("visual_logic") or beat.get("content") or beat.get("caption") or context or "finance stress")
        else:
            visual_logic = self._visual_logic_to_text(visual_logic_object) if logic_valid else self._visual_logic_to_text(self._contextual_visual_logic_object(context, beat))
        intent = raw_intent if raw_intent in self.INTENT_PATTERN_MAP else self._infer_intent(raw_pattern, visual_logic)
        pattern = raw_pattern if raw_pattern in self._all_patterns() else self._pattern_for_intent(intent, visual_logic)
        logic_type = self._logic_type(visual_logic_object)
        if logic_type in self.LOGIC_TYPE_TO_PATTERN and logic_valid and raw_intent != "HOOK":
            pattern = self.LOGIC_TYPE_TO_PATTERN[logic_type]
            intent = "EMPHASIS" if logic_type == "emphasis" else ("COMPARISON" if pattern == "COMPARISON" else "EXPLANATION")
        if pattern not in self.INTENT_PATTERN_MAP[intent]:
            pattern = self._pattern_for_intent(intent, visual_logic)
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
            or (raw_intent == "DATA" and raw_pattern == "GROWTH" and not self._has_chart_data(beat, raw_visual_logic_text))
            or not self._visual_logic_relevant_to_context(visual_logic_object, context)
            or not self._pattern_has_required_concrete_data(intent, pattern, beat, visual_logic)
            or not self._passes_visual_gate(intent, pattern, visual_logic, beat)
        ):
            visual_logic_object = self._safe_emphasis_logic_object(context) if not context.strip() else self._contextual_visual_logic_object(context, beat)
            visual_logic = self._visual_logic_to_text(visual_logic_object)
            logic_type = self._logic_type(visual_logic_object)
            intent = "COMPARISON" if logic_type == "comparison" else "EXPLANATION"
            pattern = self.LOGIC_TYPE_TO_PATTERN.get(logic_type, "MONEY_FLOW")
            if raw_intent in {"HOOK", "EMPHASIS"} and (explicit_invalid_object or not context.strip()):
                intent = "EMPHASIS"
                pattern = "EMPHASIS"
                force_emphasis = True
            if not context.strip():
                intent = "EMPHASIS"
                pattern = "EMPHASIS"
                force_emphasis = True

        component = self._derive_component(intent, pattern, beat, visual_logic)
        if raw_intent == "HOOK" and component == "FlowDiagram":
            intent = "EMPHASIS"
            pattern = "EMPHASIS"
            component = "StatExplosion"
        animation_intent = self._normalize_animation_intent(beat.get("animation_intent"))
        duration = self._structured_duration(intent, beat)
        caption = self._repair_caption(
            str(beat.get("caption") or (beat.get("props") or {}).get("caption") or ""),
            visual_logic,
            str(beat.get("narration") or ""),
        )
        props = self._repair_props(component, pattern, visual_logic, caption, beat)
        if not self._props_pass_visual_gate(component, pattern, visual_logic, props):
            if not force_emphasis:
                visual_logic_object = visual_logic_object if self._typed_visual_logic_is_valid(visual_logic_object) else self._contextual_visual_logic_object(context, beat)
                visual_logic = self._visual_logic_to_text(visual_logic_object)
                intent = "COMPARISON" if self._logic_type(visual_logic_object) == "comparison" else "EXPLANATION"
                pattern = self.LOGIC_TYPE_TO_PATTERN.get(self._logic_type(visual_logic_object), "MONEY_FLOW")
                if raw_intent == "HOOK":
                    intent = "EMPHASIS"
                    pattern = "EMPHASIS"
                component = self._derive_component(intent, pattern, beat, visual_logic)
                if raw_intent == "HOOK" and component == "FlowDiagram":
                    component = "StatExplosion"
                props = self._regenerate_props(component, pattern, visual_logic, caption, context, beat)
        if not self._props_pass_visual_gate(component, pattern, visual_logic, props):
            intent = "EMPHASIS"
            pattern = "EMPHASIS"
            component = "StatExplosion"
            visual_logic_object = self._safe_emphasis_logic_object(context)
            visual_logic = self._visual_logic_to_text(visual_logic_object)
            caption = self._repair_caption("", visual_logic, context)
            props = self._safe_emphasis_props(visual_logic, caption)
        animation_spec = self.ANIMATION_MAP[animation_intent]
        if component == "FlowDiagram":
            props = self._polish_flow_display_props(props, visual_logic)
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
            "estimated_duration_sec": duration,
            "props": props,
        }

    def _structured_beat_spec(self, beat: dict[str, Any], source_asset_path: Path | None = None) -> RenderSpec:
        normalized = self.normalize_structured_beat(beat)
        component = normalized["component"]
        props = dict(normalized["props"])
        duration_sec = float(normalized["estimated_duration_sec"])
        visual_logic_text = str(normalized.get("visual_logic_text") or self._visual_logic_to_text(normalized.get("visual_logic")))
        if not self._props_pass_visual_gate(component, normalized["pattern"], visual_logic_text, props):
            normalized = self._kill_switch_beat(normalized)
            component = normalized["component"]
            props = dict(normalized["props"])
            duration_sec = float(normalized["estimated_duration_sec"])
            visual_logic_text = str(normalized.get("visual_logic_text") or self._visual_logic_to_text(normalized.get("visual_logic")))

        if component == "BrollOverlay":
            if source_asset_path is None:
                raise ValueError("BrollOverlay structured beat requires a Pexels/Pixabay source video path.")
            props["videoPath"] = str(source_asset_path)
            props.setdefault("brand", "10 Minute Finance")
            props.setdefault("sentiment", self._sentiment(f"{visual_logic_text} {normalized['caption']}"))
            return RenderSpec(component, props, duration_sec, "remotion_broll_overlay", source_asset_path=source_asset_path)
        if component in {"BarChart", "LineChart"}:
            props.setdefault("animationSpeed", "fast")
            return RenderSpec(component, props, duration_sec, f"remotion_{component.lower()}")
        return RenderSpec(component, props, duration_sec, f"remotion_{component.lower()}")

    def transition_spec(self, duration_sec: float = 0.5) -> RenderSpec:
        return RenderSpec(
            composition="SceneTransition",
            props={"durationSec": duration_sec},
            duration_sec=duration_sec,
            source="remotion_transition",
        )

    def intro_spec(self, title: str, duration_sec: float = 3.0) -> RenderSpec:
        return RenderSpec(
            composition="IntroCard",
            props={"title": title, "channelName": "YTCreate Finance", "durationSec": duration_sec},
            duration_sec=duration_sec,
            source="remotion_intro",
        )

    def end_card_spec(self, next_title: str = "", duration_sec: float = 5.0) -> RenderSpec:
        return RenderSpec(
            composition="EndCard",
            props={
                "message": "Subscribe for more finance insights",
                "nextTitle": next_title,
                "durationSec": duration_sec,
            },
            duration_sec=duration_sec,
            source="remotion_end_card",
        )

    def thumbnail_spec(self, title: str, variant: int = 1) -> RenderSpec:
        dominant = self._dominant_phrase(title)
        return RenderSpec(
            composition="ThumbnailFrame",
            props={
                "title": title,
                "dominantText": dominant,
                "supportingText": self._short_overlay(title.replace(dominant, ""), 4),
                "variant": variant,
                "brand": "YTCreate",
            },
            duration_sec=1 / 30,
            source="remotion_thumbnail",
            output_ext=".jpg",
        )

    def _stat_reveal_spec(self, instruction: str, duration_sec: float) -> RenderSpec:
        headline = self._dominant_phrase(instruction)
        sentiment = self._sentiment(instruction)
        return RenderSpec(
            composition="StatReveal",
            props={
                "headline": headline,
                "subtext": self._short_overlay(instruction.replace(headline, ""), 7),
                "sentiment": sentiment,
                "durationSec": duration_sec,
                "kicker": self._kicker(instruction),
            },
            duration_sec=duration_sec,
            source="remotion_stat_reveal",
        )

    def _graph_spec(self, instruction: str, duration_sec: float) -> RenderSpec:
        data = self._extract_data_points(instruction)
        if len(data) < 2:
            return self._stat_reveal_spec(instruction, duration_sec)
        composition = "LineChart" if self._looks_like_line_chart(instruction) else "BarChart"
        return RenderSpec(
            composition=composition,
            props={
                "title": self._extract_named_field(instruction, "title") or self._short_overlay(instruction, 8) or "Financial Trend",
                "data": data,
                "color": self._extract_color(instruction) or self._chart_color(instruction),
                "durationSec": duration_sec,
                "unit": self._extract_named_field(instruction, "unit") or self._unit_label(instruction),
            },
            duration_sec=duration_sec,
            source=f"remotion_{composition.lower()}",
        )

    def _is_structured_beat(self, beat: dict[str, Any]) -> bool:
        return any(key in beat for key in ("intent", "pattern", "props", "visual_logic", "animation_intent"))

    def _all_patterns(self) -> set[str]:
        patterns: set[str] = set()
        for values in self.INTENT_PATTERN_MAP.values():
            patterns.update(values)
        return patterns

    def _infer_intent(self, pattern: str, visual_logic: str) -> str:
        text = visual_logic.lower()
        if pattern == "EMPHASIS":
            return "EMPHASIS"
        if pattern == "CONTEXT":
            return "CONTEXT"
        if pattern == "COMPARISON" or re.search(r"\b(vs|versus|compared|reality|instead)\b", text):
            return "COMPARISON"
        if pattern in self.FLOW_PATTERNS or any(word in text for word in ("because", "leads to", "turns into", "cycle", "flow", "moves", "inflation", "tax")):
            return "EXPLANATION"
        if re.search(r"[₹\d%]", visual_logic):
            return "DATA"
        if pattern == "CONTEXT" or any(word in text for word in ("person", "office", "bank", "phone", "background")):
            return "CONTEXT"
        return "EMPHASIS"

    def _pattern_for_intent(self, intent: str, visual_logic: str) -> str:
        text = visual_logic.lower()
        if intent == "HOOK":
            return "EMPHASIS"
        if intent == "COMPARISON":
            return "COMPARISON"
        if intent == "DATA":
            return "COMPARISON" if re.search(r"\b(vs|versus|compared|than)\b", text) else "GROWTH"
        if intent == "EXPLANATION":
            if any(word in text for word in ("inflation", "tax", "fee", "fees", "erode", "erosion", "decay", "shrink", "reduced")):
                return "VALUE_DECAY"
            if any(word in text for word in ("debt", "credit", "cycle", "repeat", "trap", "loop")):
                return "LOOP"
            if any(word in text for word in ("compound", "sip", "growth", "grow", "invest", "wealth")):
                return "GROWTH"
            return "MONEY_FLOW"
        if intent == "CONTEXT":
            return "CONTEXT"
        return "EMPHASIS"

    def _derive_component(self, intent: str, pattern: str, beat: dict[str, Any], visual_logic: str) -> str:
        if pattern in {"MONEY_FLOW", "VALUE_DECAY", "LOOP"}:
            return "FlowDiagram"
        if pattern == "GROWTH":
            return "LineChart" if intent == "DATA" and self._has_chart_data(beat, visual_logic) else "FlowDiagram"
        if pattern == "COMPARISON":
            return "SplitComparison"
        if pattern == "CONTEXT":
            return "BrollOverlay"
        props = beat.get("props") if isinstance(beat.get("props"), dict) else {}
        emphasis_text = " ".join(
            str(value)
            for value in (
                visual_logic,
                beat.get("caption") or "",
                props.get("headline") or "",
                props.get("subtext") or "",
                props.get("content") or "",
            )
            if value
        )
        return self._emphasis_component(emphasis_text)

    def _has_chart_data(self, beat: dict[str, Any], visual_logic: str) -> bool:
        props = beat.get("props") if isinstance(beat.get("props"), dict) else {}
        data = props.get("data")
        return (isinstance(data, list) and len(data) >= 2) or len(self._extract_data_points(visual_logic)) >= 2

    def _pattern_has_required_concrete_data(self, intent: str, pattern: str, beat: dict[str, Any], visual_logic: str) -> bool:
        props = beat.get("props") if isinstance(beat.get("props"), dict) else {}
        if pattern == "COMPARISON":
            left = str(props.get("leftContent") or "")
            right = str(props.get("rightContent") or "")
            text = f"{visual_logic} {left} {right}"
            return bool(
                (
                    left.strip()
                    and right.strip()
                    and self._passes_text_gate(f"{left} vs {right}")
                )
                or re.search(r"\b(vs|versus|compared|than)\b", text.lower())
            )
        if pattern == "GROWTH" and intent == "DATA":
            return self._has_chart_data(beat, visual_logic)
        if pattern in self.FLOW_PATTERNS:
            nodes = props.get("nodes")
            if isinstance(nodes, list) and len(nodes) >= 2:
                labels = [
                    str(node.get("label") if isinstance(node, dict) else node)
                    for node in nodes
                ]
                return (len(labels) >= 3 and self._passes_text_gate(" -> ".join(labels))) or self._passes_text_gate(visual_logic)
            return self._passes_text_gate(visual_logic)
        return True

    def _emphasis_component(self, text: str) -> str:
        if re.search(r"[₹\d%]", text):
            return "StatExplosion"
        if len(re.findall(r"\S+", text)) <= 3:
            return "TextBurst"
        return "ReactionCard"

    def _normalize_animation_intent(self, value: Any) -> str:
        animation = str(value or "reveal").strip().lower()
        return animation if animation in self.ANIMATION_MAP else "reveal"

    def _structured_duration(self, intent: str, beat: dict[str, Any]) -> float:
        if beat.get("duration_locked"):
            try:
                return max(1.0, min(float(beat.get("estimated_duration_sec") or 3.0), 6.0))
            except (TypeError, ValueError):
                pass
        return self.DURATION_BY_INTENT.get(intent, 3.0)

    def _repair_caption(self, caption: str, visual_logic: str, narration: str = "") -> str:
        caption = " ".join(re.findall(r"[A-Za-z0-9₹%.,'-]+", caption)).strip()
        narration_clean = " ".join(re.findall(r"[A-Za-z0-9₹%.,'-]+", narration)).strip().lower()
        if not caption or caption.lower() == narration_clean:
            caption = self._short_overlay(visual_logic, 10)
        words = caption.split()
        if len(words) > 10:
            caption = " ".join(words[:10])
        return self._complete_caption(caption) or "watch the money move"

    def _beat_context(self, beat: dict[str, Any]) -> str:
        props = beat.get("props") if isinstance(beat.get("props"), dict) else {}
        pieces = [
            beat.get("narration"),
            beat.get("visual_instruction"),
            beat.get("content"),
            beat.get("caption"),
        ]
        return " ".join(str(piece) for piece in pieces if piece).strip()

    def _logic_type(self, visual_logic: Any) -> str:
        if isinstance(visual_logic, dict):
            return str(visual_logic.get("type") or "").strip().lower()
        return ""

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
        cleaned = " ".join(str(text or "").split())
        if not cleaned or self._is_abstract_visual_logic(cleaned):
            return None
        if context and not self._numbers_respect_context(cleaned, context):
            return None
        comparison = re.split(r"\s+vs\.?\s+|\s+versus\s+", cleaned, maxsplit=1, flags=re.I)
        if len(comparison) == 2:
            left = comparison[0].strip()
            right = comparison[1].strip()
            if self._has_number(left) and self._has_number(right):
                return {"type": "comparison", "left": left, "right": right}
            return None
        parts = [part.strip() for part in re.split(r"\s*(?:->|→)\s*", cleaned) if part.strip()]
        if len(parts) >= 3:
            lowered = cleaned.lower()
            if any(word in lowered for word in ("inflation", "tax", "fee", "fees", "real value", "loss", "lose")):
                return {"type": "decay", "input": parts[0], "factor": parts[1], "output": parts[2]}
            if any(word in lowered for word in ("growth", "return", "sip", "compound", "wealth")):
                return {"type": "growth", "input": parts[0], "rate": parts[1], "output": parts[2]}
            return {"type": "flow", "source": parts[0], "process": parts[1], "result": parts[2]}
        return None

    def _typed_visual_logic_is_valid(self, visual_logic: Any) -> bool:
        if not isinstance(visual_logic, dict):
            return False
        logic_type = self._logic_type(visual_logic)
        required = self.VISUAL_LOGIC_SCHEMA.get(logic_type)
        if not required:
            return False
        if not all(str(visual_logic.get(key) or "").strip() for key in required):
            return False
        text = self._visual_logic_to_text(visual_logic)
        if self._is_abstract_visual_logic(text) or not self._has_number(text) or not self._has_impact(text):
            return False
        if logic_type == "comparison":
            return self._has_number(str(visual_logic.get("left") or "")) and self._has_number(str(visual_logic.get("right") or ""))
        if logic_type == "emphasis":
            return self._has_number(text) and self._has_impact(text)
        if logic_type == "flow" and not self._flow_semantically_valid(visual_logic):
            return False
        if logic_type in {"flow", "decay", "growth"}:
            return self._has_visual_structure(text) and all(self._has_number(str(visual_logic.get(key) or "")) for key in required)
        return True

    def _flow_semantically_valid(self, visual_logic: dict[str, Any]) -> bool:
        source = str(visual_logic.get("source") or "")
        process = str(visual_logic.get("process") or "")
        result = str(visual_logic.get("result") or "")
        lowered = f"{source} {process} {result}".lower()
        if any(word in lowered for word in ("salary", "income", "paycheck")):
            return (
                any(word in source.lower() for word in ("salary", "income", "paycheck"))
                and any(word in process.lower() for word in ("expense", "expenses", "tax", "spend", "spent", "emi", "rent"))
                and any(word in result.lower() for word in ("left", "saving", "savings", "leak", "loss"))
            )
        values = [self._first_numeric_value(part) for part in (source, process, result)]
        money_parts = [part for part in (source, process, result) if "₹" in part]
        if len(money_parts) == 3 and all(value > 0 for value in values):
            return values[0] >= values[1] >= values[2] or values[0] <= values[1] <= values[2]
        return True

    def _visual_logic_relevant_to_context(self, visual_logic: Any, context: str) -> bool:
        if not isinstance(visual_logic, dict) or not context.strip():
            return True
        logic_text = self._visual_logic_to_text(visual_logic)
        context_numbers = set(self._money_tokens(context) + self._percent_tokens(context))
        logic_numbers = set(self._money_tokens(logic_text) + self._percent_tokens(logic_text))
        if context_numbers and logic_numbers and not logic_numbers.issubset(context_numbers | self._derived_context_number_tokens(context)):
            return False
        logic_keywords = self._meaningful_keywords(logic_text)
        context_keywords = self._meaningful_keywords(context)
        if not context_keywords or not logic_keywords:
            return True
        return bool(logic_keywords & context_keywords)

    def _derived_context_number_tokens(self, context: str) -> set[str]:
        lowered = context.lower()
        derived: set[str] = set()
        amounts = self._money_tokens(context)
        percents = self._percent_tokens(context)
        if any(word in lowered for word in ("month", "monthly", "year", "yearly", "leak", "lost", "gone")):
            for amount in amounts:
                derived.add(self._format_rupees(self._first_numeric_value(amount) * 12))
        if amounts and any(word in lowered for word in ("cannot", "can't", "broke", "save", "saved", "emotion", "manual")):
            derived.add("₹0")
        if any(word in lowered for word in ("inflation", "real value", "fd", "fixed deposit")) and amounts and percents:
            derived.add(self._inflation_output(amounts[0], percents[0]))
        return derived

    def _meaningful_keywords(self, text: str) -> set[str]:
        stop = {
            "cannot", "cant", "save", "saved", "emergency", "fund", "money", "real",
            "value", "left", "source", "process", "result", "year", "month", "months",
        }
        words = set(re.findall(r"[A-Za-z]{3,}", text.lower()))
        return {word for word in words if word not in stop}

    def _visual_logic_to_text(self, visual_logic: Any) -> str:
        if not isinstance(visual_logic, dict):
            return " ".join(str(visual_logic or "").split())
        logic_type = self._logic_type(visual_logic)
        if logic_type == "comparison":
            return f"{self._humanize_money_phrase(str(visual_logic.get('left', '')))} vs {self._humanize_money_phrase(str(visual_logic.get('right', '')))}".strip()
        if logic_type == "flow":
            return (
                f"{self._humanize_money_phrase(str(visual_logic.get('source', '')))} -> "
                f"{self._humanize_money_phrase(str(visual_logic.get('process', '')))} -> "
                f"{self._humanize_money_phrase(str(visual_logic.get('result', '')))}"
            ).strip()
        if logic_type == "decay":
            return f"{visual_logic.get('input', '')} -> {visual_logic.get('factor', '')} -> {visual_logic.get('output', '')}".strip()
        if logic_type == "growth":
            return f"{visual_logic.get('input', '')} -> {visual_logic.get('rate', '')} -> {visual_logic.get('output', '')}".strip()
        if logic_type == "emphasis":
            return f"{visual_logic.get('headline', '')} {visual_logic.get('subtext', '')}".strip()
        return " ".join(str(value) for value in visual_logic.values() if value).strip()

    def _repair_visual_logic(self, visual_logic: Any, beat: dict[str, Any], context: str = "") -> str:
        visual_logic_text = self._visual_logic_to_text(visual_logic)
        candidates = [visual_logic_text]
        props = beat.get("props") if isinstance(beat.get("props"), dict) else {}
        combined = " ".join(
            str(props.get(key) or "")
            for key in ("headline", "subtext", "leftContent", "rightContent", "content", "caption")
            if props.get(key)
        )
        if combined:
            candidates.append(combined)
        if props.get("leftContent") and props.get("rightContent"):
            candidates.append(f"{props.get('leftContent')} vs {props.get('rightContent')}")
        for key in ("headline", "subtext", "leftContent", "rightContent", "content", "caption", "query", "title"):
            value = props.get(key)
            if value:
                candidates.append(str(value))
        raw_data = props.get("data")
        if isinstance(raw_data, list):
            data_parts = []
            for point in raw_data[:4]:
                if isinstance(point, dict):
                    label = point.get("label")
                    value = point.get("value")
                    if label is not None and value is not None:
                        data_parts.append(f"{label}={value}")
            if data_parts:
                candidates.append("data: " + ", ".join(data_parts))
        raw_nodes = props.get("nodes")
        if isinstance(raw_nodes, list):
            labels = [
                str(node.get("label") if isinstance(node, dict) else node)
                for node in raw_nodes
                if str(node.get("label") if isinstance(node, dict) else node).strip()
            ]
            if labels:
                candidates.append(" -> ".join(labels))
        for candidate in candidates:
            cleaned = " ".join(str(candidate or "").split())
            if not self._numbers_respect_context(cleaned, context):
                continue
            if self._is_concrete_visual_logic(cleaned) and self._has_visual_structure(cleaned):
                return cleaned
        return self._contextual_visual_logic(context or self._beat_context(beat), beat)

    def _contextual_visual_logic(self, context: str, beat: dict[str, Any] | None = None) -> str:
        return self._visual_logic_to_text(self._contextual_visual_logic_object(context, beat))

    def _contextual_visual_logic_object(self, context: str, beat: dict[str, Any] | None = None) -> dict[str, Any]:
        lowered = context.lower()
        amounts = list(dict.fromkeys(self._money_tokens(context)))
        percents = list(dict.fromkeys(self._percent_tokens(context)))
        if any(word in lowered for word in ("tax", "taxes", "elss", "deduction", "80c")):
            paid = self._amount_with_label(amounts[0] if amounts else "₹20,000", "tax paid")
            deduction = self._amount_with_label(amounts[1] if len(amounts) > 1 else "₹1,50,000", "deduction")
            return {"type": "comparison", "left": paid, "right": deduction}
        if percents and amounts and any(word in lowered for word in ("save", "saved", "cannot", "can't", "broke")):
            return {"type": "comparison", "left": f"{percents[0]} cannot save", "right": f"{amounts[0]} emergency fund"}
        if any(word in lowered for word in ("automate", "auto debit", "manual", "emotion", "emotional")):
            amount = amounts[0] if amounts else "₹5,000"
            result = amounts[1] if len(amounts) > 1 and self._first_numeric_value(amounts[1]) == 0 else "₹0 Saved"
            return {
                "type": "flow",
                "source": self._amount_with_label(amount, "Auto Debit"),
                "process": self._amount_with_label(amount, "Invested"),
                "result": self._amount_with_label(result, "Emotional Spend"),
            }
        if (
            beat
            and isinstance(beat.get("visual_logic"), dict)
            and str(beat["visual_logic"].get("type") or "").lower() == "flow"
            and any(word in lowered for word in ("salary", "paycheck", "income"))
        ):
            salary = amounts[0] if amounts else "₹25,000 Salary"
            expense = amounts[1] if len(amounts) > 1 else self._derived_rupee(salary, 0.92, "Expenses")
            left = amounts[2] if len(amounts) > 2 else self._derived_rupee(salary, 0.08, "Left")
            return {
                "type": "flow",
                "source": self._amount_with_label(salary, "Salary"),
                "process": self._amount_with_label(expense, "Expenses"),
                "result": self._amount_with_label(left, "Left"),
            }
        if any(word in lowered for word in ("salary", "paycheck", "income")) and any(word in lowered for word in ("leak", "defaults", "default")) and len(amounts) >= 2:
            return {
                "type": "comparison",
                "left": self._amount_with_label(amounts[0], "Salary"),
                "right": self._amount_with_label(amounts[1], "Invisible Leak"),
            }
        if any(word in lowered for word in ("budget", "waste", "spend", "spent", "monthly", "leak", "gone")):
            waste = amounts[0] if amounts else "₹5,000 Monthly Leak"
            yearly = amounts[1] if len(amounts) > 1 else self._derived_rupee(waste, 12, "Yearly Loss")
            return {"type": "flow", "source": self._amount_with_label(waste, "Monthly Leak"), "process": "12 months", "result": self._amount_with_label(yearly, "Lost")}
        if any(word in lowered for word in ("fd", "fixed deposit", "inflation")):
            principal = amounts[0] if amounts else "₹1,00,000"
            rate = percents[0] if percents else "6% Inflation"
            output = self._inflation_output(principal, rate) if amounts or percents else "₹94,000 Real Value"
            return {"type": "decay", "input": principal, "factor": rate if "inflation" in rate.lower() else f"{rate} Inflation", "output": f"{output} Real Value"}
        if any(word in lowered for word in ("credit", "debt", "loan", "interest")):
            debt = amounts[0] if amounts else "₹50,000 Debt"
            interest = amounts[1] if len(amounts) > 1 else "₹18,000 Interest/year"
            return {"type": "comparison", "left": debt, "right": interest}
        if any(word in lowered for word in ("salary", "paycheck", "income", "expense", "expenses")):
            salary = amounts[0] if amounts else "₹25,000 Salary"
            expense = amounts[1] if len(amounts) > 1 else self._derived_rupee(salary, 0.92, "Expenses")
            left = amounts[2] if len(amounts) > 2 else self._derived_rupee(salary, 0.08, "Left")
            return {
                "type": "flow",
                "source": self._amount_with_label(salary, "Salary"),
                "process": self._amount_with_label(expense, "Expenses"),
                "result": self._amount_with_label(left, "Left"),
            }
        if len(amounts) >= 2:
            return {"type": "comparison", "left": amounts[0], "right": amounts[1]}
        if beat:
            fallback = self._concrete_fallback_logic(beat)
            logic = self._string_visual_logic_to_object(fallback, context)
            if logic and self._typed_visual_logic_is_valid(logic):
                return logic
        return {"type": "flow", "source": "₹5,000 Manual Choice", "process": "12 months", "result": "₹60,000 Lost"}

    def _coerce_logic_to_pattern(self, logic: dict[str, Any], context: str, preferred_pattern: str) -> dict[str, Any]:
        amounts = list(dict.fromkeys(self._money_tokens(context)))
        percents = list(dict.fromkeys(self._percent_tokens(context)))
        if preferred_pattern == "COMPARISON":
            if len(amounts) >= 2:
                return {"type": "comparison", "left": amounts[0], "right": amounts[1]}
            if amounts and percents:
                return {"type": "comparison", "left": percents[0], "right": amounts[0]}
        if preferred_pattern in {"MONEY_FLOW", "VALUE_DECAY", "LOOP", "GROWTH"}:
            if preferred_pattern == "VALUE_DECAY":
                principal = amounts[0] if amounts else "₹1,00,000"
                rate = percents[0] if percents else "6% Inflation"
                return {"type": "decay", "input": principal, "factor": rate if "inflation" in rate.lower() else f"{rate} Inflation", "output": f"{self._inflation_output(principal, rate)} Real Value"}
            if preferred_pattern == "GROWTH":
                amount = amounts[0] if amounts else "₹5,000"
                output = amounts[1] if len(amounts) > 1 else self._derived_rupee(amount, 12, "Invested")
                rate = percents[0] if percents else "12 months"
                return {"type": "growth", "input": self._amount_with_label(amount, "SIP"), "rate": rate, "output": output}
            source = amounts[0] if amounts else "₹5,000 Monthly Leak"
            result = amounts[1] if len(amounts) > 1 else self._derived_rupee(source, 12, "Lost")
            return {"type": "flow", "source": self._amount_with_label(source, "Monthly Leak"), "process": "12 months", "result": self._amount_with_label(result, "Lost")}
        if preferred_pattern == "EMPHASIS":
            return logic
        return logic

    def _amount_with_label(self, amount: str, label: str) -> str:
        return amount if label.lower() in amount.lower() else f"{amount} {label}"

    def _safe_emphasis_logic_object(self, context: str) -> dict[str, Any]:
        logic = self._contextual_visual_logic_object(context, None)
        if self._typed_visual_logic_is_valid(logic):
            return logic
        return {"type": "comparison", "left": "76% cannot save", "right": "₹5,000 emergency fund"}

    def _inflation_output(self, principal: str, rate: str) -> str:
        principal_value = self._first_numeric_value(principal)
        rate_value = self._first_numeric_value(rate)
        if principal_value <= 0 or rate_value <= 0:
            return "₹94,000"
        return self._format_rupees(principal_value * max(0.0, 1 - (rate_value / 100)))

    def _derived_rupee(self, amount: str, multiplier: float, label: str) -> str:
        value = self._first_numeric_value(amount)
        if value <= 0:
            return f"₹0 {label}"
        return f"{self._format_rupees(value * multiplier)} {label}"

    def _first_numeric_value(self, text: str) -> float:
        match = re.search(r"[\d,.]+", text)
        if not match:
            return 0.0
        try:
            return float(match.group(0).replace(",", ""))
        except ValueError:
            return 0.0

    def _format_rupees(self, value: float) -> str:
        number = int(round(value / 100.0) * 100) if value >= 1000 else int(round(value))
        raw = str(max(number, 0))
        if len(raw) <= 3:
            return f"₹{raw}"
        last_three = raw[-3:]
        rest = raw[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        return "₹" + ",".join(groups + [last_three])

    def _concrete_fallback_logic(self, beat: dict[str, Any]) -> str:
        props = beat.get("props") if isinstance(beat.get("props"), dict) else {}
        headline = self._short_overlay(str(props.get("headline") or props.get("content") or beat.get("content") or ""), 5)
        subtext = self._short_overlay(str(props.get("subtext") or props.get("caption") or beat.get("caption") or ""), 8)
        combined = f"{headline} {subtext}".strip()
        if self._passes_text_gate(combined):
            return combined
        return "76% can't save ₹5,000"

    def _is_concrete_visual_logic(self, text: str) -> bool:
        if not text or len(text.strip()) < 6:
            return False
        if self._is_abstract_visual_logic(text):
            return False
        return self._has_number(text)

    def _is_abstract_visual_logic(self, text: str) -> bool:
        lowered = " ".join(str(text or "").lower().replace("_", " ").split())
        if not lowered:
            return True
        if lowered in self.ABSTRACT_VISUAL_WORDS:
            return True
        if any(re.search(rf"\b{re.escape(bad)}\b", lowered) for bad in self.ABSTRACT_VISUAL_WORDS):
            return True
        return any(bad in lowered for bad in {"static image", "split screen", "display statistic", "show comparison", "display data"})

    def _has_number(self, text: str) -> bool:
        return bool(re.search(r"(?:₹\s?[\d,.]+(?:\s?(?:lakh|crore|k|m)\b)?|\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?\b)", text, re.I))

    def _numbers_respect_context(self, candidate: str, context: str) -> bool:
        context_numbers = set(self._money_tokens(context) + self._percent_tokens(context))
        if not context_numbers:
            return True
        candidate_numbers = set(self._money_tokens(candidate) + self._percent_tokens(candidate))
        if not candidate_numbers:
            return True
        return candidate_numbers.issubset(context_numbers)

    def _has_visual_structure(self, text: str) -> bool:
        lowered = text.lower()
        if re.search(r"\s(?:->|→)\s", text):
            return len([part for part in re.split(r"\s*(?:->|→)\s*", text) if part.strip()]) >= 3
        if re.search(r"\b(vs|versus|compared|than)\b", lowered):
            return len(re.split(r"\b(?:vs|versus|compared|than)\b", lowered, maxsplit=1)) == 2
        if any(word in lowered for word in ("left", "loss", "interest/year", "real value", "after inflation", "yearly loss")):
            return True
        return False

    def _has_impact(self, text: str) -> bool:
        lowered = text.lower()
        if any(word in lowered for word in ("loss", "lose", "lost", "left", "debt", "interest", "broke", "can't", "cannot", "real value", "inflation", "less than", "more than")):
            return True
        if re.search(r"\b(vs|versus|compared|than)\b", lowered):
            return True
        if re.search(r"(?:->|→)", text):
            numbers = self._numeric_values(text)
            if len(numbers) >= 2:
                high = max(numbers)
                low = min(numbers)
                return high > 0 and ((high - low) / high) >= 0.05
        return bool(re.search(r"\b(?:[7-9]\d|100)%", text))

    def _passes_text_gate(self, text: str) -> bool:
        return self._is_concrete_visual_logic(text) and self._has_visual_structure(text) and self._has_impact(text)

    def _passes_visual_gate(self, intent: str, pattern: str, visual_logic: str, beat: dict[str, Any]) -> bool:
        if intent == "CONTEXT" or pattern == "CONTEXT":
            return True
        return self._passes_text_gate(visual_logic)

    def _props_pass_visual_gate(self, component: str, pattern: str, visual_logic: str, props: dict[str, Any]) -> bool:
        if component == "BrollOverlay":
            return True
        if component == "FlowDiagram":
            nodes = props.get("nodes")
            if not isinstance(nodes, list) or len(nodes) < 3:
                return False
            labels = [str(node.get("label") if isinstance(node, dict) else node) for node in nodes]
            return self._passes_text_gate(" -> ".join(labels))
        if component == "SplitComparison":
            return self._passes_text_gate(f"{props.get('leftContent', '')} vs {props.get('rightContent', '')}")
        if component in {"BarChart", "LineChart"}:
            data = props.get("data")
            title = str(props.get("title") or visual_logic)
            return isinstance(data, list) and len(data) >= 2 and not self._is_abstract_visual_logic(title)
        if component in {"StatExplosion", "TextBurst", "ReactionCard", "StatReveal"}:
            text = " ".join(str(props.get(key) or "") for key in ("headline", "content", "subtext", "kicker"))
            return self._has_number(text or visual_logic) and self._has_impact(text or visual_logic) and not self._is_abstract_visual_logic(text or visual_logic)
        return self._passes_text_gate(visual_logic)

    def _regenerate_props(
        self,
        component: str,
        pattern: str,
        visual_logic: str,
        caption: str,
        context: str,
        beat: dict[str, Any],
    ) -> dict[str, Any]:
        regenerated_logic = visual_logic if self._passes_text_gate(visual_logic) else self._contextual_visual_logic(context, beat)
        color = "red" if self._sentiment(regenerated_logic) == "negative" else self._beat_color(beat.get("color"))
        if component == "FlowDiagram":
            return self._flow_props(pattern, regenerated_logic, caption, {}, color, {**beat, "props": {}})
        if component == "SplitComparison":
            left, right = self._concrete_split_from_logic(regenerated_logic, caption)
            return {"leftLabel": "CLAIM", "leftContent": left, "rightLabel": "REALITY", "rightContent": right}
        if component in {"BarChart", "LineChart"}:
            data = self._extract_data_points(regenerated_logic)
            if len(data) >= 2:
                return {
                    "title": self._short_overlay(regenerated_logic, 8),
                    "data": data,
                    "color": self._chart_color(regenerated_logic),
                    "unit": self._unit_label(regenerated_logic),
                    "animationSpeed": "fast",
                }
        return self._safe_emphasis_props(self._safe_emphasis_logic(context or regenerated_logic), caption)

    def _safe_emphasis_logic(self, context: str) -> str:
        logic = self._visual_logic_to_text(self._safe_emphasis_logic_object(context))
        if self._passes_text_gate(logic):
            return logic
        return "76% can't save ₹5,000"

    def _safe_emphasis_props(self, visual_logic: str, caption: str) -> dict[str, Any]:
        headline = self._dominant_phrase(visual_logic)
        words = headline.split()
        if len(words) > 6:
            headline = " ".join(words[:6])
        return {
            "headline": headline,
            "subtext": caption or self._short_overlay(visual_logic.replace(headline, ""), 6),
            "color": "red" if self._sentiment(visual_logic) == "negative" else "orange",
        }

    def _kill_switch_beat(self, normalized: dict[str, Any]) -> dict[str, Any]:
        context = self._beat_context(normalized)
        visual_logic_object = self._safe_emphasis_logic_object(context)
        visual_logic_text = self._visual_logic_to_text(visual_logic_object)
        caption = self._repair_caption("", visual_logic_text, context)
        props = self._safe_emphasis_props(visual_logic_text, caption)
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

    def _repair_props(
        self,
        component: str,
        pattern: str,
        visual_logic: str,
        caption: str,
        beat: dict[str, Any],
    ) -> dict[str, Any]:
        raw_props = beat.get("props") if isinstance(beat.get("props"), dict) else {}
        color = self._beat_color(raw_props.get("color") or beat.get("color"))
        if component == "FlowDiagram":
            return self._flow_props(pattern, visual_logic, caption, raw_props, color, beat)
        if component == "SplitComparison":
            left_label, left_content, right_label, right_content = self._parse_split(
                str(raw_props.get("leftContent") or visual_logic),
                str(raw_props.get("rightContent") or caption),
            )
            if self._is_abstract_visual_logic(left_content) or self._is_abstract_visual_logic(right_content):
                left_content, right_content = self._concrete_split_from_logic(visual_logic, caption)
            left_content = self._humanize_money_phrase(left_content)
            right_content = self._humanize_money_phrase(right_content)
            left_label = self._extract_split_label(left_content)
            right_label = self._extract_split_label(right_content)
            return {
                "leftLabel": self._humanize_split_label(str(raw_props.get("leftLabel") or left_label), left_content),
                "leftContent": left_content,
                "rightLabel": self._humanize_split_label(str(raw_props.get("rightLabel") or right_label), right_content),
                "rightContent": right_content,
                "leftColor": self._color_for_label(left_content),
                "rightColor": self._color_for_label(right_content),
            }
        if component in {"BarChart", "LineChart"}:
            data = raw_props.get("data") if isinstance(raw_props.get("data"), list) else self._extract_data_points(visual_logic)
            if len(data) < 2:
                return {"content": self._short_overlay(visual_logic, 5), "subtext": caption, "color": color}
            chart_color = self._extract_color(visual_logic) or (color if color in {"red", "teal", "orange"} else "orange")
            return {
                "title": str(raw_props.get("title") or self._short_overlay(visual_logic, 8) or "Financial Trend"),
                "data": data,
                "color": chart_color,
                "unit": str(raw_props.get("unit") or self._unit_label(visual_logic)),
                "animationSpeed": "fast",
            }
        if component == "StatExplosion":
            return {"headline": str(raw_props.get("headline") or self._dominant_phrase(visual_logic)), "subtext": caption, "color": self._color_for_label(f"{visual_logic} {caption}") or color}
        if component == "TextBurst":
            return {"content": str(raw_props.get("content") or self._short_overlay(visual_logic, 5)), "color": color}
        if component == "ReactionCard":
            return {"content": str(raw_props.get("content") or self._short_overlay(visual_logic, 5)), "subtext": caption, "color": color}
        if component == "BrollOverlay":
            return {
                "overlayText": caption,
                "query": str(raw_props.get("query") or raw_props.get("searchQuery") or self._short_overlay(visual_logic, 5)),
                "brand": "10 Minute Finance",
                "sentiment": self._sentiment(f"{visual_logic} {caption}"),
            }
        return {"content": self._short_overlay(visual_logic, 5), "color": color}

    def _flow_props(
        self,
        pattern: str,
        visual_logic: str,
        caption: str,
        raw_props: dict[str, Any],
        color: str,
        beat: dict[str, Any],
    ) -> dict[str, Any]:
        mode = self._flow_mode(pattern, raw_props.get("mode"))
        layout = self._flow_layout(mode, raw_props.get("layout"))
        nodes = self._flow_nodes(raw_props.get("nodes"), visual_logic, pattern)
        connections = self._flow_connections(raw_props.get("connections"), nodes, mode)
        if beat.get("context_ref"):
            layout = str(raw_props.get("layout") or layout)
        caption = self._complete_caption(caption)
        semantic_color = (
            self._color_for_label(" ".join(str(node.get("label") or "") for node in nodes))
            or self._color_for_label(caption)
            or self._color_for_label(visual_logic)
            or color
        )
        return {
            "mode": mode,
            "layout": layout,
            "spacing": str(raw_props.get("spacing") or "equal") if raw_props.get("spacing") in {"equal", "weighted"} else "equal",
            "direction": str(raw_props.get("direction") or "forward") if raw_props.get("direction") in {"forward", "reverse"} else "forward",
            "nodes": nodes,
            "connections": connections,
            "caption": caption,
            "captionColor": self._color_for_label(caption) or semantic_color,
            "color": semantic_color,
            "contextRef": str(beat.get("context_ref") or ""),
            "isOutro": bool(beat.get("is_outro")),
        }

    def _polish_flow_display_props(self, props: dict[str, Any], visual_logic: str) -> dict[str, Any]:
        nodes = props.get("nodes")
        if not isinstance(nodes, list):
            return props
        polished = dict(props)
        result_text = str(nodes[-1].get("label") if nodes and isinstance(nodes[-1], dict) else "")
        flow_text = f"{visual_logic} {result_text} {polished.get('caption', '')}"
        if self._is_loss_result(flow_text):
            polished["captionColor"] = "red"
            polished["color"] = "red"
        if props.get("isOutro") and self._looks_like_outro_loss(flow_text) and len(nodes) >= 3:
            first = dict(nodes[0])
            last = dict(nodes[-1])
            first["label"] = self._monthly_punchline_source(str(first.get("label") or ""))
            first["style"] = self._node_style(str(first.get("role") or "source"), first["label"], "MONEY_FLOW")
            last["label"] = self._humanize_money_phrase(str(last.get("label") or ""))
            last["style"] = self._node_style("result", last["label"], "MONEY_FLOW")
            polished["nodes"] = [first, last]
            polished["connections"] = [{"from": first["id"], "to": last["id"]}]
            polished["caption"] = f"{self._short_money(first['label'])}/month -> {self._short_money(last['label'])} gone"
            polished["captionColor"] = "red"
            polished["color"] = "red"
        return polished

    def _flow_mode(self, pattern: str, value: Any) -> str:
        mode = str(value or "").lower()
        if mode in {"linear", "branch", "loop", "decay", "growth"}:
            return mode
        return {
            "MONEY_FLOW": "linear",
            "VALUE_DECAY": "decay",
            "LOOP": "loop",
            "GROWTH": "growth",
        }.get(pattern, "linear")

    def _flow_layout(self, mode: str, value: Any) -> str:
        layout = str(value or "").lower()
        if layout in {"horizontal", "vertical", "radial"}:
            return layout
        return {"branch": "vertical", "loop": "radial"}.get(mode, "horizontal")

    def _flow_nodes(self, raw_nodes: Any, visual_logic: str, pattern: str) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        if isinstance(raw_nodes, list):
            for index, node in enumerate(raw_nodes[:5]):
                if isinstance(node, dict):
                    node_id = str(node.get("id") or f"node{index + 1}")
                    label = self._humanize_money_phrase(str(node.get("label") or node_id))
                    if self._is_abstract_visual_logic(label):
                        label = self._fallback_node_label(visual_logic, index, pattern)
                    role = str(node.get("role") or self._default_node_role(index, len(raw_nodes))).lower()
                    children = node.get("children") if isinstance(node.get("children"), list) else []
                    nodes.append(
                        {
                            "id": self._safe_id(node_id, index),
                            "label": self._short_overlay(label, 4) or f"Step {index + 1}",
                            "role": role if role in self.VALID_NODE_ROLES else self._default_node_role(index, len(raw_nodes)),
                            "style": self._node_style(role if role in self.VALID_NODE_ROLES else self._default_node_role(index, len(raw_nodes)), label, pattern),
                            "children": [self._short_overlay(str(child), 3) for child in children[:4] if str(child).strip()],
                        }
                    )
                else:
                    label = self._humanize_money_phrase(self._short_overlay(str(node), 4)) if not self._is_abstract_visual_logic(str(node)) else self._fallback_node_label(visual_logic, index, pattern)
                    role = self._default_node_role(index, len(raw_nodes))
                    nodes.append(
                        {
                            "id": f"node{index + 1}",
                            "label": label,
                            "role": role,
                    "style": self._node_style(role, label, pattern),
                            "children": [],
                        }
                    )
        if len(nodes) < 2:
            nodes = self._fallback_flow_nodes(visual_logic, pattern)
        return nodes[:5]

    def _fallback_node_label(self, visual_logic: str, index: int, pattern: str) -> str:
        fallback_nodes = self._fallback_flow_nodes(visual_logic, pattern)
        if index < len(fallback_nodes):
            return fallback_nodes[index]["label"]
        return f"Step {index + 1}"

    def _fallback_flow_nodes(self, visual_logic: str, pattern: str) -> list[dict[str, Any]]:
        arrow_parts = [self._humanize_money_phrase(self._short_overlay(part, 4)) for part in re.split(r"\s*(?:->|→)\s*", visual_logic) if part.strip()]
        if len(arrow_parts) >= 3:
            labels = arrow_parts[:5]
            if pattern == "VALUE_DECAY":
                roles = ["source", "modifier", "result"]
            elif pattern == "GROWTH":
                roles = ["source", "modifier", "result"]
            else:
                roles = ["source"] + ["process"] * max(len(labels) - 2, 0) + ["result"]
        elif pattern == "VALUE_DECAY":
            labels = ["₹1,00,000", "6% Inflation", "₹94,000 Value"]
            roles = ["source", "modifier", "result"]
        elif pattern == "LOOP":
            labels = ["₹50,000 Debt", "₹18,000 Interest", "₹68,000 Owed", "Repeat"]
            roles = ["source", "process", "result", "process"]
        elif pattern == "GROWTH":
            labels = ["₹5,000 SIP", "12% Growth", "₹60,000 Invested", "Wealth"]
            roles = ["source", "process", "modifier", "result"]
        else:
            words = [word for word in re.findall(r"[A-Za-z₹0-9%.,]+", visual_logic) if len(word) > 2][:4]
            labels = words if len(words) >= 3 else ["₹25,000 Salary", "₹23,000 Expenses", "₹2,000 Left"]
            roles = ["source"] + ["process"] * max(len(labels) - 2, 0) + ["result"]
        return [
            {
                "id": f"node{index + 1}",
                "label": label,
                "role": roles[min(index, len(roles) - 1)],
                "style": self._node_style(roles[min(index, len(roles) - 1)], label, pattern),
                "children": [],
            }
            for index, label in enumerate(labels[:5])
        ]

    def _node_style(self, role: str, label: str, pattern: str = "") -> dict[str, str]:
        semantic_color = self._color_for_label(label)
        if role == "source":
            return {"size": "large", "color": semantic_color or "teal"}
        if role == "modifier":
            return {"size": "small", "color": semantic_color or "orange"}
        if role == "result":
            is_loss_result = pattern == "VALUE_DECAY" or self._sentiment(label) == "negative" or "left" in label.lower()
            return {"size": "large", "color": semantic_color or ("red" if is_loss_result else "teal")}
        return {"size": "medium", "color": semantic_color or "orange"}

    def _flow_connections(self, raw_connections: Any, nodes: list[dict[str, Any]], mode: str) -> list[dict[str, str]]:
        node_ids = {node["id"] for node in nodes}
        connections: list[dict[str, str]] = []
        if isinstance(raw_connections, list):
            for connection in raw_connections:
                if not isinstance(connection, dict):
                    continue
                start = str(connection.get("from") or "")
                end = str(connection.get("to") or "")
                if start in node_ids and end in node_ids and start != end:
                    connections.append({"from": start, "to": end})
        if connections:
            return connections[:6]
        for index in range(len(nodes) - 1):
            connections.append({"from": nodes[index]["id"], "to": nodes[index + 1]["id"]})
        if mode == "loop" and len(nodes) > 2:
            connections.append({"from": nodes[-1]["id"], "to": nodes[0]["id"]})
        return connections

    def _default_node_role(self, index: int, total: int) -> str:
        if index == 0:
            return "source"
        if index == total - 1:
            return "result"
        return "process"

    def _safe_id(self, value: str, index: int) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
        return cleaned or f"node{index + 1}"

    def _dominant_phrase(self, text: str) -> str:
        money_match = re.search(r"(₹\s?[\d,.]+(?:\s?(?:lakh|crore|k|m)\b)?)", text, re.I)
        pct_match = re.search(r"(\d+(?:\.\d+)?%)", text)
        if money_match:
            return money_match.group(1).replace(" ", "")
        if pct_match:
            return pct_match.group(1)
        words = re.findall(r"[A-Za-z0-9₹%]+", text)
        return " ".join(words[:4]).upper() if words else "KEY STAT"

    def _short_overlay(self, text: str, max_words: int) -> str:
        words = re.findall(r"[A-Za-z0-9₹%.,]+", text)
        return " ".join(words[:max_words]).strip()

    def _sentiment(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ("debt", "broke", "loss", "lose", "risk", "mistake", "negative")):
            return "negative"
        if any(word in lowered for word in ("save", "profit", "growth", "invest", "positive", "wealth")):
            return "positive"
        return "neutral"

    def _looks_like_line_chart(self, text: str) -> bool:
        lowered = text.lower()
        return any(word in lowered for word in ("line", "trend", "growth", "over time", "from 20"))

    def _chart_color(self, text: str) -> str:
        sentiment = self._sentiment(text)
        if sentiment == "negative":
            return "red"
        if sentiment == "positive":
            return "teal"
        return "orange"

    def _kicker(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ("debt", "broke", "loss", "mistake")):
            return "Risk signal"
        if any(word in lowered for word in ("save", "invest", "wealth", "growth")):
            return "Money move"
        return "Finance insight"

    def _unit_label(self, text: str) -> str:
        if "%" in text:
            return "%"
        if "₹" in text or "rupee" in text.lower():
            return "₹"
        return ""

    def _money_tokens(self, text: str) -> list[str]:
        return [
            token.replace(" ", "")
            for token in re.findall(r"₹\s?[\d,.]+(?:\s?(?:lakh|crore|k|m)\b)?", text, re.I)
        ]

    def _percent_tokens(self, text: str) -> list[str]:
        return re.findall(r"\d+(?:\.\d+)?%", text)

    def _numeric_values(self, text: str) -> list[float]:
        values: list[float] = []
        for value in re.findall(r"\d+(?:\.\d+)?", text):
            try:
                values.append(float(value))
            except ValueError:
                continue
        return values

    def _extract_data_points(self, text: str) -> list[dict[str, float | str]]:
        data_section = self._extract_data_section(text)
        pairs = re.findall(r"([^=,;:]+?)\s*=\s*₹?\s*([\d,.]+)", data_section)
        if pairs:
            return [
                {"label": label.strip(), "value": float(value.replace(",", ""))}
                for label, value in pairs[:6]
            ]
        pairs = re.findall(r"([A-Za-z]{3,9}\s?\d{0,4}|\d{4})\D{0,12}(\d+(?:\.\d+)?)", text)
        data = [{"label": label.strip(), "value": float(value)} for label, value in pairs[:6]]
        if len(data) >= 2:
            return data
        numbers = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", text)[:5]]
        if len(numbers) >= 2:
            return [{"label": f"Point {idx}", "value": value} for idx, value in enumerate(numbers, start=1)]
        return []

    def _extract_data_section(self, text: str) -> str:
        match = re.search(r"data\s*:\s*(.*?)(?:,\s*(?:title|color|unit|insight)\s*:|$)", text, re.I)
        return match.group(1) if match else text

    def _extract_named_field(self, text: str, field: str) -> str:
        match = re.search(rf"{field}\s*:\s*([^,;]+)", text, re.I)
        return match.group(1).strip() if match else ""

    def _extract_color(self, text: str) -> str:
        color = self._extract_named_field(text, "color").lower()
        return color if color in {"red", "teal", "orange"} else ""

    def _beat_color(self, value: Any) -> str:
        color = str(value or "orange").lower()
        return color if color in {"red", "orange", "teal", "navy", "white"} else "orange"

    def _parse_split(self, content: str, caption: str) -> tuple[str, str, str, str]:
        text = content or caption
        parts = re.split(r"\s+vs\.?\s+|\s+\|\s+", text, maxsplit=1, flags=re.I)
        left = parts[0].strip() if parts else "What you think"
        right = parts[1].strip() if len(parts) > 1 else (caption or "Reality")
        return self._extract_split_label(left), left, self._extract_split_label(right), right

    def _concrete_split_from_logic(self, visual_logic: str, caption: str) -> tuple[str, str]:
        parts = re.split(r"\s+vs\.?\s+|\s+versus\s+|\s+\|\s+", visual_logic, maxsplit=1, flags=re.I)
        if len(parts) == 2:
            return self._short_overlay(parts[0], 6), self._short_overlay(parts[1], 6)
        numbers = re.findall(r"(?:₹\s?[\d,.]+(?:\s?(?:lakh|crore|k))?|\d+(?:\.\d+)?%)", visual_logic, re.I)
        if len(numbers) >= 2:
            return numbers[0], numbers[1]
        return self._short_overlay(visual_logic, 6) or "Claim", self._short_overlay(caption, 6) or "Reality"

    def _extract_split_label(self, content: str) -> str:
        cleaned = re.sub(r"₹\s?[\d,.]+(?:\s?(?:lakh|crore|k|m)\b)?|\d+(?:\.\d+)?%", "", content, flags=re.I)
        words = [
            word
            for word in re.findall(r"[A-Za-z]+", cleaned)
            if word.lower() not in {"cannot", "cant", "less", "than", "left", "goes", "to"}
        ]
        return " ".join(words[:3]).title() or "Amount"

    def _humanize_split_label(self, label: str, content: str) -> str:
        if label.strip().upper() in {"WHAT YOU THINK", "REALITY", "CLAIM"}:
            return self._extract_split_label(content)
        return self._extract_split_label(content) or label

    def _humanize_money_phrase(self, text: str) -> str:
        cleaned = " ".join(str(text or "").replace("₹0.", "₹0").split())
        cleaned = re.sub(r"₹0\s+Saved\s+Emotional Spend\b", "₹0 left to spend", cleaned, flags=re.I)
        cleaned = re.sub(r"₹0\s+Emotional Spend\b", "₹0 left to spend", cleaned, flags=re.I)
        cleaned = re.sub(r"₹0\s+left\s+to\b(?!\s+spend)", "₹0 left to spend", cleaned, flags=re.I)
        cleaned = re.sub(r"\bmonthly leak\b", "leaks every month", cleaned, flags=re.I)
        cleaned = re.sub(r"\bauto\s+(?:invested|investment)\b", "auto-invested", cleaned, flags=re.I)
        cleaned = re.sub(r"\bgoes to investment\b", "auto-invested", cleaned, flags=re.I)
        cleaned = re.sub(r"\b(?:Invested|Investment)\b", "auto-invested", cleaned, flags=re.I)
        cleaned = cleaned.replace("auto-auto-invested", "auto-invested")
        return cleaned

    def _complete_caption(self, caption: str) -> str:
        cleaned = self._humanize_money_phrase(caption)
        cleaned = re.sub(r"₹0\s+left\s+to\b(?!\s+spend)", "₹0 left to spend", cleaned, flags=re.I)
        return cleaned

    def _color_for_label(self, label: str) -> str:
        lowered = str(label or "").lower()
        if "₹0" in str(label or "") or any(word in lowered for word in ("lost", "loss", "leak", "leaks", "debt", "expense", "expenses")):
            return "red"
        if any(word in lowered for word in ("investment", "invested", "auto-invested", "saved", "growth")):
            return "teal"
        return ""

    def _is_loss_result(self, text: str) -> bool:
        lowered = str(text or "").lower()
        return "₹0" in str(text or "") or any(word in lowered for word in ("loss", "lost", "leak", "leaks", "debt", "expense"))

    def _looks_like_outro_loss(self, text: str) -> bool:
        lowered = str(text or "").lower()
        return (
            any(word in lowered for word in ("month", "monthly", "leaks every month", "/month"))
            and any(word in lowered for word in ("gone", "lost", "loss"))
            and len(self._money_tokens(text)) >= 2
        )

    def _monthly_punchline_source(self, label: str) -> str:
        money = self._short_money(label)
        return f"{money} leaks every month" if money else self._humanize_money_phrase(label)

    def _short_money(self, text: str) -> str:
        tokens = self._money_tokens(text)
        return tokens[0] if tokens else ""
