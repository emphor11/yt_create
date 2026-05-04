CREATE TABLE IF NOT EXISTS video_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT,
    angle TEXT,
    target_duration_minutes INTEGER,
    channel_niche TEXT,
    script_tone TEXT,
    working_title TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'idea',
    final_video_path TEXT,
    selected_title TEXT,
    selected_description TEXT,
    selected_thumbnail_path TEXT,
    youtube_video_id TEXT,
    scheduled_publish_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS script_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_project_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    hook_json TEXT,
    outro_json TEXT,
    titles_json TEXT,
    description_text TEXT,
    tags_json TEXT,
    full_script_json TEXT NOT NULL,
    source_prompt TEXT,
    ai_generated_at TEXT,
    user_edited_at TEXT,
    approved_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(video_project_id) REFERENCES video_projects(id) ON DELETE CASCADE,
    UNIQUE(video_project_id, version_number)
);

CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_project_id INTEGER NOT NULL,
    script_version_id INTEGER NOT NULL,
    scene_order INTEGER NOT NULL,
    kind TEXT NOT NULL,
    narration_text TEXT NOT NULL,
    visual_instruction TEXT,
    visual_type TEXT,
    audio_path TEXT,
    audio_duration_sec REAL,
    subtitle_path TEXT,
    visual_path TEXT,
    visual_plan_json TEXT DEFAULT NULL,
    visual_scene_json TEXT DEFAULT NULL,
    audio_source TEXT,
    visual_source TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(video_project_id) REFERENCES video_projects(id) ON DELETE CASCADE,
    FOREIGN KEY(script_version_id) REFERENCES script_versions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS publish_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_project_id INTEGER NOT NULL,
    privacy_status TEXT,
    publish_at TEXT,
    youtube_video_id TEXT,
    uploaded_at TEXT,
    published_at TEXT,
    FOREIGN KEY(video_project_id) REFERENCES video_projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS run_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_project_id INTEGER,
    stage_name TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(video_project_id) REFERENCES video_projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS analytics_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_project_id INTEGER NOT NULL,
    snapshot_day TEXT NOT NULL,
    views INTEGER,
    impressions INTEGER,
    impression_ctr REAL,
    average_view_duration_sec REAL,
    average_view_percentage REAL,
    captured_at TEXT NOT NULL,
    FOREIGN KEY(video_project_id) REFERENCES video_projects(id) ON DELETE CASCADE
);
