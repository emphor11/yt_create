from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from flask import current_app

from .scene_mapper import map_pattern_to_component
from .voice_service import VoiceService

MIN_BEAT_DURATION = 1.2
DIRECTED_MIN_BEAT_DURATION = 1.5
COMPONENT_DURATION_WEIGHTS = {
    "StatCard": 1.0,
    "HighlightText": 0.9,
    "ConceptCard": 1.0,
    "ConceptCardScene": 1.0,
    "RiskCard": 1.1,
    "RiskCardScene": 1.1,
    "FlowBar": 1.4,
    "FlowDiagram": 1.6,
    "BalanceBar": 1.5,
    "CalculationStrip": 1.6,
    "SplitComparison": 1.3,
    "SplitComparisonScene": 1.3,
    "GrowthChart": 1.5,
    "GrowthChartScene": 1.5,
    "StepFlow": 1.4,
    "StepFlowScene": 1.4,
    "MoneyFlowDiagram": 1.8,
    "DebtSpiralVisualizer": 1.8,
    "SIPGrowthEngine": 1.9,
}
PATTERN_PRIORITY = {
    "MoneyFlowDiagram": 7,
    "DebtSpiralVisualizer": 7,
    "SIPGrowthEngine": 7,
    "GrowthChart": 6,
    "SplitComparison": 6,
    "FlowDiagram": 6,
    "BalanceBar": 6,
    "NumericComparison": 5,
    "RiskCard": 3,
    "StepFlow": 2,
    "ConceptCard": 1,
}


class SceneBuilder:
    def __init__(self) -> None:
        self.voice_service = VoiceService()

    def build_scenes(self, sections: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        scenes: list[dict[str, Any]] = []
        audio_root = self._audio_root()

        for index, section in enumerate(sections, start=1):
            narration = str(section.get("text") or "").strip()
            if not narration:
                continue

            audio_file = str(section.get("audio_file") or "").strip()
            supplied_duration = section.get("audio_duration")
            if audio_file and supplied_duration:
                resolved_audio_file = str(Path(audio_file).expanduser().resolve())
                resolved_duration = float(supplied_duration)
            else:
                voice_result = self.voice_service.generate_scene_audio(audio_root, index, narration)
                resolved_audio_file = str(Path(voice_result.audio_path).expanduser().resolve())
                resolved_duration = float(voice_result.duration_sec)

            audio_duration = round(max(resolved_duration, 0.0), 2)
            scene_duration = self._scene_duration(audio_duration, section)
            beats = self._section_beats(section)
            timed_beats = self._timeline_from_beats(beats, audio_duration, section)
            self._extend_last_beat_to_scene_duration(timed_beats, scene_duration)
            pattern, data, concept = self._scene_visual_contract(section)
            map_pattern_to_component(pattern)

            scenes.append(
                {
                    "scene_id": f"scene_{index}",
                    "concept": concept,
                    "concept_type": str(section.get("concept_type") or concept or "").strip(),
                    "pattern": pattern,
                    "data": data,
                    "direction": section.get("direction"),
                    "theme": section.get("theme") or {},
                    "beats": timed_beats,
                    "duration": round(scene_duration, 2),
                    "total_duration": round(scene_duration, 2),
                    "audio_duration": round(audio_duration, 2),
                    "audio_file": resolved_audio_file,
                }
            )

        return {"scenes": scenes}

    def _section_beats(self, section: dict[str, Any]) -> list[dict[str, Any]]:
        visual_plan = section.get("visual_plan") or []
        beats: list[dict[str, Any]] = []
        for item in visual_plan:
            beats.extend((item.get("beats") or {}).get("beats") or [])

        cleaned = self._clean_and_dedupe_beats(beats, str(section.get("text") or ""))
        if len(cleaned) >= 2:
            return self._force_escalation(cleaned, str(section.get("text") or ""))
        if cleaned:
            return self._force_escalation(self._expand_minimum_beats(cleaned, str(section.get("text") or "")), str(section.get("text") or ""))

        fallback_text = self._fallback_text(str(section.get("text") or ""))
        return self._force_escalation(
            self._expand_minimum_beats([{"component": "ConceptCard", "text": fallback_text}], str(section.get("text") or "")),
            str(section.get("text") or ""),
        )

    def _timeline_from_beats(
        self,
        beats: list[dict[str, Any]],
        audio_duration: float,
        section: dict[str, Any],
    ) -> list[dict[str, Any]]:
        min_duration = DIRECTED_MIN_BEAT_DURATION if section.get("direction") else MIN_BEAT_DURATION
        beats = self._merge_for_min_duration(beats, audio_duration, min_duration)
        if not beats:
            return []
        aligned_spans = self._sentence_aligned_spans(beats, audio_duration, section)
        if aligned_spans is not None:
            return self._timeline_from_spans(beats, aligned_spans)
        durations = self._component_weighted_durations(beats, audio_duration, min_duration)

        timeline: list[dict[str, Any]] = []
        cursor = 0.0
        for index, (beat, duration) in enumerate(zip(beats, durations)):
            start_time = cursor
            end_time = cursor + duration
            if index == len(beats) - 1:
                end_time = audio_duration if audio_duration > 0 else cursor + duration
            timed_beat = {
                "component": beat["component"],
                "text": beat["text"],
                "start_time": round(start_time, 2),
                "end_time": round(end_time, 2),
                "emphasis": self._beat_emphasis(index, len(beats)),
            }
            for key in ("subtext", "steps", "props", "data", "source_text", "sentence_index"):
                if key in beat:
                    timed_beat[key] = beat[key]
            timeline.append(timed_beat)
            cursor = end_time

        return timeline

    def _extend_last_beat_to_scene_duration(self, beats: list[dict[str, Any]], scene_duration: float) -> None:
        if not beats:
            return
        beats[-1]["end_time"] = round(max(scene_duration, float(beats[-1].get("end_time") or 0.0)), 2)

    def _timeline_from_spans(
        self,
        beats: list[dict[str, Any]],
        spans: list[tuple[float, float]],
    ) -> list[dict[str, Any]]:
        timeline: list[dict[str, Any]] = []
        for index, (beat, (start_time, end_time)) in enumerate(zip(beats, spans)):
            timed_beat = {
                "component": beat["component"],
                "text": beat["text"],
                "start_time": round(start_time, 2),
                "end_time": round(end_time, 2),
                "emphasis": self._beat_emphasis(index, len(beats)),
            }
            for key in ("subtext", "steps", "props", "data", "source_text", "sentence_index"):
                if key in beat:
                    timed_beat[key] = beat[key]
            timeline.append(timed_beat)
        return timeline

    def _audio_root(self) -> Path:
        storage_root = Path(current_app.config["STORAGE_ROOT"]).expanduser().resolve()
        audio_root = storage_root / "audio" / "scene_builder"
        audio_root.mkdir(parents=True, exist_ok=True)
        return audio_root

    def _scene_visual_contract(self, section: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
        visual_plan = section.get("visual_plan") or []
        best_pattern = ""
        best_data: dict[str, Any] = {}
        best_concept = ""
        best_score = -1

        if visual_plan:
            for item in visual_plan:
                visual = item.get("visual") or {}
                pattern = str(visual.get("pattern") or "").strip()
                data = dict(visual.get("data") or {})
                concept = str((item.get("concept") or {}).get("concept") or "").strip()
                score = PATTERN_PRIORITY.get(pattern, 0)
                if pattern and data and concept and score > best_score:
                    best_pattern = pattern
                    best_data = data
                    best_concept = concept
                    best_score = score

            if best_pattern:
                return best_pattern, self._enrich_data_with_section(best_pattern, best_data, section), best_concept

            inferred = self._infer_contract_from_visual_plan(visual_plan)
            if inferred is not None:
                pattern, data, concept = inferred
                return pattern, self._enrich_data_with_section(pattern, data, section), concept
        fallback_text = self._fallback_text(str(section.get("text") or ""))
        return "ConceptCard", {"title": fallback_text.upper()}, fallback_text

    def _infer_contract_from_visual_plan(self, visual_plan: list[dict[str, Any]]) -> tuple[str, dict[str, Any], str] | None:
        best: tuple[str, dict[str, Any], str] | None = None
        best_score = -1
        for item in visual_plan:
            inferred = self._infer_contract_from_beats(item)
            if inferred is None:
                continue
            pattern, _, _ = inferred
            score = PATTERN_PRIORITY.get(pattern, 0)
            if score > best_score:
                best = inferred
                best_score = score
        return best

    def _infer_contract_from_beats(self, item: dict[str, Any]) -> tuple[str, dict[str, Any], str] | None:
        beats = ((item.get("beats") or {}).get("beats") or [])
        if not beats:
            return None
        last_beat = beats[-1]
        component = str(last_beat.get("component") or "").strip()
        concept = str(last_beat.get("text") or "").strip()
        if not component or not concept:
            return None
        if component == "RiskCard":
            return "RiskCard", {"title": concept.upper()}, concept
        if component == "SplitComparison":
            return "SplitComparison", {"headline": concept}, concept
        if component == "StepFlow":
            return "StepFlow", {"steps": [concept]}, concept
        if component == "GrowthChart":
            return "GrowthChart", {"end": concept, "curve": "up"}, concept
        values = [str(beat.get("text") or "").strip() for beat in beats if str(beat.get("text") or "").strip()]
        if component == "CalculationStrip":
            flat_steps: list[Any] = []
            for beat in beats:
                data = beat.get("data") if isinstance(beat.get("data"), dict) else {}
                steps = data.get("steps") or beat.get("steps") or []
                if isinstance(steps, list):
                    flat_steps.extend(steps)
            if flat_steps:
                return "CalculationStrip", {"steps": flat_steps}, concept
            return "CalculationStrip", {"values": values}, concept
        if component == "StatCard":
            return "NumericComparison", {"values": values}, concept
        return "ConceptCard", {"title": concept.upper()}, concept

    def _enrich_data_with_section(self, pattern: str, data: dict[str, Any], section: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(data)
        finance_concept = section.get("finance_concept") or {}
        narrative_arc = section.get("narrative_arc") or {}
        state = section.get("state") or {}

        start_value = self._first_text_value(
            finance_concept.get("start_value"),
            narrative_arc.get("start_state"),
            state.get("money_in"),
        )
        end_value = self._first_text_value(
            finance_concept.get("end_value"),
            narrative_arc.get("end_state"),
            state.get("balance_change"),
        )
        rate = self._first_text_value(
            narrative_arc.get("rate"),
            state.get("money_out"),
            self._percentage_text(finance_concept.get("percentage")),
        )

        if pattern == "NumericComparison":
            values = [str(value).strip() for value in enriched.get("values") or [] if str(value).strip()]
            values = self._append_unique_values(values, [start_value, rate, end_value])
            if values:
                enriched["values"] = values[:3]
            if start_value:
                enriched["start"] = start_value
            if rate:
                enriched["rate"] = rate
            if end_value:
                enriched["end"] = end_value
        elif pattern == "GrowthChart":
            if start_value:
                enriched["start"] = start_value
            if end_value:
                enriched["end"] = end_value
            if rate:
                enriched["rate"] = rate
        elif pattern in {"RiskCard", "ConceptCard"}:
            if rate:
                enriched["subtitle"] = f"{rate} impact"
            if end_value:
                enriched["value"] = end_value
            if state:
                enriched["state"] = dict(state)
        elif pattern == "SplitComparison":
            if start_value and not enriched.get("left"):
                enriched["left"] = {"label": start_value}
            if end_value and not enriched.get("right"):
                enriched["right"] = {"label": end_value}
            if rate:
                enriched["rate"] = rate
        elif pattern == "StepFlow":
            steps = [str(step).strip() for step in enriched.get("steps") or [] if str(step).strip()]
            enriched["steps"] = self._append_unique_values(steps, [start_value, rate, end_value]) or steps

        visual_type = str(section.get("visual_type") or narrative_arc.get("visual_type") or "").strip()
        if visual_type:
            enriched["visual_type"] = visual_type
        return enriched

    def _clean_and_dedupe_beats(self, beats: list[dict[str, Any]], section_text: str) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        seen_texts: set[str] = set()
        for beat in beats:
            text = self._clean_beat_text(str(beat.get("text") or "").strip(), section_text)
            if not text:
                continue
            key = text.lower()
            if key in seen_texts:
                continue
            seen_texts.add(key)
            cleaned_beat: dict[str, Any] = {
                "component": str(beat.get("component") or "").strip() or "ConceptCard",
                "text": text,
            }
            for extra_key in ("subtext", "steps", "props", "data", "source_text", "sentence_index"):
                if extra_key in beat:
                    cleaned_beat[extra_key] = beat[extra_key]
            cleaned.append(cleaned_beat)
        return cleaned

    def _sentence_aligned_spans(
        self,
        beats: list[dict[str, Any]],
        audio_duration: float,
        section: dict[str, Any],
    ) -> list[tuple[float, float]] | None:
        if audio_duration <= 0:
            return None
        if not beats or any("sentence_index" not in beat or not str(beat.get("source_text") or "").strip() for beat in beats):
            return None

        sentence_text_by_index: dict[int, str] = {}
        for beat in beats:
            try:
                sentence_index = int(beat.get("sentence_index"))
            except (TypeError, ValueError):
                return None
            sentence_text_by_index.setdefault(sentence_index, str(beat.get("source_text") or "").strip())

        ordered_sentence_indices = sorted(sentence_text_by_index)
        word_counts = {
            index: max(len(sentence_text_by_index[index].split()), 1)
            for index in ordered_sentence_indices
        }
        total_words = sum(word_counts.values())
        if total_words <= 0:
            return None

        sentence_ranges: dict[int, tuple[float, float]] = {}
        cursor = 0.0
        for position, sentence_index in enumerate(ordered_sentence_indices):
            duration = (word_counts[sentence_index] / total_words) * audio_duration
            start = cursor
            end = cursor + duration
            if position == len(ordered_sentence_indices) - 1:
                end = audio_duration
            sentence_ranges[sentence_index] = (start, end)
            cursor = end

        beat_indices_by_sentence: dict[int, list[int]] = {}
        for beat_index, beat in enumerate(beats):
            beat_indices_by_sentence.setdefault(int(beat.get("sentence_index")), []).append(beat_index)

        spans: list[tuple[float, float]] = [(0.0, 0.0) for _ in beats]
        for sentence_index, beat_indices in beat_indices_by_sentence.items():
            sentence_start, sentence_end = sentence_ranges[sentence_index]
            sentence_duration = max(sentence_end - sentence_start, 0.0)
            weights = [
                COMPONENT_DURATION_WEIGHTS.get(str(beats[index].get("component") or "ConceptCard"), 1.0)
                for index in beat_indices
            ]
            total_weight = sum(weights) or float(len(beat_indices))
            local_cursor = sentence_start
            for position, (beat_index, weight) in enumerate(zip(beat_indices, weights)):
                duration = sentence_duration * (weight / total_weight)
                start = local_cursor
                end = local_cursor + duration
                if position == len(beat_indices) - 1:
                    end = sentence_end
                spans[beat_index] = (start, end)
                local_cursor = end
        return spans

    def _component_weighted_durations(self, beats: list[dict[str, Any]], audio_duration: float, min_duration: float = MIN_BEAT_DURATION) -> list[float]:
        if not beats:
            return []
        if audio_duration <= 0:
            return [min_duration for _ in beats]
        if audio_duration <= min_duration * len(beats):
            equal_duration = audio_duration / len(beats)
            return [equal_duration for _ in beats]

        weights = [COMPONENT_DURATION_WEIGHTS.get(str(beat.get("component") or "ConceptCard"), 1.0) for beat in beats]
        durations = [0.0 for _ in beats]
        remaining_indices = set(range(len(beats)))
        remaining_duration = audio_duration

        while remaining_indices:
            total_weight = sum(weights[index] for index in remaining_indices)
            if total_weight <= 0:
                equal_duration = remaining_duration / len(remaining_indices)
                for index in remaining_indices:
                    durations[index] = equal_duration
                break

            below_minimum = [
                index
                for index in remaining_indices
                if (weights[index] / total_weight) * remaining_duration < min_duration
            ]
            if not below_minimum:
                for index in remaining_indices:
                    durations[index] = (weights[index] / total_weight) * remaining_duration
                break

            for index in below_minimum:
                durations[index] = min_duration
                remaining_duration -= min_duration
                remaining_indices.remove(index)

            if remaining_duration <= 0 and remaining_indices:
                equal_duration = audio_duration / len(beats)
                return [equal_duration for _ in beats]

        return durations

    def _beat_emphasis(self, index: int, total: int) -> str:
        if total <= 1 or index == total - 1:
            return "hero"
        if index == 0:
            return "normal"
        return "subtle"

    def _append_unique_values(self, current: list[str], candidates: list[str]) -> list[str]:
        values = list(current)
        seen = {value.lower() for value in values}
        for candidate in candidates:
            value = str(candidate or "").strip()
            if not value or value.lower() in seen:
                continue
            seen.add(value.lower())
            values.append(value)
        return values

    def _first_text_value(self, *values: Any) -> str:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return ""

    def _percentage_text(self, value: Any) -> str:
        if value is None:
            return ""
        try:
            return f"{float(value):g}%"
        except (TypeError, ValueError):
            return str(value).strip()

    def _fallback_text(self, section_text: str) -> str:
        lowered = section_text.lower()
        if "salary" in lowered and any(token in lowered for token in ("vanish", "vanishes", "disappear", "disappears")):
            return "Salary disappears early"
        if "fix the system" in lowered or ("automate" in lowered and "spend" in lowered):
            return "Automate before you spend"
        words = section_text.split()
        if not words:
            return "Core message"
        phrase = " ".join(words[: min(len(words), 3)]).strip(" ,.-")
        if not re.search(r"[A-Za-z0-9₹]", phrase):
            return "Core message"
        return phrase or "Core message"

    def _merge_for_min_duration(self, beats: list[dict[str, Any]], audio_duration: float, min_duration: float = MIN_BEAT_DURATION) -> list[dict[str, Any]]:
        merged = [dict(beat) for beat in beats]
        while len(merged) > 1 and audio_duration > 0 and (audio_duration / len(merged)) < min_duration:
            last = merged.pop()
            merged[-1]["text"] = self._clean_beat_text(f"{merged[-1]['text']} {last['text']}", merged[-1]["text"])
            merged[-1]["component"] = last["component"] or merged[-1]["component"]
        return merged

    def _expand_minimum_beats(self, beats: list[dict[str, str]], section_text: str) -> list[dict[str, str]]:
        if len(beats) >= 2:
            return beats
        first, second = self._split_section_ideas(section_text)
        base_component = beats[0]["component"] if beats else "ConceptCard"
        primary_text = beats[0]["text"] if beats else first
        if not second or second.lower() == primary_text.lower():
            second = self._consequence_phrase(section_text, primary_text)
        if primary_text.lower() == second.lower():
            words = second.split()
            if len(words) > 1:
                second = " ".join(words[-2:])
        return [
            {"component": base_component, "text": primary_text},
            {"component": "ConceptCard", "text": self._clean_beat_text(second, section_text)},
        ]

    def _split_section_ideas(self, section_text: str) -> tuple[str, str]:
        parts = [part.strip(" ,.-") for part in re.split(r",| and | but | so | because ", section_text, maxsplit=1, flags=re.IGNORECASE) if part.strip()]
        if len(parts) >= 2:
            return self._short_phrase(parts[0]), self._short_phrase(parts[1])
        words = section_text.split()
        midpoint = max(len(words) // 2, 1)
        return self._short_phrase(" ".join(words[:midpoint])), self._short_phrase(" ".join(words[midpoint:]))

    def _short_phrase(self, text: str) -> str:
        words = text.split()
        phrase = " ".join(words[:4]).strip() or self._fallback_text(text)
        return self._clean_beat_text(phrase, text)

    def _scene_duration(self, audio_duration: float, section: dict[str, Any]) -> float:
        visual_plan = section.get("visual_plan") or []
        pattern = ""
        if visual_plan:
            visual = visual_plan[0].get("visual") or {}
            pattern = str(visual.get("pattern") or "").strip()
        tail = 0.8 if pattern in {"MoneyFlowDiagram", "DebtSpiralVisualizer", "SIPGrowthEngine"} else 0.4
        return round(max(float(audio_duration or 0), 0.0) + tail, 2)

    def _clean_beat_text(self, text: str, section_text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip(" ,.-")
        cleaned = re.sub(r"\b(by|and|the|is)$", "", cleaned, flags=re.IGNORECASE).strip(" ,.-")
        lowered = cleaned.lower()
        if lowered == "salary can vanish":
            return "Salary vanishes early"
        if lowered == "salary can vanish by":
            return "Salary vanishes early"
        if lowered == "fix the system":
            return "Automate before you spend"
        if lowered.startswith("automate the") and "₹5,000" in cleaned:
            return "Automate savings"
        if not cleaned:
            return self._fallback_text(section_text)
        return cleaned[:1].upper() + cleaned[1:]

    def _force_escalation(self, beats: list[dict[str, str]], section_text: str) -> list[dict[str, str]]:
        if len(beats) < 2:
            return beats
        first = beats[0]["text"].lower()
        second = beats[1]["text"].lower()
        if first == second or first in second or second in first or self._ideas_overlap(first, second):
            beats[1]["text"] = self._consequence_phrase(section_text, beats[0]["text"])
        return beats

    def _consequence_phrase(self, section_text: str, primary_text: str) -> str:
        lowered = section_text.lower()
        if "salary" in lowered and any(token in lowered for token in ("month feel broken", "month breaks", "feel broken")):
            return "Month feels broken"
        if "salary" in lowered and any(token in lowered for token in ("vanish", "disappear")):
            return "Month feels broken"
        if "fix the system" in lowered or ("automate" in lowered and "spend" in lowered):
            return "Automate savings"
        if "leak" in lowered:
            return "Money leaks away"
        if "debt" in lowered and "trap" in lowered:
            return "Debt keeps growing"
        fallback = self._fallback_text(section_text)
        if fallback.lower() != primary_text.lower():
            return fallback
        words = [word for word in re.findall(r"[A-Za-z0-9₹%,']+", section_text) if word]
        if len(words) >= 2:
            return self._clean_beat_text(" ".join(words[-2:]), section_text)
        return self._clean_beat_text(section_text, section_text)

    def _ideas_overlap(self, first: str, second: str) -> bool:
        stopwords = {"the", "and", "a", "an", "to", "you", "your", "before"}
        first_words = {word for word in re.findall(r"[a-z]+", first) if word not in stopwords}
        second_words = {word for word in re.findall(r"[a-z]+", second) if word not in stopwords}
        return len(first_words.intersection(second_words)) >= 1


def build_scenes(sections: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return SceneBuilder().build_scenes(sections)
