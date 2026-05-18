"""Script contract wrappers compatible with stored script JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from .adapters import narration_from_payload
from .base import ContractValidationResult, ValidationIssue

SCRIPT_BRIEF_FORMATS = {
    "mechanism_explainer",
    "myth_busting",
    "mistake_breakdown",
    "cautionary_story",
    "psychological_essay",
    "case_study",
    "comparison_breakdown",
    "action_plan",
}

SCRIPT_BRIEF_MECHANISMS = {
    "salary_drain",
    "lifestyle_inflation",
    "emi_pressure",
    "debt_trap",
    "inflation_erosion",
    "sip_growth",
    "compounding",
    "risk_return",
    "emergency_fund",
    "speculation_risk",
    "diversification",
    "tax_saving",
    "rent_burden",
    "expense_leakage",
    "payment_pain_reduction",
    "affordability_illusion",
    "price_anchoring",
    "subscription_lock_in",
    "commitment_stacking",
    "anchoring",
    "lock_in",
    "delayed_consequence",
    "temptation_discount",
    "liquidity_pressure",
    "social_pressure",
    "risk_concentration",
    "opportunity_cost",
    "leverage",
    "cash_flow_squeeze",
}

SCRIPT_BRIEF_EMOTIONAL_DIRECTIONS = {
    "building",
    "revealing",
    "tightening",
    "releasing",
    "warning",
    "clarity",
}

SCRIPT_BRIEF_VAGUE_RECURRING_EXAMPLES = {
    "money",
    "money habits",
    "personal finance",
    "finance decision",
    "financial decision",
    "the topic",
    "the angle",
    "viewer journey",
    "wealth building",
}

SCRIPT_BRIEF_CONCRETE_EXAMPLE_SIGNALS = {
    "purchase",
    "payment",
    "emi",
    "loan",
    "card",
    "phone",
    "car",
    "house",
    "rent",
    "subscription",
    "salary",
    "sip",
    "fd",
    "fund",
    "portfolio",
    "stock",
    "business",
    "cash",
    "price",
    "bill",
}

SCRIPT_BRIEF_BODY_ADVICE_FUNCTION_MARKERS = {
    "advice",
    "budgeting",
    "call to action",
    "conclusion",
    "guidance",
    "reassess",
    "summarize",
    "summary",
    "takeaway",
    "takeaways",
}

SCRIPT_BRIEF_BUDGETING_DRIFT_MARKERS = {
    "50 30 20",
    "budgeting",
    "set a budget",
    "spend less",
    "track expenses",
    "tracking expenses",
}


@dataclass(frozen=True)
class ScriptBriefSceneFunction:
    scene_index: int
    function: str
    mechanism: str
    emotional_direction: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScriptBriefSceneFunction":
        try:
            scene_index = int(payload.get("scene_index") or 0)
        except (TypeError, ValueError):
            scene_index = 0
        return cls(
            scene_index=scene_index,
            function=str(payload.get("function") or ""),
            mechanism=str(payload.get("mechanism") or ""),
            emotional_direction=str(payload.get("emotional_direction") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_index": self.scene_index,
            "function": self.function,
            "mechanism": self.mechanism,
            "emotional_direction": self.emotional_direction,
        }


@dataclass(frozen=True)
class ScriptBriefContract:
    topic_interpretation: str = ""
    thesis: str = ""
    viewer_promise: str = ""
    selected_format: str = ""
    format_rationale: str = ""
    recurring_example: str = ""
    allowed_mechanisms: tuple[str, ...] = ()
    forbidden_drift: tuple[str, ...] = ()
    scene_function_map: tuple[ScriptBriefSceneFunction, ...] = ()
    tone_directive: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScriptBriefContract":
        return cls(
            topic_interpretation=str(payload.get("topic_interpretation") or ""),
            thesis=str(payload.get("thesis") or ""),
            viewer_promise=str(payload.get("viewer_promise") or ""),
            selected_format=str(payload.get("selected_format") or ""),
            format_rationale=str(payload.get("format_rationale") or ""),
            recurring_example=str(payload.get("recurring_example") or ""),
            allowed_mechanisms=tuple(str(item) for item in (payload.get("allowed_mechanisms") or ())),
            forbidden_drift=tuple(str(item) for item in (payload.get("forbidden_drift") or ())),
            scene_function_map=tuple(
                ScriptBriefSceneFunction.from_dict(item)
                for item in (payload.get("scene_function_map") or ())
                if isinstance(item, dict)
            ),
            tone_directive=str(payload.get("tone_directive") or ""),
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_interpretation": self.topic_interpretation,
            "thesis": self.thesis,
            "viewer_promise": self.viewer_promise,
            "selected_format": self.selected_format,
            "format_rationale": self.format_rationale,
            "recurring_example": self.recurring_example,
            "allowed_mechanisms": list(self.allowed_mechanisms),
            "forbidden_drift": list(self.forbidden_drift),
            "scene_function_map": [item.to_dict() for item in self.scene_function_map],
            "tone_directive": self.tone_directive,
        }

    def validate(self) -> ContractValidationResult:
        result = ContractValidationResult()
        required_text_fields = {
            "topic_interpretation": self.topic_interpretation,
            "thesis": self.thesis,
            "viewer_promise": self.viewer_promise,
            "selected_format": self.selected_format,
            "format_rationale": self.format_rationale,
            "recurring_example": self.recurring_example,
            "tone_directive": self.tone_directive,
        }
        for field_name, value in required_text_fields.items():
            if not str(value).strip():
                result = result.with_issue(
                    ValidationIssue("missing_script_brief_field", f"Script brief is missing {field_name}.", field_name)
                )
        if self.selected_format and self.selected_format not in SCRIPT_BRIEF_FORMATS:
            result = result.with_issue(
                ValidationIssue("invalid_script_brief_format", "Script brief selected_format is not supported.", "selected_format")
            )
        if self.recurring_example and not self._recurring_example_is_concrete():
            result = result.with_issue(
                ValidationIssue(
                    "vague_recurring_example",
                    "Script brief recurring_example must name a concrete reusable object, decision, or money situation.",
                    "recurring_example",
                )
            )
        if not self.allowed_mechanisms:
            result = result.with_issue(
                ValidationIssue("missing_script_brief_mechanisms", "Script brief needs at least one allowed mechanism.", "allowed_mechanisms")
            )
        if not self.forbidden_drift:
            result = result.with_issue(
                ValidationIssue("missing_forbidden_drift", "Script brief needs at least one forbidden drift item.", "forbidden_drift")
            )
        for mechanism in self.allowed_mechanisms:
            if mechanism not in SCRIPT_BRIEF_MECHANISMS:
                result = result.with_issue(
                    ValidationIssue("invalid_script_brief_mechanism", f"Unsupported script brief mechanism: {mechanism}", "allowed_mechanisms")
                )
        if not self.scene_function_map:
            result = result.with_issue(
                ValidationIssue("missing_scene_function_map", "Script brief scene_function_map is required.", "scene_function_map")
            )
        expected_indices = list(range(1, len(self.scene_function_map) + 1))
        actual_indices = [item.scene_index for item in self.scene_function_map]
        if self.scene_function_map and actual_indices != expected_indices:
            result = result.with_issue(
                ValidationIssue(
                    "non_consecutive_scene_function_map",
                    "Script brief scene_function_map indices must be consecutive starting at 1.",
                    "scene_function_map",
                )
            )
        seen_functions: set[str] = set()
        for index, item in enumerate(self.scene_function_map):
            field_prefix = f"scene_function_map[{index}]"
            if item.scene_index < 1:
                result = result.with_issue(ValidationIssue("invalid_scene_index", "Scene function needs a 1-based scene_index.", field_prefix))
            if not item.function.strip():
                result = result.with_issue(ValidationIssue("missing_scene_function", "Scene function is required.", f"{field_prefix}.function"))
            function_signature = self._normalized_text(item.function)
            if function_signature and function_signature in seen_functions:
                result = result.with_issue(
                    ValidationIssue(
                        "duplicate_scene_function",
                        "Scene function entries must do distinct jobs.",
                        f"{field_prefix}.function",
                    )
                )
            seen_functions.add(function_signature)
            if self.selected_format != "action_plan" and self._is_generic_advice_function(function_signature):
                result = result.with_issue(
                    ValidationIssue(
                        "generic_body_advice_scene_function",
                        "Non-action-plan ScriptBrief body scenes must not be generic summary, takeaway, or advice scenes.",
                        f"{field_prefix}.function",
                    )
                )
            if self._forbids_general_budgeting() and self._contains_budgeting_marker(function_signature):
                result = result.with_issue(
                    ValidationIssue(
                        "forbidden_budgeting_scene_function",
                        "Scene function drifts into forbidden general budgeting advice.",
                        f"{field_prefix}.function",
                    )
                )
            if item.mechanism not in SCRIPT_BRIEF_MECHANISMS:
                result = result.with_issue(
                    ValidationIssue("invalid_scene_mechanism", f"Unsupported scene mechanism: {item.mechanism}", f"{field_prefix}.mechanism")
                )
            elif self.allowed_mechanisms and item.mechanism not in self.allowed_mechanisms:
                result = result.with_issue(
                    ValidationIssue(
                        "scene_mechanism_not_allowed",
                        f"Scene mechanism is not listed in allowed_mechanisms: {item.mechanism}",
                        f"{field_prefix}.mechanism",
                    )
                )
            if item.emotional_direction not in SCRIPT_BRIEF_EMOTIONAL_DIRECTIONS:
                result = result.with_issue(
                    ValidationIssue(
                        "invalid_emotional_direction",
                        f"Unsupported emotional direction: {item.emotional_direction}",
                        f"{field_prefix}.emotional_direction",
                    )
                )
        return result

    def _is_generic_advice_function(self, normalized_function: str) -> bool:
        tokens = set(normalized_function.split())
        if bool(tokens.intersection(SCRIPT_BRIEF_BODY_ADVICE_FUNCTION_MARKERS)):
            return True
        return any(
            phrase in normalized_function
            for phrase in (
                "avoid pitfalls",
                "make informed decision",
                "make informed financial decision",
                "provide strategies",
                "discuss strategies",
            )
        )

    def _forbids_general_budgeting(self) -> bool:
        normalized = " ".join(self._normalized_text(item) for item in self.forbidden_drift)
        return "general budgeting advice" in normalized or self._contains_budgeting_marker(normalized)

    def _contains_budgeting_marker(self, normalized_text: str) -> bool:
        return any(marker in normalized_text for marker in SCRIPT_BRIEF_BUDGETING_DRIFT_MARKERS)

    def _recurring_example_is_concrete(self) -> bool:
        normalized = self._normalized_text(self.recurring_example)
        if normalized in SCRIPT_BRIEF_VAGUE_RECURRING_EXAMPLES:
            return False
        tokens = re.findall(r"[a-zA-Z0-9₹]+", normalized)
        if len(tokens) < 5:
            return False
        if re.search(r"(?:₹\s*|rs\.?\s*)\d|\d", self.recurring_example, re.IGNORECASE):
            return True
        return any(signal in tokens for signal in SCRIPT_BRIEF_CONCRETE_EXAMPLE_SIGNALS)

    def _normalized_text(self, value: str) -> str:
        return " ".join(re.findall(r"[a-zA-Z0-9₹]+", str(value or "").lower()))


@dataclass(frozen=True)
class ScriptSceneContract:
    scene_index: int | None = None
    kind: str = "body"
    title: str = ""
    narration: str = ""
    visual: str = ""
    visual_intent: str = ""
    visual_beats: tuple[Any, ...] = ()
    numbers: tuple[str, ...] = ()
    emotion: str = ""
    mechanism: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScriptSceneContract":
        return cls(
            scene_index=payload.get("scene_index"),
            kind=str(payload.get("kind") or "body"),
            title=str(payload.get("title") or payload.get("heading") or ""),
            narration=str(payload.get("narration") or payload.get("voiceover") or payload.get("text") or ""),
            visual=str(payload.get("visual") or payload.get("visual_description") or ""),
            visual_intent=str(payload.get("visual_intent") or ""),
            visual_beats=tuple(payload.get("visual_beats") or ()),
            numbers=tuple(str(number) for number in (payload.get("numbers") or ())),
            emotion=str(payload.get("emotion") or ""),
            mechanism=str(payload.get("mechanism") or ""),
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data.update(
            {
                "kind": self.kind,
                "narration": self.narration,
            }
        )
        if self.scene_index is not None:
            data["scene_index"] = self.scene_index
        if self.title:
            data["title"] = self.title
        if self.visual:
            data["visual"] = self.visual
        if self.visual_intent:
            data["visual_intent"] = self.visual_intent
        if self.visual_beats:
            data["visual_beats"] = list(self.visual_beats)
        if self.numbers:
            data["numbers"] = list(self.numbers)
        if self.emotion:
            data["emotion"] = self.emotion
        if self.mechanism:
            data["mechanism"] = self.mechanism
        return data


@dataclass(frozen=True)
class ScriptDraftContract:
    hook: dict[str, Any] = field(default_factory=dict)
    scenes: tuple[ScriptSceneContract, ...] = ()
    outro: dict[str, Any] = field(default_factory=dict)
    titles: tuple[str, ...] = ()
    description: str = ""
    tags: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScriptDraftContract":
        raw_scenes = payload.get("scenes") or []
        hook = payload.get("hook") if isinstance(payload.get("hook"), dict) else {"narration": payload.get("hook") or ""}
        outro = payload.get("outro") if isinstance(payload.get("outro"), dict) else {"narration": payload.get("outro") or ""}
        return cls(
            hook=dict(hook),
            scenes=tuple(ScriptSceneContract.from_dict(scene) for scene in raw_scenes if isinstance(scene, dict)),
            outro=dict(outro),
            titles=tuple(str(title) for title in (payload.get("titles") or payload.get("suggested_titles") or ())),
            description=str(payload.get("description") or payload.get("suggested_description") or ""),
            tags=tuple(str(tag) for tag in (payload.get("tags") or ())),
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data.update(
            {
                "hook": dict(self.hook),
                "scenes": [scene.to_dict() for scene in self.scenes],
                "outro": dict(self.outro),
            }
        )
        if self.titles:
            data["titles"] = list(self.titles)
        if self.description:
            data["description"] = self.description
        if self.tags:
            data["tags"] = list(self.tags)
        return data

    @property
    def hook_narration(self) -> str:
        return narration_from_payload(self.hook)

    @property
    def outro_narration(self) -> str:
        return narration_from_payload(self.outro)

    def validate(self) -> ContractValidationResult:
        result = ContractValidationResult()
        if not self.hook_narration:
            result = result.with_issue(ValidationIssue("missing_hook", "Script hook is missing.", "hook"))
        if not self.scenes:
            result = result.with_issue(ValidationIssue("missing_scenes", "Script scenes are missing.", "scenes"))
        if not self.outro_narration:
            result = result.with_issue(ValidationIssue("missing_outro", "Script outro is missing.", "outro"))
        return result
