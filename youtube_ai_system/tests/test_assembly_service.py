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
        self.assertIn("-b:v", command)
        self.assertIn("8M", command)
        self.assertIn("-maxrate", command)
        self.assertIn("10M", command)
        self.assertIn("-bufsize", command)
        self.assertIn("16M", command)
        self.assertIn("fps=30,setpts=N/(30*TB)", " ".join(command))
        self.assertIn("-fps_mode", command)
        self.assertIn("cfr", command)

    def test_concat_segments_forces_constant_30fps_master(self) -> None:
        segment_path = Path(self.temp_dir.name) / "scene-00.mp4"
        output_path = Path(self.temp_dir.name) / "assembled_timeline.mp4"
        segment_path.write_bytes(b"video")

        with patch.object(self.service, "_run_ffmpeg") as run:
            self.service._concat_segments("ffmpeg", [segment_path], output_path, Path(self.temp_dir.name))

        command = run.call_args.args[0]
        command_text = " ".join(command)
        self.assertIn("-i", command)
        self.assertIn("scene-00.mp4", command)
        self.assertIn("fps=30,setpts=PTS-STARTPTS", command_text)
        self.assertIn("aresample=async=1:first_pts=0", command_text)
        self.assertIn("concat=n=1:v=1:a=1", command_text)
        self.assertIn("-b:v", command)
        self.assertIn("8M", command)
        self.assertIn("-maxrate", command)
        self.assertIn("10M", command)
        self.assertIn("-bufsize", command)
        self.assertIn("16M", command)
        self.assertIn("-r", command)
        self.assertIn("30", command)
        self.assertIn("-fps_mode", command)
        self.assertIn("cfr", command)
        self.assertEqual(run.call_args.kwargs["cwd"], Path(self.temp_dir.name))

    def test_concat_segments_preserves_explicit_segment_order(self) -> None:
        segments = [Path(self.temp_dir.name) / f"scene-{index:02d}.mp4" for index in range(3)]
        for segment in segments:
            segment.write_bytes(b"video")

        with patch.object(self.service, "_run_ffmpeg") as run:
            self.service._concat_segments("ffmpeg", segments, Path(self.temp_dir.name) / "out.mp4", Path(self.temp_dir.name))

        command = run.call_args.args[0]
        input_names = [command[index + 1] for index, part in enumerate(command) if part == "-i"]
        self.assertEqual(input_names, ["scene-00.mp4", "scene-01.mp4", "scene-02.mp4"])
        self.assertIn("[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1", " ".join(command))

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

    def test_caption_burn_failure_still_exports_final_video(self) -> None:
        input_path = Path(self.temp_dir.name) / "timeline.mp4"
        captions_path = Path(self.temp_dir.name) / "captions.srt"
        output_path = Path(self.temp_dir.name) / "final.mp4"
        captions_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
        self.app.config.update({"MUSIC_ENABLED": False, "CAPTIONS_ENABLED": True})

        def fake_run(command, *args, **kwargs):
            if "subtitles=" in " ".join(command):
                raise RuntimeError("subtitle filter unavailable")

        with patch.object(self.service, "_run_ffmpeg", side_effect=fake_run) as run:
            result = self.service._apply_music_and_captions(
                "ffmpeg",
                input_path,
                captions_path,
                output_path,
            )

        self.assertEqual(result, output_path)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 2)
        self.assertIn("subtitles=", " ".join(commands[0]))
        self.assertIn("loudnorm=I=-16:TP=-1.5:LRA=11", " ".join(commands[1]))

    def test_run_ffmpeg_timeout_raises_clear_error(self) -> None:
        with patch(
            "youtube_ai_system.services.assembly_service.subprocess.run",
            side_effect=TimeoutExpired(cmd=["ffmpeg"], timeout=77),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed out after 77s"):
                self.service._run_ffmpeg(["ffmpeg", "-version"])


if __name__ == "__main__":
    unittest.main()
