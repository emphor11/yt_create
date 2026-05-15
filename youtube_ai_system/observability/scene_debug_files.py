"""File persistence helpers for scene debug traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .scene_debug_support import utcnow


class SceneDebugFileStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def project_dir(self, project_id: int) -> Path:
        return self.root / f"project-{int(project_id)}"

    def scene_path(self, project_id: int, scene_order: int, *, replay_stage: str = "") -> Path:
        name = (
            f"scene-{int(scene_order):02d}.json"
            if not replay_stage
            else f"scene-{int(scene_order):02d}-replay-{replay_stage}.json"
        )
        return self.project_dir(project_id) / name

    def write_scene_payload(self, project_id: int, scene_order: int, payload: dict[str, Any], *, replay_stage: str = "") -> Path:
        path = self.scene_path(project_id, scene_order, replay_stage=replay_stage)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def read_scene_payload(self, project_id: int, scene_order: int, *, replay_stage: str = "") -> dict[str, Any] | None:
        path = self.scene_path(project_id, scene_order, replay_stage=replay_stage)
        return self.read_payload(path)

    def read_latest_scene_payload(self, project_id: int, scene_order: int) -> dict[str, Any] | None:
        payload = self.read_scene_payload(project_id, scene_order)
        if payload is not None:
            return payload
        project_dir = self.project_dir(project_id)
        candidates = sorted(
            project_dir.glob(f"scene-{int(scene_order):02d}*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in candidates:
            payload = self.read_payload(path)
            if payload is not None:
                return payload
        return None

    def read_project_payloads(self, project_id: int) -> list[tuple[Path, dict[str, Any]]]:
        project_dir = self.project_dir(project_id)
        if not project_dir.exists():
            return []
        payloads: list[tuple[Path, dict[str, Any]]] = []
        for path in sorted(project_dir.glob("scene-*.json")):
            payload = self.read_payload(path)
            if payload is not None:
                payloads.append((path, payload))
        return payloads

    def read_payload(self, path: Path) -> dict[str, Any] | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def write_index(self, project_id: int, scenes: list[dict[str, Any]]) -> None:
        project_dir = self.project_dir(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        index_path = project_dir / "index.json"
        index_path.write_text(
            json.dumps({"project_id": project_id, "updated_at": utcnow(), "scenes": scenes}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
