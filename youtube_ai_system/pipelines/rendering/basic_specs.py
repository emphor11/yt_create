from __future__ import annotations

from typing import Any

from ...contracts.rendering import RenderSpec


class BasicRenderSpecFactory:
    """Builds simple Remotion specs that do not need semantic normalization."""

    def stat_explosion(self, content: str, caption: str, color: str, duration_sec: float) -> RenderSpec:
        return RenderSpec(
            composition="StatExplosion",
            props={"headline": content, "subtext": caption, "color": color, "durationSec": duration_sec},
            duration_sec=duration_sec,
            source="remotion_stat_explosion",
        )

    def text_burst(self, content: str, color: str, duration_sec: float) -> RenderSpec:
        return RenderSpec(
            composition="TextBurst",
            props={"content": content, "color": color, "durationSec": duration_sec},
            duration_sec=duration_sec,
            source="remotion_text_burst",
        )

    def reaction_card(self, content: str, caption: str, color: str, duration_sec: float) -> RenderSpec:
        return RenderSpec(
            composition="ReactionCard",
            props={"content": content, "subtext": caption, "color": color, "durationSec": duration_sec},
            duration_sec=duration_sec,
            source="remotion_reaction_card",
        )

    def split_comparison(
        self,
        left_label: str,
        left_content: str,
        right_label: str,
        right_content: str,
        duration_sec: float,
    ) -> RenderSpec:
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

    def transition(self, duration_sec: float = 0.5) -> RenderSpec:
        return RenderSpec(
            composition="SceneTransition",
            props={"durationSec": duration_sec},
            duration_sec=duration_sec,
            source="remotion_transition",
        )

    def intro(self, title: str, duration_sec: float = 3.0) -> RenderSpec:
        return RenderSpec(
            composition="IntroCard",
            props={"title": title, "channelName": "YTCreate Finance", "durationSec": duration_sec},
            duration_sec=duration_sec,
            source="remotion_intro",
        )

    def end_card(self, next_title: str = "", duration_sec: float = 5.0) -> RenderSpec:
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

    def thumbnail(self, title: str, dominant: str, supporting: str, variant: int = 1) -> RenderSpec:
        return RenderSpec(
            composition="ThumbnailFrame",
            props={
                "title": title,
                "dominantText": dominant,
                "supportingText": supporting,
                "variant": variant,
                "brand": "YTCreate",
            },
            duration_sec=1 / 30,
            source="remotion_thumbnail",
            output_ext=".jpg",
        )

    def stat_reveal(self, headline: str, subtext: str, sentiment: str, kicker: str, duration_sec: float) -> RenderSpec:
        return RenderSpec(
            composition="StatReveal",
            props={
                "headline": headline,
                "subtext": subtext,
                "sentiment": sentiment,
                "durationSec": duration_sec,
                "kicker": kicker,
            },
            duration_sec=duration_sec,
            source="remotion_stat_reveal",
        )

    def graph(
        self,
        composition: str,
        title: str,
        data: list[dict[str, Any]],
        color: str,
        unit: str,
        duration_sec: float,
    ) -> RenderSpec:
        return RenderSpec(
            composition=composition,
            props={
                "title": title,
                "data": data,
                "color": color,
                "durationSec": duration_sec,
                "unit": unit,
            },
            duration_sec=duration_sec,
            source=f"remotion_{composition.lower()}",
        )
