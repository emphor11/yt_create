from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from flask import current_app

from .render_spec_service import RenderSpec


class RemotionUnavailableError(RuntimeError):
    pass


FILE_PATH_PROP_KEYS = {
    "audio_file",
    "audioFile",
    "videoPath",
    "video_path",
    "imagePath",
    "image_path",
    "backgroundVideo",
    "background_video",
    "sourceVideo",
    "source_video",
}

DEFAULT_RENDER_THEME = {
    "background": "#0A0A14",
    "primary": "#FF9F1C",
    "negative": "#E63946",
    "positive": "#2EC4B6",
    "neutral": "#4361EE",
    "textPrimary": "#FFFFFF",
    "textSecondary": "rgba(255,255,255,0.6)",
}


class RemotionService:
    """Thin Python wrapper around the sibling Remotion render project."""

    def render_video(self, spec: RenderSpec, output_path: Path) -> Path:
        self._render(spec, output_path)
        return output_path

    def render_still(self, spec: RenderSpec, output_path: Path, frame: int = 0) -> Path:
        self._render(spec, output_path, still=True, frame=frame)
        return output_path

    def is_available(self) -> bool:
        if not current_app.config.get("REMOTION_ENABLED", True):
            return False
        project_path = Path(current_app.config["REMOTION_PROJECT_PATH"])
        local_remotion = project_path / "node_modules" / ".bin" / "remotion"
        return (
            project_path.exists()
            and local_remotion.exists()
            and shutil.which(str(current_app.config.get("REMOTION_CLI", "npx"))) is not None
        )

    def _render(self, spec: RenderSpec, output_path: Path, still: bool = False, frame: int = 0) -> None:
        if not self.is_available():
            raise RemotionUnavailableError("Remotion is not available or REMOTION_ENABLED=false.")

        project_path = Path(current_app.config["REMOTION_PROJECT_PATH"])
        entry = str(current_app.config.get("REMOTION_ENTRY", "src/index.ts"))
        cli = str(current_app.config.get("REMOTION_CLI", "npx"))
        timeout_sec = int(current_app.config.get("REMOTION_RENDER_TIMEOUT", 300))
        concurrency = int(current_app.config.get("REMOTION_CONCURRENCY", 2))
        render_output_path = self._still_output_path(output_path) if still else output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        props = self._props_for_render(spec, project_path)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as props_file:
            json.dump(props, props_file)
            props_path = Path(props_file.name)

        started_at = time.monotonic()
        try:
            if still:
                command = [
                    cli,
                    "remotion",
                    "still",
                    entry,
                    spec.composition,
                    str(render_output_path),
                    f"--props={props_path}",
                    "--log=error",
                ]
            else:
                command = [
                    cli,
                    "remotion",
                    "render",
                    entry,
                    spec.composition,
                    str(output_path),
                    f"--props={props_path}",
                    "--codec=h264",
                    "--crf=18",
                    "--pixel-format=yuv420p",
                    f"--concurrency={concurrency}",
                    "--log=error",
                ]
            subprocess.run(
                command,
                cwd=project_path,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            elapsed = round(time.monotonic() - started_at, 1)
            current_app.logger.info(
                "Remotion rendered %s -> %s in %ss",
                spec.composition,
                render_output_path.name if still else output_path.name,
                elapsed,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Remotion render timed out after {timeout_sec}s for {spec.composition}. "
                "Check for infinite loops or hanging components."
            ) from exc
        except FileNotFoundError as exc:
            raise RemotionUnavailableError("Remotion CLI is not installed. Run npm install in your Remotion project.") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            if len(detail) > 800:
                detail = detail[:800].rstrip() + "...[truncated]"
            elapsed = round(time.monotonic() - started_at, 1)
            current_app.logger.error("Remotion failed %s after %ss: %s", spec.composition, elapsed, detail)
            raise RuntimeError(f"Remotion render failed for {spec.composition}: {detail}") from exc
        finally:
            props_path.unlink(missing_ok=True)

    def _props_for_render(self, spec: RenderSpec, project_path: Path) -> dict:
        props = dict(spec.props)
        props.setdefault("theme", dict(DEFAULT_RENDER_THEME))
        props = self._stage_file_props(project_path, props)
        if spec.source_asset_path is not None:
            props["videoPath"] = self._stage_public_asset(project_path, spec.source_asset_path)
        return props

    def _stage_file_props(self, project_path: Path, value: object, key: str = "") -> object:
        if isinstance(value, dict):
            return {child_key: self._stage_file_props(project_path, child_value, child_key) for child_key, child_value in value.items()}
        if isinstance(value, list):
            return [self._stage_file_props(project_path, item, key) for item in value]
        if isinstance(value, str) and key in FILE_PATH_PROP_KEYS:
            return self._stage_if_existing_file(project_path, value, key)
        return value

    def _stage_if_existing_file(self, project_path: Path, value: str, key: str) -> str:
        source_path = Path(value).expanduser()
        if not source_path.exists() or not source_path.is_file():
            return value
        asset_subdir = self._asset_subdir_for_key(key)
        return self._stage_public_asset(project_path, source_path.resolve(), asset_subdir=asset_subdir)

    def _asset_subdir_for_key(self, key: str) -> str:
        lowered = key.lower()
        if "audio" in lowered:
            return "audio"
        if "image" in lowered:
            return "images"
        return "broll"

    def _still_output_path(self, output_path: Path) -> Path:
        if output_path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            return output_path
        return output_path.with_suffix(".png")

    def _stage_public_asset(self, project_path: Path, source_path: Path, asset_subdir: str = "broll") -> str:
        source_path = source_path.expanduser().resolve()
        if not source_path.exists():
            raise RuntimeError(f"Remotion source asset does not exist: {source_path}")
        stat = source_path.stat()
        digest = hashlib.sha1(f"{source_path}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")).hexdigest()[:12]
        suffix = source_path.suffix or ".mp4"
        relative_path = Path("render-assets") / asset_subdir / f"{source_path.stem}-{digest}{suffix}"
        destination = project_path / "public" / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or destination.stat().st_size != stat.st_size:
            shutil.copy2(source_path, destination)
        return relative_path.as_posix()
