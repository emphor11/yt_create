from __future__ import annotations

import re
from typing import Any

from .action_beat_engine import ActionBeatEngine
from .cinematic_event_compiler import CinematicEventCompiler
from .scene_debug import SceneDebugTrace
from ..pipelines.visual import BeatExpansionTextHelper, MECHANISM_PHASES, OBJECT_TO_VIEWER_TEXT, PRIMARY_MECHANISM_COMPONENTS


class VisualBeatExpander:
    """Adds enough visual beats for longer narration without changing the scene concept."""

    def __init__(self, action_beat_engine: ActionBeatEngine | None = None) -> None:
        self.action_beat_engine = action_beat_engine or ActionBeatEngine()
        self.cinematic_event_compiler = CinematicEventCompiler()
        self.text_helper = BeatExpansionTextHelper()

    PRIMARY_MECHANISM_COMPONENTS = PRIMARY_MECHANISM_COMPONENTS
    MECHANISM_PHASES = MECHANISM_PHASES
    OBJECT_TO_VIEWER_TEXT = OBJECT_TO_VIEWER_TEXT

    def expand_section(self, section: dict[str, Any], debug_trace: SceneDebugTrace | None = None) -> dict[str, Any]:
        visual_plan = section.get("visual_plan") or []
        if not visual_plan:
            if debug_trace:
                debug_trace.snapshot("beat_expansion_post", section, owner="visual_beat_expander", note="no visual plan")
            return self._attach_cinematic_events(section, debug_trace=debug_trace)

        item = visual_plan[0]
        beats = list(((item.get("beats") or {}).get("beats") or []))
        action_beats = self.action_beat_engine.beats_from_section(section, item, beats)
        if action_beats and len(action_beats) > len(beats):
            return self._attach_cinematic_events(self._updated_section_with_expanded_beats(
                section=section,
                visual_plan=visual_plan,
                item=item,
                before_beats=beats,
                expanded=action_beats,
                strategy="visual_action_graph",
                confidence=0.86,
                debug_trace=debug_trace,
            ), debug_trace=debug_trace)
        text = str(section.get("text") or "")
        sentences = self._sentences(text)
        target = self._target_beat_count(text, sentences)
        if len(beats) >= target or target <= 3:
            if debug_trace:
                debug_trace.snapshot("beat_expansion_post", section, owner="visual_beat_expander", note="unchanged; enough beats")
                debug_trace.determinism("beat_expansion", {"section": section, "target": target}, section)
            return self._attach_cinematic_events(section, debug_trace=debug_trace)

        visual = item.get("visual") or {}
        pattern = str(visual.get("pattern") or "").strip()
        if self._is_already_phase_based_primary_plan(pattern, beats):
            if debug_trace:
                debug_trace.snapshot("beat_expansion_post", section, owner="visual_beat_expander", note="unchanged; primary phase plan")
                debug_trace.determinism("beat_expansion", {"section": section, "target": target}, section)
            return self._attach_cinematic_events(section, debug_trace=debug_trace)
        concept = item.get("concept") or {}
        mechanism = str(section.get("concept_type") or (concept.get("type") if isinstance(concept, dict) else "") or "").strip()
        data = visual.get("data") if isinstance(visual.get("data"), dict) else {}
        story_state = section.get("story_state") if isinstance(section.get("story_state"), dict) else {}
        story_beats = self._beats_from_story_state(
            story_state=story_state,
            mechanism=mechanism,
            pattern=pattern,
            data=data,
            fallback_beats=beats,
            target=target,
        )
        if story_beats:
            expanded = story_beats
            strategy = "story_state"
        else:
            expanded = self._beats_from_sentences(
                sentences=sentences,
                mechanism=mechanism,
                pattern=pattern,
                data=data,
                target=target,
                fallback_beats=beats,
            )
            strategy = "sentence"
        expanded = self._preserve_directed_beats(expanded, beats, pattern, mechanism)
        if len(expanded) <= len(beats):
            if debug_trace:
                debug_trace.snapshot("beat_expansion_post", section, owner="visual_beat_expander", note="unchanged; expansion not longer")
                debug_trace.determinism("beat_expansion", {"section": section, "target": target}, section)
            return self._attach_cinematic_events(section, debug_trace=debug_trace)

        return self._attach_cinematic_events(self._updated_section_with_expanded_beats(
            section=section,
            visual_plan=visual_plan,
            item=item,
            before_beats=beats,
            expanded=expanded,
            strategy=strategy,
            confidence=0.8 if strategy == "story_state" else 0.68,
            debug_trace=debug_trace,
            target=target,
        ), debug_trace=debug_trace)

    def _attach_cinematic_events(self, section: dict[str, Any], debug_trace: SceneDebugTrace | None = None) -> dict[str, Any]:
        updated = self.cinematic_event_compiler.attach_to_section(section, duration_seconds=self._duration_hint(section))
        if debug_trace and updated.get("cinematic_events"):
            debug_trace.snapshot(
                "cinematic_events",
                {
                    "event_count": len(updated.get("cinematic_events") or []),
                    "events": updated.get("cinematic_events") or [],
                },
                owner="cinematic_event_compiler",
            )
            debug_trace.ownership(
                "cinematic_events",
                "cinematic_event_compiler",
                updated.get("cinematic_events") or [],
                "narration-driven visual attention timeline",
            )
        return updated

    def _duration_hint(self, section: dict[str, Any]) -> float | None:
        for key in ("audio_duration", "duration", "target_duration"):
            try:
                value = float(section.get(key) or 0)
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                return value
        return None

    def _updated_section_with_expanded_beats(
        self,
        *,
        section: dict[str, Any],
        visual_plan: list[dict[str, Any]],
        item: dict[str, Any],
        before_beats: list[dict[str, Any]],
        expanded: list[dict[str, Any]],
        strategy: str,
        confidence: float,
        debug_trace: SceneDebugTrace | None,
        target: int | None = None,
    ) -> dict[str, Any]:
        updated_item = dict(item)
        updated_item["beats"] = {"beats": expanded}
        updated_section = dict(section)
        updated_section["visual_plan"] = [updated_item, *visual_plan[1:]]
        if debug_trace:
            pattern = str((item.get("visual") or {}).get("pattern") or "").strip()
            debug_trace.snapshot(
                "beat_expansion_post",
                {
                    "target": target or len(expanded),
                    "strategy": strategy,
                    "before_beats": before_beats,
                    "after_beats": expanded,
                    "section": updated_section,
                },
                owner="visual_beat_expander",
            )
            debug_trace.ownership("beats", "visual_beat_expander", expanded, f"expanded beats using {strategy} strategy")
            debug_trace.confidence("beat_expansion", "beats", f"{len(expanded)} beats", confidence, [f"{strategy} expansion"])
            for index, beat in enumerate(expanded):
                beat_id = f"beat:{index}:{str(beat.get('component') or 'component')}"
                source_ids = [f"director_plan:0:{pattern}"]
                active_action = ((beat.get("data") or {}).get("active_action") or {}) if isinstance(beat.get("data"), dict) else {}
                if active_action.get("id"):
                    source_ids.append(str(active_action["id"]))
                debug_trace.lineage_node(
                    beat_id,
                    "beat",
                    "beat_expansion",
                    str(beat.get("text") or beat.get("component") or f"Beat {index + 1}"),
                    beat,
                    owner="visual_beat_expander",
                    confidence=confidence,
                    source_ids=source_ids,
                )
                debug_trace.lineage_edge(source_ids[0], beat_id, "beat_generated_from_director_plan")
                if len(source_ids) > 1:
                    debug_trace.lineage_edge(source_ids[1], beat_id, "micro_beat_from_visual_action")
            debug_trace.determinism("beat_expansion", {"section": section, "target": target or len(expanded)}, updated_section)
        return updated_section

    def _is_already_phase_based_primary_plan(self, pattern: str, beats: list[dict[str, Any]]) -> bool:
        """Primary mechanism components already carry their own visual phases.

        Expanding these scenes into sentence-count beats repeats the same phase
        multiple times, which restarts Remotion's frameWithinBeat animation and
        makes the visual loop instead of progress. Keep the director's compact
        phase plan and let SceneBuilder stretch phase durations to the audio.
        """
        if pattern not in self.PRIMARY_MECHANISM_COMPONENTS:
            return False
        primary_beats = [beat for beat in beats if beat.get("component") == pattern]
        if len(primary_beats) < 2:
            return False
        return all(str(beat.get("beat_phase") or "").strip() for beat in primary_beats)

    def _beats_from_story_state(
        self,
        *,
        story_state: dict[str, Any],
        mechanism: str,
        pattern: str,
        data: dict[str, Any],
        fallback_beats: list[dict[str, Any]],
        target: int,
    ) -> list[dict[str, Any]]:
        if not story_state:
            return []
        state_change = story_state.get("state_change") or {}
        money = state_change.get("money") if isinstance(state_change.get("money"), dict) else {}
        active_objects = [str(obj) for obj in (story_state.get("active_objects") or []) if str(obj)]
        visual_answer = str(story_state.get("visual_answer") or "").strip()
        visual_question = str(story_state.get("visual_question") or "").strip()
        texts = [
            self._object_setup_text(active_objects, money),
            str(money.get("change_label") or "").strip(),
            self._mechanism_text(pattern, mechanism),
            visual_question,
            visual_answer,
        ]
        texts = [self._sanitize_viewer_text(text) for text in texts if text]
        texts = [text for text in texts if text]
        if len(texts) < target:
            for fallback in self._fallback_texts(fallback_beats, target - len(texts)):
                sanitized = self._sanitize_viewer_text(fallback)
                if sanitized and sanitized not in texts:
                    texts.append(sanitized)
                if len(texts) >= target:
                    break
        if len(texts) < 3:
            return []
        beats: list[dict[str, Any]] = []
        for index, text in enumerate(texts[: max(3, min(target, 7))]):
            is_first = index == 0
            is_last = index == min(len(texts), max(3, min(target, 7))) - 1
            component = self._story_component_for(index, is_first, is_last, pattern, mechanism)
            beat_phase = self._phase_for(pattern, index)
            beat: dict[str, Any] = {
                "component": component,
                "text": text,
                "source_text": text,
                "sentence_index": index,
            }
            if beat_phase:
                beat["beat_phase"] = beat_phase
            beat_data = {"story_state": story_state, **data} if data else {"story_state": story_state}
            if beat_phase:
                beat_data["active_phase"] = beat_phase
            beat["data"] = beat_data
            if component in {
                "FlowDiagram",
                "FlowBar",
                "GrowthChart",
                "EMIStackVisualizer",
                "FOMOPriceCrashVisualizer",
                "PortfolioDiversificationVisualizer",
                "SmallLeaksAccumulator",
                "RiskReturnVisualizer",
                "EmergencyFundVisualizer",
                "OutroRecapVisualizer",
            } and data:
                beat["props"] = data
            beats.append(beat)
        return self._dedupe_adjacent(beats)

    def _story_component_for(self, index: int, is_first: bool, is_last: bool, pattern: str, mechanism: str) -> str:
        if pattern in self.PRIMARY_MECHANISM_COMPONENTS:
            return pattern
        if is_first:
            return "StatCard"
        if is_last:
            return "HighlightText"
        if index == 2 and pattern in {"MoneyFlowDiagram", "FlowDiagram"}:
            return "FlowDiagram"
        if index == 2 and pattern in {"DebtSpiralVisualizer", "CalculationStrip"}:
            return "CalculationStrip"
        if index == 2 and pattern == "InflationErosionVisualizer":
            return "InflationErosionVisualizer"
        if index == 2 and pattern in {"GrowthChart", "SIPGrowthEngine"}:
            return "GrowthChart"
        if mechanism == "risk_return" or pattern == "RiskReturnVisualizer":
            return "RiskReturnVisualizer"
        if index == 2 and pattern == "SplitComparison":
            return "SplitComparison"
        return self._component_for("", index, is_first, is_last, pattern, mechanism)

    def _phase_for(self, pattern: str, index: int) -> str:
        phases = self.MECHANISM_PHASES.get(pattern)
        if not phases:
            return ""
        return phases[min(index, len(phases) - 1)]

    def _object_setup_text(self, active_objects: list[str], money: dict[str, Any]) -> str:
        primary = active_objects[0] if active_objects else ""
        label = self.OBJECT_TO_VIEWER_TEXT.get(primary, "")
        amount = str(money.get("from") or "").strip()
        if amount and label:
            return f"{amount} - {label}"
        if amount:
            return amount
        if label:
            return label
        return primary.replace("_", " ").title() if primary else ""

    def _mechanism_text(self, pattern: str, mechanism: str) -> str:
        if pattern == "MoneyFlowDiagram":
            return "Money path becomes visible"
        if pattern == "DebtSpiralVisualizer":
            return "Interest beats payment"
        if pattern == "SIPGrowthEngine":
            return "Compounding engine starts"
        if pattern == "EMIStackVisualizer":
            return "Fixed payments stack"
        if pattern == "FOMOPriceCrashVisualizer":
            return "Hype becomes loss"
        if pattern == "PortfolioDiversificationVisualizer":
            return "Risk gets spread"
        if pattern == "SmallLeaksAccumulator":
            return "Small leaks add up"
        if pattern == "RiskReturnVisualizer":
            return "Risk and return separate"
        if pattern == "EmergencyFundVisualizer":
            return "The buffer absorbs the shock"
        if pattern == "OutroRecapVisualizer":
            return "The system comes together"
        if pattern == "UniversalMechanismRenderer":
            return "The idea changes on screen"
        if pattern in {"GrowthChart", "InflationErosionVisualizer"}:
            return "Value path changes"
        if pattern == "SplitComparison":
            return "Two paths separate"
        return mechanism.replace("_", " ").title()

    def _sanitize_viewer_text(self, text: str) -> str:
        return self.text_helper.sanitize_viewer_text(text)

    def _target_beat_count(self, text: str, sentences: list[str]) -> int:
        return self.text_helper.target_beat_count(text, sentences)

    def _beats_from_sentences(
        self,
        *,
        sentences: list[str],
        mechanism: str,
        pattern: str,
        data: dict[str, Any],
        target: int,
        fallback_beats: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        selected = sentences[:target]
        if len(selected) < target:
            selected.extend(self._fallback_texts(fallback_beats, target - len(selected)))
        if not selected:
            return fallback_beats

        beats: list[dict[str, Any]] = []
        for index, sentence in enumerate(selected[:target]):
            is_first = index == 0
            is_last = index == min(target, len(selected)) - 1
            component = self._component_for(sentence, index, is_first, is_last, pattern, mechanism)
            beat_phase = self._phase_for(pattern, index)
            raw_text = self._beat_text(sentence, mechanism, is_last)
            sanitized_text = self._sanitize_viewer_text(raw_text) or raw_text
            beat = {
                "component": component,
                "text": sanitized_text,
                "source_text": sentence,
                "sentence_index": min(index, max(len(sentences) - 1, 0)),
            }
            if beat_phase:
                beat["beat_phase"] = beat_phase
            component_data = {**data, "active_phase": beat_phase} if data and beat_phase else data
            if component in self.PRIMARY_MECHANISM_COMPONENTS and component_data:
                beat["data"] = component_data
            if component in {
                "FlowDiagram",
                "FlowBar",
                "EMIStackVisualizer",
                "FOMOPriceCrashVisualizer",
                "PortfolioDiversificationVisualizer",
                "SmallLeaksAccumulator",
                "RiskReturnVisualizer",
                "EmergencyFundVisualizer",
                "OutroRecapVisualizer",
            } and data:
                beat["data"] = data
                beat["props"] = data
            if component == "GrowthChart" and data:
                beat["data"] = data
                beat["props"] = data
            if component == "SplitComparison" and data:
                beat["data"] = data
            beats.append(beat)
        return self._dedupe_adjacent(beats)

    def _preserve_directed_beats(
        self,
        expanded: list[dict[str, Any]],
        original: list[dict[str, Any]],
        pattern: str,
        mechanism: str,
    ) -> list[dict[str, Any]]:
        required_components: list[str] = []
        if pattern == "DebtSpiralVisualizer" or mechanism == "debt_trap":
            required_components.append("DebtSpiralVisualizer")
        if pattern == "SIPGrowthEngine" or mechanism in {"sip_growth", "compounding"}:
            required_components.append("SIPGrowthEngine")
        if pattern == "MoneyFlowDiagram" or mechanism in {"salary_drain", "rent_burden", "tax_drain"}:
            required_components.append("MoneyFlowDiagram")
        if pattern == "InflationErosionVisualizer" or mechanism in {"inflation_erosion", "real_return", "fd_vs_inflation"}:
            required_components.append("InflationErosionVisualizer")
        if pattern == "LifestyleCreepVisualizer" or mechanism == "lifestyle_inflation":
            required_components.append("LifestyleCreepVisualizer")
        if pattern == "EMIStackVisualizer" or mechanism in {"emi_pressure", "emi_stack"}:
            required_components.append("EMIStackVisualizer")
        if pattern == "FOMOPriceCrashVisualizer" or mechanism in {"fomo_risk", "speculation_risk"}:
            required_components.append("FOMOPriceCrashVisualizer")
        if pattern == "PortfolioDiversificationVisualizer" or mechanism == "diversification":
            required_components.append("PortfolioDiversificationVisualizer")
        if pattern == "SmallLeaksAccumulator" or mechanism in {"expense_leakage", "subscription_leak"}:
            required_components.append("SmallLeaksAccumulator")
        if pattern == "RiskReturnVisualizer" or mechanism == "risk_return":
            required_components.append("RiskReturnVisualizer")
        if pattern == "EmergencyFundVisualizer" or mechanism == "emergency_fund":
            required_components.append("EmergencyFundVisualizer")
        if pattern == "OutroRecapVisualizer" or mechanism == "outro":
            required_components.append("OutroRecapVisualizer")

        result = list(expanded)
        for component in required_components:
            original_beat = next((beat for beat in original if beat.get("component") == component), None)
            existing_index = next((index for index, beat in enumerate(result) if beat.get("component") == component), None)
            if existing_index is not None:
                if original_beat and self._has_component_data(original_beat, component) and not self._has_component_data(result[existing_index], component):
                    merged = dict(result[existing_index])
                    merged["data"] = original_beat.get("data")
                    if original_beat.get("props") is not None:
                        merged["props"] = original_beat.get("props")
                    result[existing_index] = merged
                continue
            if not original_beat:
                continue
            preserved = dict(original_beat)
            preserved.setdefault("source_text", preserved.get("text") or component)
            insert_at = min(2, len(result))
            result.insert(insert_at, preserved)
        return self._dedupe_adjacent(result[:9])

    def _has_component_data(self, beat: dict[str, Any], component: str = "") -> bool:
        data = beat.get("data")
        props = beat.get("props")
        expected_keys = {
            "CalculationStrip": ("steps",),
            "DebtSpiralVisualizer": ("balances", "principal"),
            "MoneyFlowDiagram": ("flows", "source", "remainder"),
            "SIPGrowthEngine": ("monthly_sip", "final_corpus"),
            "InflationErosionVisualizer": ("start", "end"),
            "LifestyleCreepVisualizer": ("start_income", "end_income"),
            "EMIStackVisualizer": ("salary", "emis"),
            "FOMOPriceCrashVisualizer": ("points",),
            "PortfolioDiversificationVisualizer": ("assets",),
            "SmallLeaksAccumulator": ("leaks", "monthly_loss"),
            "RiskReturnVisualizer": ("safe_asset", "growth_asset"),
            "EmergencyFundVisualizer": ("buffer_label", "shock_label"),
            "OutroRecapVisualizer": ("actions",),
            "UniversalMechanismRenderer": ("cinematic_events",),
        }.get(component, ("steps", "balances", "flows", "monthly_sip"))
        if isinstance(data, dict) and any(key in data for key in expected_keys):
            return True
        if isinstance(props, dict) and any(key in props for key in expected_keys):
            return True
        return False

    def _component_for(self, sentence: str, index: int, is_first: bool, is_last: bool, pattern: str, mechanism: str) -> str:
        if pattern in self.PRIMARY_MECHANISM_COMPONENTS:
            return pattern
        if is_first:
            return "StatCard"
        if is_last:
            return "HighlightText"
        if re.search(r"₹|%|\d", sentence):
            return "StatCard"
        if pattern in {"FlowDiagram", "MoneyFlowDiagram"} or mechanism in {"expense_leakage", "emi_pressure", "lifestyle_inflation", "salary_drain"}:
            return "FlowDiagram" if index in {2, 4} else "StatCard"
        if pattern in {"DebtSpiralVisualizer", "CalculationStrip"} or mechanism == "debt_trap":
            return "CalculationStrip" if index in {2, 4} else "StatCard"
        if pattern == "InflationErosionVisualizer" or mechanism in {"inflation_erosion", "real_return", "fd_vs_inflation"}:
            return "InflationErosionVisualizer" if index in {2, 4} else "StatCard"
        if pattern in {"GrowthChart", "SIPGrowthEngine"} or mechanism in {"sip_growth", "compounding"}:
            return "GrowthChart" if index in {2, 4} else "StatCard"
        if mechanism == "risk_return" or pattern == "RiskReturnVisualizer":
            return "RiskReturnVisualizer"
        if pattern == "SplitComparison" or mechanism in {"diversification", "speculation_risk"}:
            return "SplitComparison" if index == 2 else "StatCard"
        return "StatCard"

    def _beat_text(self, sentence: str, mechanism: str, is_last: bool) -> str:
        return self.text_helper.beat_text(sentence, mechanism, is_last)

    def _money_tail(self, lowered: str) -> str:
        return self.text_helper.money_tail(lowered)

    def _percent_tail(self, lowered: str) -> str:
        return self.text_helper.percent_tail(lowered)

    def _consequence_text(self, clean: str, mechanism: str) -> str:
        return self.text_helper.consequence_text(clean, mechanism)

    def _short_phrase(self, text: str, max_words: int = 5) -> str:
        return self.text_helper.short_phrase(text, max_words)

    def _fallback_texts(self, beats: list[dict[str, Any]], count: int) -> list[str]:
        return self.text_helper.fallback_texts(beats, count)

    def _sentences(self, text: str) -> list[str]:
        return self.text_helper.sentences(text)

    def _dedupe_adjacent(self, beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.text_helper.dedupe_adjacent(beats)
