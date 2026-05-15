"""Compatibility exports for assembly and publishing use cases."""

from __future__ import annotations

from .assembly_workflow import AssembleDraftMasterUseCase, AssembleProjectUseCase
from .final_review_workflow import (
    BuildFinalReviewUseCase,
    MarkMasterReadyUseCase,
    RegenerateThumbnailsUseCase,
    SaveUploadPackageUseCase,
    SelectThumbnailUseCase,
)
from .publish_commands import MockUploadUseCase, SchedulePublishUseCase, StagePublishUseCase, UploadPrivateVideoUseCase

__all__ = [
    "AssembleDraftMasterUseCase",
    "AssembleProjectUseCase",
    "BuildFinalReviewUseCase",
    "MarkMasterReadyUseCase",
    "MockUploadUseCase",
    "RegenerateThumbnailsUseCase",
    "SaveUploadPackageUseCase",
    "SchedulePublishUseCase",
    "SelectThumbnailUseCase",
    "StagePublishUseCase",
    "UploadPrivateVideoUseCase",
]
