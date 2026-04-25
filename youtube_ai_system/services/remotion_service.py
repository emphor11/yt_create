from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from flask import current_app

from .render_spec_service import RenderSpec


class RemotionUnavailableError(RuntimeError):
    pass


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
        output_path.parent.mkdir(parents=True, exist_ok=True)
        props = self._props_for_render(spec, project_path)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as props_file:
            json.dump(props, props_file)
            props_path = Path(props_file.name)

        try:
            if still:
                command = [
                    cli,
                    "remotion",
                    "still",
                    entry,
                    spec.composition,
                    str(output_path),
                    f"--props={props_path}",
                    f"--frame={frame}",
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
                ]
            subprocess.run(command, cwd=project_path, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise RemotionUnavailableError("Remotion CLI is not installed.") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            raise RuntimeError(f"Remotion render failed for {spec.composition}: {detail}") from exc
        finally:
            props_path.unlink(missing_ok=True)

    def _props_for_render(self, spec: RenderSpec, project_path: Path) -> dict:
        props = dict(spec.props)
        if spec.composition == "VideoRenderer":
            scenes = []
            for scene in props.get("scenes", []):
                scene_copy = dict(scene)
                audio_file = str(scene_copy.get("audio_file") or "").strip()
                if audio_file:
                    staged_audio = self._stage_public_asset(
                        project_path,
                        Path(audio_file).expanduser().resolve(),
                        asset_subdir="audio",
                    )
                    scene_copy["audio_file"] = staged_audio
                scenes.append(scene_copy)
            props["scenes"] = scenes
        if spec.composition == "BrollOverlay" and spec.source_asset_path is not None:
            props["videoPath"] = self._stage_public_asset(project_path, spec.source_asset_path)
        return props

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
