from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from flask import current_app

from .scene_mapper import map_pattern_to_component
from .voice_service import VoiceService

MIN_BEAT_DURATION = 1.2
COMPONENT_DURATION_WEIGHTS = {
    "StatCard": 1.0,
    "HighlightText": 0.9,
    "ConceptCard": 1.0,
    "ConceptCardScene": 1.0,
    "RiskCard": 1.1,
    "RiskCardScene": 1.1,
    "FlowBar": 1.4,
    "CalculationStrip": 1.6,
    "SplitComparison": 1.3,
    "SplitComparisonScene": 1.3,
    "GrowthChart": 1.5,
    "GrowthChartScene": 1.5,
    "StepFlow": 1.4,
    "StepFlowScene": 1.4,
}
PATTERN_PRIORITY = {
    "NumericComparison": 5,
    "GrowthChart": 4,
    "SplitComparison": 4,
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

            audio_duration = self._scene_duration(resolved_duration, section)
            beats = self._section_beats(section)
            timed_beats = self._timeline_from_beats(beats, audio_duration, section)
            pattern, data, concept = self._scene_visual_contract(section)
            map_pattern_to_component(pattern)

            scenes.append(
                {
                    "scene_id": f"scene_{index}",
                    "concept": concept,
                    "pattern": pattern,
                    "data": data,
                    "beats": timed_beats,
                    "duration": round(audio_duration, 2),
                    "total_duration": round(audio_duration, 2),
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
        beats = self._merge_for_min_duration(beats, audio_duration)
        if not beats:
            return []
        durations = self._component_weighted_durations(beats, audio_duration)

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
            for key in ("subtext", "steps"):
                if key in beat:
                    timed_beat[key] = beat[key]
            timeline.append(timed_beat)
            cursor = end_time

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
        if component in {"CalculationStrip", "StatCard"}:
            values = [str(beat.get("text") or "").strip() for beat in beats if str(beat.get("text") or "").strip()]
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
            for extra_key in ("subtext", "steps"):
                if extra_key in beat:
                    cleaned_beat[extra_key] = beat[extra_key]
            cleaned.append(cleaned_beat)
        return cleaned

    def _component_weighted_durations(self, beats: list[dict[str, Any]], audio_duration: float) -> list[float]:
        if not beats:
            return []
        if audio_duration <= 0:
            return [MIN_BEAT_DURATION for _ in beats]
        if audio_duration <= MIN_BEAT_DURATION * len(beats):
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
                if (weights[index] / total_weight) * remaining_duration < MIN_BEAT_DURATION
            ]
            if not below_minimum:
                for index in remaining_indices:
                    durations[index] = (weights[index] / total_weight) * remaining_duration
                break

            for index in below_minimum:
                durations[index] = MIN_BEAT_DURATION
                remaining_duration -= MIN_BEAT_DURATION
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
        return self._clean_beat_text(phrase, section_text)

    def _merge_for_min_duration(self, beats: list[dict[str, Any]], audio_duration: float) -> list[dict[str, Any]]:
        merged = [dict(beat) for beat in beats]
        while len(merged) > 1 and audio_duration > 0 and (audio_duration / len(merged)) < MIN_BEAT_DURATION:
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
        return audio_duration

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
