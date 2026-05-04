from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..db import get_db


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectRepository:
    def create_project(self, working_title: str) -> int:
        now = utcnow()
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO video_projects (
                working_title, state, created_at, updated_at
            ) VALUES (?, 'idea', ?, ?)
            """,
            (working_title, now, now),
        )
        db.commit()
        return int(cursor.lastrowid)

    def list_projects(self, include_discarded: bool = False) -> list[dict[str, Any]]:
        db = get_db()
        if include_discarded:
            rows = db.execute(
                "SELECT * FROM video_projects ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT * FROM video_projects
                WHERE state != 'discarded'
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_project(self, project_id: int) -> dict[str, Any] | None:
        row = get_db().execute(
            "SELECT * FROM video_projects WHERE id = ?", (project_id,)
        ).fetchone()
        return dict(row) if row else None

    def update_project(self, project_id: int, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = utcnow()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [project_id]
        db = get_db()
        db.execute(
            f"UPDATE video_projects SET {assignments} WHERE id = ?",
            values,
        )
        db.commit()

    def create_script_version(
        self,
        project_id: int,
        hook_json: dict[str, Any],
        outro_json: dict[str, Any],
        titles_json: list[str],
        description_text: str,
        tags_json: list[str],
        full_script_json: dict[str, Any],
        source_prompt: str,
    ) -> int:
        db = get_db()
        row = db.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 FROM script_versions WHERE video_project_id = ?",
            (project_id,),
        ).fetchone()
        version_number = int(row[0])
        now = utcnow()
        cursor = db.execute(
            """
            INSERT INTO script_versions (
                video_project_id, version_number, hook_json, outro_json, titles_json,
                description_text, tags_json, full_script_json, source_prompt,
                ai_generated_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                version_number,
                json.dumps(hook_json),
                json.dumps(outro_json),
                json.dumps(titles_json),
                description_text,
                json.dumps(tags_json),
                json.dumps(full_script_json),
                source_prompt,
                now,
                now,
                now,
            ),
        )
        db.commit()
        return int(cursor.lastrowid)

    def get_latest_script_version(self, project_id: int) -> dict[str, Any] | None:
        row = get_db().execute(
            """
            SELECT * FROM script_versions
            WHERE video_project_id = ?
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_script_version(self, script_version_id: int) -> dict[str, Any] | None:
        row = get_db().execute(
            "SELECT * FROM script_versions WHERE id = ?",
            (script_version_id,),
        ).fetchone()
        return dict(row) if row else None

    def update_script_version(self, script_version_id: int, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = utcnow()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [script_version_id]
        db = get_db()
        db.execute(
            f"UPDATE script_versions SET {assignments} WHERE id = ?",
            values,
        )
        db.commit()

    def replace_scenes(
        self,
        project_id: int,
        script_version_id: int,
        scenes: list[dict[str, Any]],
    ) -> None:
        db = get_db()
        now = utcnow()
        db.execute("DELETE FROM scenes WHERE video_project_id = ?", (project_id,))
        db.executemany(
            """
            INSERT INTO scenes (
                video_project_id, script_version_id, scene_order, kind, narration_text,
                visual_instruction, visual_type, visual_plan_json, visual_scene_json,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            [
                (
                    project_id,
                    script_version_id,
                    scene["scene_order"],
                    scene["kind"],
                    scene["narration_text"],
                    scene.get("visual_instruction"),
                    scene.get("visual_type"),
                    scene.get("visual_plan_json"),
                    scene.get("visual_scene_json"),
                    now,
                    now,
                )
                for scene in scenes
            ],
        )
        db.commit()

    def list_scenes(self, project_id: int) -> list[dict[str, Any]]:
        rows = get_db().execute(
            """
            SELECT * FROM scenes
            WHERE video_project_id = ?
            ORDER BY scene_order ASC, id ASC
            """,
            (project_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_scene(self, scene_id: int) -> dict[str, Any] | None:
        row = get_db().execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
        return dict(row) if row else None

    def update_scene(self, scene_id: int, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = utcnow()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [scene_id]
        db = get_db()
        db.execute(f"UPDATE scenes SET {assignments} WHERE id = ?", values)
        db.commit()

    def create_publish_record(self, project_id: int, privacy_status: str) -> int:
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO publish_records (
                video_project_id, privacy_status
            ) VALUES (?, ?)
            """,
            (project_id, privacy_status),
        )
        db.commit()
        return int(cursor.lastrowid)

    def get_publish_record(self, project_id: int) -> dict[str, Any] | None:
        row = get_db().execute(
            """
            SELECT * FROM publish_records
            WHERE video_project_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        return dict(row) if row else None

    def update_publish_record(self, record_id: int, **fields: Any) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [record_id]
        db = get_db()
        db.execute(f"UPDATE publish_records SET {assignments} WHERE id = ?", values)
        db.commit()

    def add_run_log(
        self,
        stage_name: str,
        status: str,
        message: str,
        project_id: int | None = None,
    ) -> None:
        db = get_db()
        db.execute(
            """
            INSERT INTO run_logs (
                video_project_id, stage_name, status, message, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, stage_name, status, message, utcnow()),
        )
        db.commit()

    def list_run_logs(self, project_id: int) -> list[dict[str, Any]]:
        rows = get_db().execute(
            """
            SELECT * FROM run_logs
            WHERE video_project_id = ?
            ORDER BY id DESC
            """,
            (project_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def add_analytics_snapshot(
        self,
        project_id: int,
        snapshot_day: str,
        metrics: dict[str, Any],
    ) -> int:
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO analytics_snapshots (
                video_project_id, snapshot_day, views, impressions, impression_ctr,
                average_view_duration_sec, average_view_percentage, captured_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                snapshot_day,
                metrics.get("views"),
                metrics.get("impressions"),
                metrics.get("impression_ctr"),
                metrics.get("average_view_duration_sec"),
                metrics.get("average_view_percentage"),
                utcnow(),
            ),
        )
        db.commit()
        return int(cursor.lastrowid)

    def list_analytics_rows(self) -> list[dict[str, Any]]:
        rows = get_db().execute(
            """
            SELECT vp.id AS project_id,
                   vp.selected_title,
                   vp.working_title,
                   pr.published_at,
                   MAX(CASE WHEN a.snapshot_day = 'D1' THEN a.views END) AS d1_views,
                   MAX(CASE WHEN a.snapshot_day = 'D7' THEN a.views END) AS d7_views,
                   MAX(CASE WHEN a.snapshot_day = 'D28' THEN a.views END) AS d28_views,
                   MAX(a.impression_ctr) AS best_ctr,
                   MAX(a.average_view_duration_sec) AS best_average_view_duration
            FROM video_projects vp
            LEFT JOIN publish_records pr ON pr.video_project_id = vp.id
            LEFT JOIN analytics_snapshots a ON a.video_project_id = vp.id
            WHERE vp.state IN ('scheduled', 'published', 'analyzed')
            GROUP BY vp.id, vp.selected_title, vp.working_title, pr.published_at
            ORDER BY pr.published_at DESC NULLS LAST, vp.id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
