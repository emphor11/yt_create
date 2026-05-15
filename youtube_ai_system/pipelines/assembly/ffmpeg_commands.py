"""FFmpeg command construction for final assembly."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AssemblyEncodingProfile:
    final_crf: str = "18"
    final_preset: str = "veryfast"
    target_loudness: str = "-16"
    true_peak: str = "-1.5"
    loudness_range: str = "11"
    final_fps: str = "30"
    final_video_bitrate: str = "8M"
    final_maxrate: str = "10M"
    final_bufsize: str = "16M"


class AssemblyFfmpegCommands:
    def __init__(self, profile: AssemblyEncodingProfile | None = None) -> None:
        self.profile = profile or AssemblyEncodingProfile()

    def concat_segments(self, ffmpeg_bin: str, segment_paths: list[Path], output_path: Path) -> list[str]:
        inputs: list[str] = []
        video_audio_filters: list[str] = []
        concat_inputs: list[str] = []
        for index, segment_path in enumerate(segment_paths):
            inputs.extend(["-i", segment_path.name])
            video_audio_filters.append(
                f"[{index}:v]fps={self.profile.final_fps},setpts=PTS-STARTPTS,format=yuv420p[v{index}];"
                f"[{index}:a]aresample=async=1:first_pts=0,asetpts=PTS-STARTPTS[a{index}]"
            )
            concat_inputs.append(f"[v{index}][a{index}]")
        filter_complex = (
            ";".join(video_audio_filters)
            + ";"
            + "".join(concat_inputs)
            + f"concat=n={len(segment_paths)}:v=1:a=1[v][a]"
        )
        return [
            ffmpeg_bin,
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-preset",
            self.profile.final_preset,
            "-b:v",
            self.profile.final_video_bitrate,
            "-maxrate",
            self.profile.final_maxrate,
            "-bufsize",
            self.profile.final_bufsize,
            "-r",
            self.profile.final_fps,
            "-fps_mode",
            "cfr",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            output_path.name,
        ]

    def render_scene_video(self, ffmpeg_bin: str, visual_path: str, audio_path: str, output_path: Path) -> list[str]:
        visual_suffix = Path(visual_path).suffix.lower()
        visual_input = ["-stream_loop", "-1", "-i", visual_path]
        if visual_suffix not in {".mp4", ".mov", ".mkv", ".webm"}:
            visual_input = ["-loop", "1", "-i", visual_path]
        return [
            ffmpeg_bin,
            "-y",
            *visual_input,
            "-i",
            audio_path,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
            "-vf",
            "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            self.profile.final_crf,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

    def color_clip(self, ffmpeg_bin: str, output_path: Path, duration_sec: float) -> list[str]:
        return [
            ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s=1920x1080:r=30:d={duration_sec}",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout=stereo:sample_rate=48000:d={duration_sec}",
            "-shortest",
            "-c:v",
            "libx264",
            "-preset",
            self.profile.final_preset,
            "-crf",
            self.profile.final_crf,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

    def silent_audio(self, ffmpeg_bin: str, input_path: Path, output_path: Path, duration_sec: float) -> list[str]:
        return [
            ffmpeg_bin,
            "-y",
            "-i",
            str(input_path),
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout=stereo:sample_rate=48000:d={duration_sec}",
            "-shortest",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_path),
        ]

    def mix_background_music(
        self,
        ffmpeg_bin: str,
        input_path: Path,
        music_path: Path,
        output_path: Path,
        *,
        duration: float,
        volume: float,
        fade_out_start: float,
    ) -> list[str]:
        return [
            ffmpeg_bin,
            "-y",
            "-i",
            str(input_path),
            "-stream_loop",
            "-1",
            "-i",
            str(music_path),
            "-filter_complex",
            (
                f"[1:a]atrim=0:{duration:.2f},afade=t=in:st=0:d=2,"
                f"afade=t=out:st={fade_out_start:.2f}:d=3,volume={volume}[music];"
                "[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            ),
            "-map",
            "0:v",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output_path),
        ]

    def burn_captions(self, ffmpeg_bin: str, input_path: Path, captions_path: Path, output_path: Path) -> list[str]:
        safe_srt = str(captions_path).replace("'", "\\'")
        return [
            ffmpeg_bin,
            "-y",
            "-i",
            str(input_path),
            "-vf",
            (
                f"fps={self.profile.final_fps},"
                f"subtitles='{safe_srt}':force_style='Fontsize=28,Outline=2,PrimaryColour=&HFFFFFF&,Alignment=2,MarginV=90'"
            ),
            "-c:v",
            "libx264",
            "-preset",
            self.profile.final_preset,
            "-b:v",
            self.profile.final_video_bitrate,
            "-maxrate",
            self.profile.final_maxrate,
            "-bufsize",
            self.profile.final_bufsize,
            "-r",
            self.profile.final_fps,
            "-fps_mode",
            "cfr",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

    def final_export(self, ffmpeg_bin: str, input_path: Path, output_path: Path) -> list[str]:
        return [
            ffmpeg_bin,
            "-y",
            "-i",
            str(input_path),
            "-filter_complex",
            (
                f"[0:v]fps={self.profile.final_fps},setpts=N/({self.profile.final_fps}*TB),"
                "eq=contrast=1.05:saturation=0.94:brightness=-0.01,format=yuv420p[v];"
                f"[0:a]aresample=async=1:first_pts=0,"
                f"loudnorm=I={self.profile.target_loudness}:TP={self.profile.true_peak}:LRA={self.profile.loudness_range}[a]"
            ),
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-preset",
            self.profile.final_preset,
            "-b:v",
            self.profile.final_video_bitrate,
            "-maxrate",
            self.profile.final_maxrate,
            "-bufsize",
            self.profile.final_bufsize,
            "-r",
            self.profile.final_fps,
            "-fps_mode",
            "cfr",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
