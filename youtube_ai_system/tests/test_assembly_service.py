import tempfile
import unittest
from pathlib import Path
from subprocess import TimeoutExpired
from unittest.mock import patch

from youtube_ai_system import create_app
from youtube_ai_system.db import close_db
from youtube_ai_system.services.assembly_service import AssemblyService


class AssemblyServiceTestCase(unittest.TestCase):
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
                "ASSEMBLY_FFMPEG_TIMEOUT": 77,
            }
        )
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.service = AssemblyService()

    def tearDown(self) -> None:
        close_db()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def test_final_export_uses_youtube_quality_and_loudness_flags(self) -> None:
        with patch.object(self.service, "_run_ffmpeg") as run:
            self.service._final_export(
                "ffmpeg",
                Path(self.temp_dir.name) / "input.mp4",
                Path(self.temp_dir.name) / "final.mp4",
            )

        command = run.call_args.args[0]
        self.assertIn("loudnorm=I=-16:TP=-1.5:LRA=11", " ".join(command))
        self.assertIn("-pix_fmt", command)
        self.assertIn("yuv420p", command)
        self.assertIn("-movflags", command)
        self.assertIn("+faststart", command)
        self.assertIn("-crf", command)
        self.assertIn("18", command)

    def test_music_and_caption_pipeline_runs_before_final_export(self) -> None:
        input_path = Path(self.temp_dir.name) / "timeline.mp4"
        captions_path = Path(self.temp_dir.name) / "captions.srt"
        music_path = Path(self.temp_dir.name) / "music.mp3"
        captions_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
        music_path.write_bytes(b"music")
        self.app.config.update(
            {
                "MUSIC_ENABLED": True,
                "CAPTIONS_ENABLED": True,
                "BACKGROUND_MUSIC_PATH": str(music_path),
                "BACKGROUND_MUSIC_VOLUME": 0.08,
            }
        )

        with patch.object(self.service, "_probe_duration", return_value=12.0), patch.object(self.service, "_run_ffmpeg") as run:
            self.service._apply_music_and_captions(
                "ffmpeg",
                input_path,
                captions_path,
                Path(self.temp_dir.name) / "final.mp4",
            )

        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 3)
        self.assertIn("afade=t=out", " ".join(commands[0]))
        self.assertIn("amix=inputs=2", " ".join(commands[0]))
        self.assertIn("subtitles=", " ".join(commands[1]))
        self.assertIn("loudnorm=I=-16:TP=-1.5:LRA=11", " ".join(commands[2]))

    def test_run_ffmpeg_timeout_raises_clear_error(self) -> None:
        with patch(
            "youtube_ai_system.services.assembly_service.subprocess.run",
            side_effect=TimeoutExpired(cmd=["ffmpeg"], timeout=77),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed out after 77s"):
                self.service._run_ffmpeg(["ffmpeg", "-version"])


if __name__ == "__main__":
    unittest.main()
