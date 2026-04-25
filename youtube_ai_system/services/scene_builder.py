from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from flask import current_app

from .scene_mapper import map_pattern_to_component
from .voice_service import VoiceService

MIN_BEAT_DURATION = 0.6
MAX_BEAT_DURATION = 2.5
WEIGHT_MULTIPLIERS = {
    "high": 1.2,
    "medium": 1.0,
    "low": 0.9,
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
                    "audio_file": resolved_audio_file,
                }
            )

        return {"scenes": scenes}

    def _section_beats(self, section: dict[str, Any]) -> list[dict[str, str]]:
        visual_plan = section.get("visual_plan") or []
        beats = []
        if visual_plan:
            beats = ((visual_plan[0].get("beats") or {}).get("beats") or [])

        cleaned = [
            {
                "component": str(beat.get("component") or "").strip(),
                "text": self._clean_beat_text(str(beat.get("text") or "").strip(), str(section.get("text") or "")),
            }
            for beat in beats
            if self._clean_beat_text(str(beat.get("text") or "").strip(), str(section.get("text") or ""))
        ]
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
        beats: list[dict[str, str]],
        audio_duration: float,
        section: dict[str, Any],
    ) -> list[dict[str, Any]]:
        weight_level = str((section.get("weight") or {}).get("level") or "medium").lower()
        multiplier = WEIGHT_MULTIPLIERS.get(weight_level, 1.0)
        weighted_lengths = self._weighted_lengths(beats)
        total_weight = max(sum(weighted_lengths), 1.0)
        raw_durations = []
        for index, weight in enumerate(weighted_lengths):
            base = (audio_duration * (weight / total_weight)) * multiplier
            variation = self._timing_variation(beats[index]["text"], index)
            raw_durations.append(base * variation)
        durations = [max(MIN_BEAT_DURATION, min(MAX_BEAT_DURATION, duration)) for duration in raw_durations]

        timeline: list[dict[str, Any]] = []
        current_time = 0.0
        for index, beat in enumerate(beats):
            duration = durations[index]
            end_time = min(audio_duration, current_time + duration)
            if end_time <= current_time:
                end_time = min(audio_duration, current_time + MIN_BEAT_DURATION)
            timeline.append(
                {
                    "component": beat["component"],
                    "text": beat["text"],
                    "start_time": round(current_time, 2),
                    "end_time": round(end_time, 2),
                    "emphasis": "hero" if index == len(beats) - 1 else "normal",
                }
            )
            current_time = end_time

        return timeline

    def _audio_root(self) -> Path:
        storage_root = Path(current_app.config["STORAGE_ROOT"]).expanduser().resolve()
        audio_root = storage_root / "audio" / "scene_builder"
        audio_root.mkdir(parents=True, exist_ok=True)
        return audio_root

    def _scene_visual_contract(self, section: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
        visual_plan = section.get("visual_plan") or []
        if visual_plan:
            item = visual_plan[0]
            visual = item.get("visual") or {}
            pattern = str(visual.get("pattern") or "").strip()
            data = dict(visual.get("data") or {})
            concept = str((item.get("concept") or {}).get("concept") or "").strip()
            if pattern and data and concept:
                return pattern, data, concept
            inferred = self._infer_contract_from_beats(item)
            if inferred is not None:
                return inferred
        fallback_text = self._fallback_text(str(section.get("text") or ""))
        return "ConceptCard", {"title": fallback_text.upper()}, fallback_text

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

    def _fallback_text(self, section_text: str) -> str:
        lowered = section_text.lower()
        if "salary" in lowered and any(token in lowered for token in ("vanish", "vanishes", "disappear", "disappears")):
            return "Salary disappears early"
        if "fix the system" in lowered or ("automate" in lowered and "spend" in lowered):
            return "Automate before you spend"
        words = section_text.split()
        return " ".join(words[:3]).strip() or "Key Idea"

    def _weighted_lengths(self, beats: list[dict[str, str]]) -> list[float]:
        weights: list[float] = []
        for index, beat in enumerate(beats):
            word_count = max(len(str(beat.get("text") or "").split()), 1)
            char_bonus = min(len(str(beat.get("text") or "")) / 24.0, 1.5)
            weight = word_count + char_bonus
            if index == len(beats) - 1:
                weight *= 1.35
            weights.append(weight)
        return weights

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
        phrase = " ".join(words[:4]).strip() or "Key Idea"
        return self._clean_beat_text(phrase, text)

    def _scene_duration(self, audio_duration: float, section: dict[str, Any]) -> float:
        beats = ((section.get("visual_plan") or [{}])[0].get("beats") or {}).get("beats") or []
        if len([beat for beat in beats if str(beat.get("text") or "").strip()]) <= 1:
            return round(min(audio_duration, 2.8), 2)
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
        return self._fallback_text(section_text) if self._fallback_text(section_text).lower() != primary_text.lower() else "Key impact"

    def _timing_variation(self, text: str, index: int) -> float:
        checksum = sum(ord(char) for char in text) + index
        step = (checksum % 3) - 1
        return 1.0 + (step * 0.08)

    def _ideas_overlap(self, first: str, second: str) -> bool:
        stopwords = {"the", "and", "a", "an", "to", "you", "your", "before"}
        first_words = {word for word in re.findall(r"[a-z]+", first) if word not in stopwords}
        second_words = {word for word in re.findall(r"[a-z]+", second) if word not in stopwords}
        return len(first_words.intersection(second_words)) >= 1


def build_scenes(sections: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return SceneBuilder().build_scenes(sections)
