"""Use-case wrappers around the current service workflow."""

from .analytics_workflow import BuildAnalyticsTableUseCase, CaptureAnalyticsSnapshotUseCase
from .assembly_workflow import AssembleDraftMasterUseCase, AssembleProjectUseCase
from .final_review_workflow import (
    BuildFinalReviewUseCase,
    MarkMasterReadyUseCase,
    RegenerateThumbnailsUseCase,
    SaveUploadPackageUseCase,
    SelectThumbnailUseCase,
)
from .media_workflow import (
    ApproveScenesUseCase,
    BuildSceneReviewUseCase,
    GenerateProjectMediaUseCase,
    RegenerateSceneUseCase,
    RunVoiceCheckUseCase,
)
from .page_workflow import (
    BuildDiscardedProjectsUseCase,
    BuildProjectDetailUseCase,
    BuildProjectListUseCase,
    BuildScriptEditorUseCase,
    BuildTopicSelectionUseCase,
)
from .project_workflow import (
    CreateProjectUseCase,
    DiscardProjectUseCase,
    TopicSelectionInput,
    SaveScriptEditsUseCase,
    SaveTopicUseCase,
    parse_target_duration,
)
from .publish_commands import MockUploadUseCase, SchedulePublishUseCase, StagePublishUseCase, UploadPrivateVideoUseCase
from .script_workflow import ApproveScriptUseCase, GenerateScriptUseCase

__all__ = [
    "BuildAnalyticsTableUseCase",
    "CaptureAnalyticsSnapshotUseCase",
    "ApproveScenesUseCase",
    "BuildSceneReviewUseCase",
    "GenerateProjectMediaUseCase",
    "RegenerateSceneUseCase",
    "RunVoiceCheckUseCase",
    "BuildDiscardedProjectsUseCase",
    "BuildProjectDetailUseCase",
    "BuildProjectListUseCase",
    "BuildScriptEditorUseCase",
    "BuildTopicSelectionUseCase",
    "CreateProjectUseCase",
    "DiscardProjectUseCase",
    "TopicSelectionInput",
    "SaveScriptEditsUseCase",
    "SaveTopicUseCase",
    "parse_target_duration",
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
    "ApproveScriptUseCase",
    "GenerateScriptUseCase",
]
