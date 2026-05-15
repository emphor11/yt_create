from __future__ import annotations

from pathlib import Path
from typing import Any

from ...contracts.rendering import RenderSpec


class RenderSpecDispatcher:
    """Dispatches scene/beat payloads to concrete Remotion RenderSpec objects."""

    def __init__(self, ops: Any) -> None:
        self.ops = ops

    def scene_spec(
        self,
        scene: dict[str, Any],
        duration_sec: float,
        source_asset_path: Path | None = None,
    ) -> RenderSpec:
        ops = self.ops
        visual_type = str(scene.get("visual_type") or "motion_text").lower()
        narration = str(scene.get("narration_text") or "")
        instruction = str(scene.get("visual_instruction") or narration)

        if visual_type == "graph":
            return ops._graph_spec(instruction, duration_sec)
        if visual_type == "broll":
            return ops.beat_spec(
                {
                    "intent": "EXPLANATION",
                    "pattern": "MONEY_FLOW",
                    "visual_logic": ops._regenerate_logic_from_context(instruction or narration),
                    "narration": narration,
                    "estimated_duration_sec": duration_sec,
                }
            )
        return ops._stat_reveal_spec(instruction or narration, duration_sec)

    def beat_spec(
        self,
        beat: dict[str, Any],
        source_asset_path: Path | None = None,
    ) -> RenderSpec:
        ops = self.ops
        if ops._is_structured_beat(beat):
            return ops._structured_beat_spec(beat, source_asset_path=source_asset_path)

        beat_type = str(beat.get("beat_type") or "text_burst").lower()
        content = str(beat.get("content") or "Money reality")
        caption = str(beat.get("caption") or "")
        color = ops._beat_color(beat.get("color"))
        duration_sec = max(float(beat.get("estimated_duration_sec") or 3), 0.5)

        if beat_type == "motion_text":
            return ops._stat_reveal_spec(f"{content} {caption}".strip(), duration_sec)
        if beat_type == "flow_diagram":
            return ops._legacy_flow_diagram_spec(beat, duration_sec, color)
        if beat_type == "graph":
            spec = ops._graph_spec(content, duration_sec)
            spec.props["animationSpeed"] = "fast"
            return spec
        if beat_type == "broll":
            beat_type = "broll_caption"

        if beat_type == "stat_explosion":
            return ops.basic_specs.stat_explosion(content, caption, color, duration_sec)
        if beat_type == "text_burst":
            return ops.basic_specs.text_burst(content, color, duration_sec)
        if beat_type == "reaction_card":
            return ops.basic_specs.reaction_card(content, caption, color, duration_sec)
        if beat_type == "split_comparison":
            left_label, left_content, right_label, right_content = ops._parse_split(content, caption)
            return ops.basic_specs.split_comparison(
                left_label,
                left_content,
                right_label,
                right_content,
                duration_sec,
            )
        if beat_type == "chart":
            spec = ops._graph_spec(content, duration_sec)
            spec.props["animationSpeed"] = "fast"
            return spec
        if beat_type == "broll_caption":
            context = f"{content} {caption}".strip()
            return ops.beat_spec(
                {
                    "intent": "EXPLANATION",
                    "pattern": "MONEY_FLOW",
                    "visual_logic": ops._regenerate_logic_from_context(context),
                    "narration": context,
                    "estimated_duration_sec": duration_sec,
                }
            )

        return ops._stat_reveal_spec(content or caption, duration_sec)

    def structured_beat_spec(self, beat: dict[str, Any], source_asset_path: Path | None = None) -> RenderSpec:
        ops = self.ops
        normalized = ops.normalize_structured_beat(beat)
        component = normalized["component"]
        props = dict(normalized["props"])
        duration_sec = float(normalized["estimated_duration_sec"])
        visual_logic_text = str(normalized.get("visual_logic_text") or ops._visual_logic_to_text(normalized.get("visual_logic")))
        if not ops._props_pass_visual_gate(component, normalized["pattern"], visual_logic_text, props):
            normalized = ops._kill_switch_beat(normalized)
            component = normalized["component"]
            props = dict(normalized["props"])
            duration_sec = float(normalized["estimated_duration_sec"])
            visual_logic_text = str(normalized.get("visual_logic_text") or ops._visual_logic_to_text(normalized.get("visual_logic")))

        if component == "BrollOverlay":
            if source_asset_path is None:
                raise ValueError("BrollOverlay structured beat requires a Pexels/Pixabay source video path.")
            props["videoPath"] = str(source_asset_path)
            props.setdefault("brand", "10 Minute Finance")
            props.setdefault("sentiment", ops._sentiment(f"{visual_logic_text} {normalized['caption']}"))
            return RenderSpec(component, props, duration_sec, "remotion_broll_overlay", source_asset_path=source_asset_path)
        if component in {"BarChart", "LineChart"}:
            props.setdefault("animationSpeed", "fast")
            return RenderSpec(component, props, duration_sec, f"remotion_{component.lower()}")
        return RenderSpec(component, props, duration_sec, f"remotion_{component.lower()}")

    def stat_reveal_spec(self, instruction: str, duration_sec: float) -> RenderSpec:
        ops = self.ops
        headline = ops._dominant_phrase(instruction)
        sentiment = ops._sentiment(instruction)
        return ops.basic_specs.stat_reveal(
            headline,
            ops._short_overlay(instruction.replace(headline, ""), 7),
            sentiment,
            ops._kicker(instruction),
            duration_sec,
        )

    def graph_spec(self, instruction: str, duration_sec: float) -> RenderSpec:
        ops = self.ops
        data = ops._extract_data_points(instruction)
        if len(data) < 2:
            return ops._stat_reveal_spec(instruction, duration_sec)
        composition = "LineChart" if ops._looks_like_line_chart(instruction) else "BarChart"
        return ops.basic_specs.graph(
            composition,
            ops._extract_named_field(instruction, "title") or ops._short_overlay(instruction, 8) or "Financial Trend",
            data,
            ops._extract_color(instruction) or ops._chart_color(instruction),
            ops._extract_named_field(instruction, "unit") or ops._unit_label(instruction),
            duration_sec,
        )
