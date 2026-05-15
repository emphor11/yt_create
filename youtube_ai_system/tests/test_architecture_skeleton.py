from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from youtube_ai_system.application.result import UseCaseResult
from youtube_ai_system.application.use_cases import (
    ApproveScenesUseCase,
    ApproveScriptUseCase,
    AssembleProjectUseCase,
    CreateProjectUseCase,
    DiscardProjectUseCase,
    GenerateProjectMediaUseCase,
    GenerateScriptUseCase,
    MockUploadUseCase,
    SaveScriptEditsUseCase,
    SaveTopicUseCase,
    SchedulePublishUseCase,
    StagePublishUseCase,
    UploadPrivateVideoUseCase,
)
from youtube_ai_system.contracts.assembly import AssemblyManifestContract
from youtube_ai_system.contracts.media import MediaArtifactContract
from youtube_ai_system.contracts.projects import ProjectContract
from youtube_ai_system.contracts.publishing import UploadPackageContract
from youtube_ai_system.contracts.rendering import RenderSpec, RenderSpecContract
from youtube_ai_system.contracts.scenes import SceneContract
from youtube_ai_system.contracts.scripts import ScriptDraftContract
from youtube_ai_system.contracts.visuals import VisualSceneContract
from youtube_ai_system.infrastructure.ffmpeg import FfmpegExecutor
from youtube_ai_system.infrastructure.filesystem.storage import FileStorage
from youtube_ai_system.infrastructure.llm import GroqChatClient
from youtube_ai_system.infrastructure.persistence import ProjectRepository as PersistenceProjectRepository
from youtube_ai_system.infrastructure.remotion import RemotionAssetStager
from youtube_ai_system.infrastructure.voice import VoiceAudioTools
from youtube_ai_system.infrastructure.youtube import YouTubeVideoUploader
from youtube_ai_system.models.repository import ProjectRepository as ModelProjectRepository
from youtube_ai_system.observability.artifact_log import artifact_created
from youtube_ai_system.observability.run_events import (
    ArtifactEvent,
    FailureEvent,
    PipelineEvent,
    StageTiming,
    emit_artifact_event,
    emit_failure_event,
    emit_run_event,
    emit_timing_event,
)
from youtube_ai_system.observability.tracing import StageTimer
from youtube_ai_system.pipelines.media import (
    DynamicVisualCoverageCalculator,
    IndianNumberFormatter,
    MediaSummaryBuilder,
    OutroSectionBuilder,
    SceneTextSignalResolver,
    VoiceCheckResultBuilder,
)
from youtube_ai_system.pipelines.publishing.upload_package import UploadPackageBuilder
from youtube_ai_system.pipelines.rendering import (
    BasicRenderSpecFactory,
    LegacyFlowStageBuilder,
    RenderBrollResolver,
    RenderCaptionBuilder,
    RenderChartDataExtractor,
    RenderClassifiedContract,
    RenderContextGate,
    RenderDataRequirementGate,
    RenderEmphasisBuilder,
    RenderFlowHelpers,
    RenderFlowLabelHelper,
    RenderFlowPropsBuilder,
    RenderLogicRepair,
    RenderLogicTextFormatter,
    RenderLogicValidator,
    RenderNarrationLogicBuilder,
    RenderNumberUtils,
    RenderPatternSelector,
    RenderPropsBuilder,
    RenderPropsGate,
    RenderSplitHelpers,
    RenderTextUtils,
    RenderValueDeriver,
    RenderVisualGate,
)
from youtube_ai_system.pipelines.result import PipelineStageResult
from youtube_ai_system.quality.publishing_quality import PublishingReadinessPolicy
from youtube_ai_system.services.render_spec_service import RenderSpec as ServiceRenderSpec


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
                "hook": {"narration": "Where does your salary go?"},
                "scenes": [
                    {
                        "scene_index": 1,
                        "title": "Rent",
                        "narration": "Rent rises first.",
                        "numbers": ["₹50,000"],
                    }
                ],
                "outro": {"narration": "Start tracking today."},
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
        self.assertEqual(script.hook_narration, "Where does your salary go?")
        self.assertEqual(script.to_dict()["scenes"][0]["title"], "Rent")
        self.assertEqual(script.to_dict()["scenes"][0]["numbers"], ["₹50,000"])
        self.assertTrue(render.validate().passed)
        self.assertTrue(upload.validate().passed)
        self.assertTrue(assembly.validate().passed)
        self.assertEqual(assembly.segments, ["/tmp/scene-1.mp4", "/tmp/scene-2.mp4"])
        self.assertEqual(upload.to_dict()["privacy_status"], "private")

    def test_contracts_understand_current_storage_shapes(self) -> None:
        scene = SceneContract.from_dict(
            {
                "id": 10,
                "video_project_id": 4,
                "scene_order": 2,
                "kind": "body",
                "narration_text": "Rent rises after the salary bump.",
                "visual_plan_json": '[{"beat_type":"stat_explosion","content":"₹10,000"}]',
                "visual_scene_json": '{"component":"LifestyleCreepVisualizer","mechanism":"lifestyle_inflation"}',
                "audio_path": "/tmp/audio.wav",
                "video_path": "/tmp/scene.mp4",
                "status": "rendered",
            }
        )
        visual = VisualSceneContract.from_dict(
            {
                "component": "LifestyleCreepVisualizer",
                "narration": "Rent rises after the salary bump.",
                "numbers": ["₹10,000"],
                "emotion": "anxiety",
                "mechanism": "lifestyle_inflation",
            }
        )
        media = MediaArtifactContract.from_dict({"id": 10, "video_path": "/tmp/scene.mp4", "status": "rendered"})
        upload = UploadPackageContract.from_dict(
            {
                "selected_title": "Where Does Your Salary Go?",
                "description": "Desc",
                "video_path": "/tmp/final.mp4",
                "thumbnail_path": "/tmp/thumb.jpg",
            }
        )

        self.assertTrue(scene.validate().passed)
        self.assertEqual(scene.project_id, 4)
        self.assertEqual(scene.scene_number, 2)
        self.assertEqual(scene.visual_plan[0]["content"], "₹10,000")
        self.assertEqual(scene.visual_scene["component"], "LifestyleCreepVisualizer")
        self.assertTrue(visual.validate().passed)
        self.assertEqual(visual.to_dict()["mechanism"], "lifestyle_inflation")
        self.assertTrue(media.validate().passed)
        self.assertEqual(media.artifact.path, "/tmp/scene.mp4")
        self.assertEqual(upload.title, "Where Does Your Salary Go?")
        self.assertEqual(upload.to_dict()["selected_title"], "Where Does Your Salary Go?")

    def test_pipeline_result_and_run_event_wrapper(self) -> None:
        result = PipelineStageResult.completed("assembly", "ok", data={"frames": 30})
        logger = Mock()

        emit_run_event(logger, PipelineEvent("assembly", "success", "ok", project_id=3))

        self.assertTrue(result.success)
        self.assertEqual(result.data["frames"], 30)
        logger.log.assert_called_once_with("assembly", "success", "ok", 3)

    def test_observability_events_emit_through_existing_run_logger_api(self) -> None:
        logger = Mock()

        emit_artifact_event(logger, ArtifactEvent(5, "assembly", "/tmp/final.mp4", "video"))
        emit_timing_event(logger, StageTiming(5, "assembly", 120))
        emit_failure_event(logger, FailureEvent(5, "assembly", "bad input"))

        self.assertEqual(logger.log.call_count, 3)
        self.assertEqual(logger.log.call_args_list[0].args, ("assembly", "created", "video artifact created. Artifact: /tmp/final.mp4", 5))
        self.assertEqual(logger.log.call_args_list[1].args, ("assembly", "completed", "assembly completed in 120ms.", 5))
        self.assertEqual(logger.log.call_args_list[2].args, ("assembly", "failed", "bad input", 5))

    def test_stage_timer_and_artifact_helper_create_structured_events(self) -> None:
        timing = StageTimer("media", project_id=6).finish()
        artifact = artifact_created(6, "media", "/tmp/scene.mp4", "video")

        self.assertEqual(timing.stage_name, "media")
        self.assertGreaterEqual(timing.duration_ms, 0)
        self.assertEqual(artifact.artifact_path, "/tmp/scene.mp4")

    def test_media_summary_helpers_match_current_status_language(self) -> None:
        scenes = [
            {"audio_source": "kokoro:am_eric", "visual_source": "remotion_scene_builder", "visual_path": "/tmp/a.mp4"},
            {"audio_source": "demo_silent", "visual_source": "remotion_failed", "visual_path": None},
        ]

        ratio, returned_scenes = DynamicVisualCoverageCalculator().compute(scenes)
        media = MediaSummaryBuilder().project_media_summary(scenes)
        voice = MediaSummaryBuilder().project_voice_summary(scenes, "kokoro")

        self.assertEqual(ratio, 0.5)
        self.assertEqual(returned_scenes, scenes)
        self.assertEqual(media["voice_status"], "mixed")
        self.assertEqual(media["visual_status"], "partial")
        self.assertEqual(voice["mode"], "kokoro")
        self.assertEqual(voice["status"], "mixed")

    def test_scene_text_signal_resolver_matches_current_media_heuristics(self) -> None:
        resolver = SceneTextSignalResolver()

        signals = resolver.scene_text_signals("Salary grows, but rent and EMI create risk because expenses rise.")

        self.assertEqual(signals["dominant_entity"], "salary")
        self.assertEqual(signals["idea_type"], "growth")
        self.assertTrue(signals["has_comparison"])
        self.assertTrue(signals["has_causation"])
        self.assertEqual(resolver.weight_for_scene_kind("hook"), {"level": "high", "score": 0.9})

    def test_outro_section_builder_preserves_recap_visual_contract(self) -> None:
        section = OutroSectionBuilder().section_intelligence(
            "Track expenses. Protect the emergency fund. Invest consistently. Start this month."
        )

        self.assertEqual(section["visual_plan"][0]["visual"]["pattern"], "OutroRecapVisualizer")
        self.assertEqual(section["visual_scene"]["mechanism"], "definition")
        self.assertEqual(section["cinematic_intent"]["overlay_text"], "Start this month")
        self.assertIn("Track the leak", section["visual_scene"]["visual_beats"])

    def test_voice_check_result_builder_preserves_ui_contract(self) -> None:
        result = Mock(
            source="demo_silent",
            audio_path="/tmp/audio.wav",
            subtitle_path=None,
            duration_sec=2.5,
        )
        builder = VoiceCheckResultBuilder()

        success = builder.success(result, "kokoro")
        failure = builder.failure(RuntimeError("timed out"), "kokoro")

        self.assertEqual(success["status"], "demo")
        self.assertEqual(success["message"], "Voice check used silent fallback audio. Install/configure Kokoro for live narration.")
        self.assertEqual(failure["status"], "failed")
        self.assertIn("Edge TTS timed out", failure["message"])

    def test_indian_number_formatter_preserves_chart_label_style(self) -> None:
        formatter = IndianNumberFormatter()

        self.assertEqual(formatter.format_number(999), "999")
        self.assertEqual(formatter.format_number(12345), "12,345")
        self.assertEqual(formatter.format_number(250000), "2.5L")
        self.assertEqual(formatter.format_number(10000000), "1Cr")
        self.assertEqual(formatter.format_indian_grouped_number(-1234567), "-12,34,567")

    def test_file_storage_resolves_project_artifact_directories(self) -> None:
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as temp_dir:
            storage = FileStorage(Path(temp_dir))
            video_dir = storage.project_video_dir(9)
            audio_dir = storage.project_audio_dir(9)
            image_dir = storage.project_image_dir(9)

            self.assertTrue(video_dir.exists())
            self.assertTrue(audio_dir.exists())
            self.assertTrue(image_dir.exists())
            self.assertEqual(video_dir.name, "9")

    def test_persistence_infrastructure_exports_current_repository(self) -> None:
        self.assertIs(PersistenceProjectRepository, ModelProjectRepository)

    def test_remotion_asset_stager_is_available_without_service_dependency(self) -> None:
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "remotion"
            source_path = Path(temp_dir) / "voice.wav"
            source_path.write_bytes(b"audio")

            stager = RemotionAssetStager({"audio_file"}, {"background": "#000"})
            props = stager.props_for_render(
                RenderSpec("VideoRenderer", {"audio_file": str(source_path)}, 1.0, "test"),
                project_path,
            )

        self.assertIs(ServiceRenderSpec, RenderSpec)
        self.assertEqual(props["theme"], {"background": "#000"})
        self.assertTrue(props["audio_file"].startswith("render-assets/audio/"))

    def test_basic_render_spec_factory_preserves_simple_compositions(self) -> None:
        factory = BasicRenderSpecFactory()

        stat = factory.stat_explosion("₹1 lakh", "gone", "red", 3.0)
        split = factory.split_comparison("Before", "₹50,000", "After", "₹6,000", 4.0)
        thumb = factory.thumbnail("Where Does Salary Go?", "Salary", "Where Does Go?", 1)

        self.assertEqual(stat.composition, "StatExplosion")
        self.assertEqual(stat.props["durationSec"], 3.0)
        self.assertEqual(split.props["rightContent"], "₹6,000")
        self.assertEqual(thumb.output_ext, ".jpg")

    def test_render_broll_resolver_preserves_asset_query_rules(self) -> None:
        resolver = RenderBrollResolver()

        self.assertTrue(
            resolver.beat_requires_source_asset(
                {"intent": "CONTEXT"},
                is_structured_beat=lambda _beat: True,
                normalize_structured_beat=lambda _beat: {"component": "BrollOverlay"},
            )
        )
        self.assertFalse(
            resolver.beat_requires_source_asset(
                {"content": "finance stress"},
                is_structured_beat=lambda _beat: False,
                normalize_structured_beat=lambda _beat: {},
            )
        )
        self.assertEqual(
            resolver.broll_query_for_beat(
                {"intent": "CONTEXT"},
                is_structured_beat=lambda _beat: True,
                normalize_structured_beat=lambda _beat: {"props": {"query": "office money stress"}},
            ),
            "office money stress",
        )
        self.assertEqual(
            resolver.broll_query_for_beat(
                {"caption": "salary anxiety"},
                is_structured_beat=lambda _beat: False,
                normalize_structured_beat=lambda _beat: {},
            ),
            "salary anxiety",
        )

    def test_render_text_utils_preserve_overlay_and_split_helpers(self) -> None:
        utils = RenderTextUtils()

        self.assertEqual(utils.dominant_phrase("You lost ₹ 50,000 this year"), "₹50,000")
        self.assertEqual(utils.short_overlay("salary leak happens slowly", 2), "salary leak")
        self.assertEqual(utils.sentiment("debt risk"), "negative")
        self.assertEqual(utils.chart_color("invest growth"), "teal")
        self.assertEqual(utils.kicker("save and invest"), "Money move")
        self.assertEqual(utils.unit_label("₹50,000"), "₹")
        self.assertEqual(utils.extract_color("title: SIP, color: red"), "red")
        self.assertEqual(utils.beat_color("purple"), "orange")
        self.assertEqual(
            utils.parse_split("₹50,000 Salary vs ₹6,000 Left", ""),
            ("Salary", "₹50,000 Salary", "Amount", "₹6,000 Left"),
        )

    def test_render_split_helpers_preserve_split_logic_helpers(self) -> None:
        helpers = RenderSplitHelpers()

        self.assertEqual(
            helpers.concrete_split_from_logic("₹50,000 Salary vs ₹6,000 Left", ""),
            ("₹50,000 Salary", "₹6,000 Left"),
        )
        self.assertEqual(
            helpers.concrete_split_from_logic("Numbers are ₹50,000 and ₹6,000", ""),
            ("₹50,000", "₹6,000"),
        )
        self.assertEqual(
            helpers.concrete_split_from_logic("salary leak", "only ₹6,000 left"),
            ("salary leak", "only ₹6,000 left"),
        )
        self.assertEqual(helpers.humanize_split_label("REALITY", "₹6,000 Left"), "Amount")
        self.assertEqual(helpers.humanize_split_label("Custom", "₹6,000 Left"), "Amount")

    def test_render_caption_builder_preserves_caption_and_context_helpers(self) -> None:
        builder = RenderCaptionBuilder()

        self.assertEqual(
            builder.repair_caption(
                "Salary disappears by day 12 because expenses keep hitting",
                "₹50,000 Salary -> ₹44,000 Expenses -> ₹6,000 Left",
                "salary disappears by day 12 because expenses keep hitting",
            ),
            "₹50,000 Salary ₹44,000 Expenses ₹6,000 Left",
        )
        self.assertEqual(
            builder.beat_context(
                {
                    "narration": "Salary arrives.",
                    "visual_instruction": "Show flow.",
                    "content": "₹50,000",
                    "caption": "only ₹6,000 left",
                }
            ),
            "Salary arrives. Show flow. ₹50,000 only ₹6,000 left",
        )

    def test_render_number_utils_preserve_rupee_and_token_helpers(self) -> None:
        utils = RenderNumberUtils()

        self.assertEqual(utils.first_numeric_value("₹1,23,456 left"), 123456.0)
        self.assertEqual(utils.format_rupees(123456), "₹1,23,500")
        self.assertEqual(utils.format_rupees(-20), "₹0")
        self.assertEqual(utils.money_tokens("Salary ₹ 50,000, left ₹6,000."), ["₹50,000", "₹6,000"])
        self.assertEqual(utils.percent_tokens("6.5% inflation and 12% returns"), ["6.5%", "12%"])
        self.assertEqual(utils.numeric_values("A 10 and B 20.5"), [10.0, 20.5])

    def test_render_chart_data_extractor_preserves_current_fallbacks(self) -> None:
        extractor = RenderChartDataExtractor()

        self.assertEqual(
            extractor.extract_data_points("data: Rent=20000, Food=5000, title: Expenses"),
            [{"label": "Rent", "value": 20000.0}, {"label": "Food", "value": 5000.0}],
        )
        self.assertEqual(
            extractor.extract_data_points("2024 value 10 and 2025 value 20"),
            [{"label": "2024", "value": 10.0}, {"label": "and 2025", "value": 20.0}],
        )
        self.assertEqual(
            extractor.extract_data_points("10 20 30"),
            [
                {"label": "Point 1", "value": 10.0},
                {"label": "Point 2", "value": 20.0},
                {"label": "Point 3", "value": 30.0},
            ],
        )

    def test_render_data_requirement_gate_preserves_pattern_requirements(self) -> None:
        number_utils = RenderNumberUtils()
        gate = RenderVisualGate(
            abstract_visual_words={"visual", "chart", "concept"},
            generic_visual_words={"system"},
            number_utils=number_utils,
        )
        requirements = RenderDataRequirementGate(
            flow_patterns={"MONEY_FLOW", "VALUE_DECAY", "LOOP", "GROWTH"},
            chart_data=RenderChartDataExtractor(),
            visual_gate=gate,
        )

        self.assertTrue(
            requirements.has_chart_data(
                {"props": {"data": [{"label": "A", "value": 1}, {"label": "B", "value": 2}]}},
                "",
            )
        )
        self.assertTrue(requirements.has_chart_data({}, "2024 value 10 and 2025 value 20"))
        self.assertTrue(
            requirements.pattern_has_required_concrete_data(
                "COMPARISON",
                "COMPARISON",
                {"props": {"leftContent": "₹50,000 Salary", "rightContent": "₹6,000 Left"}},
                "",
            )
        )
        self.assertTrue(
            requirements.pattern_has_required_concrete_data(
                "EXPLANATION",
                "MONEY_FLOW",
                {},
                "₹50,000 Salary -> ₹44,000 Expenses -> ₹6,000 Left",
            )
        )
        self.assertFalse(requirements.pattern_has_required_concrete_data("DATA", "GROWTH", {}, "growth concept"))

    def test_render_flow_helpers_preserve_connection_fallbacks(self) -> None:
        helpers = RenderFlowHelpers()
        nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]

        self.assertEqual(helpers.default_node_role(0, 3), "source")
        self.assertEqual(helpers.default_node_role(1, 3), "process")
        self.assertEqual(helpers.default_node_role(2, 3), "result")
        self.assertEqual(helpers.safe_id("₹50,000 Salary", 0), "50_000_Salary")
        self.assertEqual(
            helpers.flow_connections([{"from": "a", "to": "c"}, {"from": "x", "to": "a"}], nodes, "linear"),
            [{"from": "a", "to": "c"}],
        )
        self.assertEqual(
            helpers.flow_connections([], nodes, "loop"),
            [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}, {"from": "c", "to": "a"}],
        )

    def test_render_flow_label_helper_preserves_caption_and_color_rules(self) -> None:
        labels = RenderFlowLabelHelper()

        self.assertEqual(labels.humanize_money_phrase("₹0 Saved Emotional Spend"), "₹0 left to spend")
        self.assertEqual(labels.humanize_money_phrase("goes to investment"), "auto-invested")
        self.assertEqual(labels.complete_caption("₹0 left to"), "₹0 left to spend")
        self.assertEqual(labels.color_for_label("₹0 Left"), "red")
        self.assertEqual(labels.color_for_label("auto-invested growth"), "teal")
        self.assertTrue(labels.is_loss_result("monthly leak"))
        self.assertTrue(labels.looks_like_outro_loss("₹5,000/month gone, ₹60,000 lost"))

    def test_render_flow_props_builder_preserves_flow_diagram_props(self) -> None:
        number_utils = RenderNumberUtils()
        labels = RenderFlowLabelHelper(number_utils)
        builder = RenderFlowPropsBuilder(
            flow_helpers=RenderFlowHelpers(),
            flow_labels=labels,
            text_utils=RenderTextUtils(),
            visual_gate=RenderVisualGate(
                abstract_visual_words={"visual", "chart", "concept"},
                generic_visual_words={"system"},
                number_utils=number_utils,
            ),
        )

        props = builder.flow_props(
            "MONEY_FLOW",
            "₹50,000 Salary -> ₹44,000 Expenses -> ₹6,000 Left",
            "salary leak",
            {},
            "orange",
            {},
        )

        self.assertEqual(props["mode"], "linear")
        self.assertEqual(props["layout"], "horizontal")
        self.assertEqual(len(props["nodes"]), 3)
        self.assertEqual(props["nodes"][0]["style"], {"size": "large", "color": "teal"})
        self.assertEqual(props["nodes"][-1]["style"], {"size": "large", "color": "red"})
        self.assertEqual(props["connections"], [{"from": "node1", "to": "node2"}, {"from": "node2", "to": "node3"}])
        self.assertEqual(builder.flow_mode("VALUE_DECAY", ""), "decay")
        self.assertEqual(builder.flow_layout("loop", ""), "radial")
        self.assertEqual(builder.fallback_node_label("₹1 -> ₹2 -> ₹3", 4, "MONEY_FLOW"), "Step 5")
        self.assertEqual(builder.monthly_punchline_source("₹5,000 leak"), "₹5,000 leaks every month")
        self.assertEqual(builder.short_money("₹60,000 gone"), "₹60,000")

        outro = builder.polish_flow_display_props(
            {
                **props,
                "isOutro": True,
                "caption": "₹5,000/month gone ₹60,000 lost",
            },
            "₹5,000/month gone ₹60,000 lost",
        )

        self.assertEqual(outro["color"], "red")
        self.assertEqual(outro["captionColor"], "red")

    def test_legacy_flow_stage_builder_preserves_stage_derivation(self) -> None:
        number_utils = RenderNumberUtils()
        builder = LegacyFlowStageBuilder(
            flow_helpers=RenderFlowHelpers(),
            number_utils=number_utils,
            value_deriver=RenderValueDeriver(number_utils),
        )

        self.assertEqual(
            builder.beat_flow_stages(
                {"flow_stages": [{"value": "A"}, {"value": "B"}, {"value": "C"}]},
                {},
                "",
            ),
            [
                {"label": "source", "value": "A"},
                {"label": "process", "value": "B"},
                {"label": "result", "value": "C"},
            ],
        )
        self.assertEqual(
            builder.beat_flow_stages({"content": "₹50,000 -> expenses -> ₹6,000"}, {}, ""),
            [
                {"label": "start", "value": "₹50,000"},
                {"label": "change", "value": "expenses"},
                {"label": "result", "value": "₹6,000"},
            ],
        )
        self.assertEqual(
            builder.concept_flow_stages({}, "salary ₹25,000 vanished by day 12 and ₹0 left")[1],
            {"label": "change", "value": "Day 12"},
        )
        self.assertEqual(
            builder.concept_flow_stages({}, "FD ₹1,00,000 loses 6%")[2],
            {"label": "result", "value": "₹94,000"},
        )
        self.assertEqual(
            builder.concept_flow_stages({}, "₹5,000 monthly leak"),
            [
                {"label": "start", "value": "₹5,000/month"},
                {"label": "change", "value": "12 months"},
                {"label": "result", "value": "₹60,000/year"},
            ],
        )

    def test_render_visual_gate_preserves_concreteness_rules(self) -> None:
        gate = RenderVisualGate(
            abstract_visual_words={"visual", "chart", "concept"},
            generic_visual_words={"system"},
        )

        self.assertTrue(gate.is_abstract_visual_logic("show chart"))
        self.assertTrue(gate.contains_generic_visual_words("money system"))
        self.assertTrue(gate.has_number("₹50,000 left"))
        self.assertTrue(gate.has_visual_structure("₹50,000 -> expenses -> ₹6,000 left"))
        self.assertTrue(gate.has_impact("₹50,000 -> expenses -> ₹6,000 left"))
        self.assertTrue(gate.passes_text_gate("₹50,000 -> expenses -> ₹6,000 left"))
        self.assertFalse(gate.passes_text_gate("nice finance concept"))

    def test_render_props_gate_preserves_component_prop_checks(self) -> None:
        gate = RenderVisualGate(
            abstract_visual_words={"visual", "chart", "concept"},
            generic_visual_words={"system"},
        )
        props_gate = RenderPropsGate(gate)

        self.assertTrue(props_gate.passes_visual_gate("CONTEXT", "CONTEXT", "abstract visual"))
        self.assertTrue(props_gate.passes_visual_gate("EMPHASIS", "EMPHASIS", "76% cannot save"))
        self.assertFalse(props_gate.passes_visual_gate("EMPHASIS", "EMPHASIS", "finance concept"))
        self.assertTrue(
            props_gate.props_pass_visual_gate(
                "FlowDiagram",
                "MONEY_FLOW",
                "",
                {
                    "nodes": [
                        {"label": "₹50,000 Salary"},
                        {"label": "₹44,000 Expenses"},
                        {"label": "₹6,000 Left"},
                    ]
                },
            )
        )
        self.assertTrue(
            props_gate.props_pass_visual_gate(
                "SplitComparison",
                "COMPARISON",
                "",
                {"leftContent": "₹50,000 Salary", "rightContent": "₹6,000 Left"},
            )
        )
        self.assertTrue(
            props_gate.props_pass_visual_gate(
                "LineChart",
                "GROWTH",
                "SIP growth",
                {"title": "SIP growth", "data": [{"label": "A", "value": 1}, {"label": "B", "value": 2}]},
            )
        )
        self.assertFalse(props_gate.props_pass_visual_gate("FlowDiagram", "MONEY_FLOW", "", {"nodes": []}))

    def test_render_props_builder_preserves_repair_and_regenerate_props(self) -> None:
        number_utils = RenderNumberUtils()
        text_utils = RenderTextUtils()
        visual_gate = RenderVisualGate(
            abstract_visual_words={"visual", "chart", "concept"},
            generic_visual_words={"system"},
            number_utils=number_utils,
        )
        flow_labels = RenderFlowLabelHelper(number_utils)
        builder = RenderPropsBuilder(
            chart_data=RenderChartDataExtractor(),
            flow_labels=flow_labels,
            flow_props=RenderFlowPropsBuilder(
                flow_helpers=RenderFlowHelpers(),
                flow_labels=flow_labels,
                text_utils=text_utils,
                visual_gate=visual_gate,
            ),
            split_helpers=RenderSplitHelpers(text_utils),
            text_utils=text_utils,
            visual_gate=visual_gate,
        )

        split = builder.repair_props(
            "SplitComparison",
            "COMPARISON",
            "₹50,000 Salary vs ₹6,000 Left",
            "",
            {"props": {"leftLabel": "CLAIM"}},
        )
        chart = builder.repair_props("LineChart", "GROWTH", "2024 value 10 and 2025 value 20", "caption", {})
        broll = builder.repair_props("BrollOverlay", "CONTEXT", "office stress", "money anxiety", {})
        regenerated = builder.regenerate_props(
            "SplitComparison",
            "COMPARISON",
            "finance concept",
            "caption",
            "context",
            {},
            contextual_visual_logic=lambda _context, _beat: "₹50,000 Salary vs ₹6,000 Left",
            safe_emphasis_logic=lambda text: text,
            safe_emphasis_props=lambda logic, caption: {"headline": logic, "subtext": caption},
        )

        self.assertEqual(split["leftContent"], "₹50,000 Salary")
        self.assertEqual(split["rightContent"], "₹6,000 Left")
        self.assertEqual(chart["animationSpeed"], "fast")
        self.assertEqual(broll["query"], "office stress")
        self.assertEqual(regenerated["leftContent"], "₹50,000 Salary")
        self.assertEqual(regenerated["rightLabel"], "REALITY")

    def test_render_emphasis_builder_preserves_fallback_props(self) -> None:
        gate = RenderVisualGate(
            abstract_visual_words={"visual", "chart", "concept"},
            generic_visual_words={"system"},
        )
        builder = RenderEmphasisBuilder(
            text_utils=RenderTextUtils(),
            visual_gate=gate,
        )

        self.assertEqual(
            builder.concrete_fallback_logic({"props": {"headline": "76%", "subtext": "cannot save ₹5,000"}}),
            "76% can't save ₹5,000",
        )
        self.assertEqual(builder.concrete_fallback_logic({"content": "nice concept"}), "76% can't save ₹5,000")
        self.assertEqual(
            builder.safe_emphasis_props("₹50,000 debt loss", "caption"),
            {"headline": "₹50,000", "subtext": "caption", "color": "red"},
        )
        self.assertEqual(
            builder.safe_emphasis_props("₹5,000 invest growth", ""),
            {"headline": "₹5,000", "subtext": "invest growth", "color": "orange"},
        )

    def test_render_context_gate_preserves_context_relevance_rules(self) -> None:
        gate = RenderContextGate()

        self.assertFalse(gate.comparison_units_match({"type": "comparison", "left": "12%", "right": "₹50,000"}))
        self.assertEqual(gate.dominant_unit("₹50,000 salary"), "money")
        self.assertEqual(gate.dominant_unit("12% return"), "percent")
        self.assertEqual(gate.strict_contextual_number_allowlist("salary vanished"), {"₹25,000", "₹0"})
        self.assertTrue(gate.numbers_respect_context("₹0 saved", "manual emotional spending"))
        self.assertIn("rent", gate.meaningful_keywords("Rent consumes emergency fund money"))
        self.assertTrue(
            gate.visual_logic_relevant_to_context(
                {"type": "flow", "source": "₹50,000 Salary", "process": "₹44,000 Expenses", "result": "₹6,000 Left"},
                "Salary of ₹50,000 leaves only ₹6,000 after ₹44,000 expenses.",
                logic_text="₹50,000 Salary -> ₹44,000 Expenses -> ₹6,000 Left",
                logic_type="flow",
            )
        )
        self.assertFalse(
            gate.visual_logic_relevant_to_context(
                {"type": "comparison", "left": "12% return", "right": "₹50,000 salary"},
                "Salary leaves only ₹50,000 after expenses.",
                logic_text="12% return vs ₹50,000 salary",
                logic_type="comparison",
            )
        )

    def test_render_value_deriver_preserves_money_derivation_helpers(self) -> None:
        deriver = RenderValueDeriver()

        self.assertEqual(deriver.amount_with_label("₹50,000 Salary", "Salary"), "₹50,000 Salary")
        self.assertEqual(deriver.amount_with_label("₹44,000", "Expenses"), "₹44,000 Expenses")
        self.assertEqual(deriver.inflation_output("₹1,00,000", "6%"), "₹94,000")
        self.assertEqual(deriver.inflation_output("no amount", "6%"), "₹94,000")
        self.assertEqual(deriver.derived_rupee("₹50,000", 0.08, "Left"), "₹4,000 Left")
        self.assertEqual(deriver.derived_rupee("no amount", 0.08, "Left"), "₹0 Left")

    def test_render_logic_text_formatter_preserves_visual_logic_text(self) -> None:
        formatter = RenderLogicTextFormatter()

        self.assertEqual(
            formatter.visual_logic_to_text(
                {"type": "flow", "source": "₹50,000 Salary", "process": "₹44,000 Expenses", "result": "₹6,000 Left"},
                logic_type="flow",
            ),
            "₹50,000 Salary -> ₹44,000 Expenses -> ₹6,000 Left",
        )
        self.assertEqual(
            formatter.visual_logic_to_text(
                {"type": "comparison", "left": "₹0 Saved Emotional Spend", "right": "₹5,000 Investment"},
                logic_type="comparison",
            ),
            "₹0 left to spend vs ₹5,000 auto-invested",
        )
        self.assertEqual(
            formatter.visual_logic_to_text({"headline": "76%", "subtext": "cannot save"}, logic_type="emphasis"),
            "76% cannot save",
        )

    def test_render_logic_repair_preserves_candidate_order_and_fallback(self) -> None:
        repair = RenderLogicRepair()
        beat = {
            "props": {
                "headline": "Salary",
                "subtext": "₹50,000",
                "leftContent": "₹50,000 Salary",
                "rightContent": "₹6,000 Left",
                "data": [{"label": "Rent", "value": 20000}],
                "nodes": [{"label": "₹50,000 Salary"}, {"label": "₹6,000 Left"}],
            }
        }

        candidates = repair.repair_candidates("visual", beat)

        self.assertEqual(candidates[0], "visual")
        self.assertIn("₹50,000 Salary vs ₹6,000 Left", candidates)
        self.assertIn("data: Rent=20000", candidates)
        self.assertIn("₹50,000 Salary -> ₹6,000 Left", candidates)
        self.assertEqual(
            repair.repair_visual_logic(
                "visual",
                beat,
                "context",
                numbers_respect_context=lambda _candidate, _context: True,
                is_concrete_visual_logic=lambda candidate: candidate == "₹50,000 Salary vs ₹6,000 Left",
                has_visual_structure=lambda candidate: " vs " in candidate,
                contextual_visual_logic=lambda _context, _beat: "fallback",
                beat_context=lambda _beat: "beat context",
            ),
            "₹50,000 Salary vs ₹6,000 Left",
        )
        self.assertEqual(
            repair.repair_visual_logic(
                "visual",
                {},
                "",
                numbers_respect_context=lambda _candidate, _context: False,
                is_concrete_visual_logic=lambda _candidate: False,
                has_visual_structure=lambda _candidate: False,
                contextual_visual_logic=lambda context, _beat: f"fallback {context}",
                beat_context=lambda _beat: "beat context",
            ),
            "fallback beat context",
        )

    def test_render_logic_validator_preserves_typed_logic_rules(self) -> None:
        number_utils = RenderNumberUtils()
        labels = RenderFlowLabelHelper(number_utils)
        logic_text = RenderLogicTextFormatter(labels)
        visual_gate = RenderVisualGate(
            abstract_visual_words={"visual", "chart", "concept"},
            generic_visual_words={"system"},
            number_utils=number_utils,
        )
        context_gate = RenderContextGate(number_utils)
        validator = RenderLogicValidator(
            {
                "decay": ("input", "factor", "output"),
                "flow": ("source", "process", "result"),
                "comparison": ("left", "right"),
                "growth": ("input", "rate", "output"),
                "emphasis": ("headline",),
            },
            context_gate=context_gate,
            logic_text=logic_text,
            visual_gate=visual_gate,
        )

        salary_flow = {
            "type": "flow",
            "source": "₹50,000 Salary",
            "process": "₹44,000 Expenses",
            "result": "₹6,000 Left",
        }
        bad_salary_flow = {
            "type": "flow",
            "source": "₹50,000 Expenses",
            "process": "₹44,000 Salary",
            "result": "₹6,000 Left",
        }

        self.assertEqual(validator.logic_type(salary_flow), "flow")
        self.assertTrue(validator.typed_visual_logic_is_valid(salary_flow))
        self.assertTrue(validator.logic_can_reach_render(salary_flow, {"intent": "EXPLANATION"}))
        self.assertFalse(validator.flow_semantically_valid(bad_salary_flow))
        self.assertFalse(
            validator.typed_visual_logic_is_valid(
                {"type": "comparison", "left": "12% return", "right": "₹50,000 salary"}
            )
        )
        self.assertTrue(
            validator.logic_can_reach_render(
                {"type": "emphasis", "headline": "76%", "subtext": "cannot save"},
                {"intent": "HOOK"},
            )
        )
        self.assertFalse(
            validator.logic_can_reach_render(
                {"type": "emphasis", "headline": "76%", "subtext": "cannot save"},
                {"intent": "EXPLANATION"},
            )
        )

    def test_render_pattern_selector_preserves_intent_pattern_component_rules(self) -> None:
        selector = RenderPatternSelector(
            intent_pattern_map={
                "HOOK": {"EMPHASIS", "CONTEXT"},
                "COMPARISON": {"COMPARISON"},
                "DATA": {"GROWTH", "COMPARISON"},
                "EXPLANATION": {"MONEY_FLOW", "VALUE_DECAY", "LOOP", "GROWTH"},
                "EMPHASIS": {"EMPHASIS"},
                "CONTEXT": {"CONTEXT"},
            },
            flow_patterns={"MONEY_FLOW", "VALUE_DECAY", "LOOP", "GROWTH"},
            duration_by_intent={"HOOK": 2.5, "DATA": 4.0, "EXPLANATION": 4.5},
            animation_map={"reveal": {"type": "fade_sequence"}, "progress": {"type": "line_draw"}},
        )

        self.assertIn("MONEY_FLOW", selector.all_patterns())
        self.assertEqual(selector.infer_intent("COMPARISON", "₹50,000 vs ₹6,000"), "COMPARISON")
        self.assertEqual(selector.infer_intent("", "₹50,000 left"), "DATA")
        self.assertEqual(selector.pattern_for_intent("EXPLANATION", "inflation erodes ₹1,00,000"), "VALUE_DECAY")
        self.assertEqual(selector.pattern_for_intent("DATA", "₹50,000 vs ₹6,000"), "COMPARISON")
        self.assertEqual(
            selector.derive_component(
                "DATA",
                "GROWTH",
                {"props": {"data": [{"label": "A", "value": 1}, {"label": "B", "value": 2}]}},
                "growth",
                has_chart_data=lambda _beat, _logic: True,
            ),
            "LineChart",
        )
        self.assertEqual(selector.derive_component("EXPLANATION", "MONEY_FLOW", {}, "flow", has_chart_data=lambda *_: False), "FlowDiagram")
        self.assertEqual(selector.emphasis_component("76% cannot save"), "StatExplosion")
        self.assertEqual(selector.normalize_animation_intent("progress"), "progress")
        self.assertEqual(selector.normalize_animation_intent("unknown"), "reveal")
        self.assertEqual(selector.structured_duration("EXPLANATION", {}), 4.5)
        self.assertEqual(selector.structured_duration("DATA", {"duration_locked": True, "estimated_duration_sec": 99}), 6.0)

    def test_render_classified_contract_preserves_intent_contract_rules(self) -> None:
        contract = RenderClassifiedContract()

        def logic_from_intent(_context: str, classified: str) -> dict[str, str]:
            if classified == "EMPHASIS":
                return {"type": "emphasis", "headline": "76%", "subtext": "cannot save"}
            if classified == "COMPARISON":
                return {"type": "comparison", "left": "₹50,000", "right": "₹6,000"}
            if classified == "DECAY":
                return {"type": "flow", "source": "₹50,000", "process": "₹44,000", "result": "₹6,000"}
            return {"type": "flow", "source": "₹50,000", "process": "₹44,000", "result": "₹6,000"}

        self.assertEqual(contract.classify_intent("only ₹6,000 left", has_money_tokens=lambda _text: True), "EMPHASIS")
        self.assertEqual(contract.classify_intent("₹50,000 vs ₹6,000", has_money_tokens=lambda _text: True), "COMPARISON")
        self.assertEqual(contract.classify_intent("salary leak", has_money_tokens=lambda _text: True), "DECAY")
        self.assertEqual(contract.classify_intent("salary expense", has_money_tokens=lambda _text: True), "FLOW")
        self.assertEqual(
            contract.classified_intent_for_beat(
                {"pattern": "VALUE_DECAY"},
                "",
                {},
                classify_intent=lambda _context: "FLOW",
                logic_type=lambda _logic: "",
            ),
            "DECAY",
        )
        self.assertEqual(
            contract.enforce_render_contract(
                "COMPARISON",
                "EXPLANATION",
                "MONEY_FLOW",
                "FlowDiagram",
                {"type": "flow"},
                "context",
                logic_type=lambda logic: str(logic.get("type") or ""),
                logic_from_intent=logic_from_intent,
            )[:3],
            ("COMPARISON", "COMPARISON", "SplitComparison"),
        )
        self.assertEqual(
            contract.fallback_for_classified_intent("DECAY", "context", logic_from_intent=logic_from_intent)[:3],
            ("EXPLANATION", "VALUE_DECAY", "FlowDiagram"),
        )

    def test_render_narration_logic_builder_preserves_logic_factories(self) -> None:
        number_utils = RenderNumberUtils()
        builder = RenderNarrationLogicBuilder(
            number_utils=number_utils,
            text_utils=RenderTextUtils(),
            value_deriver=RenderValueDeriver(number_utils),
        )

        self.assertEqual(
            builder.emphasis_logic_from_narration("only ₹6,000 left"),
            {"type": "emphasis", "headline": "₹6,000", "subtext": "only ₹6,000 left"},
        )
        self.assertEqual(
            builder.comparison_logic_from_narration("12% people and ₹5,000 savings"),
            {"type": "comparison", "left": "12% of people", "right": "₹5,000 savings"},
        )
        self.assertEqual(
            builder.flow_logic_from_narration("salary ₹50,000 expenses ₹44,000 left ₹6,000"),
            {"type": "flow", "source": "₹50,000 Salary", "process": "₹44,000 Expenses", "result": "₹6,000 Left"},
        )
        self.assertEqual(
            builder.decay_flow_from_narration("salary ₹50,000 leak ₹10,000 loss"),
            {"type": "flow", "source": "₹50,000 Salary", "process": "₹10,000 Leak", "result": "₹40,000 Left"},
        )
        self.assertEqual(
            builder.contextual_visual_logic_object_without_classification("₹50,000 and ₹6,000"),
            {"type": "comparison", "left": "₹50,000", "right": "₹6,000"},
        )
        self.assertEqual(
            builder.coerce_logic_to_pattern({}, "₹1,00,000 at 6%", "VALUE_DECAY"),
            {"type": "decay", "input": "₹1,00,000", "factor": "6% Inflation", "output": "₹94,000 Real Value"},
        )
        self.assertEqual(
            builder.transformation_logic_to_flow({"type": "growth", "input": "₹5,000", "rate": "12%", "output": "₹60,000"}),
            {"type": "flow", "source": "₹5,000", "process": "12%", "result": "₹60,000"},
        )
        self.assertEqual(
            builder.fallback_numeric_flow(),
            {"type": "flow", "source": "₹25,000 Salary", "process": "₹23,000 Expenses", "result": "₹2,000 Left"},
        )

    def test_groq_client_builds_existing_chat_request_shape(self) -> None:
        post = Mock()
        client = GroqChatClient("secret", post_func=post)

        client.chat_json(
            model="llama",
            messages=[{"role": "user", "content": "Return JSON"}],
            temperature=0.4,
            max_tokens=100,
            timeout=20,
        )

        sent_body = post.call_args.kwargs["json"]
        self.assertEqual(post.call_args.args[0], "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(sent_body["response_format"], {"type": "json_object"})
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer secret")

    def test_ffmpeg_executor_exposes_media_helpers(self) -> None:
        from pathlib import Path

        executor = FfmpegExecutor()

        self.assertIsNone(executor.find_binary("definitely-not-ytcreate-ffmpeg"))
        with patch("youtube_ai_system.infrastructure.ffmpeg.executor.subprocess.run") as run:
            executor.encode_frame_sequence("ffmpeg", Path("/tmp/frames"), 30, Path("/tmp/out.mp4"))
        command = run.call_args.args[0]
        self.assertIn("/tmp/frames/frame-%04d.png", command)
        self.assertIn("/tmp/out.mp4", command)

    def test_voice_audio_tools_write_current_silent_wav_shape(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        tools = VoiceAudioTools()
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "scene.wav"
            duration = tools.estimate_duration("short narration")
            tools.write_silent_wav(path, duration)

            self.assertTrue(path.exists())
            self.assertEqual(duration, 2.5)

    def test_youtube_uploader_uses_existing_private_upload_body(self) -> None:
        uploader = YouTubeVideoUploader()
        youtube = Mock()
        youtube.videos.return_value.insert.return_value.next_chunk.return_value = (None, {"id": "abc123"})

        with patch("googleapiclient.http.MediaFileUpload", return_value="media"):
            video_id = uploader.upload_private_video(
                youtube,
                "/tmp/final.mp4",
                {"selected_title": "A" * 120, "description": "Desc", "tags": ["finance"]},
            )

        body = youtube.videos.return_value.insert.call_args.kwargs["body"]
        self.assertEqual(video_id, "abc123")
        self.assertEqual(body["status"]["privacyStatus"], "private")
        self.assertEqual(len(body["snippet"]["title"]), 100)

    def test_upload_package_builder_preserves_title_description_and_chapters(self) -> None:
        builder = UploadPackageBuilder()
        project = {
            "working_title": "Salary Leaks",
            "topic": "salary leaks",
            "channel_niche": "personal finance India",
        }
        script_payload = {
            "titles": ["Where Does Your Salary Go?", "Salary Leaks"],
            "description": "Base description",
            "tags": ["#salary", "money"],
        }
        scenes = [
            {"scene_order": 0, "narration_text": "Why does salary disappear by day twenty?", "audio_duration_sec": 6},
            {"scene_order": 1, "narration_text": "Rent and food delivery hit first.", "audio_duration_sec": 12},
        ]

        titles = builder.title_options(project, script_payload)
        description = builder.description(project, scenes, script_payload)
        tags = builder.tags(project, script_payload)
        chapters = builder.chapters(scenes)

        self.assertEqual(titles[0], "Where Does Your Salary Go?")
        self.assertIn("Chapters:", description)
        self.assertIn("0:06 Rent and food delivery hit first", description)
        self.assertEqual(tags[:2], ["salary", "money"])
        self.assertEqual(chapters[1]["timestamp"], "0:06")

    def test_publishing_readiness_policy_preserves_checklist_shape(self) -> None:
        from tempfile import TemporaryDirectory
        from pathlib import Path

        class Acceptance:
            passed = True
            blocking_issues = []

            def to_dict(self):
                return {"blocking_issues": []}

        with TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "final.mp4"
            thumb = Path(temp_dir) / "thumb.jpg"
            video.write_bytes(b"video")
            thumb.write_bytes(b"thumb")
            report = PublishingReadinessPolicy().evaluate(
                {
                    "final_video_path": str(video),
                    "selected_thumbnail_path": str(thumb),
                    "selected_title": "Title",
                    "selected_description": "Description",
                },
                Acceptance(),
            )

        self.assertTrue(report["passed"])
        self.assertEqual([check["key"] for check in report["checks"]], ["full_video", "thumbnail", "metadata", "scene_acceptance"])
        self.assertEqual(report["warning_count"], 0)


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

    def test_create_project_wrapper_preserves_run_log(self) -> None:
        repo = Mock()
        repo.create_project.return_value = 31
        logger = Mock()

        result = CreateProjectUseCase(repo, logger).execute("  ")

        self.assertTrue(result.success)
        repo.create_project.assert_called_once_with("Untitled Video Project")
        logger.log.assert_called_once_with("project_creation", "completed", "Created project.", 31)
        self.assertEqual(result.data["project_id"], 31)

    def test_save_topic_wrapper_preserves_two_step_state_progression(self) -> None:
        repo = Mock()
        repo.get_project.side_effect = [
            {"id": 4, "state": "idea"},
            {"id": 4, "state": "topic_selected"},
            {"id": 4, "state": "drafted"},
        ]
        topic_service = Mock()
        topic_service.lookup_comparable_videos.return_value = [{"title": "A"}]
        topic_service.last_lookup_mode = "mock"
        topic_service.last_lookup_message = "ok"
        state_machine = Mock()

        result = SaveTopicUseCase(repo, topic_service, state_machine).execute(
            4,
            topic="Saving",
            angle="Mistakes",
            target_duration_minutes=9,
            channel_niche="finance",
            script_tone="direct",
        )

        self.assertTrue(result.success)
        repo.update_project.assert_called_once_with(
            4,
            topic="Saving",
            angle="Mistakes",
            target_duration_minutes=9,
            channel_niche="finance",
            script_tone="direct",
        )
        self.assertEqual(
            [call.args for call in state_machine.transition.call_args_list],
            [
                (4, "topic_selected", "Manual topic confirmed."),
                (4, "drafted", "Ready for script generation."),
            ],
        )
        self.assertEqual(result.data["project"]["state"], "drafted")

    def test_save_script_edits_wrapper_preserves_payload_mapping(self) -> None:
        repo = Mock()
        repo.get_latest_script_version.return_value = {
            "id": 55,
            "full_script_json": '{"meta": {"a": 1}, "scenes": [{"scene_index": 3, "visual_type": "old"}]}',
        }
        script_service = Mock()
        form = {
            "hook_narration": "Hook",
            "hook_duration": "6",
            "outro_narration": "Outro",
            "titles": "One\nTwo",
            "description": "Desc",
            "tags": "a, b",
            "scene_count": "1",
            "scene_0_narration": "Body",
        }

        result = SaveScriptEditsUseCase(repo, script_service).execute(2, form)

        self.assertTrue(result.success)
        script_service.save_script_edits.assert_called_once()
        saved_payload = script_service.save_script_edits.call_args.args[1]
        self.assertEqual(saved_payload["hook"]["narration"], "Hook")
        self.assertEqual(saved_payload["scenes"][0]["kind"], "body")
        self.assertEqual(saved_payload["scenes"][0]["narration"], "Body")
        self.assertEqual(saved_payload["meta"], {"a": 1})

    def test_discard_wrapper_preserves_state_transition(self) -> None:
        state_machine = Mock()

        result = DiscardProjectUseCase(state_machine).execute(16)

        self.assertTrue(result.success)
        state_machine.transition.assert_called_once_with(16, "discarded", "User discarded project.")

    def test_publish_wrappers_preserve_state_guards_and_service_calls(self) -> None:
        repo = Mock()
        repo.get_project.return_value = {"id": 17, "state": "ready_to_publish"}
        publish_service = Mock()
        publish_service.stage_publish.return_value = 99

        stage_result = StagePublishUseCase(repo, publish_service).execute(17)
        mock_result = MockUploadUseCase(repo, publish_service).execute(17, "")

        self.assertTrue(stage_result.success)
        self.assertEqual(stage_result.data["publish_record_id"], 99)
        publish_service.stage_publish.assert_called_once_with(17)
        publish_service.mark_uploaded.assert_called_once_with(17, "demo-17")
        self.assertTrue(mock_result.success)

    def test_schedule_wrapper_preserves_publish_then_transition(self) -> None:
        repo = Mock()
        repo.get_project.side_effect = [
            {"id": 18, "state": "ready_to_publish"},
            {"id": 18, "state": "ready_to_publish"},
        ]
        publish_service = Mock()
        state_machine = Mock()

        result = SchedulePublishUseCase(repo, publish_service, state_machine).execute(18, " 2026-04-20 ")

        self.assertTrue(result.success)
        publish_service.schedule_publish.assert_called_once_with(18, "2026-04-20")
        state_machine.transition.assert_called_once_with(18, "scheduled", "Scheduled publish set.")

    def test_normal_routes_depend_on_use_cases_not_service_internals(self) -> None:
        routes_dir = Path(__file__).resolve().parents[1] / "routes"
        checked_routes = ["projects.py", "media.py", "publish.py", "analytics.py"]

        for route_name in checked_routes:
            source = (routes_dir / route_name).read_text()
            self.assertNotIn("from ..services", source, route_name)
            self.assertNotIn("from ..models", source, route_name)
            self.assertNotIn("from ..infrastructure", source, route_name)

    def test_services_and_routes_do_not_own_raw_http_provider_clients(self) -> None:
        package_root = Path(__file__).resolve().parents[1]
        checked_roots = [
            package_root / "services",
            package_root / "routes",
            package_root / "application",
        ]
        forbidden_imports = (
            "import requests",
            "from googleapiclient.discovery import build",
        )

        for root in checked_roots:
            for path in root.rglob("*.py"):
                source = path.read_text()
                for forbidden in forbidden_imports:
                    self.assertNotIn(forbidden, source, str(path.relative_to(package_root)))

    def test_ffmpeg_subprocess_details_stay_out_of_assembly_and_scene_qa_services(self) -> None:
        package_root = Path(__file__).resolve().parents[1]
        checked_files = [
            package_root / "services" / "assembly_service.py",
            package_root / "services" / "professional_scene_acceptance.py",
        ]
        forbidden_snippets = (
            "import subprocess",
            ".run_raw(",
            ".run_silent(",
        )

        for path in checked_files:
            source = path.read_text()
            for forbidden in forbidden_snippets:
                self.assertNotIn(forbidden, source, str(path.relative_to(package_root)))

    def test_application_service_and_route_layers_do_not_import_subprocess(self) -> None:
        package_root = Path(__file__).resolve().parents[1]
        checked_roots = [
            package_root / "services",
            package_root / "routes",
            package_root / "application",
        ]

        for root in checked_roots:
            for path in root.rglob("*.py"):
                source = path.read_text()
                self.assertNotIn("import subprocess", source, str(path.relative_to(package_root)))
                self.assertNotIn("subprocess.", source, str(path.relative_to(package_root)))

    def test_service_files_remain_below_refactor_size_ceiling(self) -> None:
        services_dir = Path(__file__).resolve().parents[1] / "services"
        max_lines = 700

        for path in services_dir.glob("*.py"):
            line_count = len(path.read_text().splitlines())
            self.assertLessEqual(line_count, max_lines, f"{path.name} has grown to {line_count} lines")

    def test_normal_route_files_remain_thin_http_adapters(self) -> None:
        routes_dir = Path(__file__).resolve().parents[1] / "routes"
        max_lines_by_file = {
            "projects.py": 180,
            "media.py": 140,
            "publish.py": 150,
            "analytics.py": 80,
        }

        for route_name, max_lines in max_lines_by_file.items():
            line_count = len((routes_dir / route_name).read_text().splitlines())
            self.assertLessEqual(line_count, max_lines, f"{route_name} has grown to {line_count} lines")


if __name__ == "__main__":
    unittest.main()
