import json
import tempfile
import unittest
from pathlib import Path

from youtube_ai_system import create_app
from youtube_ai_system.db import close_db
from youtube_ai_system.models.repository import ProjectRepository
from youtube_ai_system.services.scene_builder import build_scenes
from youtube_ai_system.services.scene_debug import SceneDebugStore, SceneDebugTrace, frame_probe, stable_hash


class SceneDebugTraceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": root / "instance" / "database.db",
                "INSTANCE_PATH": root / "instance",
                "STORAGE_ROOT": root / "storage",
                "DEBUG_VIDEO_PIPELINE": True,
                "VOICE_MODE": "demo",
                "REMOTION_ENABLED": False,
            }
        )
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self) -> None:
        close_db()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def test_trace_records_ownership_snapshots_lineage_and_sidecar_json(self) -> None:
        trace = SceneDebugTrace(scene_id="scene_1", project_id=7, scene_order=1, narration="Salary lands. EMI drains it.")
        trace.snapshot("groq_post_parse", {"mechanism": "salary_drain"}, owner="groq")
        trace.ownership("mechanism", "groq", "salary_drain", "Groq generated mechanism")
        trace.ownership("mechanism", "visual_scene_normalizer", "lifestyle_inflation", "keyword inference override")
        trace.lineage_node("sentence:1:0", "narration_sentence", "scene_db", "Sentence 1", "Salary lands", owner="scene_db")
        trace.lineage_node("mechanism:0:lifestyle_inflation", "mechanism", "normalizer", "lifestyle_inflation", {}, owner="visual_scene_normalizer")
        trace.lineage_edge("sentence:1:0", "mechanism:0:lifestyle_inflation", "sentence_contains_keyword")
        trace.confidence("normalizer", "mechanism", "lifestyle_inflation", 0.42, ["keyword-only inference"])

        path = SceneDebugStore().save(trace)
        loaded = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(loaded["snapshots"][0]["stage"], "groq_post_parse")
        self.assertEqual(loaded["ownership_graph"][-1]["previous_owner"], "groq")
        self.assertEqual(loaded["ownership_graph"][-1]["new_owner"], "visual_scene_normalizer")
        self.assertEqual(loaded["lineage_graph"]["edges"][0]["reason"], "sentence_contains_keyword")
        self.assertEqual(loaded["confidence"][0]["score"], 0.42)

    def test_scene_builder_trace_records_timeline_validation_and_frame_probe(self) -> None:
        trace = SceneDebugTrace(scene_id="scene_1", project_id=9, scene_order=1, narration="Debt grows because interest keeps adding pressure.")
        section = {
            "text": "Debt grows because interest keeps adding pressure.",
            "kind": "body",
            "audio_file": str((Path(self.temp_dir.name) / "dummy.wav").resolve()),
            "audio_duration": 6.0,
            "concept_type": "debt_trap",
            "visual_plan": [
                {
                    "concept": {"concept": "Debt Trap", "type": "debt_trap"},
                    "visual": {"pattern": "DebtSpiralVisualizer", "data": {"principal": "₹1,00,000"}},
                    "beats": {"beats": [{"component": "UnknownComponent", "text": "Debt grows"}]},
                }
            ],
        }

        scene = build_scenes([section], debug_trace=trace)["scenes"][0]
        probe = frame_probe(scene, 0)

        self.assertTrue(any(item["stage"] == "scene_builder_timeline" for item in trace.data["snapshots"]))
        self.assertTrue(any(item["fallback_source"] == "expand_minimum_beats" for item in trace.data["fallbacks"]))
        self.assertTrue(any(item.get("payload", {}).get("code") == "unsupported_component" for item in trace.data["validation"]["warnings"]))
        self.assertEqual(probe["fallback_component"], "ConceptCard")

    def test_debug_inspector_is_gated_by_flag(self) -> None:
        disabled_root = Path(self.temp_dir.name) / "disabled"
        disabled_app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": disabled_root / "instance" / "database.db",
                "INSTANCE_PATH": disabled_root / "instance",
                "STORAGE_ROOT": disabled_root / "storage",
                "DEBUG_VIDEO_PIPELINE": False,
            }
        )
        with disabled_app.test_client() as client:
            self.assertEqual(client.get("/debug/video-pipeline/projects/1").status_code, 404)

    def test_debug_inspector_loads_when_enabled(self) -> None:
        repo = ProjectRepository()
        project_id = repo.create_project("Debug Project")
        trace = SceneDebugTrace(scene_id="scene_1", project_id=project_id, scene_order=1, narration="Salary lands.")
        SceneDebugStore().save(trace)

        response = self.app.test_client().get(f"/debug/video-pipeline/projects/{project_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Visual Pipeline Inspector", response.data)

    def test_debug_json_route_loads_latest_replay_trace(self) -> None:
        repo = ProjectRepository()
        project_id = repo.create_project("Replay Debug Project")
        trace = SceneDebugTrace(scene_id="scene_1", project_id=project_id, scene_order=1, narration="Salary lands.")
        trace.snapshot("replay_input_scene", {"ok": True}, owner="debug_replay")
        SceneDebugStore().save(trace, replay_stage="all")

        response = self.app.test_client().get(f"/debug/video-pipeline/projects/{project_id}/scene/1.json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["snapshots"][0]["stage"], "replay_input_scene")

    def test_stable_hash_is_deterministic(self) -> None:
        left = stable_hash({"b": 2, "a": [1, 2]})
        right = stable_hash({"a": [1, 2], "b": 2})
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
