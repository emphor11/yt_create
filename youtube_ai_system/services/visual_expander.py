from __future__ import annotations

import re
from typing import List


class VisualExpander:
    def expand(self, concept: str, text: str, has_numbers: bool) -> List[str]:
        concept_key = self._normalize_concept(concept)
        context = self._context_profile(text)
        beats = list(self._template_for(concept_key, context, text))

        if has_numbers:
            numeric_beats = self._numeric_transformation_beats(text)
            if numeric_beats:
                beats = beats[: max(0, 5 - len(numeric_beats))] + numeric_beats

        beats = self._enforce_escalation(beats, context)

        beats = [self._clean_beat(beat) for beat in beats if self._clean_beat(beat)]

        if len(beats) < 5:
            fallback = self._template_for("fallback", context, text)
            for beat in fallback:
                cleaned = self._clean_beat(beat)
                if cleaned and cleaned not in beats:
                    beats.append(cleaned)
                if len(beats) >= 5:
                    break

        return beats[:5]

    def _template_for(self, concept: str, context: dict[str, str | bool], text: str) -> List[str]:
        templates = {
            "salary depletion": self._salary_depletion_template(context, text),
            "expense leakage": self._expense_leakage_template(context),
            "debt trap": self._debt_trap_template(context),
            "emergency fund": self._emergency_fund_template(context),
            "investment growth": self._investment_growth_template(context),
            "automation": self._automation_template(context),
            "fallback": self._fallback_template(context),
        }
        return templates.get(concept, templates["fallback"])

    def _normalize_concept(self, concept: str) -> str:
        normalized = " ".join(str(concept or "").strip().lower().split())
        alias_map = {
            "salary leakage": "salary depletion",
            "salary depletion": "salary depletion",
            "expense leakage": "expense leakage",
            "debt trap": "debt trap",
            "emergency fund": "emergency fund",
            "investment growth": "investment growth",
            "compounding growth": "investment growth",
            "savings automation": "automation",
            "automation": "automation",
        }
        return alias_map.get(normalized, "fallback")

    def _numeric_transformation_beats(self, text: str) -> List[str]:
        phrases = self._numeric_phrases(text)
        if not phrases:
            day_phrase = self._day_phrase(text)
            return [day_phrase, self._impact_phrase(text)] if day_phrase else []

        if len(phrases) >= 2:
            final_phrase = self._impact_phrase(text)
            beats = [phrases[0], phrases[1]]
            if final_phrase:
                beats.append(final_phrase)
            return [self._clean_beat(beat) for beat in beats if self._clean_beat(beat)]

        single = phrases[0]
        transformed = self._yearly_transform(single)
        impact = self._impact_phrase(text)
        beats = [single]
        if transformed:
            beats.append(transformed)
        if impact:
            beats.append(impact)
        return [self._clean_beat(beat) for beat in beats if self._clean_beat(beat)]

    def _numeric_phrases(self, text: str) -> List[str]:
        pattern = r"(₹\s*[\d,]+(?:\.\d+)?)\s*(per month|monthly|per year|yearly|salary|income|interest|payment|bill|loss|leak)?"
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        phrases: List[str] = []
        for amount, label in matches:
            amount = re.sub(r"\s+", "", amount)
            label = " ".join(label.strip().lower().split()) if label else ""
            if label:
                phrase = f"{amount} {label}"
            else:
                phrase = amount
            cleaned = self._clean_beat(phrase)
            if cleaned and cleaned not in phrases:
                phrases.append(cleaned)
        if phrases:
            return phrases[:2]

        percent_matches = re.findall(r"(\d+(?:\.\d+)?)\s*%\s*(salary|income|return|returns|interest|lost)?", text, flags=re.IGNORECASE)
        for value, label in percent_matches:
            phrase = f"{value}% {label}".strip()
            cleaned = self._clean_beat(phrase)
            if cleaned and cleaned not in phrases:
                phrases.append(cleaned)
        return phrases[:2]

    def _day_phrase(self, text: str) -> str | None:
        match = re.search(r"day\s+(\d+)", text, flags=re.IGNORECASE)
        if not match:
            return None
        return self._clean_beat(f"₹0 by day {match.group(1)}")

    def _yearly_transform(self, phrase: str) -> str | None:
        lowered = phrase.lower()
        match = re.search(r"₹\s*([\d,]+(?:\.\d+)?)", phrase)
        if not match:
            return None
        if "monthly" not in lowered and "per month" not in lowered:
            return None
        amount = float(match.group(1).replace(",", ""))
        yearly = amount * 12
        formatted = self._format_currency(yearly)
        return self._clean_beat(f"{formatted} yearly")

    def _impact_phrase(self, text: str) -> str | None:
        lowered = text.lower()
        if any(token in lowered for token in ("stress", "pressure", "broken")):
            return "Financial stress builds"
        if any(token in lowered for token in ("lost", "loss", "reduced", "reduce", "shrink", "shrinks")):
            return "Savings reduced"
        if any(token in lowered for token in ("leak", "leaks", "drain", "drains")):
            return "Savings reduced"
        if "interest" in lowered:
            return "Interest burden rises"
        if "debt" in lowered:
            return "Debt pressure rises"
        return "Financial impact occurs"

    def _format_currency(self, value: float) -> str:
        rounded = int(round(value))
        return f"₹{rounded:,}"

    def _clean_beat(self, beat: str) -> str:
        cleaned = re.sub(r"[^\w\s₹%]", " ", str(beat or ""))
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            return ""
        words = cleaned.split()[:5]
        return " ".join(words)

    def _context_profile(self, text: str) -> dict[str, str | bool]:
        lowered = text.lower()
        return {
            "has_rent": "rent" in lowered,
            "has_bill": any(token in lowered for token in ("bill", "bills", "card bill", "emi")),
            "has_phone": "phone" in lowered,
            "has_car": "car" in lowered,
            "has_wedding": "wedding" in lowered,
            "has_interest": "interest" in lowered,
            "has_minimum": "minimum" in lowered,
            "has_buffer": any(token in lowered for token in ("buffer", "emergency fund")),
        }

    def _pick(self, options: list[str], text: str, slot: int) -> str:
        if not options:
            return ""
        score = sum(ord(ch) for ch in text) + slot * 17
        return options[score % len(options)]

    def _salary_depletion_template(self, context: dict[str, str | bool], text: str) -> List[str]:
        second_options = ["Expenses hit early"]
        if context["has_rent"]:
            second_options.insert(0, "Rent deducted first")
        if context["has_bill"]:
            second_options.insert(0, "Bills hit first")
        third_options = ["Card bill arrives", "Spending keeps climbing"]
        if context["has_phone"]:
            third_options.insert(0, "Phone upgrade lands")
        if context["has_car"]:
            third_options.insert(0, "Car payment bites")
        if context["has_wedding"]:
            third_options.insert(0, "Wedding cost lands")
        return [
            self._pick(["Salary received", "Income gets credited"], text, 0),
            self._pick(second_options, text, 1),
            self._pick(third_options, text, 2),
            self._pick(["Money runs out", "Cash disappears fast"], text, 3),
            self._pick(["Month feels broken", "Financial stress builds"], text, 4),
        ]

    def _expense_leakage_template(self, context: dict[str, str | bool]) -> List[str]:
        second = "Daily spending grows"
        if context["has_bill"]:
            second = "Bills keep stacking"
        return [
            "Small expenses",
            second,
            "Monthly total builds",
            "Yearly loss increases",
            "Savings slowly shrink",
        ]

    def _debt_trap_template(self, context: dict[str, str | bool]) -> List[str]:
        second = "Interest starts growing" if context["has_interest"] else "Repayment pressure starts"
        third = "Minimum payments continue" if context["has_minimum"] else "Payments keep repeating"
        return [
            "Borrow money",
            second,
            third,
            "Debt keeps increasing",
            "Financial pressure rises",
        ]

    def _emergency_fund_template(self, context: dict[str, str | bool]) -> List[str]:
        third = "Savings buffer protects" if context["has_buffer"] else "Cash buffer protects"
        return [
            "Income stops suddenly",
            "Expenses still continue",
            third,
            "Time to recover",
            "Stress stays controlled",
        ]

    def _investment_growth_template(self, context: dict[str, str | bool]) -> List[str]:
        return [
            "Start investing early",
            self._pick(["Returns begin compounding", "Returns start growing"], "investment", 1),
            "Money grows steadily",
            self._pick(["Reinvest profits", "Stay invested longer"], "investment", 3),
            self._pick(["Wealth multiplies", "Future feels stronger"], "investment", 4),
        ]

    def _automation_template(self, context: dict[str, str | bool]) -> List[str]:
        return [
            "Income gets credited",
            "Savings auto transfer",
            "Spending adjusts naturally",
            "Savings stay protected",
            "Wealth builds silently",
        ]

    def _fallback_template(self, context: dict[str, str | bool]) -> List[str]:
        return [
            "Money enters system",
            "Spending begins",
            "Changes accumulate",
            "Outcome becomes visible",
            "Financial impact occurs",
        ]

    def _enforce_escalation(self, beats: List[str], context: dict[str, str | bool]) -> List[str]:
        if len(beats) < 5:
            return beats
        escalated = list(beats[:5])
        if escalated[-1] == escalated[-2]:
            escalated[-1] = "Financial stress builds"
        if any(word in escalated[1].lower() for word in ("rent", "bill", "bills")) and escalated[2] == escalated[1]:
            escalated[2] = "Pressure starts building"
        if not any(word in escalated[-1].lower() for word in ("stress", "broken", "pressure", "shrink", "reduced", "occurs")):
            escalated[-1] = "Financial stress builds"
        return escalated
