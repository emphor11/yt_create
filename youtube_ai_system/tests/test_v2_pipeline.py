import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from youtube_ai_system import create_app
from youtube_ai_system.db import close_db
from youtube_ai_system.db import get_db
from youtube_ai_system.services.script_service import ScriptService
from youtube_ai_system.models.repository import ProjectRepository
from youtube_ai_system.services.assembly_service import AssemblyService
from youtube_ai_system.services.media_service import MediaService
from youtube_ai_system.services.remotion_service import RemotionService
from youtube_ai_system.services.render_spec_service import RenderSpecService
from youtube_ai_system.services.thumbnail_service import ThumbnailService
from youtube_ai_system.services.voice_service import VoiceService


class V2PipelineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": root / "instance" / "database.db",
                "INSTANCE_PATH": root / "instance",
                "STORAGE_ROOT": root / "storage",
                "REMOTION_ENABLED": False,
                "VOICE_MODE": "demo",
            }
        )
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self) -> None:
        close_db()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def test_render_spec_maps_motion_text_to_stat_reveal(self) -> None:
        service = RenderSpecService()
        spec = service.scene_spec(
            {
                "visual_type": "motion_text",
                "visual_instruction": "Show 80% of young Indians are broke",
                "narration_text": "80 percent are broke",
            },
            6,
        )
        self.assertEqual(spec.composition, "StatReveal")
        self.assertEqual(spec.props["headline"], "80%")
        self.assertEqual(spec.props["sentiment"], "negative")

    def test_render_spec_maps_graph_to_line_or_bar(self) -> None:
        service = RenderSpecService()
        line = service.scene_spec(
            {"visual_type": "graph", "visual_instruction": "Line chart showing savings growth from 2020 20 to 2024 60"},
            8,
        )
        bar = service.scene_spec(
            {"visual_type": "graph", "visual_instruction": "Bar chart showing 2019 10 2020 20 2021 30"},
            8,
        )
        self.assertEqual(line.composition, "LineChart")
        self.assertEqual(bar.composition, "BarChart")
        self.assertGreaterEqual(len(bar.props["data"]), 2)

    def test_render_spec_broll_includes_overlay_and_asset(self) -> None:
        asset = Path("/tmp/source.mp4")
        spec = RenderSpecService().scene_spec(
            {"visual_type": "broll", "visual_instruction": "Person checking credit card debt stress"},
            7,
            source_asset_path=asset,
        )
        self.assertEqual(spec.composition, "BrollOverlay")
        self.assertEqual(spec.props["videoPath"], str(asset))
        self.assertIn("Person", spec.props["overlayText"])

    def test_render_spec_broll_requires_stock_asset(self) -> None:
        with self.assertRaises(ValueError):
            RenderSpecService().scene_spec(
                {"visual_type": "broll", "visual_instruction": "Person checking credit card debt stress"},
                7,
            )

    def test_scene_table_has_visual_plan_json_column(self) -> None:
        columns = {
            row["name"]
            for row in get_db().execute("PRAGMA table_info(scenes)").fetchall()
        }
        self.assertIn("visual_plan_json", columns)

    def test_ten_minute_prompt_contains_style_and_beat_rules(self) -> None:
        self.app.config["CHANNEL_STYLE"] = "ten_minute_finance"
        prompt = ScriptService()._build_prompt("FD returns", "inflation math", 10, None, None)
        self.assertIn("10 Minute Finance", prompt)
        self.assertIn("VISUAL BEATS", prompt)
        self.assertIn("Priority: COMPARISON > EXPLANATION > DATA > EMPHASIS", prompt)
        self.assertIn("PATTERN COMPATIBILITY MATRIX", prompt)
        self.assertIn("reaction_card", prompt)
        self.assertIn("Indian middle-class reality", prompt)

    def test_normalize_payload_preserves_and_creates_visual_beats(self) -> None:
        service = ScriptService()
        payload = service._normalize_payload(
            {
                "hook": {
                    "narration": "80% of Indians are broke by payday",
                    "visual_type": "motion_text",
                    "visual_instruction": "80% broke",
                    "visual_beats": [{"beat_type": "reaction_card", "content": "bruh", "estimated_duration_sec": 3}],
                },
                "scenes": [
                    {
                        "narration": "FD pays 6.5 but inflation is 6.7.",
                        "visual_type": "graph",
                        "visual_instruction": "bar_chart, data: FD=6.5, Inflation=6.7, title: FD vs Inflation, color: red",
                    }
                ],
                "outro": {"narration": "Fix the math before the bank sells you vibes."},
                "titles": ["FD math"],
                "description": "desc",
                "tags": ["fd"],
            },
            "FD returns",
            "inflation math",
        )
        self.assertEqual(payload["hook"]["visual_beats"][0]["component"], "StatExplosion")
        self.assertGreaterEqual(len(payload["hook"]["visual_beats"]), 2)
        self.assertIn(payload["scenes"][0]["visual_beats"][0]["component"], {"SplitComparison", "FlowDiagram", "BarChart"})

    def test_scene_rows_store_visual_plan_json(self) -> None:
        payload = ScriptService()._demo_script("Saving money", "bad defaults")
        rows = ScriptService().scene_rows_from_payload(payload)
        self.assertIn("visual_plan_json", rows[0])
        self.assertIn("comparison", rows[0]["visual_plan_json"])

    def test_beat_spec_maps_new_beat_types(self) -> None:
        service = RenderSpecService()
        self.assertEqual(
            service.beat_spec({"beat_type": "stat_explosion", "content": "₹1 lakh", "caption": "gone", "color": "red"}).composition,
            "StatExplosion",
        )
        self.assertEqual(
            service.beat_spec({"beat_type": "reaction_card", "content": "bruh", "color": "teal"}).composition,
            "ReactionCard",
        )
        self.assertEqual(
            service.beat_spec({"beat_type": "split_comparison", "content": "6.5% FD vs -0.2% real return"}).composition,
            "SplitComparison",
        )

    def test_structured_intent_pattern_conflict_auto_corrects(self) -> None:
        normalized = RenderSpecService().normalize_structured_beat(
            {
                "intent": "DATA",
                "pattern": "VALUE_DECAY",
                "visual_logic": "FD gives 6.5% vs inflation is 6.7%",
                "props": {"caption": "FD loses after inflation"},
            }
        )
        self.assertEqual(normalized["intent"], "COMPARISON")
        self.assertEqual(normalized["pattern"], "COMPARISON")
        self.assertIsInstance(normalized["visual_logic"], dict)
        self.assertNotEqual(normalized["pattern"], "VALUE_DECAY")

    def test_structured_component_is_derived_from_pattern(self) -> None:
        spec = RenderSpecService().beat_spec(
            {
                "intent": "EXPLANATION",
                "pattern": "VALUE_DECAY",
                "component": "TextBurst",
                "visual_logic": {
                    "type": "decay",
                    "input": "₹1,00,000",
                    "factor": "6% Inflation",
                    "output": "₹94,000 Real Value",
                },
                "props": {
                    "nodes": [
                        {"id": "money", "label": "₹1,00,000", "role": "source"},
                        {"id": "inflation", "label": "6% Inflation", "role": "modifier"},
                        {"id": "real", "label": "₹94,000 Real Value", "role": "result"},
                    ],
                    "caption": "Numbers rise. Value falls.",
                },
                "animation_intent": "transform",
            }
        )
        self.assertEqual(spec.composition, "FlowDiagram")
        self.assertEqual(spec.props["mode"], "decay")
        self.assertEqual(spec.props["animationSpec"]["type"], "scale_change")

    def test_emphasis_component_selection_is_deterministic(self) -> None:
        service = RenderSpecService()
        self.assertEqual(
            service.beat_spec({"intent": "EMPHASIS", "pattern": "EMPHASIS", "visual_logic": "₹1 lakh gone"}).composition,
            "StatExplosion",
        )
        self.assertEqual(
            service.beat_spec({"intent": "EMPHASIS", "pattern": "EMPHASIS", "visual_logic": "wait what"}).composition,
            "StatExplosion",
        )
        self.assertEqual(
            service.beat_spec({"intent": "EMPHASIS", "pattern": "EMPHASIS", "visual_logic": "your bank sold you comfortable vibes"}).composition,
            "StatExplosion",
        )

    def test_caption_repair_and_grouped_flow_nodes(self) -> None:
        normalized = RenderSpecService().normalize_structured_beat(
            {
                "intent": "EXPLANATION",
                "pattern": "MONEY_FLOW",
                "visual_logic": {
                    "type": "flow",
                    "source": "₹25,000 Salary",
                    "process": "₹23,000 Expenses",
                    "result": "₹2,000 Left",
                },
                "props": {
                    "caption": "salary moves through expenses before savings and investing every single month",
                    "nodes": [
                        {"id": "salary", "label": "₹25,000 Salary", "role": "source"},
                        {"id": "expenses", "label": "₹23,000 Expenses", "role": "process", "children": ["Rent", "Food", "Bills"]},
                        {"id": "savings", "label": "₹2,000 Left", "role": "result"},
                    ],
                },
            }
        )
        self.assertLessEqual(len(normalized["caption"].split()), 10)
        self.assertEqual(normalized["component"], "FlowDiagram")
        self.assertEqual(normalized["props"]["nodes"][1]["children"], ["Rent", "Food", "Bills"])

    def test_rhythm_pass_prevents_three_same_structured_intents(self) -> None:
        beats = [
            {"intent": "EXPLANATION", "pattern": "MONEY_FLOW", "visual_logic": "money moves from salary to expenses"},
            {"intent": "EXPLANATION", "pattern": "VALUE_DECAY", "visual_logic": "inflation reduces value"},
            {"intent": "EXPLANATION", "pattern": "LOOP", "visual_logic": "debt cycle repeats"},
        ]
        normalized = ScriptService()._normalize_visual_beats(beats, "motion_text", "money lesson", 15)
        self.assertNotEqual([beat.get("intent") for beat in normalized], ["EXPLANATION", "EXPLANATION", "EXPLANATION"])

    def test_context_structured_beat_requires_broll_asset(self) -> None:
        beat = {"intent": "CONTEXT", "pattern": "CONTEXT", "visual_logic": "person checking bills", "props": {"caption": "salary gone"}}
        self.assertTrue(RenderSpecService().beat_requires_source_asset(beat))
        self.assertIn("person", RenderSpecService().broll_query_for_beat(beat))

    def test_abstract_visual_logic_is_repaired_to_concrete_emphasis(self) -> None:
        normalized = RenderSpecService().normalize_structured_beat(
            {
                "intent": "DATA",
                "pattern": "GROWTH",
                "visual_logic": "static_image",
                "props": {"title": "statistic"},
            }
        )
        self.assertEqual(normalized["intent"], "EMPHASIS")
        self.assertEqual(normalized["pattern"], "EMPHASIS")
        self.assertEqual(normalized["component"], "StatExplosion")
        self.assertNotEqual(normalized["visual_logic"], "static_image")

    def test_split_comparison_repairs_abstract_props(self) -> None:
        spec = RenderSpecService().beat_spec(
            {
                "intent": "COMPARISON",
                "pattern": "COMPARISON",
                "visual_logic": "6.5% FD vs 6.7% inflation",
                "props": {"leftContent": "juxtaposition", "rightContent": "contrast"},
            }
        )
        self.assertEqual(spec.composition, "SplitComparison")
        self.assertIn("6.5%", spec.props["leftContent"])
        self.assertIn("6.7%", spec.props["rightContent"])

    def test_chart_extraction_does_not_invent_fake_data(self) -> None:
        service = RenderSpecService()
        self.assertEqual(service._extract_data_points("title: statistic"), [])
        spec = service.beat_spec(
            {
                "intent": "DATA",
                "pattern": "GROWTH",
                "visual_logic": "title: statistic",
                "props": {"title": "statistic"},
            }
        )
        self.assertNotIn(spec.composition, {"BarChart", "LineChart"})

    def test_typed_flow_requires_complete_schema(self) -> None:
        normalized = RenderSpecService().normalize_structured_beat(
            {
                "intent": "EXPLANATION",
                "pattern": "MONEY_FLOW",
                "visual_logic": {"type": "flow", "source": "₹25,000", "result": "₹2,000"},
                "narration": "salary disappears after expenses",
            }
        )
        self.assertEqual(normalized["component"], "FlowDiagram")
        self.assertEqual(normalized["props"]["nodes"][0]["label"], "₹25,000 Salary")
        self.assertNotEqual(normalized["visual_logic"], {"type": "flow", "source": "₹25,000", "result": "₹2,000"})

    def test_complete_typed_flow_passes_visual_gate(self) -> None:
        spec = RenderSpecService().beat_spec(
            {
                "intent": "EXPLANATION",
                "pattern": "MONEY_FLOW",
                "visual_logic": {
                    "type": "flow",
                    "source": "₹25,000 Salary",
                    "process": "₹23,000 Expenses",
                    "result": "₹2,000 Left",
                },
            }
        )
        self.assertEqual(spec.composition, "FlowDiagram")
        self.assertEqual([node["role"] for node in spec.props["nodes"]], ["source", "process", "result"])

    def test_number_without_structure_is_not_allowed_through(self) -> None:
        service = RenderSpecService()
        self.assertFalse(service._passes_text_gate("6% inflation exists"))
        normalized = service.normalize_structured_beat(
            {"intent": "DATA", "pattern": "GROWTH", "visual_logic": "6% inflation exists"}
        )
        self.assertNotEqual(normalized["visual_logic"], "6% inflation exists")
        self.assertEqual(normalized["component"], "StatExplosion")

    def test_string_visual_logic_is_converted_to_object(self) -> None:
        normalized = RenderSpecService().normalize_structured_beat(
            {
                "intent": "COMPARISON",
                "pattern": "COMPARISON",
                "visual_logic": "₹60,000 wasted vs ₹3,000 interest earned",
            }
        )
        self.assertIsInstance(normalized["visual_logic"], dict)
        self.assertEqual(normalized["visual_logic"]["type"], "comparison")
        self.assertEqual(normalized["component"], "SplitComparison")

    def test_weak_comparison_is_replaced_before_render(self) -> None:
        spec = RenderSpecService().beat_spec(
            {
                "intent": "COMPARISON",
                "pattern": "COMPARISON",
                "visual_logic": "₹10,00,000 vs loss",
                "narration": "A ₹10,00,000 portfolio can lose ₹1,00,000 in a bad year.",
            }
        )
        self.assertNotEqual(spec.props.get("rightContent"), "loss")
        rendered_text = " ".join(str(value) for value in spec.props.values())
        self.assertIn("₹10,00,000", rendered_text)

    def test_regeneration_prefers_narration_numbers_over_fake_llm_numbers(self) -> None:
        normalized = RenderSpecService().normalize_structured_beat(
            {
                "intent": "EXPLANATION",
                "pattern": "VALUE_DECAY",
                "visual_logic": "₹26,000 -> 5% -> ₹94,000",
                "narration": "Inflation turns ₹26,000 into 5% less buying power.",
            }
        )
        self.assertIn("₹26,000", normalized["visual_logic_text"])
        self.assertNotIn("₹94,000", normalized["visual_logic_text"])

    def test_bad_props_are_regenerated_not_patched(self) -> None:
        spec = RenderSpecService().beat_spec(
            {
                "intent": "EXPLANATION",
                "pattern": "MONEY_FLOW",
                "visual_logic": {
                    "type": "flow",
                    "source": "₹25,000 Salary",
                    "process": "₹23,000 Expenses",
                    "result": "₹2,000 Left",
                },
                "props": {"nodes": [{"label": "Living"}, {"label": "paycheck"}]},
            }
        )
        labels = [node["label"] for node in spec.props["nodes"]]
        self.assertIn("₹25,000 Salary", labels)
        self.assertNotIn("Living", labels)

    def test_hook_enforcement_creates_numeric_punch_then_meaning_beat(self) -> None:
        beats = ScriptService()._normalize_visual_beats(
            [{"intent": "EXPLANATION", "pattern": "MONEY_FLOW", "visual_logic": "money moves"}],
            "motion_text",
            "76% Indians cannot save ₹5,000",
            6,
            enforce_hook=True,
        )
        self.assertEqual(len(beats), 2)
        self.assertNotEqual(beats[0].get("component"), "FlowDiagram")
        props = beats[0].get("props") or {}
        text = f"{props.get('headline', '')} {props.get('subtext', '')}"
        self.assertTrue(RenderSpecService()._has_number(text))
        self.assertTrue(RenderSpecService()._has_impact(text))
        self.assertEqual(beats[1].get("beat_type"), "text_burst")
        self.assertFalse(RenderSpecService()._has_number(str(beats[1].get("content") or "")))
        self.assertNotIn(" vs ", props["subtext"])
        self.assertIn("can't even save ₹5,000", props["subtext"])

    def test_exact_visual_repetition_is_blocked(self) -> None:
        service = ScriptService()
        with self.app.app_context():
            beats = service._normalize_visual_beats(
                [
                    {"intent": "EMPHASIS", "pattern": "EMPHASIS", "visual_logic": "76% cannot save ₹5,000"},
                    {"intent": "EMPHASIS", "pattern": "EMPHASIS", "visual_logic": "76% cannot save ₹5,000"},
                ],
                "motion_text",
                "76% Indians cannot save ₹5,000",
                6,
                context_text="76% Indians cannot save ₹5,000",
            )
        signatures = [
            RenderSpecService()._visual_logic_to_text(beat.get("visual_logic"))
            for beat in beats
            if beat.get("visual_logic")
        ]
        self.assertEqual(len(signatures), len(set(signatures)))

    def test_hook_flow_is_forced_to_stat_explosion(self) -> None:
        beats = ScriptService()._normalize_visual_beats(
            [
                {
                    "intent": "HOOK",
                    "pattern": "MONEY_FLOW",
                    "visual_logic": {
                        "type": "flow",
                        "source": "₹5,00,000 Salary",
                        "process": "₹3,40,000 Expenses",
                        "result": "₹1,60,000 Leak",
                    },
                }
            ],
            "motion_text",
            "A ₹5,00,000 salary can leak ₹1,60,000.",
            6,
            enforce_hook=True,
            context_text="A ₹5,00,000 salary can leak ₹1,60,000.",
        )
        self.assertEqual(beats[0]["component"], "StatExplosion")
        self.assertNotEqual(beats[0]["component"], "FlowDiagram")
        self.assertEqual(beats[0]["visual_logic"]["type"], "emphasis")
        self.assertNotIn(" vs ", beats[0]["props"]["subtext"])

    def test_split_comparison_uses_content_labels_not_generic_labels(self) -> None:
        spec = RenderSpecService().beat_spec(
            {
                "intent": "COMPARISON",
                "pattern": "COMPARISON",
                "visual_logic": {"type": "comparison", "left": "₹8,00,000 Salary", "right": "₹1,60,000 Invisible Leak"},
            }
        )
        self.assertEqual(spec.props["leftLabel"], "Salary")
        self.assertEqual(spec.props["rightLabel"], "Invisible Leak")
        self.assertNotIn(spec.props["leftLabel"], {"WHAT YOU THINK", "REALITY"})
        self.assertEqual(spec.props["rightColor"], "red")

    def test_flow_labels_are_humanized_and_colored_by_meaning(self) -> None:
        spec = RenderSpecService().beat_spec(
            {
                "intent": "EXPLANATION",
                "pattern": "MONEY_FLOW",
                "visual_logic": {
                    "type": "flow",
                    "source": "₹5,000 Auto Debit",
                    "process": "₹5,000 Invested",
                    "result": "₹0. Emotional Spend",
                },
            }
        )
        labels = [node["label"] for node in spec.props["nodes"]]
        self.assertIn("₹5,000 auto-invested", labels)
        self.assertIn("₹0 left to spend", labels)
        self.assertEqual(spec.props["nodes"][1]["style"]["color"], "teal")

    def test_flow_captions_are_complete_and_loss_color_propagates(self) -> None:
        normalized = RenderSpecService().normalize_structured_beat(
            {
                "intent": "EXPLANATION",
                "pattern": "MONEY_FLOW",
                "visual_logic": {
                    "type": "flow",
                    "source": "₹5,000 Monthly Leak",
                    "process": "12 months",
                    "result": "₹60,000 Lost",
                },
                "props": {"caption": "₹0 left to"},
            }
        )
        self.assertEqual(normalized["props"]["caption"], "₹0 left to spend")
        self.assertEqual(normalized["props"]["color"], "red")
        self.assertEqual(normalized["props"]["captionColor"], "red")
        self.assertEqual(normalized["props"]["nodes"][0]["style"]["color"], "red")

    def test_outro_flow_collapses_to_two_node_punchline(self) -> None:
        service = ScriptService()
        beats = service._normalize_visual_beats(
            [
                {
                    "intent": "EXPLANATION",
                    "pattern": "MONEY_FLOW",
                    "visual_logic": {
                        "type": "flow",
                        "source": "₹5,000 Monthly Leak",
                        "process": "12 months",
                        "result": "₹60,000 Gone",
                    },
                }
            ],
            "motion_text",
            "₹5,000 monthly leak -> 12 months -> ₹60,000 gone",
            18,
            context_text="If ₹5,000 keeps leaking every month, that is ₹60,000 gone in a year.",
            is_outro=True,
        )
        self.assertEqual(len(beats[0]["props"]["nodes"]), 2)
        self.assertEqual(beats[0]["props"]["caption"], "₹5,000/month -> ₹60,000 gone")
        self.assertEqual(beats[0]["props"]["color"], "red")

    def test_tax_context_regenerates_tax_relevant_visual(self) -> None:
        normalized = RenderSpecService().normalize_structured_beat(
            {
                "intent": "COMPARISON",
                "pattern": "COMPARISON",
                "visual_logic": {"type": "comparison", "left": "15% cannot save", "right": "₹20,000 emergency fund"},
                "narration": "Taxes hurt because you paid ₹20,000 but missed a ₹1,50,000 ELSS deduction.",
            }
        )
        text = normalized["visual_logic_text"]
        self.assertIn("₹20,000", text)
        self.assertIn("₹1,50,000", text)
        self.assertNotIn("emergency fund", text)

    def test_illogical_salary_flow_is_rebuilt_in_semantic_order(self) -> None:
        normalized = RenderSpecService().normalize_structured_beat(
            {
                "intent": "EXPLANATION",
                "pattern": "MONEY_FLOW",
                "visual_logic": {
                    "type": "flow",
                    "source": "₹5,00,000 Salary",
                    "process": "₹8,00,000",
                    "result": "₹1,60,000",
                },
                "narration": "Your ₹8,00,000 salary leaves ₹5,00,000 savings after a ₹1,60,000 leak.",
            }
        )
        labels = [node["label"] for node in normalized["props"]["nodes"]]
        self.assertIn("₹8,00,000 Salary", labels)
        self.assertNotEqual(labels[0], "₹5,00,000 Salary")

    def test_semantic_duplicate_signature_blocks_reordered_comparison(self) -> None:
        service = ScriptService()
        with self.app.app_context():
            beats = service._normalize_visual_beats(
                [
                    {
                        "intent": "COMPARISON",
                        "pattern": "COMPARISON",
                        "visual_logic": {"type": "comparison", "left": "76% cannot save", "right": "₹5,000 emergency fund"},
                    },
                    {
                        "intent": "COMPARISON",
                        "pattern": "COMPARISON",
                        "visual_logic": {"type": "comparison", "left": "₹5,000 emergency fund", "right": "76% cannot save"},
                    },
                ],
                "motion_text",
                "76% Indians cannot save ₹5,000.",
                6,
                context_text="76% Indians cannot save ₹5,000.",
            )
        signatures = [service._visual_text_signature(beat) for beat in beats]
        self.assertEqual(len(signatures), len(set(signatures)))

    def test_demo_script_uses_scene_specific_visuals_without_hook_stat_spam(self) -> None:
        service = ScriptService()
        with self.app.app_context():
            payload = service._normalize_payload(service._demo_script("Saving money", "bad defaults"), "Saving money", "bad defaults")
        all_beats = [*payload["hook"]["visual_beats"]]
        for scene in payload["scenes"]:
            all_beats.extend(scene["visual_beats"])
        all_beats.extend(payload["outro"]["visual_beats"])
        texts = [
            RenderSpecService()._visual_logic_to_text(beat.get("visual_logic"))
            for beat in all_beats
            if beat.get("visual_logic")
        ]
        hook_stat_uses = sum("80%" in text and "₹5,000" in text for text in texts)
        self.assertLessEqual(hook_stat_uses, 1)
        self.assertTrue(any("₹8,00,000" in text and "₹1,60,000" in text for text in texts))
        self.assertTrue(any("₹60,000" in text for text in texts))
        self.assertFalse(any("Salary=100" in text or "Savings=12" in text for text in texts))

    def test_consecutive_scene_components_are_varied_for_fallbacks(self) -> None:
        service = ScriptService()
        with self.app.app_context():
            payload = service._normalize_payload(
                {
                    "hook": {"narration": "80% of Indians have less than ₹5,000 saved.", "visual_type": "motion_text"},
                    "scenes": [
                        {"narration": "A ₹8,00,000 salary leaks ₹1,60,000 through defaults.", "visual_type": "motion_text"},
                        {"narration": "Automate ₹5,000 before emotion turns savings into ₹0.", "visual_type": "motion_text"},
                    ],
                    "outro": {"narration": "A ₹5,000 leak becomes ₹60,000 gone in a year."},
                    "titles": ["x"],
                    "description": "x",
                    "tags": ["x"],
                },
                "Saving money",
                "bad defaults",
            )
        first_components = [scene["visual_beats"][0]["component"] for scene in payload["scenes"]]
        self.assertNotEqual(first_components[0], first_components[1])

    def test_manual_good_visual_beats_map_to_expected_components(self) -> None:
        service = RenderSpecService()
        beats = [
            {
                "intent": "EMPHASIS",
                "pattern": "EMPHASIS",
                "props": {"headline": "75%", "subtext": "live paycheck to paycheck"},
            },
            {
                "intent": "COMPARISON",
                "pattern": "COMPARISON",
                "props": {"leftContent": "₹50,000 salary", "rightContent": "₹48,000 expenses"},
            },
            {
                "intent": "EXPLANATION",
                "pattern": "VALUE_DECAY",
                "props": {
                    "nodes": [
                        {"label": "₹1,00,000"},
                        {"label": "Inflation 6%"},
                        {"label": "₹94,000 value"},
                    ]
                },
            },
        ]
        self.assertEqual(service.beat_spec(beats[0]).composition, "StatExplosion")
        self.assertEqual(service.beat_spec(beats[1]).composition, "SplitComparison")
        self.assertEqual(service.beat_spec(beats[2]).composition, "FlowDiagram")

    def test_ten_minute_generation_merges_second_call_beats(self) -> None:
        self.app.config.update({"CHANNEL_STYLE": "ten_minute_finance", "LLM_PROVIDER": "groq", "GROQ_API_KEY": "test"})
        skeleton = {
            "hook": {"narration": "80% of Indians are broke by payday", "visual_type": "motion_text", "visual_instruction": "80% broke"},
            "scenes": [{"narration": "FD pays 6.5 but inflation is 6.7.", "visual_type": "graph", "visual_instruction": "FD vs inflation"}],
            "outro": {"narration": "Fix the math before the bank sells you vibes.", "visual_type": "motion_text", "visual_instruction": "fix the math"},
            "titles": ["FD math"],
            "description": "desc",
            "tags": ["fd"],
        }
        beats = [{"beat_index": 0, "beat_type": "reaction_card", "content": "wait what", "estimated_duration_sec": 3}]
        with patch.object(ScriptService, "_groq_script", return_value=skeleton):
            with patch.object(ScriptService, "_groq_visual_beats", return_value=beats):
                payload, source = ScriptService()._generate_payload("FD returns", "inflation math", "prompt")
        self.assertIn("visual beats", source)
        self.assertEqual(payload["scenes"][0]["visual_beats"][0]["component"], "FlowDiagram")

    def test_voice_demo_fallback_creates_wav(self) -> None:
        audio_root = Path(self.app.config["STORAGE_ROOT"]) / "audio" / "test"
        result = VoiceService().generate_scene_audio(audio_root, 1, "short narration")
        self.assertEqual(result.source, "demo_silent")
        self.assertTrue(result.audio_path.exists())
        self.assertGreater(result.duration_sec, 0)

    def test_remotion_command_uses_render_entry_composition_and_props(self) -> None:
        project_root = Path(self.temp_dir.name) / "remotion"
        (project_root / "src").mkdir(parents=True)
        (project_root / "node_modules" / ".bin").mkdir(parents=True)
        (project_root / "src" / "index.ts").write_text("", encoding="utf-8")
        (project_root / "node_modules" / ".bin" / "remotion").write_text("", encoding="utf-8")
        self.app.config.update(
            {
                "REMOTION_ENABLED": True,
                "REMOTION_PROJECT_PATH": project_root,
                "REMOTION_CLI": "npx",
            }
        )
        spec = RenderSpecService().transition_spec()
        with patch("youtube_ai_system.services.remotion_service.shutil.which", return_value="/usr/bin/npx"):
            with patch("youtube_ai_system.services.remotion_service.subprocess.run") as run:
                RemotionService().render_video(spec, Path(self.temp_dir.name) / "out.mp4")
        command = run.call_args.args[0]
        self.assertIn("render", command)
        self.assertIn("SceneTransition", command)
        self.assertTrue(any(str(part).startswith("--props=") for part in command))

    def test_assembly_caption_chunks_limit_words(self) -> None:
        chunks = AssemblyService()._caption_chunks("one two three four five six seven eight nine", words_per_line=7)
        self.assertEqual(chunks, ["one two three four five six seven", "eight nine"])

    def test_thumbnail_uses_remotion_candidate(self) -> None:
        self.app.config["REMOTION_ENABLED"] = True
        with patch("youtube_ai_system.services.remotion_service.RemotionService.render_still") as render_still:
            render_still.side_effect = lambda spec, output_path: Path(output_path).write_bytes(b"remotion-jpg")
            path = ThumbnailService().ensure_thumbnails(1, ["Why Salaried Indians Stay Broke"])[0]
        self.assertTrue(Path(path).exists())
        self.assertTrue(path.endswith(".jpg"))

    def test_thumbnail_disabled_remotion_raises(self) -> None:
        self.app.config["REMOTION_ENABLED"] = False
        with self.assertRaises(RuntimeError):
            ThumbnailService().ensure_thumbnails(1, ["Why Salaried Indians Stay Broke"])

    def test_broll_without_stock_keys_fails_before_remotion(self) -> None:
        self.app.config.update({"PEXELS_API_KEY": None, "PIXABAY_API_KEY": None, "REMOTION_ENABLED": True})
        with self.assertRaisesRegex(RuntimeError, "B-roll scenes require"):
            MediaService()._generate_visual(
                1,
                Path(self.app.config["STORAGE_ROOT"]) / "images" / "1",
                {"visual_type": "broll", "visual_instruction": "credit card stress person"},
                1,
                "A person checks a credit card bill.",
                "broll",
                "credit card stress person",
                5,
            )

    def test_generate_beat_clips_renders_timeline_for_ten_minute_style(self) -> None:
        self.app.config.update({"CHANNEL_STYLE": "ten_minute_finance", "REMOTION_ENABLED": True})
        project_id = ProjectRepository().create_project("Beat Test")
        scene = {
            "scene_order": 1,
            "visual_type": "motion_text",
            "visual_instruction": "salary vanished",
            "narration_text": "The salary is gone by day twelve.",
            "visual_plan_json": '[{"beat_index":0,"beat_type":"text_burst","content":"salary gone","color":"orange","estimated_duration_sec":3},{"beat_index":1,"beat_type":"reaction_card","content":"bruh","color":"red","estimated_duration_sec":3}]',
        }
        with patch("youtube_ai_system.services.remotion_service.RemotionService.render_video") as render_video:
            render_video.side_effect = lambda spec, output_path: Path(output_path).write_bytes(b"beat")
            with patch.object(MediaService, "_concat_beat_clips") as concat:
                concat.side_effect = lambda paths, output_path, duration: Path(output_path).write_bytes(b"timeline")
                timeline, source = MediaService().generate_beat_clips(
                    project_id,
                    Path(self.app.config["STORAGE_ROOT"]) / "images" / str(project_id),
                    scene,
                    6,
                )
        self.assertTrue(Path(timeline).exists())
        self.assertIn("beat_timeline", source)


if __name__ == "__main__":
    unittest.main()
