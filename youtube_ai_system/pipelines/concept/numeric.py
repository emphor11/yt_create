from __future__ import annotations

import re


def numeric_amount(text: str) -> float:
    raw = str(text or "")
    money = re.search(r"₹\s?([\d,.]+)(?:\s?(crores?|lakhs?|k)\b)?", raw, re.I)
    if money:
        value = float(money.group(1).replace(",", ""))
        unit = str(money.group(2) or "").lower()
        if unit.startswith("crore"):
            return value * 10_000_000
        if unit.startswith("lakh"):
            return value * 100_000
        if unit == "k":
            return value * 1_000
        return value
    cleaned = raw.lower().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if not match:
        return 0.0
    value = float(match.group(1))
    if "crore" in cleaned:
        return value * 10_000_000
    if "lakh" in cleaned:
        return value * 100_000
    if re.search(r"\bk\b", cleaned):
        return value * 1_000
    return value


def validate_numbers(
    start: str,
    change: str,
    end: str,
    concept_type: str,
    narration: str = "",
) -> tuple[bool, str]:
    """Validate visible finance math before a beat can reach rendering."""

    start_value = numeric_amount(start)
    end_value = numeric_amount(end)
    process_text = str(change or "").lower()
    concept = "flow" if str(concept_type or "").lower() == "process" else str(concept_type or "").lower()
    context = f"{start} {change} {end} {narration}"

    if concept == "emphasis":
        return (start_value > 0 or end_value > 0 or bool(re.search(r"\d+(?:\.\d+)?%", f"{start} {end}"))), "emphasis_number"

    if start_value <= 0 or end_value < 0:
        return False, "missing_start_or_end"

    if re.search(r"\b12\s*months?\b|\byear(?:ly)?\b", process_text):
        expected = round(start_value * 12)
        if abs(end_value - expected) > max(1, expected * 0.02):
            return False, "monthly_yearly_math_mismatch"
        return True, "valid_monthly_yearly"

    pct = re.search(r"(\d+(?:\.\d+)?)%", process_text)
    if pct and start_value > 0:
        rate = float(pct.group(1)) / 100.0
        if concept == "growth":
            expected = start_value * (1 + rate)
        else:
            expected = start_value * (1 - rate)
        rate_amount = start_value * rate
        if abs(end_value - expected) > max(2, expected * 0.03) and not (
            concept == "decay" and abs(end_value - rate_amount) <= max(2, rate_amount * 0.03)
        ):
            return False, "percent_math_mismatch"

    if concept == "decay" and not end_value < start_value:
        return False, "decay_must_decrease"
    if concept == "growth" and not end_value > start_value:
        return False, "growth_must_increase"

    if start_value > 0 and end_value / start_value > 100 and not re.search(r"\b(years?|months?|age|%|return|sip)\b", process_text):
        return False, "implausible_jump"
    if start_value > 0 and end_value / start_value > 1000 and not re.search(r"\b(crore|lakh|years?|months?|age|%|return|sip|compound|wealth)\b", context, re.I):
        return False, "random_number_jump"
    return True, "valid"


def validate_numeric_logic(start: str, process: str, end: str, concept_type: str) -> tuple[bool, str]:
    return validate_numbers(start, process, end, concept_type)
