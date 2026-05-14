from __future__ import annotations

import unittest
from unittest.mock import Mock

from youtube_ai_system.application.result import UseCaseResult
from youtube_ai_system.application.use_cases import (
    ApproveScenesUseCase,
    ApproveScriptUseCase,
    AssembleProjectUseCase,
    GenerateProjectMediaUseCase,
    GenerateScriptUseCase,
    UploadPrivateVideoUseCase,
)
from youtube_ai_system.contracts.assembly import AssemblyManifestContract
from youtube_ai_system.contracts.projects import ProjectContract
from youtube_ai_system.contracts.publishing import UploadPackageContract
from youtube_ai_system.contracts.rendering import RenderSpecContract
from youtube_ai_system.contracts.scripts import ScriptDraftContract
from youtube_ai_system.observability.run_events import PipelineEvent, emit_run_event
from youtube_ai_system.pipelines.result import PipelineStageResult


class ArchitectureSkeletonTest(unittest.TestCase):
    def test_use_case_result_helpers(self) -> None:
        success = UseCaseResult.ok("done", data={"id": 1})
        failure = UseCaseResult.fail("failed", errors=["a", "b"])

        self.assertTrue(success.success)
        self.assertEqual(success.data["id"], 1)
        self.assertFalse(failure.success)
        self.assertEqual(failure.errors, ("a", "b"))
        self.assertEqual(failure.primary_message, "failed")

    def test_contracts_round_trip_existing_dict_shapes(self) -> None:
        project = ProjectContract.from_dict(
            {"id": 7, "working_title": "Salary Leaks", "topic": "salary", "angle": "leaks", "state": "drafted"}
        )
        script = ScriptDraftContract.from_dict(
            {
                "hook": "Where does your salary go?",
                "scenes": [{"title": "Rent", "narration": "Rent rises first."}],
                "outro": "Start tracking today.",
            }
        )
        render = RenderSpecContract.from_dict(
            {"composition": "SceneRenderer", "props": {"scene": 1}, "duration_frames": 120, "fps": 30}
        )
        upload = UploadPackageContract.from_dict(
            {"title": "Where Does Your Salary Go?", "video_path": "/tmp/final.mp4", "tags": ["finance"]}
        )
        assembly = AssemblyManifestContract.from_dict(
            {"segments": ["/tmp/scene-1.mp4", "/tmp/scene-2.mp4"], "output_path": "/tmp/final.mp4"}
        )

        self.assertTrue(project.validate().passed)
        self.assertEqual(script.to_dict()["scenes"][0]["title"], "Rent")
        self.assertTrue(render.validate().passed)
        self.assertTrue(upload.validate().passed)
        self.assertTrue(assembly.validate().passed)
        self.assertEqual(assembly.segments, ["/tmp/scene-1.mp4", "/tmp/scene-2.mp4"])
        self.assertEqual(upload.to_dict()["privacy_status"], "private")

    def test_pipeline_result_and_run_event_wrapper(self) -> None:
        result = PipelineStageResult.completed("assembly", "ok", data={"frames": 30})
        logger = Mock()

        emit_run_event(logger, PipelineEvent("assembly", "success", "ok", project_id=3))

        self.assertTrue(result.success)
        self.assertEqual(result.data["frames"], 30)
        logger.log.assert_called_once_with("assembly", "success", "ok", 3)


class UseCaseWrapperBehaviorTest(unittest.TestCase):
    def test_generate_script_wrapper_preserves_current_route_sequence(self) -> None:
        repo = Mock()
        repo.get_project.return_value = {
            "id": 12,
            "topic": "salary leaks",
            "angle": "hidden expenses",
            "state": "drafted",
            "target_duration_minutes": 8,
            "channel_niche": "finance",
            "script_tone": "direct",
        }
        script_service = Mock()
        script_service.generate_script.return_value = 44
        state_machine = Mock()

        result = GenerateScriptUseCase(repo, script_service, state_machine).execute(12)

        self.assertTrue(result.success)
        state_machine.transition.assert_called_once_with(12, "script_review", "Script review started.")
        script_service.generate_script.assert_called_once_with(
            12,
            "salary leaks",
            "hidden expenses",
            8,
            "finance",
            "direct",
        )
        self.assertEqual(result.data["script_version_id"], 44)

    def test_approve_script_wrapper_preserves_scene_replacement_sequence(self) -> None:
        repo = Mock()
        repo.get_project.return_value = {"id": 5, "state": "script_review"}
        repo.get_latest_script_version.return_value = {"id": 22, "full_script_json": "{}"}
        script_service = Mock()
        script_service.approval_ready.return_value = (True, [], {"scenes": []})
        script_service.scene_rows_from_payload.return_value = [{"scene_order": 1}]
        state_machine = Mock()

        result = ApproveScriptUseCase(repo, script_service, state_machine).execute(5)

        self.assertTrue(result.success)
        repo.update_script_version.assert_called_once()
        repo.replace_scenes.assert_called_once_with(5, 22, [{"scene_order": 1}])
        state_machine.transition.assert_called_once_with(5, "script_approved", "Script approved.")

    def test_generate_media_wrapper_preserves_transition_order(self) -> None:
        repo = Mock()
        repo.get_project.return_value = {"id": 6, "state": "script_approved"}
        media_service = Mock()
        media_service.project_media_summary.return_value = {
            "voice_message": "live",
            "visual_message": "generated",
        }
        state_machine = Mock()

        result = GenerateProjectMediaUseCase(repo, media_service, state_machine).execute(6)

        self.assertTrue(result.success)
        self.assertEqual(
            state_machine.transition.call_args_list[0].args,
            (6, "media_generating", "Media generation started."),
        )
        self.assertEqual(
            state_machine.transition.call_args_list[1].args,
            (6, "scene_review", "Media assets ready for scene review."),
        )
        media_service.generate_voice_and_visuals.assert_called_once_with(6)

    def test_approve_scenes_wrapper_preserves_professional_gate(self) -> None:
        repo = Mock()
        repo.get_project.return_value = {"id": 8, "state": "scene_review"}
        media_service = Mock()
        media_service.compute_dynamic_visual_ratio.return_value = (1.0, [{"id": 1}])
        acceptance_report = Mock()
        acceptance_report.passed = True
        acceptance_service = Mock()
        acceptance_service.evaluate_project.return_value = acceptance_report
        state_machine = Mock()

        result = ApproveScenesUseCase(repo, media_service, acceptance_service, state_machine).execute(8)

        self.assertTrue(result.success)
        acceptance_service.evaluate_project.assert_called_once_with(8)
        state_machine.transition.assert_called_once_with(8, "assets_ready", "Scene review approved.")

    def test_assemble_wrapper_preserves_qa_before_assembly(self) -> None:
        repo = Mock()
        repo.get_project.return_value = {"id": 9, "state": "assets_ready"}
        acceptance_report = Mock()
        acceptance_report.passed = True
        acceptance_service = Mock()
        acceptance_service.evaluate_project.return_value = acceptance_report
        assembly_service = Mock()
        assembly_service.assemble_project.return_value = "/tmp/final.mp4"
        state_machine = Mock()

        result = AssembleProjectUseCase(repo, assembly_service, acceptance_service, state_machine).execute(9)

        self.assertTrue(result.success)
        acceptance_service.evaluate_project.assert_called_once_with(9)
        assembly_service.assemble_project.assert_called_once_with(9)
        self.assertEqual(
            state_machine.transition.call_args_list[0].args,
            (9, "assembling", "Assembly started."),
        )
        self.assertEqual(
            state_machine.transition.call_args_list[1].args,
            (9, "ready_to_publish", "Assembly complete."),
        )

    def test_upload_wrapper_preserves_duplicate_upload_guard(self) -> None:
        repo = Mock()
        repo.get_project.return_value = {
            "id": 10,
            "state": "ready_to_publish",
            "youtube_video_id": "abc123",
        }
        upload_service = Mock()

        result = UploadPrivateVideoUseCase(repo, upload_service).execute(10)

        self.assertTrue(result.success)
        self.assertTrue(result.data["already_uploaded"])
        upload_service.upload_private.assert_not_called()


if __name__ == "__main__":
    unittest.main()
