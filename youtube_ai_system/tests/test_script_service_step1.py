import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from youtube_ai_system import create_app
from youtube_ai_system.contracts.scripts import ScriptBriefContract
from youtube_ai_system.db import close_db
from youtube_ai_system.models.repository import ProjectRepository, utcnow
from youtube_ai_system.pipelines.script.json_payload import extract_json_payload
from youtube_ai_system.services.script_service import ScriptService
from youtube_ai_system.services.story_pipeline import StoryPipeline


def _find_visual_keys(value, path="root"):
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            if path.startswith("root.story_plan"):
                found.extend(_find_visual_keys(child, f"{path}.{key}"))
                continue
            if key in {"visual_instruction", "visual_type"}:
                found.append(f"{path}.{key}")
            found.extend(_find_visual_keys(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_find_visual_keys(child, f"{path}[{index}]"))
    return found


def _spoken_words(count: int, sentence_size: int = 20) -> str:
    sentences = []
    for start in range(0, count, sentence_size):
        end = min(start + sentence_size, count)
        sentences.append(" ".join(f"word{index}" for index in range(start, end)) + ".")
    return " ".join(sentences)


def _valid_script_brief(scene_count: int = 2) -> dict:
    mechanisms = ["payment_pain_reduction", "affordability_illusion", "commitment_stacking", "subscription_lock_in"]
    return {
        "topic_interpretation": "Monthly payments can be a strategic cash-flow tool for wealthy buyers and a consumer trap for everyone else.",
        "thesis": "Monthly pricing reduces payment pain, preserves liquidity strategically, and creates consumer risk when it hides the full commitment.",
        "viewer_promise": "The viewer will spot the strategic use and the psychological trick before accepting another payment.",
        "selected_format": "psychological_essay",
        "format_rationale": "The topic is about behavior and perception, not a checklist.",
        "recurring_example": "an expensive phone purchase reframed as a small monthly payment",
        "allowed_mechanisms": mechanisms[:scene_count],
        "forbidden_drift": ["salary disappearing by day 20", "generic SIP advice", "emergency fund curriculum"],
        "scene_function_map": [
            {
                "scene_index": index + 1,
                "function": f"Show part {index + 1} of the monthly-payment strategy and consumer psychology.",
                "mechanism": mechanisms[index],
                "emotional_direction": ["revealing", "tightening", "warning", "clarity"][index],
            }
            for index in range(scene_count)
        ],
        "tone_directive": "Dark psychological finance storytelling with concrete Indian money examples.",
    }


def _brief_scene_narration(mechanism: str, scene_index: int) -> str:
    opener = (
        "The expensive phone purchase reframed as a small monthly payment looks harmless in the store. "
        "The full price is still real, but the mind stops feeling the full hit. "
        "The monthly payment becomes the object the buyer judges. "
        f"Scene {scene_index} focuses on {mechanism.replace('_', ' ')} with one clear rupee decision. "
    )
    return opener + _spoken_words(155)


class ScriptServiceStep1TestCase(unittest.TestCase):
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
                "GROQ_API_KEY": None,
            }
        )
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.service = ScriptService()
        self.pipeline = StoryPipeline()

    def tearDown(self) -> None:
        close_db()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def test_normalize_payload_removes_legacy_visual_fields_and_adds_story_plan(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {
                    "narration": "80% of Indians are broke by payday.",
                    "estimated_duration_sec": 6,
                    "visual_type": "motion_text",
                    "visual_instruction": "80% broke",
                    "visual_beats": [{"beat_type": "reaction_card"}],
                },
                "scenes": [
                    {
                        "kind": "body",
                        "scene_index": 1,
                        "narration": "Build an emergency fund before you invest.",
                        "estimated_duration_sec": 30,
                        "visual_type": "graph",
                        "visual_instruction": "fund chart",
                    }
                ],
                "outro": {
                    "narration": "Fix the system before you blame yourself.",
                    "estimated_duration_sec": 18,
                    "visual_type": "motion_text",
                },
            },
            "Emergency Fund",
            "stability first",
        )

        self.assertEqual(payload["hook"], {"narration": "80% of Indians are broke by payday.", "duration": 6})
        self.assertEqual(payload["scenes"][0]["duration"], 30)
        self.assertEqual(payload["outro"]["duration"], 18)
        self.assertIn("story_plan", payload)
        self.assertTrue(payload["story_plan"]["sections"])
        self.assertEqual(_find_visual_keys(payload), [])

    def test_prompt_hook_contract_matches_validator(self) -> None:
        prompt = self.service._build_prompt("salary leaks", "young professionals")

        self.assertIn("Must pass this hook contract", prompt)
        self.assertIn("Do not copy this old salary hook unless TOPIC is specifically about salary disappearing", prompt)
        self.assertIn("Avoid validator-weak hooks", prompt)
        self.assertIn("RECURRING FINANCIAL EXAMPLE", prompt)
        self.assertIn("must come from the TOPIC and AUDIENCE", prompt)
        self.assertIn("Do not create a named fictional character", prompt)
        self.assertIn("Visuals will be diagrams, financial animations, charts, stacks, flows", prompt)
        self.assertIn("VISUAL-SCENE CONTRACT", prompt)
        self.assertIn("visual_intent", prompt)
        self.assertIn("visual_beats", prompt)

    def test_prompt_does_not_force_salary_world_for_monthly_payment_topic(self) -> None:
        prompt = self.service._build_prompt(
            "Why rich people love monthly payments",
            "Dark Psychological Financial Storytelling",
        )

        self.assertIn("expensive purchase being reframed", prompt)
        self.assertIn("payment pain reduction", prompt)
        self.assertIn("affordability illusion", prompt)
        self.assertIn("TONE_HINT is binding", prompt)
        self.assertNotIn("salaried Indian earning around ₹50,000/month in a metro city", prompt)
        self.assertNotIn("Prefer hooks like", prompt)

    def test_valid_script_brief_contract_passes(self) -> None:
        validation = ScriptBriefContract.from_dict(_valid_script_brief()).validate()

        self.assertTrue(validation.passed)

    def test_script_brief_contract_rejects_missing_required_fields(self) -> None:
        brief = _valid_script_brief()
        brief["thesis"] = ""
        brief["recurring_example"] = ""

        validation = ScriptBriefContract.from_dict(brief).validate()

        self.assertFalse(validation.passed)
        self.assertTrue(any(issue.field == "thesis" for issue in validation.errors))
        self.assertTrue(any(issue.field == "recurring_example" for issue in validation.errors))

    def test_script_brief_contract_rejects_unknown_mechanisms(self) -> None:
        brief = _valid_script_brief()
        brief["allowed_mechanisms"] = ["crypto_bubble"]
        brief["scene_function_map"][0]["mechanism"] = "crypto_bubble"

        validation = ScriptBriefContract.from_dict(brief).validate()

        self.assertFalse(validation.passed)
        self.assertTrue(any(issue.code == "invalid_script_brief_mechanism" for issue in validation.errors))

    def test_script_brief_contract_rejects_incomplete_scene_map_entry(self) -> None:
        brief = _valid_script_brief()
        brief["scene_function_map"][0].pop("emotional_direction")

        validation = ScriptBriefContract.from_dict(brief).validate()

        self.assertFalse(validation.passed)
        self.assertTrue(any(issue.code == "invalid_emotional_direction" for issue in validation.errors))

    def test_script_brief_contract_rejects_non_consecutive_scene_indices(self) -> None:
        brief = _valid_script_brief()
        brief["scene_function_map"][1]["scene_index"] = 4

        validation = ScriptBriefContract.from_dict(brief).validate()

        self.assertFalse(validation.passed)
        self.assertTrue(any(issue.code == "non_consecutive_scene_function_map" for issue in validation.errors))

    def test_script_brief_contract_rejects_vague_recurring_example(self) -> None:
        brief = _valid_script_brief()
        brief["recurring_example"] = "money habits"

        validation = ScriptBriefContract.from_dict(brief).validate()

        self.assertFalse(validation.passed)
        self.assertTrue(any(issue.code == "vague_recurring_example" for issue in validation.errors))

    def test_script_brief_contract_rejects_duplicate_scene_functions(self) -> None:
        brief = _valid_script_brief()
        brief["scene_function_map"][1]["function"] = brief["scene_function_map"][0]["function"]

        validation = ScriptBriefContract.from_dict(brief).validate()

        self.assertFalse(validation.passed)
        self.assertTrue(any(issue.code == "duplicate_scene_function" for issue in validation.errors))

    def test_script_brief_contract_rejects_generic_body_advice_for_non_action_plan(self) -> None:
        brief = _valid_script_brief()
        brief["selected_format"] = "mechanism_explainer"
        brief["scene_function_map"][1]["function"] = "Provide a conclusion and call to action for viewers to reassess payments."

        validation = ScriptBriefContract.from_dict(brief).validate()

        self.assertFalse(validation.passed)
        self.assertTrue(any(issue.code == "generic_body_advice_scene_function" for issue in validation.errors))

    def test_script_brief_contract_rejects_budgeting_function_when_forbidden(self) -> None:
        brief = _valid_script_brief()
        brief["forbidden_drift"] = ["general budgeting advice"]
        brief["scene_function_map"][1]["function"] = "Explain 50/30/20 budgeting strategies for monthly payments."

        validation = ScriptBriefContract.from_dict(brief).validate()

        self.assertFalse(validation.passed)
        self.assertTrue(any(issue.code == "forbidden_budgeting_scene_function" for issue in validation.errors))

    def test_script_service_repairs_generic_brief_body_function_before_validation(self) -> None:
        brief = _valid_script_brief()
        brief["selected_format"] = "mechanism_explainer"
        brief["forbidden_drift"] = ["general budgeting advice"]
        brief["scene_function_map"][1]["function"] = (
            "Provide a conclusion and call to action for viewers to reassess payment strategies."
        )

        repaired = self.service._repair_script_brief_contract(brief)
        validation = ScriptBriefContract.from_dict(repaired).validate()

        self.assertTrue(validation.passed)
        self.assertIn("recurring example", repaired["scene_function_map"][1]["function"])
        self.assertNotIn("conclusion", repaired["scene_function_map"][1]["function"].lower())

    def test_brief_prompt_requests_exact_contract_shape(self) -> None:
        prompt = self.service._build_brief_prompt(
            "Why rich people love monthly payments",
            "Dark Psychological Financial Storytelling",
            target_duration_minutes=3,
        )

        self.assertIn("ScriptBrief", prompt)
        self.assertIn('"topic_interpretation"', prompt)
        self.assertIn('"scene_function_map"', prompt)
        self.assertIn("BODY_SCENE_COUNT: 3", prompt)
        self.assertIn("scene_index values must be consecutive", prompt)
        self.assertIn("must not be vague text", prompt)
        self.assertIn("payment_pain_reduction", prompt)
        self.assertIn("cash_flow_squeeze", prompt)
        self.assertIn("Do not choose salary_drain unless the topic is actually about salary disappearing", prompt)
        self.assertIn("explain both the strategic use case and the consumer trap", prompt)
        self.assertIn("Do not reduce the whole video to overspending advice", prompt)
        self.assertIn("explain the rational incentive for that group", prompt)
        self.assertIn("Do not use generic summary/takeaway/advice functions", prompt)
        self.assertIn("scene_function_map must not include budgeting", prompt)

    def test_full_script_prompt_binds_brief_contract(self) -> None:
        brief = _valid_script_brief()
        prompt = self.service._build_prompt(
            "Why rich people love monthly payments",
            "Dark Psychological Financial Storytelling",
            target_duration_minutes=8,
            script_brief=brief,
        )

        self.assertIn("SCRIPT STRATEGY BRIEF (BINDING CONTRACT)", prompt)
        self.assertIn("Every body scene must use recurring_example as the primary example", prompt)
        self.assertIn("Generate exactly one body scene per scene_function_map entry", prompt)
        self.assertIn("Each scene's mechanism must match its scene_function_map entry exactly", prompt)
        self.assertIn("Generate EXACTLY 2 body scenes", prompt)
        self.assertIn("Total script including hook and outro should be around 438-585 spoken words", prompt)
        self.assertIn("salary disappearing by day 20", prompt)
        self.assertIn("an expensive phone purchase reframed as a small monthly payment", prompt)
        self.assertIn("forbidden_drift is a hard boundary", prompt)
        self.assertIn("do not write 50/30/20", prompt)

    def test_prompt_requires_long_form_scene_depth(self) -> None:
        prompt = self.service._build_prompt("salary leaks", "young professionals", target_duration_minutes=8)

        self.assertIn("Generate EXACTLY 8 body scenes", prompt)
        self.assertIn("Each body scene must be 160-200 spoken words", prompt)
        self.assertIn("Do NOT write checklist-style scenes", prompt)
        self.assertIn("Total script including hook and outro should be around 1398-1785 spoken words", prompt)
        self.assertIn("Each body scene narration must be 160-200 words", prompt)

    def test_prompt_duration_math_scales_with_target_minutes(self) -> None:
        prompt = self.service._build_prompt("salary leaks", "young professionals", target_duration_minutes=10)

        self.assertIn("Generate EXACTLY 10 body scenes", prompt)
        self.assertIn("Total script including hook and outro should be around 1718-2185 spoken words", prompt)

    def test_long_form_total_word_gate_allows_small_generation_shortfall(self) -> None:
        repo = ProjectRepository()
        project_id = repo.create_project("near target long script")
        repo.update_project(project_id, target_duration_minutes=8)
        body_scenes = [{"kind": "body", "narration": _spoken_words(160)} for _ in range(8)]
        payload = {
            "hook": {"narration": _spoken_words(8)},
            "scenes": body_scenes,
            "outro": {"narration": _spoken_words(98)},
        }

        errors = self.service._validate_long_form_depth(
            {"video_project_id": project_id},
            payload,
            body_scenes,
        )

        self.assertEqual(errors, [])

    def test_long_form_total_word_gate_still_blocks_material_shortfall(self) -> None:
        repo = ProjectRepository()
        project_id = repo.create_project("short long script")
        repo.update_project(project_id, target_duration_minutes=8)
        body_scenes = [{"kind": "body", "narration": _spoken_words(160)} for _ in range(8)]
        payload = {
            "hook": {"narration": _spoken_words(8)},
            "scenes": body_scenes,
            "outro": {"narration": _spoken_words(80)},
        }

        errors = self.service._validate_long_form_depth(
            {"video_project_id": project_id},
            payload,
            body_scenes,
        )

        self.assertTrue(any("spoken words" in error for error in errors))

    def test_groq_rate_limit_wait_parser_uses_error_message(self) -> None:
        response = Mock()
        response.headers = {}
        response.json.return_value = {
            "error": {
                "message": (
                    "Rate limit reached for model. Please try again in 10.46s. "
                    "Need more tokens?"
                )
            }
        }

        self.assertEqual(self.service._groq_retry_wait_seconds(response), 10.96)

    @patch("youtube_ai_system.services.script_service.time.sleep", return_value=None)
    @patch("youtube_ai_system.infrastructure.llm.groq_client.requests.post")
    def test_groq_script_retries_once_after_rate_limit(self, post: Mock, sleep: Mock) -> None:
        limited_response = Mock()
        limited_response.status_code = 429
        limited_response.headers = {}
        limited_response.text = '{"error":{"message":"Please try again in 1.5s."}}'
        limited_response.json.return_value = {"error": {"message": "Please try again in 1.5s."}}
        limited_response.raise_for_status.side_effect = requests.HTTPError(response=limited_response)

        success_response = Mock()
        success_response.raise_for_status.return_value = None
        success_response.json.return_value = {
            "choices": [{"message": {"content": '{"hook":{"narration":"Why now?"},"scenes":[],"outro":{"narration":"Done."}}'}}]
        }
        post.side_effect = [limited_response, success_response]
        self.app.config["GROQ_RATE_LIMIT_RETRIES"] = 1

        payload = self.service._groq_script("salary leaks", "young professionals", "prompt", "key")

        self.assertEqual(payload["hook"]["narration"], "Why now?")
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(2.0)
        sent_body = post.call_args_list[0].kwargs["json"]
        self.assertEqual(sent_body["max_tokens"], self.app.config["GROQ_MAX_TOKENS"])

    @patch("youtube_ai_system.services.script_service.time.sleep", return_value=None)
    @patch("youtube_ai_system.infrastructure.llm.gemini_client.requests.post")
    def test_gemini_script_uses_generate_content_json_mode(self, post: Mock, sleep: Mock) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{"hook":{"narration":"Why now?"},'
                                    '"scenes":[],"outro":{"narration":"Done."}}'
                                )
                            }
                        ]
                    }
                }
            ]
        }
        post.return_value = response

        payload = self.service._gemini_script("salary leaks", "young professionals", "prompt", "gemini-key")

        self.assertEqual(payload["hook"]["narration"], "Why now?")
        self.assertEqual(post.call_count, 1)
        url = post.call_args.args[0]
        self.assertIn("/v1beta/models/gemini-2.5-flash:generateContent", url)
        sent_body = post.call_args.kwargs["json"]
        self.assertEqual(sent_body["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(sent_body["generationConfig"]["maxOutputTokens"], self.app.config["GEMINI_MAX_TOKENS"])
        self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "gemini-key")
        sleep.assert_not_called()

    def test_script_json_parser_recovers_common_long_model_glitches(self) -> None:
        payload = extract_json_payload(
            """
            ```json
            {
              "hook": {"narration": "Why now?"}
              "scenes": [
                {"narration": "Scene one."}
              ],
              "outro": {"narration": "Done."},
            }
            ```
            """
        )

        self.assertEqual(payload["hook"]["narration"], "Why now?")
        self.assertEqual(payload["scenes"][0]["narration"], "Scene one.")
        self.assertEqual(payload["outro"]["narration"], "Done.")

    @patch("youtube_ai_system.services.script_service.time.sleep", return_value=None)
    @patch("youtube_ai_system.infrastructure.llm.gemini_client.requests.post")
    def test_gemini_script_recovers_missing_comma_json_response(self, post: Mock, sleep: Mock) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{\n'
                                    '  "hook": {"narration": "Why now?"}\n'
                                    '  "scenes": [],\n'
                                    '  "outro": {"narration": "Done."}\n'
                                    "}"
                                )
                            }
                        ]
                    }
                }
            ]
        }
        post.return_value = response

        payload = self.service._gemini_script("salary leaks", "young professionals", "prompt", "gemini-key")

        self.assertEqual(payload["hook"]["narration"], "Why now?")
        self.assertEqual(payload["outro"]["narration"], "Done.")
        sleep.assert_not_called()

    def test_auto_script_generation_falls_back_to_gemini_after_groq_rate_limit(self) -> None:
        brief = _valid_script_brief()
        full_payload = {
            "hook": {"narration": "Why does a giant phone price feel tiny after one monthly payment?", "duration": 7},
            "scenes": [
                {
                    "kind": "body",
                    "scene_index": 1,
                    "narration": _brief_scene_narration("payment_pain_reduction", 1),
                    "duration": 60,
                    "mechanism": "payment_pain_reduction",
                },
                {
                    "kind": "body",
                    "scene_index": 2,
                    "narration": _brief_scene_narration("affordability_illusion", 2),
                    "duration": 60,
                    "mechanism": "affordability_illusion",
                },
            ],
            "outro": {"narration": "Judge the full price before the monthly number judges your budget.", "duration": 30},
            "titles": ["Monthly payments trick"],
            "description": "A finance psychology video.",
            "tags": ["monthly payments"],
        }
        self.app.config.update(
            {
                "LLM_PROVIDER": "auto",
                "GROQ_API_KEY": "groq-key",
                "GEMINI_API_KEY": "gemini-key",
            }
        )

        with patch.object(self.service, "_groq_script", side_effect=ValueError("Groq API error 429: rate_limit_exceeded")):
            with patch.object(self.service, "_gemini_script", return_value=full_payload) as gemini_call:
                payload, source = self.service._generate_payload(
                    1,
                    "Why rich people love monthly payments",
                    "Dark Psychological Financial Storytelling",
                    "prompt",
                    script_brief=brief,
                )

        self.assertEqual(source, "live Gemini API")
        self.assertEqual(payload["meta"]["source"], "live_gemini")
        self.assertTrue(payload["meta"]["script_brief_compliance"]["passed"])
        gemini_call.assert_called_once()

    def test_generate_script_uses_brief_before_full_script_and_stores_meta(self) -> None:
        repo = ProjectRepository()
        project_id = repo.create_project("monthly payment psychology")
        brief = _valid_script_brief()
        full_payload = {
            "hook": {"narration": "Why does a giant phone price feel tiny after one monthly payment?", "duration": 7},
            "scenes": [
                {
                    "kind": "body",
                    "scene_index": 1,
                    "narration": _brief_scene_narration("payment_pain_reduction", 1),
                    "duration": 60,
                    "visual_intent": "Show full phone price shrinking into a monthly payment.",
                    "visual_beats": ["Full price appears", "Monthly number takes over", "Pain fades"],
                    "numbers": [],
                    "emotion": "shock",
                    "mechanism": "payment_pain_reduction",
                },
                {
                    "kind": "body",
                    "scene_index": 2,
                    "narration": _brief_scene_narration("affordability_illusion", 2),
                    "duration": 60,
                    "visual_intent": "Show the monthly number hiding the real cost.",
                    "visual_beats": ["Small payment glows", "Total cost recedes", "Decision tilts"],
                    "numbers": [],
                    "emotion": "anxiety",
                    "mechanism": "affordability_illusion",
                },
            ],
            "outro": {"narration": "Judge the full price before the monthly number judges your budget.", "duration": 30},
            "titles": ["Monthly payments trick"],
            "description": "A finance psychology video.",
            "tags": ["monthly payments"],
        }
        call_order: list[str] = []

        def brief_call(_prompt: str, _api_key: str) -> dict:
            call_order.append("brief")
            return brief

        def script_call(_topic: str, _angle: str, prompt: str, _api_key: str) -> dict:
            call_order.append("script")
            self.assertIn("SCRIPT STRATEGY BRIEF", prompt)
            return full_payload

        self.app.config.update({"LLM_PROVIDER": "groq", "GROQ_API_KEY": "test-key"})
        with patch.object(self.service, "_groq_script_brief", side_effect=brief_call):
            with patch.object(self.service, "_groq_script", side_effect=script_call):
                script_id = self.service.generate_script(
                    project_id,
                    "Why rich people love monthly payments",
                    "Dark Psychological Financial Storytelling",
                    target_duration_minutes=2,
                )

        saved = self.service.load_script_payload(repo.get_script_version(script_id))
        self.assertEqual(call_order, ["brief", "script"])
        self.assertEqual(saved["meta"]["script_brief"]["thesis"], brief["thesis"])
        self.assertTrue(saved["meta"]["script_brief_compliance"]["passed"])
        self.assertEqual(saved["meta"]["script_brief_compliance"]["scene_count"]["expected"], 2)
        self.assertEqual(len(saved["scenes"]), 2)
        self.assertEqual(saved["scenes"][0]["mechanism"], "payment_pain_reduction")

    def test_script_brief_failure_blocks_full_script_generation(self) -> None:
        repo = ProjectRepository()
        project_id = repo.create_project("bad brief")
        invalid_brief = _valid_script_brief()
        invalid_brief["thesis"] = ""
        self.app.config.update({"LLM_PROVIDER": "groq", "GROQ_API_KEY": "test-key"})

        with patch.object(self.service, "_groq_script_brief", return_value=invalid_brief):
            with patch.object(self.service, "_groq_script") as script_call:
                with self.assertRaisesRegex(ValueError, "ScriptBrief generation failed validation"):
                    self.service.generate_script(
                        project_id,
                        "Why rich people love monthly payments",
                        "Dark Psychological Financial Storytelling",
                        target_duration_minutes=2,
                    )

        script_call.assert_not_called()

    def test_script_brief_topic_alignment_rejects_salary_drift_for_non_salary_topic(self) -> None:
        brief = _valid_script_brief()
        brief["thesis"] = "The video proves why your ₹50,000 salary disappears by day 20."

        errors = self.service._validate_script_brief_topic_alignment(
            "Why rich people love monthly payments",
            "Dark Psychological Financial Storytelling",
            brief,
        )

        self.assertTrue(any("salary/day-20" in error for error in errors))

    def test_script_brief_topic_alignment_requires_rich_topic_dual_frame(self) -> None:
        brief = _valid_script_brief()
        brief["thesis"] = "Monthly pricing reduces payment pain and makes purchases feel harmless."
        brief["topic_interpretation"] = "Monthly payments hide the real price."
        brief["viewer_promise"] = "The viewer will spot the trick."
        brief["scene_function_map"][0]["function"] = "Show the payment trick."
        brief["scene_function_map"][1]["function"] = "Show the hidden cost."

        errors = self.service._validate_script_brief_topic_alignment(
            "Why rich people love monthly payments",
            "Dark Psychological Financial Storytelling",
            brief,
        )

        self.assertTrue(any("strategic-use" in error for error in errors))

    def test_generated_script_must_match_brief_scene_map(self) -> None:
        brief = _valid_script_brief()
        payload = {
            "scenes": [
                {"kind": "body", "narration": _brief_scene_narration("payment_pain_reduction", 1), "mechanism": "payment_pain_reduction"},
                {"kind": "body", "narration": _brief_scene_narration("wrong mechanism", 2), "mechanism": "salary_drain"},
            ]
        }

        with self.assertRaisesRegex(ValueError, "does not match ScriptBrief mechanism"):
            self.service._validate_script_against_brief(payload, brief)

    def test_generated_script_requires_recurring_example_consistency(self) -> None:
        brief = _valid_script_brief()
        payload = {
            "scenes": [
                {"kind": "body", "narration": _spoken_words(170), "mechanism": "payment_pain_reduction"},
                {"kind": "body", "narration": _spoken_words(170), "mechanism": "affordability_illusion"},
            ]
        }

        with self.assertRaisesRegex(ValueError, "recurring example appears"):
            self.service._validate_script_against_brief(payload, brief)

    def test_generated_script_rejects_forbidden_drift_phrase(self) -> None:
        brief = _valid_script_brief()
        payload = {
            "scenes": [
                {"kind": "body", "narration": _brief_scene_narration("payment_pain_reduction", 1), "mechanism": "payment_pain_reduction"},
                {
                    "kind": "body",
                    "narration": _brief_scene_narration("affordability_illusion", 2) + " This is not generic SIP advice.",
                    "mechanism": "affordability_illusion",
                },
            ]
        }

        with self.assertRaisesRegex(ValueError, "forbidden drift phrase appears"):
            self.service._validate_script_against_brief(payload, brief)

    def test_payload_repair_replaces_exact_forbidden_drift_phrase(self) -> None:
        brief = _valid_script_brief()
        brief["forbidden_drift"] = ["investment strategies for beginners"]
        payload = {
            "hook": {"narration": "Why does a monthly payment feel smaller?"},
            "scenes": [
                {"kind": "body", "narration": _brief_scene_narration("payment_pain_reduction", 1), "mechanism": "payment_pain_reduction"},
                {
                    "kind": "body",
                    "narration": _brief_scene_narration("affordability_illusion", 2)
                    + " This is not investment strategies for beginners.",
                    "mechanism": "affordability_illusion",
                },
            ],
            "outro": {"narration": "Judge the full cost first."},
            "meta": {},
        }

        repaired = self.service._repair_payload_for_script_brief(payload, brief)

        self.assertNotIn("investment strategies for beginners", repaired["scenes"][1]["narration"].lower())
        self.assertIn("expensive phone purchase", repaired["scenes"][1]["narration"])
        self.service._validate_script_against_brief(repaired, brief)

    def test_payload_repair_replaces_forbidden_investment_markers(self) -> None:
        brief = _valid_script_brief()
        brief["forbidden_drift"] = ["Complex, unrelated investment strategies"]
        payload = {
            "hook": {"narration": "Why does a monthly payment feel smaller?"},
            "scenes": [
                {"kind": "body", "narration": _brief_scene_narration("payment_pain_reduction", 1), "mechanism": "payment_pain_reduction"},
                {
                    "kind": "body",
                    "narration": (
                        _brief_scene_narration("affordability_illusion", 2)
                        + " The remaining cash can go into a high-growth SIP or a diversified mutual fund."
                    ),
                    "mechanism": "affordability_illusion",
                },
            ],
            "outro": {"narration": "Judge the full cost first."},
            "meta": {},
        }

        repaired = self.service._repair_payload_for_script_brief(payload, brief)

        narration = repaired["scenes"][1]["narration"].lower()
        self.assertNotIn("sip", narration)
        self.assertNotIn("mutual fund", narration)
        self.assertIn("productive capital", narration)
        self.assertIn("productive opportunity", narration)
        self.service._validate_script_against_brief(repaired, brief)

    def test_payload_repair_removes_weak_generic_finance_advisory_language(self) -> None:
        brief = _valid_script_brief()
        brief["forbidden_drift"] = ["generic financial literacy"]
        payload = {
            "hook": {"narration": "Why does a monthly payment feel smaller?"},
            "scenes": [
                {
                    "kind": "body",
                    "narration": (
                        "Monthly payments help people make informed financial decisions. "
                        "They can use them wisely and achieve their financial goals."
                    ),
                    "mechanism": "payment_pain_reduction",
                }
            ],
            "outro": {"narration": "Use them wisely and you can live a life of luxury and freedom."},
            "meta": {},
        }

        repaired = self.service._repair_payload_for_script_brief(payload, brief)
        combined = " ".join([repaired["scenes"][0]["narration"], repaired["outro"]["narration"]]).lower()

        self.assertNotIn("make informed financial decisions", combined)
        self.assertNotIn("achieve their financial goals", combined)
        self.assertNotIn("use them wisely", combined)
        self.assertNotIn("life of luxury and freedom", combined)
        self.assertIn("judge the full payment", combined)

    def test_payload_repair_removes_weak_must_advice_language(self) -> None:
        brief = _valid_script_brief()
        payload = {
            "hook": {"narration": "Why does a monthly payment feel smaller?"},
            "scenes": [
                {
                    "kind": "body",
                    "narration": (
                        "People must be careful. They must consider the true cost. "
                        "They must not fool themselves. Monthly payments are just a mechanism. "
                        "They are not a substitute for financial discipline."
                    ),
                    "mechanism": "affordability_illusion",
                }
            ],
            "outro": {
                "narration": (
                    "Do not just look at the monthly payment. Look at the total cost. "
                    "Do not let the affordability illusion trap you."
                )
            },
            "meta": {},
        }

        repaired = self.service._repair_payload_for_script_brief(payload, brief)
        combined = " ".join([repaired["scenes"][0]["narration"], repaired["outro"]["narration"]]).lower()

        self.assertNotIn("people must be careful", combined)
        self.assertNotIn("they must consider the true cost", combined)
        self.assertNotIn("they must not fool themselves", combined)
        self.assertNotIn("financial discipline", combined)
        self.assertIn("full cost has to stay visible", combined)

    def test_script_brief_repair_rewrites_generic_guidance_body_scene(self) -> None:
        brief = _valid_script_brief()
        brief["scene_function_map"][1]["function"] = (
            "Provide guidance on how to avoid the pitfalls of monthly payments and make informed financial decisions."
        )

        repaired = self.service._repair_script_brief_contract(brief)

        self.assertIn("recurring example", repaired["scene_function_map"][1]["function"])
        validation = ScriptBriefContract.from_dict(repaired).validate()
        self.assertTrue(validation.passed, [issue.message for issue in validation.errors])

    def test_script_brief_repair_remaps_direction_used_as_scene_mechanism(self) -> None:
        brief = _valid_script_brief(scene_count=3)
        brief["scene_function_map"][1]["mechanism"] = "clarity"
        brief["scene_function_map"][1]["function"] = (
            "Reveal how the affordability illusion makes the monthly payment feel safer than the full phone price."
        )

        repaired = self.service._repair_script_brief_contract(brief)

        self.assertEqual(repaired["scene_function_map"][1]["mechanism"], "affordability_illusion")
        validation = ScriptBriefContract.from_dict(repaired).validate()
        self.assertTrue(validation.passed, [issue.message for issue in validation.errors])

    def test_generated_script_rejects_semantic_budgeting_drift(self) -> None:
        brief = _valid_script_brief()
        brief["forbidden_drift"] = ["general budgeting advice"]
        payload = {
            "scenes": [
                {
                    "kind": "body",
                    "narration": _brief_scene_narration("payment_pain_reduction", 1)
                    + " Use the 50/30/20 rule and track your expenses every week.",
                    "mechanism": "payment_pain_reduction",
                },
                {"kind": "body", "narration": _brief_scene_narration("affordability_illusion", 2), "mechanism": "affordability_illusion"},
            ]
        }

        with self.assertRaisesRegex(ValueError, "forbidden drift phrase appears"):
            self.service._validate_script_against_brief(payload, brief)

    def test_refiner_uses_mechanism_specific_payment_tails(self) -> None:
        refined = self.service.scene_refiner._template_for(
            "payment_pain_reduction",
            "The restaurant bill feels smaller when the card removes the pain.",
            "Why credit cards make people spend more",
            "credit card psychology",
        )

        self.assertGreaterEqual(self.service._word_count(refined), 160)
        self.assertIn("Cash creates a visible loss", refined)
        self.assertNotIn("danger is not a random finance mistake", refined)

    def test_refiner_uses_mechanism_specific_monthly_payment_tails(self) -> None:
        cases = {
            "cash_flow_squeeze": "monthly number controls the rhythm",
            "commitment_stacking": "Five payments begin behaving like a private tax",
            "compounding": "opportunity cost",
            "leverage": "sharp edge of the monthly-payment logic",
            "debt_trap": "fixed payments like flexible money",
            "emi_pressure": "claim on future income",
            "inflation_erosion": "full-cost view",
        }
        for mechanism, phrase in cases.items():
            with self.subTest(mechanism=mechanism):
                refined = self.service.scene_refiner._template_for(
                    mechanism,
                    "A luxury car lease costs ₹50,000 a month.",
                    "Why Rich People Love Monthly Payments",
                    "rich",
                )

                self.assertGreaterEqual(self.service._word_count(refined), 160)
                self.assertIn(phrase, refined)
                self.assertNotIn("real pressure comes from rich", refined)

    def test_hook_refiner_rewrites_validator_weak_salary_hook(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {
                    "narration": (
                        "You are working hard, getting a decent salary. "
                        "Still, your bank account is almost empty by the 20th of every month."
                    ),
                    "duration": 10,
                },
                "scenes": [{"narration": "Lifestyle inflation quietly drains your salary every month."}],
                "outro": {"narration": "Track the leak before the month tracks you."},
            },
            "salary mistakes",
            "young professionals",
        )

        hook = payload["hook"]["narration"]
        self.assertEqual(hook, "Why does your salary feel gone by day 20?")
        self.assertEqual(self.service.validate_hook(payload["hook"]), [])

    def test_hook_refiner_preserves_already_valid_hook(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "Why does your ₹50,000 salary feel gone by day 20?", "duration": 6},
                "scenes": [{"narration": "Lifestyle inflation quietly drains your salary every month."}],
                "outro": {"narration": "Track the leak before the month tracks you."},
            },
            "salary mistakes",
            "young professionals",
        )

        self.assertEqual(payload["hook"]["narration"], "Why does your ₹50,000 salary feel gone by day 20?")

    def test_visual_scene_fields_feed_story_plan_but_not_top_level_scenes(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "Why does your ₹50,000 salary feel gone by day 20?", "duration": 6},
                "scenes": [
                    {
                        "narration": "Income rises. Lifestyle rises with it. Savings stay stuck.",
                        "visual_intent": "Show income rising, lifestyle absorbing it, and savings staying flat.",
                        "visual_beats": ["Income rises", "Lifestyle rises", "Savings stay stuck"],
                        "numbers": [],
                        "emotion": "anxiety",
                        "mechanism": "lifestyle_inflation",
                    }
                ],
                "outro": {"narration": "Track the leak before the month tracks you."},
            },
            "salary mistakes",
            "young professionals",
        )

        self.assertIn("visual_beats", payload["scenes"][0])
        self.assertEqual(payload["scenes"][0]["visual_beats"][0], "Income rises")
        section = next(section for section in payload["story_plan"]["sections"] if section.get("concept_type") == "lifestyle_inflation")
        self.assertEqual(section["visual_scene"]["mechanism"], "lifestyle_inflation")
        self.assertEqual(section["visual_scene"]["visual_beats"][0], "Income rises")
        self.assertEqual(section["concept_type"], "lifestyle_inflation")

    def test_script_brief_scene_contract_prevents_lifestyle_scene_splitting(self) -> None:
        brief = _valid_script_brief(scene_count=1)
        brief["allowed_mechanisms"] = ["lifestyle_inflation"]
        brief["scene_function_map"][0]["mechanism"] = "lifestyle_inflation"
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "Why do rich people love monthly payments?", "duration": 6},
                "scenes": [
                    {
                        "narration": (
                            "Lifestyle inflation is another consequence. "
                            "When people buy luxury cars with monthly payments, the car changes what normal spending feels like. "
                            "They start adding insurance, fuel, service, accessories, and weekend plans around the same purchase. "
                            "The affordability illusion makes each add-on feel separate from the original loan."
                        ),
                        "mechanism": "lifestyle_inflation",
                    }
                ],
                "outro": {"narration": "Judge the full payment before saying yes."},
                "meta": {"script_brief": brief},
            },
            "Why Rich People Love Monthly Payments",
            "Monthly payments are designed to make expensive things feel emotionally painless.",
        )

        sections = [
            section
            for section in payload["story_plan"]["sections"]
            if section.get("idea_group_id") != "idea_hook"
        ]
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["concept_type"], "lifestyle_inflation")
        self.assertIn("insurance, fuel, service", sections[0]["text"])
        visual_plan = sections[0]["visual_plan"]
        plan_data = visual_plan[0]["visual"]["data"] if isinstance(visual_plan, list) else visual_plan["data"]
        plan_beats = visual_plan[0]["beats"]["beats"] if isinstance(visual_plan, list) else sections[0]["beats"]
        self.assertEqual(plan_data["title"], "The EMI upgrades the lifestyle.")
        self.assertEqual(plan_data["story_state"]["visual_question"], "How does one EMI become a lifestyle upgrade?")
        self.assertIn("Status costs attach", plan_beats[1]["text"])

    def test_short_body_scenes_are_expanded_before_story_planning(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "Why does your ₹50,000 salary feel gone by day 20?", "duration": 6},
                "scenes": [
                    {"narration": "EMIs stack up. Debt trap forms."},
                    {"narration": "SIP growth helps. Patience required."},
                ],
                "outro": {"narration": "Track the leak before the month tracks you."},
            },
            "salary mistakes",
            "young professionals",
        )

        self.assertGreaterEqual(self.service._word_count(payload["scenes"][0]["narration"]), 160)
        self.assertIn("EMIs stack up", payload["scenes"][0]["narration"])
        self.assertIn("salary mistakes", payload["scenes"][0]["narration"])
        self.assertGreaterEqual(self.service._word_count(payload["scenes"][1]["narration"]), 160)
        self.assertIn("SIP growth helps", payload["scenes"][1]["narration"])
        self.assertIn("salary mistakes", payload["scenes"][1]["narration"])
        emi_section = next(section for section in payload["story_plan"]["sections"] if section.get("concept_type") == "emi_pressure")
        self.assertEqual(emi_section["visual_scene"]["mechanism"], "emi_pressure")

    def test_refiner_templates_satisfy_approval_word_counter(self) -> None:
        mechanisms = [
            "salary_drain",
            "lifestyle_inflation",
            "emi_pressure",
            "debt_trap",
            "inflation_erosion",
            "sip_growth",
            "compounding",
            "risk_return",
            "diversification",
            "speculation_risk",
            "emergency_fund",
        ]

        for mechanism in mechanisms:
            with self.subTest(mechanism=mechanism):
                narration = self.service.scene_refiner._template_for(mechanism, "", "salary mistakes", "young professionals")
                self.assertGreaterEqual(self.service._word_count(narration), 160)

    def test_refiner_expands_short_scene_without_importing_salary_template(self) -> None:
        narration = "The full price hurts, but the monthly payment feels painless."

        refined = self.service.scene_refiner._template_for(
            "payment_pain_reduction",
            narration,
            "Why rich people love monthly payments",
            "Dark Psychological Financial Storytelling",
        )

        self.assertGreaterEqual(self.service._word_count(refined), 160)
        self.assertIn("monthly payment feels painless", refined)
        self.assertIn("Why rich people love monthly payments", refined)
        self.assertNotIn("Your salary rises from ₹50,000 to ₹80,000", refined)
        self.assertNotIn("A ₹5,000 SIP looks boring", refined)

    def test_strong_emi_scene_keeps_emi_mechanism_and_stack_beats(self) -> None:
        narration = (
            "One EMI feels harmless. Then a phone EMI joins it. Then a bike EMI joins it. "
            "Then a personal loan starts taking its share. Suddenly ₹18,000 leaves before the month even begins. "
            "That is how EMI pressure builds. The trap is not one huge payment. "
            "It is five small payments behaving like one big leak."
        )
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "Why does your ₹50,000 salary feel gone by day 20?", "duration": 6},
                "scenes": [{"narration": narration}],
                "outro": {"narration": "Track the leak before the month tracks you."},
            },
            "salary mistakes",
            "young professionals",
        )

        section = next(section for section in payload["story_plan"]["sections"] if section.get("concept_type") == "emi_pressure")
        beats = section["visual_plan"][0]["beats"]["beats"]
        self.assertEqual(section["visual_scene"]["mechanism"], "emi_pressure")
        self.assertEqual(section["visual_plan"][0]["visual"]["pattern"], "EMIStackVisualizer")
        self.assertGreaterEqual(len(beats), 3)
        self.assertIn("₹18,000", json.dumps(beats, ensure_ascii=False))

    def test_lifestyle_absorbs_sentence_is_preserved_in_story_grouping(self) -> None:
        grouped = self.pipeline.group_payload_for_story_plan(
            {
                "hook": {"narration": "Why does your ₹50,000 salary feel gone by day 20?"},
                "scenes": [
                    {
                        "narration": "Your salary rises. Lifestyle absorbs it. Savings stay flat.",
                    }
                ],
            }
        )

        text = " ".join(scene["narration"] for scene in grouped["scenes"])
        self.assertIn("Lifestyle absorbs it.", text)

    def test_generic_refiner_template_does_not_leak_internal_meta_language(self) -> None:
        result = self.service.scene_refiner.refine_scene(
            {},
            "You buy a smartphone. Then a new watch. Subscription services add up.",
            index=1,
            topic="Why most salaried Indians stay broke",
            angle="money leaks",
        )

        narration = result["narration"]
        self.assertNotIn("weak version", narration.lower())
        self.assertNotIn("this scene is about", narration.lower())
        self.assertNotIn("real story needs", narration.lower())
        self.assertNotIn("the angle is", narration.lower())
        self.assertNotIn("the mechanism here is", narration.lower())
        self.assertNotIn("first name the visible choice", narration.lower())
        self.assertNotIn("the visual plan should", narration.lower())

    def test_refiner_expansion_tails_are_spoken_not_instructional(self) -> None:
        result = self.service.scene_refiner.refine_scene(
            {"mechanism": "affordability_illusion"},
            "A ₹50 lakh car feels easier to buy when the decision becomes ₹50,000 a month.",
            index=1,
            topic="Why Rich People Love Monthly Payments",
            angle="Monthly payments are designed to make expensive things feel emotionally painless.",
        )

        narration = result["narration"].lower()
        self.assertGreaterEqual(self.service._word_count(result["narration"]), 160)
        self.assertIn("₹50 lakh car feels easier", result["narration"])
        self.assertNotIn("the angle is", narration)
        self.assertNotIn("the mechanism here is", narration)
        self.assertNotIn("the narration should", narration)
        self.assertNotIn("the scene should", narration)

    def test_scene_rows_store_visual_scene_payload_for_body_scenes(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "Why does your ₹50,000 salary feel gone by day 20?", "duration": 6},
                "scenes": [
                    {
                        "narration": "Income rises. Lifestyle rises with it. Savings stay stuck.",
                        "visual_intent": "Show income rising, lifestyle absorbing it, and savings staying flat.",
                        "visual_beats": ["Income rises", "Lifestyle rises", "Savings stay stuck"],
                        "numbers": [],
                        "emotion": "anxiety",
                        "mechanism": "lifestyle_inflation",
                    }
                ],
                "outro": {"narration": "Track the leak before the month tracks you."},
            },
            "Saving money",
            "bad defaults",
        )

        rows = self.service.scene_rows_from_payload(payload)
        self.assertTrue(rows)
        self.assertTrue(all("visual_instruction" not in row for row in rows))
        self.assertTrue(all("visual_type" not in row for row in rows))
        self.assertTrue(all("visual_plan_json" not in row for row in rows))
        self.assertNotIn("visual_scene_json", rows[0])
        self.assertIn("visual_scene_json", rows[1])
        self.assertIn("lifestyle_inflation", rows[1]["visual_scene_json"])

    def test_approval_blocks_duplicate_body_scenes(self) -> None:
        repo = ProjectRepository()
        project_id = repo.create_project("duplicate check")
        repo.update_project(project_id, target_duration_minutes=3)
        payload = {
            "hook": {"narration": "Why does your ₹50,000 salary feel gone by day 20?", "duration": 6},
            "scenes": [
                {
                    "kind": "body",
                    "narration": "A ₹1,00,000 credit card balance does not look scary at first. The bank says the minimum payment is only ₹3,000. At 40% annual interest, the balance barely moves.",
                },
                {
                    "kind": "body",
                    "narration": "A ₹1,00,000 credit card balance does not look scary at first. The bank says the minimum payment is only ₹3,000. At 40% annual interest, the balance barely moves.",
                },
            ],
            "outro": {"narration": "Pay down the trap before it owns the month.", "duration": 18},
        }
        script_id = repo.create_script_version(project_id, payload["hook"], payload["outro"], [], "", [], payload, "")
        repo.update_script_version(script_id, user_edited_at=utcnow())

        ready, errors, _ = self.service.approval_ready(repo.get_script_version(script_id))

        self.assertFalse(ready)
        self.assertTrue(any("too similar" in error for error in errors))

    def test_approval_blocks_too_few_body_scenes_for_long_form(self) -> None:
        repo = ProjectRepository()
        project_id = repo.create_project("short long form")
        repo.update_project(project_id, target_duration_minutes=8)
        payload = {
            "hook": {"narration": "Why does your ₹50,000 salary feel gone by day 20?", "duration": 6},
            "scenes": [
                {"kind": "body", "narration": f"Scene {index} explains one money leak with a concrete example."}
                for index in range(1, 6)
            ],
            "outro": {"narration": "Track the leak before the month tracks you.", "duration": 18},
        }
        script_id = repo.create_script_version(project_id, payload["hook"], payload["outro"], [], "", [], payload, "")
        repo.update_script_version(script_id, user_edited_at=utcnow())

        ready, errors, _ = self.service.approval_ready(repo.get_script_version(script_id))

        self.assertFalse(ready)
        self.assertTrue(any("only 5 body scenes" in error for error in errors))

    def test_approval_blocks_project_86_style_short_script(self) -> None:
        repo = ProjectRepository()
        project_id = repo.create_project("project 86 regression")
        repo.update_project(project_id, target_duration_minutes=8)
        payload = {
            "hook": {"narration": "Why does your ₹50,000 salary feel gone by day 20?", "duration": 8},
            "scenes": [
                {
                    "kind": "body",
                    "narration": (
                        "You earn ₹50,000 monthly. Rent takes ₹15,000. EMIs take ₹8,000. "
                        "You are left with ₹27,000. Food and travel take ₹10,000. "
                        "You are left with ₹17,000. Savings seem impossible."
                    ),
                    "visual_intent": "Show salary draining into fixed expenses",
                    "visual_beats": ["Salary lands", "Expenses drain", "Savings shrink"],
                    "numbers": ["50000", "15000", "8000", "27000", "10000", "17000"],
                    "emotion": "anxiety",
                    "mechanism": "salary_drain",
                }
                for _ in range(8)
            ],
            "outro": {"narration": "Track the leak before the month tracks you.", "duration": 18},
            "story_plan": {"sections": []},
        }
        script_id = repo.create_script_version(project_id, payload["hook"], payload["outro"], [], "", [], payload, "")
        repo.update_script_version(script_id, user_edited_at=utcnow())

        ready, errors, _ = self.service.approval_ready(repo.get_script_version(script_id))

        self.assertFalse(ready)
        self.assertTrue(any("Body scene 1 is too short" in error for error in errors))
        self.assertTrue(any("spoken words" in error for error in errors))

    def test_approval_blocks_visual_numbers_not_spoken_in_narration(self) -> None:
        repo = ProjectRepository()
        project_id = repo.create_project("visual number grounding")
        repo.update_project(project_id, target_duration_minutes=3)
        long_scene = (
            "You have ₹17,000 left after expenses. The emergency fund should protect that leftover cash before a shock arrives. "
            "The money is not for excitement. It is for survival. A medical bill can disturb the month. A job delay can disturb the month. "
            "A cash buffer absorbs that shock before credit card debt enters. The viewer should see the buffer taking the hit. "
            "That is how boring money keeps the plan alive."
        )
        payload = {
            "hook": {"narration": "Why does your ₹50,000 salary feel gone by day 20?", "duration": 8},
            "scenes": [
                {
                    "kind": "body",
                    "narration": long_scene,
                    "visual_intent": "Show emergency fund protecting leftover cash",
                    "visual_beats": ["Cash buffer", "Shock arrives", "Debt avoided"],
                    "numbers": ["17000", "50000"],
                    "emotion": "clarity",
                    "mechanism": "emergency_fund",
                }
            ],
            "outro": {"narration": "Build survival before chasing returns.", "duration": 18},
            "story_plan": {"sections": []},
        }
        script_id = repo.create_script_version(project_id, payload["hook"], payload["outro"], [], "", [], payload, "")
        repo.update_script_version(script_id, user_edited_at=utcnow())

        ready, errors, _ = self.service.approval_ready(repo.get_script_version(script_id))

        self.assertFalse(ready)
        self.assertTrue(any("not spoken in the narration" in error for error in errors))

    def test_approval_blocks_internal_prompt_language_in_narration(self) -> None:
        repo = ProjectRepository()
        project_id = repo.create_project("meta leakage")
        repo.update_project(project_id, target_duration_minutes=3)
        payload = {
            "hook": {"narration": "Why does a ₹50 lakh car feel cheap at ₹50,000 a month?", "duration": 8},
            "scenes": [
                {
                    "kind": "body",
                    "narration": (
                        "A monthly payment can hide the real cost. The angle is monthly payments are designed to feel painless. "
                        "The mechanism here is affordability illusion, and the narration should show how it changes the decision. "
                        + _spoken_words(150)
                    ),
                    "visual_intent": "Show monthly price hiding full price",
                    "visual_beats": ["Full price appears", "Monthly payment takes focus", "Hidden cost returns"],
                    "numbers": ["₹50 lakh", "₹50,000"],
                    "emotion": "anxiety",
                    "mechanism": "affordability_illusion",
                }
            ],
            "outro": {"narration": "Judge the full cost before the small payment comforts you.", "duration": 18},
            "story_plan": {"sections": []},
        }
        script_id = repo.create_script_version(project_id, payload["hook"], payload["outro"], [], "", [], payload, "")
        repo.update_script_version(script_id, user_edited_at=utcnow())

        ready, errors, _ = self.service.approval_ready(repo.get_script_version(script_id))

        self.assertFalse(ready)
        self.assertTrue(any("meta-visual narration" in error for error in errors))

    def test_save_script_edits_preserves_scene_mechanism_metadata(self) -> None:
        repo = ProjectRepository()
        project_id = repo.create_project("preserve metadata")
        repo.update_project(project_id, topic="Emergency fund", angle="stability first")
        payload = {
            "hook": {"narration": "Why does your ₹50,000 salary feel gone by day 20?", "duration": 6},
            "scenes": [
                {
                    "kind": "body",
                    "narration": "Emergency fund is crucial. 3-6 months of expenses are a must. Job loss and medical emergencies can arrive without warning.",
                    "duration": 45,
                    "mechanism": "emergency_fund",
                    "emotion": "clarity",
                    "visual_intent": "Show emergency fund as protection",
                }
            ],
            "outro": {"narration": "Build survival before chasing returns.", "duration": 18},
        }
        script_id = repo.create_script_version(project_id, payload["hook"], payload["outro"], [], "", [], payload, "")

        self.service.save_script_edits(script_id, payload)
        saved = self.service.load_script_payload(repo.get_script_version(script_id))

        self.assertEqual(saved["scenes"][0]["mechanism"], "emergency_fund")
        self.assertIn("emergency fund", saved["scenes"][0]["narration"].lower())

    def test_save_script_edits_rebuilds_brief_constrained_story_plan(self) -> None:
        repo = ProjectRepository()
        project_id = repo.create_project("brief save repair")
        repo.update_project(
            project_id,
            topic="Why Rich People Love Monthly Payments",
            angle="Monthly payments are designed to make expensive things feel emotionally painless.",
        )
        brief = _valid_script_brief(scene_count=1)
        brief["recurring_example"] = "a luxury car purchase with a 5-year loan"
        brief["allowed_mechanisms"] = ["lifestyle_inflation"]
        brief["scene_function_map"][0]["function"] = (
            "Explain how lifestyle inflation can result from frequent monthly payments."
        )
        brief["scene_function_map"][0]["mechanism"] = "lifestyle_inflation"
        payload = {
            "hook": {"narration": "Why do rich people love monthly payments?", "duration": 6},
            "scenes": [
                {
                    "kind": "body",
                    "narration": (
                        "People must be careful. Lifestyle inflation is another consequence. "
                        "When people buy luxury cars with monthly payments, the car changes what normal spending feels like. "
                        "They start adding insurance, fuel, service, accessories, and weekend plans around the same purchase. "
                        "They must consider the true cost. They must not fool themselves."
                    ),
                    "duration": 71,
                    "mechanism": "lifestyle_inflation",
                }
            ],
            "outro": {"narration": "Do not just look at the monthly payment. Look at the total cost.", "duration": 18},
            "meta": {"script_brief": brief},
        }
        script_id = repo.create_script_version(project_id, payload["hook"], payload["outro"], [], "", [], payload, "")

        self.service.save_script_edits(script_id, payload)
        saved = self.service.load_script_payload(repo.get_script_version(script_id))

        saved_text = " ".join(
            [saved["scenes"][0]["narration"], saved["outro"]["narration"]]
        ).lower()
        self.assertNotIn("people must be careful", saved_text)
        self.assertNotIn("they must consider the true cost", saved_text)
        self.assertNotIn("they must not fool themselves", saved_text)
        self.assertIn("the payment has to survive the full term", saved_text)
        self.assertEqual(saved["meta"]["script_brief_compliance"]["scene_count"]["actual"], 1)
        sections = [
            section
            for section in saved["story_plan"]["sections"]
            if section.get("idea_group_id") != "idea_hook"
        ]
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["concept_type"], "lifestyle_inflation")
        visual_plan = sections[0]["visual_plan"]
        plan_data = visual_plan[0]["visual"]["data"] if isinstance(visual_plan, list) else visual_plan["data"]
        plan_beats = visual_plan[0]["beats"]["beats"] if isinstance(visual_plan, list) else sections[0]["beats"]
        self.assertEqual(plan_data["title"], "The EMI upgrades the lifestyle.")
        self.assertEqual(plan_data["story_state"]["visual_question"], "How does one EMI become a lifestyle upgrade?")
        self.assertIn("Status costs attach", plan_beats[1]["text"])

    def test_group_sentences_into_sections_pairs_simple_sequence(self) -> None:
        grouped = self.pipeline.group_sentences_into_sections(
            ["Sentence 1", "Sentence 2", "Sentence 3", "Sentence 4"]
        )
        self.assertEqual(grouped, ["Sentence 1 Sentence 2", "Sentence 3 Sentence 4"])

    def test_group_sentences_merges_short_section_with_next(self) -> None:
        grouped = self.pipeline.group_sentences_into_sections(
            [
                "Debt hurts families.",
                "Interest grows monthly.",
                "Budgeting works before income shocks.",
            ]
        )
        self.assertEqual(len(grouped), 1)
        self.assertGreaterEqual(len(grouped[0].split()), 8)

    def test_group_sentences_breaks_before_transition_starter(self) -> None:
        grouped = self.pipeline.group_sentences_into_sections(
            [
                "Debt hurts families badly.",
                "Interest grows every month.",
                "Because banks earn more from delay.",
                "Budgeting can reduce the damage.",
            ]
        )
        self.assertEqual(
            grouped,
            [
                "Debt hurts families badly. Interest grows every month.",
                "Because banks earn more from delay. Budgeting can reduce the damage.",
            ],
        )

    def test_group_payload_filters_short_and_filler_sentences_before_grouping(self) -> None:
        grouped_payload = self.pipeline.group_payload_for_story_plan(
            {
                "hook": {"narration": "Debt grows quietly.", "duration": 6},
                "scenes": [
                    {
                        "narration": (
                            "Let's start with the obvious. "
                            "Minimum payments often look completely harmless. "
                            "For instance, this is a common trap. "
                            "Interest charges keep growing every month."
                        )
                    }
                ],
                "outro": {"narration": "You know this already. Build a repayment plan this month."},
            }
        )
        narrations = [scene["narration"] for scene in grouped_payload["scenes"]]
        self.assertEqual(
            narrations,
            [
                (
                    "Minimum payments often look completely harmless. "
                    "Interest charges keep growing every month."
                ),
            ],
        )

    def test_group_payload_uses_idea_grouper_metadata(self) -> None:
        grouped_payload = self.pipeline.group_payload_for_story_plan(
            {
                "hook": {"narration": "Debt can quietly grow.", "duration": 6},
                "scenes": [
                    {
                        "narration": (
                            "Your salary rises every year. "
                            "But your expenses rise faster. "
                            "Another problem is credit card debt. "
                            "Because interest grows every month."
                        )
                    }
                ],
                "outro": {"narration": "Build better money systems."},
            }
        )
        scenes = grouped_payload["scenes"]
        self.assertGreaterEqual(len(scenes), 2)
        self.assertEqual(scenes[0]["dominant_entity"], "salary")
        self.assertIn(scenes[1]["dominant_entity"], {"credit", "debt"})
        self.assertIn("idea_group_id", scenes[0])
        self.assertIn("idea_type", scenes[0])
        self.assertIn("has_numbers", scenes[0])
        self.assertIn("has_comparison", scenes[0])
        self.assertIn("has_causation", scenes[0])

    def test_idea_grouper_keeps_complete_lifestyle_inflation_idea_together(self) -> None:
        grouped_payload = self.pipeline.group_payload_for_story_plan(
            {
                "hook": {"narration": "Raises can still leave you broke.", "duration": 6},
                "scenes": [
                    {
                        "narration": (
                            "As soon as we get a raise, we upgrade our lifestyle. "
                            "Whether it's a fancy phone or a new car. "
                            "Spending rises faster than savings. "
                            "That quietly slows wealth building."
                        )
                    }
                ],
                "outro": {"narration": "Keep the gap and invest the difference."},
            }
        )
        scenes = grouped_payload["scenes"]
        self.assertEqual(len(scenes), 1)
        self.assertIn("Spending rises faster than savings.", scenes[0]["narration"])
        self.assertIn("That quietly slows wealth building.", scenes[0]["narration"])

    def test_idea_grouper_splits_credit_card_and_emergency_fund_ideas(self) -> None:
        grouped_payload = self.pipeline.group_payload_for_story_plan(
            {
                "hook": {"narration": "Debt feels manageable until it isn't.", "duration": 6},
                "scenes": [
                    {
                        "narration": (
                            "Credit card debt grows fast when interest compounds every month. "
                            "Minimum payments keep the balance alive. "
                            "Without an emergency fund, one medical bill pushes you into debt. "
                            "A cash buffer protects your long-term investments."
                        )
                    }
                ],
                "outro": {"narration": "Fix the system before the next shock arrives."},
            }
        )
        scenes = grouped_payload["scenes"]
        self.assertEqual(len(scenes), 2)
        self.assertIn("Credit card debt grows fast", scenes[0]["narration"])
        self.assertIn("Without an emergency fund", scenes[1]["narration"])

    def test_three_sample_scripts_normalize_to_minimal_shape(self) -> None:
        samples = [
            (
                "Emergency fund",
                "why savings comes first",
                {
                    "hook": {"narration": "Most people invest before they can survive one bad month.", "duration": 6},
                    "scenes": [
                        {"narration": "Without cash, one hospital bill becomes debt.", "duration": 30},
                        {"narration": "An emergency fund buys time when income stops.", "duration": 28},
                    ],
                    "outro": {"narration": "Build survival before chasing returns.", "duration": 15},
                },
            ),
            (
                "Lifestyle inflation",
                "income growth trap",
                {
                    "hook": {"narration": "A raise can make you feel rich and still keep you broke.", "estimated_duration_sec": 6},
                    "scenes": [
                        {"narration_text": "Your expenses rise faster than your peace of mind.", "estimated_duration_sec": 32},
                        {"content": "The fix is raising investments before lifestyle catches up.", "estimated_duration_sec": 34},
                    ],
                    "outro": {"text": "Automate the gap before spending expands.", "estimated_duration_sec": 18},
                },
            ),
            (
                "Credit cards",
                "minimum payment trap",
                {
                    "hook": {"text": "Minimum payment is how small debt stays with you for years.", "duration": 6},
                    "scenes": [
                        {"narration": "Interest keeps compounding when you delay the real payment.", "duration": 31},
                    ],
                    "outro": {"narration": "Cheap convenience becomes expensive silence.", "duration": 16},
                },
            ),
        ]

        for topic, angle, raw in samples:
            with self.subTest(topic=topic):
                payload = self.service._normalize_payload(raw, topic, angle)
                self.assertEqual(_find_visual_keys(payload), [])
                self.assertIn("story_plan", payload)
                self.assertIn("hook", payload)
                self.assertIn("scenes", payload)
                self.assertIn("outro", payload)
                self.assertIsInstance(payload["hook"]["duration"], int)
                self.assertTrue(all("duration" in scene for scene in payload["scenes"]))
                self.assertIsInstance(payload["story_plan"]["agenda"], list)

    def test_story_sections_include_deterministic_concepts(self) -> None:
        samples = [
            {
                "topic": "Inflation",
                "angle": "saving value",
                "payload": {
                    "hook": {"narration": "Inflation can quietly damage your savings.", "duration": 6},
                    "scenes": [
                        {"narration": "Inflation makes your savings lose value.", "duration": 30},
                        {"narration": "Equity is risky while debt is stable.", "duration": 30},
                    ],
                    "outro": {"narration": "Investment growth protects your future.", "duration": 18},
                },
            },
            {
                "topic": "Debt",
                "angle": "avoid the trap",
                "payload": {
                    "hook": {"narration": "One minimum payment can keep debt alive for years.", "duration": 6},
                    "scenes": [
                        {"narration": "Paying minimum dues creates a debt trap.", "duration": 30},
                        {"narration": "Budgeting works before and after income shocks.", "duration": 30},
                    ],
                    "outro": {"narration": "Debt risk destroys financial freedom.", "duration": 18},
                },
            },
        ]

        for sample in samples:
            with self.subTest(topic=sample["topic"]):
                payload = self.service._normalize_payload(
                    sample["payload"],
                    sample["topic"],
                    sample["angle"],
                )
                sections = payload["story_plan"]["sections"]
                self.assertTrue(sections)
                self.assertTrue(all("concepts" in section for section in sections))
                self.assertTrue(all("visual_plan" in section for section in sections))
                self.assertTrue(all(isinstance(section["concepts"], list) for section in sections))
                self.assertTrue(all(isinstance(section["visual_plan"], list) for section in sections))
                self.assertTrue(any(section["concepts"] for section in sections))
                self.assertTrue(any(section["visual_plan"] for section in sections))
                for section in sections:
                    for concept in section["concepts"]:
                        self.assertTrue(concept["concept"])
                        self.assertLessEqual(len(concept["concept"].split()), 3)
                        self.assertNotEqual(concept["type"], "unknown")
                    for item in section["visual_plan"]:
                        self.assertIn("concept", item)
                        self.assertIn("visual", item)
                        self.assertIn("beats", item)

    def test_finance_concepts_are_strong_on_grouped_sections(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "Invisible leaks keep salaries stuck.", "duration": 6},
                "scenes": [
                    {
                        "narration": (
                            "As soon as we get a raise, we upgrade our lifestyle. "
                            "Spending rises faster than savings. "
                            "Credit card debt grows fast when interest compounds every month. "
                            "Minimum payments keep the balance alive."
                        ),
                        "duration": 30,
                    }
                ],
                "outro": {"narration": "Protect the gap before it disappears.", "duration": 18},
            },
            "Money leaks",
            "salary trap",
        )
        concepts = [section["concepts"][0]["concept"] for section in payload["story_plan"]["sections"] if section["concepts"]]
        self.assertIn("Lifestyle Inflation", concepts)
        self.assertIn("Debt Trap", concepts)

    def test_story_plan_uses_grouped_sections_before_engine(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "Debt can quietly take over your life.", "duration": 6},
                "scenes": [
                    {
                        "narration": (
                            "Paying minimum dues creates a debt trap. "
                            "Interest keeps growing every month. "
                            "But most people notice too late. "
                            "Debt risk destroys financial freedom."
                        ),
                        "duration": 30,
                    }
                ],
                "outro": {"narration": "Budgeting works before and after income shocks.", "duration": 18},
            },
            "Debt",
            "avoid the trap",
        )
        self.assertIn("story_plan", payload)
        self.assertEqual(len(payload["story_plan"]["sections"]), 2)
        self.assertEqual(
            [section["idea_group_id"] for section in payload["story_plan"]["sections"]],
            ["idea_hook", "idea_00"],
        )

    def test_numeric_visuals_enhance_concept_visuals_and_agenda_uses_top_concepts(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "A ₹50,000 balance can quietly explode.", "duration": 6},
                "scenes": [
                    {
                        "narration": (
                            "A ₹50,000 bill with a ₹2,000 minimum can create ₹15,000 interest. "
                            "Paying minimum dues creates a debt trap."
                        ),
                        "duration": 35,
                    },
                    {
                        "narration": "Inflation makes your savings lose value.",
                        "duration": 35,
                    },
                ],
                "outro": {"narration": "Investment growth protects your long-term financial freedom.", "duration": 18},
            },
            "Debt",
            "minimum payment trap",
        )
        sections = payload["story_plan"]["sections"]
        self.assertTrue(sections[0]["visual_plan"])
        self.assertIn(sections[0]["visual_plan"][0]["concept"]["type"], {"risk", "debt_trap"})
        unified_item = sections[0]["visual_plan"][0]
        self.assertIn(unified_item["visual"]["pattern"], {"NumericComparison", "DebtSpiralVisualizer"})
        if unified_item["visual"]["pattern"] == "NumericComparison":
            self.assertEqual(
                unified_item["visual"]["data"]["values"],
                ["₹50,000 bill", "₹2,000 payment", "₹15,000 interest"],
            )
        else:
            self.assertIn("balances", unified_item["visual"]["data"])
        self.assertIn(sections[0]["visual_type"], {"balance_decay", "comparison"})
        self.assertIn("state", sections[0])
        self.assertTrue(sections[0]["narrative_arc"]["story_goal"])
        self.assertIn("Debt Trap", payload["story_plan"]["agenda"])
        self.assertNotIn("SIP Growth", payload["story_plan"]["agenda"])

    def test_visual_plan_uses_section_narrative_arc_beats(self) -> None:
        story_plan = {
            "hook": "",
            "agenda": [],
            "sections": [
                {
                    "type": "explanation",
                    "text": "Credit card debt grows fast when interest compounds every month.",
                    "weight": {"level": "medium", "score": 0.55},
                    "concepts": [{"concept": "Debt Trap", "type": "risk"}],
                    "has_numbers": False,
                }
            ],
        }
        story_plan = self.pipeline.attach_section_narrative_arc(story_plan)
        planned = self.pipeline.attach_section_visual_plan(story_plan)
        section = planned["sections"][0]
        beats = planned["sections"][0]["visual_plan"][0]["beats"]["beats"]
        self.assertGreaterEqual(len(beats), 1)
        self.assertEqual(section["visual_type"], "pressure")
        self.assertEqual(section["visual_plan"][0]["visual"]["pattern"], "FlowDiagram")
        self.assertEqual(beats[0]["text"], "Swipe now")
        self.assertIn("source_text", beats[0])
        self.assertTrue(all("component" in beat for beat in beats))

    def test_numeric_arc_uses_calculation_steps_when_values_are_related(self) -> None:
        story_plan = {
            "hook": "",
            "agenda": [],
            "sections": [
                {
                    "type": "explanation",
                    "text": (
                        "A ₹1,00,000 credit card debt at 40% interest costs ₹40,000 every year. "
                        "Paying minimum dues creates a debt trap."
                    ),
                    "weight": {"level": "high", "score": 0.9},
                    "dominant_entity": "debt",
                    "idea_type": "risk",
                    "has_numbers": True,
                    "has_causation": True,
                }
            ],
        }
        story_plan = self.pipeline.attach_section_concepts(story_plan)
        story_plan = self.pipeline.attach_section_narrative_arc(story_plan)
        planned = self.pipeline.attach_section_visual_plan(story_plan)
        beats = planned["sections"][0]["visual_plan"][0]["beats"]["beats"]
        spiral = next(beat for beat in beats if beat["component"] == "DebtSpiralVisualizer")

        self.assertEqual(planned["sections"][0]["visual_type"], "balance_decay")
        data = spiral.get("data") or {}
        self.assertEqual(spiral.get("beat_phase"), "principal")
        self.assertEqual(data.get("active_phase"), "principal")
        self.assertIn("balances", data)
        self.assertIn("monthly_interest", data)
        self.assertTrue(all(beat["component"] == "DebtSpiralVisualizer" for beat in beats))

    def test_section_flow_validation_logs_warning_without_failing_story_plan(self) -> None:
        class FakeLogger:
            def __init__(self) -> None:
                self.messages = []

            def log(self, stage_name, status, message, project_id=None) -> None:
                self.messages.append((stage_name, status, message, project_id))

        logger = FakeLogger()
        pipeline = StoryPipeline(logger=logger)

        def fail_section_flow(sections):
            raise ValueError("Story sections are out of order.")

        pipeline.story_intelligence._validate_section_flow = fail_section_flow
        story_plan = pipeline.story_plan_from_idea_groups(
            {
                "hook": {"narration": "Debt can quietly trap you.", "duration": 6},
                "scenes": [
                    {
                        "narration": "Paying minimum dues creates a debt trap.",
                        "idea_group_id": "idea_00",
                        "dominant_entity": "debt",
                        "idea_type": "risk",
                    },
                    {
                        "narration": "Budgeting can reduce the damage.",
                        "idea_group_id": "idea_01",
                        "dominant_entity": "budgeting",
                        "idea_type": "optimization",
                    },
                ],
            }
        )

        self.assertTrue(story_plan["sections"])
        self.assertEqual(logger.messages[0][0], "story_planning")
        self.assertEqual(logger.messages[0][1], "warning")
        self.assertIn("out of order", logger.messages[0][2])

    def test_invalid_numeric_candidate_falls_back_to_concept_visual(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {"narration": "Minimum payments feel harmless.", "duration": 6},
                "scenes": [
                    {
                        "narration": "A minimum payment cycle can last 10 years.",
                        "duration": 35,
                    }
                ],
                "outro": {"narration": "Minimum payment cycles quietly extend debt.", "duration": 18},
            },
            "Debt",
            "minimum payment trap",
        )
        concept_section = payload["story_plan"]["sections"][1]
        self.assertEqual(concept_section["concepts"], [{"concept": "Debt Trap", "type": "risk"}])
        self.assertTrue(concept_section["visual_plan"])
        self.assertNotEqual(concept_section["visual_plan"][0]["concept"]["type"], "numeric")

    def test_invalid_visual_item_is_rejected_without_text_fallback(self) -> None:
        fallback = self.pipeline.safe_visual_item(
            {
                "concept": {"concept": "", "type": "numeric"},
                "visual": {"component": "StatCard", "props": {"title": ""}},
                "beats": {"beats": [{"component": "StatCard", "text": ""}]},
            }
        )
        self.assertIsNone(fallback)

    def test_invalid_visual_item_rejects_sentence_fragments(self) -> None:
        fallback = self.pipeline.safe_visual_item(
            {
                "concept": {"concept": "Debt Trap", "type": "risk"},
                "visual": {"pattern": "RiskCard", "data": {"title": "DEBT TRAP"}},
                "beats": {"beats": [{"component": "StatCard", "text": "as soon as"}]},
            }
        )
        self.assertIsNone(fallback)

    def test_agenda_uses_strongest_section_insights_when_concepts_missing(self) -> None:
        agenda = self.pipeline.agenda_from_top_concepts(
            [
                {
                    "weight": {"score": 0.9},
                    "concepts": [],
                    "visual_plan": [{"concept": {"concept": "Salary disappears early", "type": "fallback"}}],
                },
                {
                    "weight": {"score": 0.8},
                    "concepts": [],
                    "visual_plan": [{"concept": {"concept": "₹1,60,000 leak", "type": "numeric"}}],
                },
                {
                    "weight": {"score": 0.7},
                    "concepts": [],
                    "visual_plan": [{"concept": {"concept": "Automate savings", "type": "fallback"}}],
                },
            ]
        )
        self.assertEqual(agenda, ["₹1,60,000 leak", "Salary disappears early", "Automate savings"])

    def test_financial_number_filter_rejects_age_and_day_numbers(self) -> None:
        phrases = self.pipeline.numeric_phrases(
            "In your 20s, salary can vanish by day 12, and one card bill can break the month."
        )
        self.assertEqual(phrases, [])

    def test_numeric_labels_add_financial_meaning(self) -> None:
        phrases = self.pipeline.numeric_phrases(
            "A ₹8,00,000 salary can still leak ₹1,60,000 before you notice."
        )
        self.assertEqual(phrases, ["₹8,00,000 salary", "₹1,60,000 leak"])
