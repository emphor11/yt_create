import tempfile
import unittest
from pathlib import Path

from youtube_ai_system import create_app
from youtube_ai_system.db import close_db
from youtube_ai_system.services.narration_refiner import refine
from youtube_ai_system.services.script_service import ScriptService


class NarrationRefinerTestCase(unittest.TestCase):
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

    def tearDown(self) -> None:
        close_db()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def test_refine_splits_long_sentence(self) -> None:
        result = refine("So, you just landed your first job, and you're already thinking about investing in the stock market.")
        self.assertEqual(
            result,
            [
                "You just landed your first job.",
                "Most people look at mutual funds immediately.",
            ],
        )

    def test_refine_splits_parallel_risks(self) -> None:
        result = refine("You could lose your job, your car could break down, or you might face medical expenses.")
        self.assertEqual(
            result,
            [
                "Job loss is possible.",
                "A car breakdown is possible.",
                "Unexpected medical expenses are possible.",
            ],
        )

    def test_refine_rewrites_question_after_filler(self) -> None:
        result = refine("Now, you might be thinking, why do I need an emergency fund?")
        self.assertEqual(result, ["Why do I need an emergency fund?"])

    def test_normalize_payload_handles_previous_emergency_fund_failure(self) -> None:
        payload = self.service._normalize_payload(
            {
                "hook": {
                    "narration": "Did you know that nearly 60% of Indians can't afford a ₹10,000 expense without going into debt? Yeah, that's a recipe for disaster.",
                    "duration": 6,
                },
                "scenes": [
                    {
                        "scene_index": 1,
                        "kind": "body",
                        "narration": "So, you just landed your first job, and you're already thinking about investing in the stock market or putting your money into a mutual fund. Hold up, buddy! Before you start investing, you need to build an emergency fund. Think of it like having a safety net that'll catch you if you fall.",
                        "duration": 60,
                    },
                    {
                        "scene_index": 2,
                        "kind": "body",
                        "narration": "The general rule of thumb is to have at least 3-6 months' worth of living expenses set aside in your emergency fund. So, if your monthly expenses are around ₹30,000, you should aim to save ₹90,000 to ₹1,80,000. Yeah, it's a lot, but trust me, it's worth it.",
                        "duration": 60,
                    },
                    {
                        "scene_index": 3,
                        "kind": "body",
                        "narration": "Now, you might be thinking, 'But why do I need an emergency fund when I have a steady income?' Well, life is unpredictable, my friend. You could lose your job, your car could break down, or you might need to pay for unexpected medical expenses. Having an emergency fund will give you peace of mind and help you avoid going into debt.",
                        "duration": 60,
                    },
                ],
                "outro": {
                    "narration": "So, that's it for today's video on emergency funds. If you're not already building one, start now!",
                    "duration": 18,
                },
            },
            "Emergency fund",
            "why young professionals need cash before investing",
        )
        self.assertIn("story_plan", payload)
        self.assertTrue(payload["story_plan"]["sections"])

    def test_generate_payload_uses_live_path_when_refined_payload_is_valid(self) -> None:
        raw_payload = {
            "hook": {
                "narration": "Did you know that paying just the minimum amount due on your credit card bill can cost you a whopping 20,000 rupees in interest over 5 years on a 50,000 rupee outstanding balance?",
                "duration": 6,
                "tension_type": "shocking_statistic",
            },
            "scenes": [
                {
                    "scene_index": 1,
                    "kind": "body",
                    "narration": "Let's talk about credit cards. They're convenient, they're widely accepted, and they offer rewards and cashback. But there's a dark side to credit cards that we don't often discuss - the minimum payment trap. When you get your credit card bill, you'll notice that there's a minimum amount due, which is usually around 5% of the total outstanding balance. Paying just this amount might seem like a good idea, but trust me, it's not.",
                    "duration": 60,
                },
                {
                    "scene_index": 2,
                    "kind": "body",
                    "narration": "For example, let's say you have a credit card with an outstanding balance of 50,000 rupees and an interest rate of 36% per annum. If you pay just the minimum amount due, which is 2,500 rupees, you'll be charged an interest of around 1,500 rupees. So, you're essentially paying 1,500 rupees to borrow 47,500 rupees for the next month. That's like paying 3% interest per month, or 36% interest per year.",
                    "duration": 60,
                },
                {
                    "scene_index": 3,
                    "kind": "body",
                    "narration": "Now, you might think that paying the minimum amount due is a good idea because it helps you avoid late payment fees. But the truth is, the interest charges will far outweigh any late payment fees. In fact, if you pay just the minimum amount due on a 50,000 rupee outstanding balance, it'll take you around 10 years to pay off the entire amount, and you'll end up paying a total of around 1.4 lakh rupees in interest and principal.",
                    "duration": 60,
                },
            ],
            "outro": {
                "narration": "Thanks for watching this episode of 10 Minute Finance. If you want to learn more about managing your credit card debt, check out our next video where we'll be discussing the best credit cards for balance transfers in India. Don't forget to like and subscribe for more personal finance content.",
                "duration": 18,
            },
            "suggested_titles": ["t1", "t2"],
            "suggested_description": "desc",
            "tags": ["credit cards", "debt trap"],
        }

        self.app.config.update({"LLM_PROVIDER": "groq", "GROQ_API_KEY": "test-key"})
        original = ScriptService._groq_script

        try:
            ScriptService._groq_script = lambda _self, topic, angle, prompt, api_key: raw_payload
            payload, source = self.service._generate_payload("Credit cards", "how minimum payments become a debt trap", "prompt")
        finally:
            ScriptService._groq_script = original

        self.assertEqual(source, "live Groq API")
        self.assertEqual(payload["meta"]["source"], "live_groq")
        self.assertIn("story_plan", payload)
