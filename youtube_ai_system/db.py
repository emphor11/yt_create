import sqlite3
from pathlib import Path

from flask import current_app, g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db_path = Path(current_app.config["DATABASE_PATH"])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    db.executescript(schema_path.read_text())
    _run_migrations(db)
    db.commit()


def init_app(app) -> None:
    @app.cli.command("init-db")
    def init_db_command() -> None:
        init_db()
        print("Initialized the database.")

    with app.app_context():
        init_db()


def _run_migrations(db: sqlite3.Connection) -> None:
    project_columns = set()
    for row in db.execute("PRAGMA table_info(video_projects)").fetchall():
        try:
            project_columns.add(row["name"])
        except (TypeError, IndexError, KeyError):
            project_columns.add(row[1])

    scene_columns = set()
    for row in db.execute("PRAGMA table_info(scenes)").fetchall():
        try:
            scene_columns.add(row["name"])
        except (TypeError, IndexError, KeyError):
            scene_columns.add(row[1])

    _ensure_column(db, "video_projects", "target_duration_minutes INTEGER", project_columns)
    _ensure_column(db, "video_projects", "channel_niche TEXT", project_columns)
    _ensure_column(db, "video_projects", "script_tone TEXT", project_columns)
    _ensure_column(db, "scenes", "subtitle_path TEXT", scene_columns)
    _ensure_column(db, "scenes", "visual_plan_json TEXT DEFAULT NULL", scene_columns)
    _ensure_column(db, "scenes", "audio_source TEXT", scene_columns)
    _ensure_column(db, "scenes", "visual_source TEXT", scene_columns)


def _ensure_column(
    db: sqlite3.Connection,
    table_name: str,
    column_definition: str,
    existing_columns: set[str],
) -> None:
    column_name = column_definition.split()[0]
    if column_name in existing_columns:
        return
    try:
        db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}")
    except sqlite3.OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise
