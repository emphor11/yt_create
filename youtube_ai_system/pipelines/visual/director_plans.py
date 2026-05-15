from __future__ import annotations

from .director_debt_growth_plans import VisualDirectorDebtGrowthPlansMixin
from .director_money_plans import VisualDirectorMoneyPlansMixin
from .director_plan_helpers import VisualDirectorPlanHelpersMixin
from .director_qualitative_plans import VisualDirectorQualitativePlansMixin
from .director_risk_plans import VisualDirectorRiskPlansMixin


class VisualDirectorPlansMixin(
    VisualDirectorPlanHelpersMixin,
    VisualDirectorMoneyPlansMixin,
    VisualDirectorDebtGrowthPlansMixin,
    VisualDirectorRiskPlansMixin,
    VisualDirectorQualitativePlansMixin,
):
    """Compatibility mixin composed from focused visual director plan families."""

