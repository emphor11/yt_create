from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
    "UniversalMechanismRenderer",
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
