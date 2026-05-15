from __future__ import annotations

from .agenda_support import StoryAgendaSupportMixin
from .alignment_support import StoryAlignmentSupportMixin
from .arc_support import StoryArcSupportMixin
from .numeric_support import StoryNumericSupportMixin
from .planning_validation import StoryPlanningValidationMixin
from .section_text_support import StorySectionTextSupportMixin


class StoryPlanningSupportMixin(
    StoryAgendaSupportMixin,
    StoryArcSupportMixin,
    StoryAlignmentSupportMixin,
    StoryNumericSupportMixin,
    StorySectionTextSupportMixin,
    StoryPlanningValidationMixin,
):
    """Compatibility mixin composed from focused story planning helpers."""

