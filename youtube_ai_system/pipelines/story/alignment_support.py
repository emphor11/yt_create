from __future__ import annotations

import re
from typing import Any


class StoryAlignmentSupportMixin:
    def _sentence_aligned_beats(self, section: dict[str, Any]) -> list[dict[str, Any]]:
        beats = self._beats_from_narrative_arc(section)
        sentences = self._split_story_sentences(str(section.get("text") or ""))
        if not beats or not sentences:
            return beats

        aligned: list[dict[str, Any]] = []
        used_indices: set[int] = set()
        for index, beat in enumerate(beats):
            sentence_index = self._best_sentence_index_for_beat(beat, sentences, used_indices)
            used_indices.add(sentence_index)
            aligned_beat = dict(beat)
            aligned_beat["sentence_index"] = sentence_index
            aligned_beat["source_text"] = sentences[sentence_index]
            aligned.append(aligned_beat)
        return aligned

    def _best_sentence_index_for_beat(self, beat: dict[str, Any], sentences: list[str], used_indices: set[int]) -> int:
        beat_terms = self._beat_alignment_terms(beat)
        best_index = 0
        best_score = -1
        for index, sentence in enumerate(sentences):
            sentence_terms = self._alignment_terms(sentence)
            score = len(beat_terms.intersection(sentence_terms))
            if index not in used_indices:
                score += 0.25
            if score > best_score:
                best_score = score
                best_index = index
        if best_score <= 0:
            return min(len(sentences) - 1, len(used_indices))
        return best_index

    def _beat_alignment_terms(self, beat: dict[str, Any]) -> set[str]:
        parts = [str(beat.get("text") or ""), str(beat.get("subtext") or "")]
        props = beat.get("props") or {}
        if isinstance(props, dict):
            for key in ("title", "subtitle", "start", "end", "rate"):
                parts.append(str(props.get(key) or ""))
            for side_key in ("left", "right"):
                side = props.get(side_key)
                if isinstance(side, dict):
                    parts.append(str(side.get("label") or ""))
                    parts.append(str(side.get("value") or ""))
            nodes = props.get("nodes")
            if isinstance(nodes, list):
                for node in nodes:
                    if isinstance(node, dict):
                        parts.append(str(node.get("label") or ""))
                        parts.append(str(node.get("value") or ""))
                        parts.append(str(node.get("subtext") or ""))
        return self._alignment_terms(" ".join(parts))

    def _alignment_terms(self, text: str) -> set[str]:
        stopwords = {
            "the",
            "and",
            "your",
            "you",
            "are",
            "this",
            "that",
            "with",
            "from",
            "into",
            "then",
            "when",
            "almost",
        }
        aliases = {
            "emis": "emi",
            "expenses": "expense",
            "spends": "spending",
            "spent": "spending",
            "drains": "drain",
            "drain": "drain",
            "disappears": "disappear",
            "vanishes": "vanish",
            "leftover": "left",
        }
        terms: set[str] = set()
        for word in re.findall(r"[A-Za-z0-9₹%,.]+", str(text or "").lower()):
            cleaned = word.strip(".,")
            if not cleaned or cleaned in stopwords:
                continue
            terms.add(aliases.get(cleaned, cleaned))
        return terms
