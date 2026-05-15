from __future__ import annotations

from .director_component_data import VisualDirectorComponentDataMixin
from .director_concept_classification import VisualDirectorConceptClassificationMixin
from .director_debt_growth_data import VisualDirectorDebtGrowthDataMixin
from .director_flow_data import VisualDirectorFlowDataMixin
from .director_lifestyle_data import VisualDirectorLifestyleDataMixin
from .director_money_parsing import VisualDirectorMoneyParsingMixin


class VisualDirectorDataHelpersMixin(
    VisualDirectorMoneyParsingMixin,
    VisualDirectorFlowDataMixin,
    VisualDirectorLifestyleDataMixin,
    VisualDirectorDebtGrowthDataMixin,
    VisualDirectorConceptClassificationMixin,
    VisualDirectorComponentDataMixin,
):
    """Compatibility mixin composed from focused visual director data helpers."""

