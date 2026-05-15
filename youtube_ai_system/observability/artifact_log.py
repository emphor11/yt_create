"""Artifact event helpers."""

from __future__ import annotations

from pathlib import Path

from .run_events import ArtifactEvent


def artifact_created(project_id: int | None, stage_name: str, path: str | Path, kind: str = "file") -> ArtifactEvent:
    return ArtifactEvent(
        project_id=project_id,
        stage_name=stage_name,
        artifact_path=str(path),
        artifact_kind=kind,
        status="created",
    )

