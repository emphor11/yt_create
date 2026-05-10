from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any


CONCEPT_POLICIES: dict[str, dict[str, list[str]]] = {
    "lifestyle_inflation": {
        "allowed": ["spending_growth", "savings_flatline", "income_expansion", "raise_absorption"],
        "blocked": ["macro_inflation", "cpi", "currency_devaluation", "purchasing_power_erosion"],
    },
    "sip_growth": {
        "allowed": ["monthly_sip", "compounding", "long_term_growth", "corpus_growth"],
        "blocked": ["salary_drain", "debt_trap", "emergency_fund"],
    },
    "compounding": {
        "allowed": ["returns_on_returns", "time_growth", "investment_growth"],
        "blocked": ["savings_account_only", "debt_interest_spiral"],
    },
    "emergency_fund": {
        "allowed": ["cash_buffer", "shock_absorption", "debt_prevention"],
        "blocked": ["debt_trap", "credit_card_strategy", "investment_return"],
    },
    "diversification": {
        "allowed": ["risk_spread", "asset_buckets", "concentration_risk"],
        "blocked": ["single_stock_bet", "guaranteed_return"],
    },
    "speculation_risk": {
        "allowed": ["fomo", "late_entry", "panic_exit", "price_crash"],
        "blocked": ["investment_growth", "disciplined_sip"],
    },
    "inflation_erosion": {
        "allowed": ["macro_inflation", "purchasing_power_erosion", "real_return"],
        "blocked": ["lifestyle_upgrade", "raise_absorption"],
    },
}

META_VISUAL_PHRASES = (
    "viewer should see",
    "viewer can see",
    "scene should",
    "visual should",
    "not just hear generic advice",
    "money system",
    "every rupee has a job",
)

REPEATED_THEME_PHRASES = (
    "every rupee has a job",
    "viewer can see",
    "viewer should see",
    "money system",
    "generic advice",
    "not just hear",
    "before the month starts",
    "the important part",
)


@dataclass(frozen=True)
class NumericFact:
    id: str
    raw: str
    amount: float | None
    unit: str
    role: str
    source: str = "narration"
    sentence_index: int | None = None
    confidence: float = 1.0
    derived: bool = False
    source_number_ids: list[str] | None = None
    derivation_method: str | None = None
    owner: str = "numeric_provenance"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", str(text or "").strip()) if part.strip()]


def numeric_facts_from_narration(text: str, *, scene_id: str = "scene") -> list[dict[str, Any]]:
    sentences = split_sentences(text)
    facts: list[NumericFact] = []
    for sentence_index, sentence in enumerate(sentences or [str(text or "")]):
        for match in _number_matches(sentence):
            raw = match.group(0).strip()
            amount, unit = _amount_and_unit(match)
            role, confidence = _role_for_number(sentence, raw, amount, unit)
            facts.append(
                NumericFact(
                    id=f"num:{scene_id}:{len(facts)}",
                    raw=raw,
                    amount=amount,
                    unit=unit,
                    role=role,
                    sentence_index=sentence_index,
                    confidence=confidence,
                )
            )
    facts = _refine_cross_sentence_roles(facts, text)
    return [fact.to_dict() for fact in facts]


def numeric_role_map(text: str, *, scene_id: str = "scene") -> dict[str, Any]:
    facts = numeric_facts_from_narration(text, scene_id=scene_id)
    roles: dict[str, Any] = {"facts": facts}
    for fact in facts:
        role = str(fact.get("role") or "")
        if role and role not in roles:
            roles[role] = fact.get("raw")
    roles["spoken_numbers"] = [fact.get("raw") for fact in facts]
    return roles


def first_fact(facts: list[dict[str, Any]], *roles: str) -> dict[str, Any] | None:
    role_set = set(roles)
    return next((fact for fact in facts if fact.get("role") in role_set), None)


def apply_concept_policy(concept_key: str, text: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = _normalize_concept_key(concept_key)
    policy = CONCEPT_POLICIES.get(normalized, {"allowed": [], "blocked": []})
    lowered = str(text or "").lower()
    contaminations: list[dict[str, str]] = []

    if normalized == "lifestyle_inflation":
        macro_only = any(token in lowered for token in ("cpi", "currency devaluation", "purchasing power", "prices rise", "price rise", "buying power"))
        if macro_only:
            contaminations.append({"blocked": "macro_inflation", "reason": "lifestyle inflation mixed with macro inflation language"})
    if normalized == "sip_growth" and any(token in lowered for token in ("salary drains", "salary drain", "nothing left")):
        contaminations.append({"blocked": "salary_drain", "reason": "SIP growth mixed with salary drain language"})
    if normalized == "emergency_fund" and "credit card debt" in lowered:
        # Debt can be a consequence here; warn only if the payload reclassifies it as the main concept.
        if _normalize_concept_key(str((payload or {}).get("concept_name") or "")) == "debt_trap":
            contaminations.append({"blocked": "debt_trap", "reason": "Emergency fund classified as debt trap"})

    return {
        "concept": normalized,
        "allowed": list(policy.get("allowed") or []),
        "blocked": list(policy.get("blocked") or []),
        "contaminations": contaminations,
        "status": "warning" if contaminations else "ok",
    }


def scene_density_report(scene: dict[str, Any]) -> dict[str, Any]:
    narration = str(scene.get("narration") or scene.get("text") or "")
    beats = scene.get("beats") or []
    duration = float(scene.get("duration") or scene.get("total_duration") or scene.get("audio_duration") or 0)
    sentences = split_sentences(narration)
    semantic_claims = [
        sentence
        for sentence in sentences
        if re.search(r"\b(because|then|if|when|but|so|that is|this is|means|becomes|turns|keeps|starts|stops|protects|destroys)\b", sentence, re.I)
    ]
    component_count = len({str(beat.get("component") or "") for beat in beats if isinstance(beat, dict)})
    beat_count = len([beat for beat in beats if isinstance(beat, dict)])
    warnings: list[dict[str, Any]] = []
    if duration > 45 and beat_count < 5:
        warnings.append({"code": "too_few_beats_for_duration", "message": "Long scene has too few beat phases for narration duration."})
    if len(sentences) > 14:
        warnings.append({"code": "scene_too_dense", "message": "Scene has too many spoken sentences for one visual arc."})
    if len(semantic_claims) > 6:
        warnings.append({"code": "semantic_overload", "message": "Scene contains too many semantic claims for one visual mechanism."})
    if duration > 0 and beat_count > 0 and duration / beat_count > 9:
        warnings.append({"code": "visual_lag_risk", "message": "Each beat carries too much narration time."})
    return {
        "word_count": len(re.findall(r"[A-Za-z0-9₹%]+(?:[.,][A-Za-z0-9]+)*", narration)),
        "sentence_count": len(sentences),
        "semantic_claim_count": len(semantic_claims),
        "beat_count": beat_count,
        "duration": duration,
        "visual_component_count": component_count,
        "narration_to_beat_ratio": round(duration / max(beat_count, 1), 3) if duration else 0,
        "recommended_split_points": [sentences[index] for index in (4, 9, 14) if index < len(sentences)],
        "warnings": warnings,
    }


def repetition_report(scenes: list[dict[str, Any]]) -> dict[str, Any]:
    phrase_hits: dict[str, list[int]] = {}
    meta_leaks: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes, start=1):
        text = str(scene.get("narration") or scene.get("text") or "")
        lowered = text.lower()
        for phrase in REPEATED_THEME_PHRASES:
            if phrase in lowered:
                phrase_hits.setdefault(phrase, []).append(index)
        for phrase in META_VISUAL_PHRASES:
            if phrase in lowered:
                meta_leaks.append({"scene_index": index, "phrase": phrase})
    repeated = [
        {"phrase": phrase, "count": len(scene_indexes), "scenes": scene_indexes}
        for phrase, scene_indexes in sorted(phrase_hits.items())
        if len(scene_indexes) > 1
    ]
    return {
        "already_used_phrases": sorted(phrase_hits),
        "already_used_themes": [item["phrase"] for item in repeated],
        "banned_repeats": [item["phrase"] for item in repeated if item["count"] >= 2],
        "repeated_phrases": repeated,
        "meta_visual_leaks": meta_leaks,
        "status": "warning" if repeated or meta_leaks else "ok",
    }


def narrative_progression_report(scenes: list[dict[str, Any]]) -> dict[str, Any]:
    roles = [_scene_role(scene, index, len(scenes)) for index, scene in enumerate(scenes)]
    warnings: list[dict[str, Any]] = []
    role_counts: dict[str, int] = {}
    for role in roles:
        role_counts[role["role"]] = role_counts.get(role["role"], 0) + 1
    repeated_roles = [role for role, count in role_counts.items() if count > 2 and role not in {"control_mechanism"}]
    if repeated_roles:
        warnings.append({"code": "repeated_scene_role", "message": "Too many scenes perform the same narrative role.", "roles": repeated_roles})
    if len({role["role"] for role in roles}) <= max(2, len(roles) // 3):
        warnings.append({"code": "curriculum_chain", "message": "Scenes read like topic modules instead of a progressing transformation."})
    if scenes:
        outro_text = str(scenes[-1].get("narration") or scenes[-1].get("text") or "").lower()
        if sum(1 for token in ("must", "you can", "start", "avoid", "use ") if token in outro_text) >= 3:
            warnings.append({"code": "checklist_outro", "message": "Outro reads like a checklist instead of a resolved story."})
    return {
        "opening_state": "money controls viewer",
        "middle_state": "viewer discovers hidden systems",
        "ending_state": "viewer builds intentional structure",
        "scene_roles": roles,
        "warnings": warnings,
        "status": "warning" if warnings else "ok",
    }


def educational_integrity_report(scene: dict[str, Any]) -> dict[str, Any]:
    narration = str(scene.get("narration") or scene.get("text") or "")
    concept_type = _normalize_concept_key(str(scene.get("concept_type") or scene.get("mechanism") or ""))
    facts = numeric_facts_from_narration(narration, scene_id=str(scene.get("scene_id") or scene.get("scene_order") or "scene"))
    spoken_tokens = {_number_token(str(fact.get("raw") or "")) for fact in facts}
    spoken_tokens.discard("")
    visual_numbers = _visual_number_records(scene)
    warnings: list[dict[str, Any]] = []
    for item in visual_numbers:
        token = item["token"]
        if spoken_tokens and token not in spoken_tokens and not item.get("derived"):
            warnings.append({"code": "unspoken_visual_number", "message": f"Visual data contains unspoken number {item['raw']}.", **item})
        if item.get("derived") and not item.get("derived_from") and not item.get("derivation_method"):
            warnings.append({"code": "derived_number_missing_provenance", "message": f"Derived number {item['raw']} is missing provenance.", **item})
    if concept_type == "lifestyle_inflation" and any(item["token"] not in spoken_tokens for item in visual_numbers if item.get("path", "").endswith("end_income.value")):
        warnings.append({"code": "semantic_role_conflict", "message": "Lifestyle inflation end income is not grounded in spoken income values."})
    if concept_type in {"inflation_erosion", "inflation_loss"}:
        endpoint = str(scene.get("end_state") or scene.get("end_value") or "")
        if "%" in endpoint:
            warnings.append({"code": "percentage_used_as_money_endpoint", "message": "Percentage was used as a final money state."})
    policy = apply_concept_policy(concept_type, narration, scene)
    for contamination in policy.get("contaminations") or []:
        warnings.append({"code": "concept_contamination", "message": contamination["reason"], **contamination})
    return {
        "numeric_facts": facts,
        "visual_numbers": visual_numbers,
        "concept_policy": policy,
        "warnings": warnings,
        "confidence": _integrity_confidence(warnings, visual_numbers),
        "status": "warning" if warnings else "ok",
    }


def _scene_role(scene: dict[str, Any], index: int, total: int) -> dict[str, Any]:
    text = str(scene.get("narration") or scene.get("text") or "").lower()
    concept = _normalize_concept_key(str(scene.get("mechanism") or scene.get("concept_type") or ""))
    if index == 0 and any(token in text for token in ("why", "gone", "disappear", "drain")):
        role = "problem_visible"
    elif concept in {"salary_drain", "lifestyle_inflation", "emi_pressure", "debt_trap"}:
        role = "pressure_build"
    elif concept in {"inflation_erosion", "expense_leakage"}:
        role = "hidden_force"
    elif concept in {"sip_growth", "compounding"}:
        role = "future_growth"
    elif concept in {"diversification", "emergency_fund", "risk_return"}:
        role = "risk_protection"
    elif index == total - 1:
        role = "resolution"
    else:
        role = "control_mechanism"
    return {"scene_index": index + 1, "role": role, "concept": concept or "unknown"}


def _number_matches(sentence: str) -> list[re.Match[str]]:
    pattern = re.compile(r"(?:₹\s*|Rs\.?\s*)?\d[\d,]*(?:\.\d+)?\s*(?:lakh|lakhs|crore|crores|k|%)?", re.I)
    matches: list[re.Match[str]] = []
    for match in pattern.finditer(sentence):
        raw = match.group(0).strip()
        if not raw:
            continue
        before = sentence[max(0, match.start() - 12) : match.start()].lower()
        after = sentence[match.end() : match.end() + 18].lower()
        if "%" not in raw and "₹" not in raw and not raw.lower().startswith("rs"):
            if re.match(r"\s*(years?|months?|days?)\b", after):
                matches.append(match)
                continue
            if re.search(r"(day|year|month|minute|second|hour|age)\s*$", before) or re.match(r"\s*(minutes?|seconds?|hours?)\b", after):
                continue
        matches.append(match)
    return matches


def _amount_and_unit(match: re.Match[str]) -> tuple[float | None, str]:
    raw = match.group(0)
    number_match = re.search(r"\d[\d,]*(?:\.\d+)?", raw)
    if not number_match:
        return None, "number"
    amount = float(number_match.group(0).replace(",", ""))
    lowered = raw.lower()
    if "%" in lowered:
        return amount, "percent"
    if "crore" in lowered:
        return amount * 10000000, "INR"
    if "lakh" in lowered:
        return amount * 100000, "INR"
    if lowered.strip().endswith("k"):
        return amount * 1000, "INR"
    if "₹" in lowered or lowered.startswith("rs"):
        return amount, "INR"
    return amount, "number"


def _role_for_number(sentence: str, raw: str, amount: float | None, unit: str) -> tuple[str, float]:
    lowered = sentence.lower()
    raw_lower = raw.lower()
    if unit == "percent":
        return "rate", 1.0
    after_raw = re.escape(re.search(r"\d[\d,]*(?:\.\d+)?", raw).group(0)) if re.search(r"\d[\d,]*(?:\.\d+)?", raw) else ""
    if after_raw and re.search(after_raw + r"\s*(years?|months?|days?)\b", sentence, re.I):
        return "duration", 1.0
    if "sip" in lowered and amount and amount <= 100000 and ("month" in lowered or "monthly" in lowered or "per month" in lowered or unit == "INR"):
        return "monthly_sip", 0.95
    if "from" in lowered and " to " in lowered and ("salary" in lowered or "income" in lowered):
        amounts = [m.group(0).strip() for m in _number_matches(sentence)]
        if len(amounts) >= 2:
            if raw == amounts[0]:
                return "start_income", 1.0
            if raw == amounts[1]:
                return "end_income", 1.0
    if "extra" in lowered or "raise" in lowered or "increase" in lowered:
        return "raise_delta", 0.9
    if any(token in lowered for token in ("corpus", "turn it into", "become", "becomes", "nearly")) and unit == "INR" and amount and amount > 100000:
        return "target_value", 0.85
    if any(token in lowered for token in ("from your pocket", "invest about", "total invested", "contribution")):
        return "total_contribution", 0.85
    if any(token in lowered for token in ("salary", "income")) and unit == "INR":
        return "income", 0.75
    if any(token in lowered for token in ("savings", "sits idle", "balance", "principal")) and unit == "INR":
        return "principal", 0.8
    return "money_amount" if unit == "INR" else "number", 0.55


def _refine_cross_sentence_roles(facts: list[NumericFact], text: str) -> list[NumericFact]:
    lowered = text.lower()
    if "sip" in lowered:
        return [_replace_role(fact, "monthly_sip") if fact.role == "money_amount" and fact.amount and fact.amount <= 100000 else fact for fact in facts]
    return facts


def _replace_role(fact: NumericFact, role: str) -> NumericFact:
    return NumericFact(**{**fact.to_dict(), "role": role, "confidence": max(float(fact.confidence), 0.8)})


def _visual_number_records(value: Any, path: str = "scene") -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(value, dict):
        derived = bool(value.get("derived")) if "derived" in value else False
        derived_from = value.get("derived_from") or value.get("source_number_ids")
        method = value.get("derivation_method") or value.get("method")
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in {"value", "text", "label", "start", "end", "title", "punch"} and isinstance(child, str):
                for raw in re.findall(r"₹\s*\d[\d,]*(?:\.\d+)?(?:\s*(?:lakh|crore|k))?|\d[\d,]*(?:\.\d+)?%", child, re.I):
                    records.append(
                        {
                            "raw": raw.strip(),
                            "token": _number_token(raw),
                            "path": child_path,
                            "derived": derived,
                            "derived_from": derived_from,
                            "derivation_method": method,
                        }
                    )
            records.extend(_visual_number_records(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            records.extend(_visual_number_records(child, f"{path}[{index}]"))
    return records


def _number_token(raw: str) -> str:
    match = re.search(r"\d[\d,]*(?:\.\d+)?", str(raw or ""))
    if not match:
        return ""
    token = match.group(0).replace(",", "")
    return token[:-2] if token.endswith(".0") else token


def _integrity_confidence(warnings: list[dict[str, Any]], visual_numbers: list[dict[str, Any]]) -> float:
    score = 1.0
    score -= 0.12 * len([warning for warning in warnings if warning.get("code") == "unspoken_visual_number"])
    score -= 0.18 * len([warning for warning in warnings if warning.get("code") in {"semantic_role_conflict", "concept_contamination"}])
    derived_unique = {str(item.get("raw") or "") for item in visual_numbers if item.get("derived")}
    score -= min(0.24, 0.04 * len(derived_unique))
    return round(max(0.1, min(score, 1.0)), 3)


def _normalize_concept_key(value: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "lifestyle_inflation": "lifestyle_inflation",
        "inflation_loss": "inflation_erosion",
        "inflation_erosion": "inflation_erosion",
        "sip_growth": "sip_growth",
        "compound_growth": "compounding",
        "fomo_risk": "speculation_risk",
        "investing_vs_speculation": "speculation_risk",
    }
    return aliases.get(text, text)


def safe_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
