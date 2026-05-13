from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from ..models.repository import ProjectRepository


@dataclass(frozen=True)
class SceneAcceptanceIssue:
    scene_order: int | None
    severity: str
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_order": self.scene_order,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class SceneAcceptanceReport:
    passed: bool
    score: int
    scene_count: int
    blocking_issues: list[SceneAcceptanceIssue]
    warnings: list[SceneAcceptanceIssue]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "scene_count": self.scene_count,
            "blocking_issues": [issue.to_dict() for issue in self.blocking_issues],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }

    @property
    def status_label(self) -> str:
        if self.passed:
            return "Professional QA passed"
        return "Needs scene fixes"


class ProfessionalSceneAcceptanceService:
    """Reusable gate that prevents generic or internally-worded scenes from final assembly."""

    STRONG_COMPONENTS = {
        "MoneyFlowDiagram",
        "LifestyleCreepVisualizer",
        "EMIStackVisualizer",
        "InflationErosionVisualizer",
        "SIPGrowthEngine",
        "DebtSpiralVisualizer",
        "FOMOPriceCrashVisualizer",
        "PortfolioDiversificationVisualizer",
        "SmallLeaksAccumulator",
        "RiskReturnVisualizer",
        "EmergencyFundVisualizer",
        "OutroRecapVisualizer",
    }
    WEAK_BODY_COMPONENTS = {
        "ConceptCard",
        "ConceptCardScene",
        "HighlightText",
        "StatCard",
        "RiskCard",
        "RiskCardScene",
        "SplitComparison",
        "SplitComparisonScene",
        "FlowDiagram",
        "FlowBar",
        "StepFlow",
        "StepFlowScene",
    }
    CONCRETE_FINANCE_TERMS = {
        "salary",
        "income",
        "rent",
        "emi",
        "loan",
        "debt",
        "interest",
        "inflation",
        "sip",
        "invest",
        "investment",
        "savings",
        "buffer",
        "emergency",
        "tax",
        "food",
        "shopping",
        "subscription",
        "credit",
        "expense",
        "rupee",
        "₹",
        "rs",
    }
    INTERNAL_LANGUAGE_PATTERNS = (
        r"\bthe\s+topic\s+is\b",
        r"\bthis\s+scene\s+(?:shows|needs|should|will)\b",
        r"\bthe\s+viewer\s+(?:is|will|should|sees|notices)\b",
        r"\bvisual\s+(?:should|needs|will)\b",
        r"\bnarration\s+(?:says|introduces|mentions)\b",
        r"\bconcrete\s+mechanism\b",
        r"\binternal\s+logic\b",
    )

    def __init__(self, repo: ProjectRepository | None = None) -> None:
        self.repo = repo or ProjectRepository()

    def evaluate_project(self, project_id: int) -> SceneAcceptanceReport:
        project = self.repo.get_project(project_id) or {}
        scenes = self.repo.list_scenes(project_id)
        return self.evaluate_scenes(scenes, project=project)

    def evaluate_scenes(self, scenes: list[dict[str, Any]], project: dict[str, Any] | None = None) -> SceneAcceptanceReport:
        blockers: list[SceneAcceptanceIssue] = []
        warnings: list[SceneAcceptanceIssue] = []
        project_title = str((project or {}).get("working_title") or "").strip().lower()

        if not scenes:
            blockers.append(SceneAcceptanceIssue(None, "blocker", "no_scenes", "No scenes are available for professional review."))
            return SceneAcceptanceReport(False, 0, 0, blockers, warnings)

        previous_visual = ""
        weak_run = 0
        for scene in scenes:
            scene_blockers, scene_warnings = self._evaluate_scene(scene, project_title)
            blockers.extend(scene_blockers)
            warnings.extend(scene_warnings)
            visual = self._primary_component(scene)
            if visual and visual == previous_visual and visual in self.WEAK_BODY_COMPONENTS:
                weak_run += 1
            else:
                weak_run = 0
            if weak_run >= 1:
                warnings.append(
                    SceneAcceptanceIssue(
                        self._scene_order(scene),
                        "warning",
                        "repeated_weak_visual_shape",
                        f"Adjacent scenes reuse generic {visual}; visual rhythm may feel repetitive.",
                    )
                )
            previous_visual = visual

        score = self._score(scenes, blockers, warnings)
        return SceneAcceptanceReport(
            passed=not blockers,
            score=score,
            scene_count=len(scenes),
            blocking_issues=blockers,
            warnings=warnings,
        )

    def _evaluate_scene(self, scene: dict[str, Any], project_title: str) -> tuple[list[SceneAcceptanceIssue], list[SceneAcceptanceIssue]]:
        blockers: list[SceneAcceptanceIssue] = []
        warnings: list[SceneAcceptanceIssue] = []
        order = self._scene_order(scene)
        kind = str(scene.get("kind") or "body").strip().lower()
        narration = str(scene.get("narration_text") or "").strip()
        component = self._primary_component(scene)
        duration = float(scene.get("audio_duration_sec") or 0)
        moments = self._perceptual_moments(scene)

        if not narration:
            blockers.append(SceneAcceptanceIssue(order, "blocker", "missing_narration", "Scene has no narration text."))
        if not scene.get("audio_path"):
            blockers.append(SceneAcceptanceIssue(order, "blocker", "missing_voice", "Scene has no generated voice audio."))
        if not scene.get("visual_path"):
            blockers.append(SceneAcceptanceIssue(order, "blocker", "missing_visual", "Scene has no generated visual asset."))

        internal_match = self._internal_language_match(narration)
        if internal_match:
            blockers.append(
                SceneAcceptanceIssue(
                    order,
                    "blocker",
                    "internal_planning_language",
                    f"Scene narration contains production/planning language: '{internal_match}'.",
                )
            )

        if self._title_leak(project_title, narration, kind):
            blockers.append(
                SceneAcceptanceIssue(
                    order,
                    "blocker",
                    "title_repeated_as_script",
                    "Scene repeats the project title as script copy instead of natural narration.",
                )
            )

        if kind == "hook" and component not in self.STRONG_COMPONENTS:
            blockers.append(
                SceneAcceptanceIssue(
                    order,
                    "blocker",
                    "generic_hook_visual",
                    f"Hook uses {component or 'unknown visual'}; hooks need a concrete cinematic mechanism.",
                )
            )

        if kind == "body" and component in self.WEAK_BODY_COMPONENTS:
            blockers.append(
                SceneAcceptanceIssue(
                    order,
                    "blocker",
                    "generic_body_visual",
                    f"Body scene uses generic {component}; select a stronger finance visual archetype.",
                )
            )

        if kind == "outro" and component not in {"OutroRecapVisualizer", "MoneyFlowDiagram", "StepFlow"}:
            blockers.append(
                SceneAcceptanceIssue(
                    order,
                    "blocker",
                    "generic_outro_visual",
                    f"Outro uses {component or 'unknown visual'}; outros need action recap sequencing.",
                )
            )

        if kind == "body" and duration >= 25 and moments < 3:
            blockers.append(
                SceneAcceptanceIssue(
                    order,
                    "blocker",
                    "insufficient_perceptual_moments",
                    "Long body scene has fewer than 3 distinct visual moments.",
                )
            )
        elif duration >= 40 and moments < 4:
            warnings.append(
                SceneAcceptanceIssue(
                    order,
                    "warning",
                    "low_event_density",
                    "Long scene would benefit from more visual attention relocations.",
                )
            )

        if kind == "body" and not self._has_concrete_finance_entity(narration):
            blockers.append(
                SceneAcceptanceIssue(
                    order,
                    "blocker",
                    "no_concrete_finance_entity",
                    "Scene narration lacks concrete finance entities that the renderer can focus on.",
                )
            )

        if component in self.STRONG_COMPONENTS and duration >= 35 and moments < 4:
            warnings.append(
                SceneAcceptanceIssue(
                    order,
                    "warning",
                    "strong_component_underused",
                    f"{component} is present but not enough distinct phases were detected.",
                )
            )

        return blockers, warnings

    def _score(self, scenes: list[dict[str, Any]], blockers: list[SceneAcceptanceIssue], warnings: list[SceneAcceptanceIssue]) -> int:
        score = 100
        score -= 18 * len(blockers)
        score -= 5 * len(warnings)
        strong_count = sum(1 for scene in scenes if self._primary_component(scene) in self.STRONG_COMPONENTS)
        if scenes:
            strong_ratio = strong_count / len(scenes)
            if strong_ratio < 0.75:
                score -= round((0.75 - strong_ratio) * 40)
        return max(0, min(100, score))

    def _scene_order(self, scene: dict[str, Any]) -> int | None:
        try:
            return int(scene.get("scene_order"))
        except (TypeError, ValueError):
            return None

    def _primary_component(self, scene: dict[str, Any]) -> str:
        visual_type = str(scene.get("visual_type") or "").strip()
        if visual_type:
            return visual_type
        plan = self._visual_plan(scene)
        for item in plan:
            visual = item.get("visual") if isinstance(item, dict) else {}
            pattern = str((visual or {}).get("pattern") or "").strip()
            if pattern:
                return pattern
        return ""

    def _visual_plan(self, scene: dict[str, Any]) -> list[dict[str, Any]]:
        raw = scene.get("visual_plan_json")
        if not raw:
            return []
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        try:
            parsed = json.loads(str(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []

    def _perceptual_moments(self, scene: dict[str, Any]) -> int:
        phases: set[str] = set()
        components: set[str] = set()
        for item in self._visual_plan(scene):
            visual = item.get("visual") if isinstance(item, dict) else {}
            pattern = str((visual or {}).get("pattern") or "").strip()
            if pattern:
                components.add(pattern)
            beats = ((item.get("beats") or {}).get("beats") or []) if isinstance(item, dict) else []
            for beat in beats:
                if not isinstance(beat, dict):
                    continue
                component = str(beat.get("component") or "").strip()
                if component:
                    components.add(component)
                data = beat.get("data") if isinstance(beat.get("data"), dict) else {}
                phase = str(beat.get("beat_phase") or data.get("active_phase") or "").strip()
                if phase:
                    phases.add(phase)
        return max(len(phases), len(components))

    def _internal_language_match(self, narration: str) -> str:
        for pattern in self.INTERNAL_LANGUAGE_PATTERNS:
            match = re.search(pattern, narration, re.IGNORECASE)
            if match:
                return match.group(0)
        return ""

    def _title_leak(self, project_title: str, narration: str, kind: str) -> bool:
        if not project_title or kind != "body":
            return False
        lowered = narration.lower()
        title_hits = lowered.count(project_title)
        return title_hits >= 2 or bool(re.search(rf"\btopic\s+is\s+{re.escape(project_title)}\b", lowered))

    def _has_concrete_finance_entity(self, narration: str) -> bool:
        lowered = narration.lower()
        if re.search(r"₹|rs\.?\s*\d|\d+\s*%", lowered):
            return True
        return any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in self.CONCRETE_FINANCE_TERMS if term not in {"₹", "rs"})
