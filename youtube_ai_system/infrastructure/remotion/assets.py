from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping


class RemotionAssetStager:
    """Stages local files into Remotion's public asset tree before rendering."""

    def __init__(self, file_path_prop_keys: Iterable[str], default_theme: Mapping[str, str]) -> None:
        self.file_path_prop_keys = set(file_path_prop_keys)
        self.default_theme = dict(default_theme)

    def props_for_render(self, spec: Any, project_path: Path) -> dict[str, Any]:
        props = dict(spec.props)
        props.setdefault("theme", dict(self.default_theme))
        props = self.stage_file_props(project_path, props)
        if spec.source_asset_path is not None:
            props["videoPath"] = self.stage_public_asset(project_path, spec.source_asset_path)
        return props

    def stage_file_props(self, project_path: Path, value: object, key: str = "") -> object:
        if isinstance(value, dict):
            return {
                child_key: self.stage_file_props(project_path, child_value, child_key)
                for child_key, child_value in value.items()
            }
        if isinstance(value, list):
            return [self.stage_file_props(project_path, item, key) for item in value]
        if isinstance(value, str) and key in self.file_path_prop_keys:
            return self.stage_if_existing_file(project_path, value, key)
        return value

    def stage_if_existing_file(self, project_path: Path, value: str, key: str) -> str:
        source_path = Path(value).expanduser()
        if not source_path.exists() or not source_path.is_file():
            return value
        asset_subdir = self.asset_subdir_for_key(key)
        return self.stage_public_asset(project_path, source_path.resolve(), asset_subdir=asset_subdir)

    def asset_subdir_for_key(self, key: str) -> str:
        lowered = key.lower()
        if "audio" in lowered:
            return "audio"
        if "image" in lowered:
            return "images"
        return "broll"

    def stage_public_asset(self, project_path: Path, source_path: Path, asset_subdir: str = "broll") -> str:
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
