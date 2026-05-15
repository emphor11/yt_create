from __future__ import annotations

import re
from typing import Any

from .scene_builder_constants import MIN_BEAT_DURATION


class SceneBuilderTextMixin:
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

    def _merge_for_min_duration(
        self,
        beats: list[dict[str, Any]],
        audio_duration: float,
        min_duration: float = MIN_BEAT_DURATION,
    ) -> list[dict[str, Any]]:
        merged = [dict(beat) for beat in beats]
        while len(merged) > 1 and audio_duration > 0 and (audio_duration / len(merged)) < min_duration:
            last = merged.pop()
            merged[-1]["text"] = self._clean_beat_text(f"{merged[-1]['text']} {last['text']}", merged[-1]["text"])
            merged[-1]["component"] = last["component"] or merged[-1]["component"]
        return merged

    def _expand_minimum_beats(self, beats: list[dict[str, Any]], section_text: str) -> list[dict[str, Any]]:
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
        primary_beat = dict(beats[0]) if beats else {"component": base_component}
        primary_beat["component"] = base_component
        primary_beat["text"] = primary_text
        return [
            primary_beat,
            {"component": "ConceptCard", "text": self._clean_beat_text(second, section_text)},
        ]

    def _split_section_ideas(self, section_text: str) -> tuple[str, str]:
        parts = [
            part.strip(" ,.-")
            for part in re.split(r",| and | but | so | because ", section_text, maxsplit=1, flags=re.IGNORECASE)
            if part.strip()
        ]
        if len(parts) >= 2:
            return self._short_phrase(parts[0]), self._short_phrase(parts[1])
        words = section_text.split()
        midpoint = max(len(words) // 2, 1)
        return self._short_phrase(" ".join(words[:midpoint])), self._short_phrase(" ".join(words[midpoint:]))

    def _short_phrase(self, text: str) -> str:
        words = text.split()
        phrase = " ".join(words[:4]).strip() or self._fallback_text(text)
        return self._clean_beat_text(phrase, text)

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
