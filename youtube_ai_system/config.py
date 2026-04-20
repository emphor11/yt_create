import os
from pathlib import Path


def load_local_env() -> None:
    root_dir = Path(__file__).resolve().parent.parent
    env_path = root_dir / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_local_env()


class Config:
    BASE_DIR = Path(__file__).resolve().parent
    INSTANCE_PATH = BASE_DIR / "instance"
    STORAGE_ROOT = BASE_DIR / "storage"
    DATABASE_PATH = INSTANCE_PATH / "database.db"

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "auto").lower()
    CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
    CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-3-5-sonnet-latest")
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("groq_api_key")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
    YOUTUBE_CLIENT_SECRETS = os.environ.get("YOUTUBE_CLIENT_SECRETS")
    YOUTUBE_TOKEN_PATH = os.environ.get(
        "YOUTUBE_TOKEN_PATH", str(INSTANCE_PATH / "youtube_token.json")
    )
    PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
    PEXELS_API_TIMEOUT = int(os.environ.get("PEXELS_API_TIMEOUT", "15"))
    PEXELS_SEARCH_LIMIT = int(os.environ.get("PEXELS_SEARCH_LIMIT", "10"))
    PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")
    VOICE_PROVIDER = os.environ.get("VOICE_PROVIDER", "kokoro").lower()
    VOICE_FALLBACK_PROVIDER = os.environ.get("VOICE_FALLBACK_PROVIDER", "gtts").lower()
    KOKORO_LANG_CODE = os.environ.get("KOKORO_LANG_CODE", "a")
    KOKORO_VOICE_MALE = os.environ.get("KOKORO_VOICE_MALE", "am_eric")
    KOKORO_VOICE_FEMALE = os.environ.get("KOKORO_VOICE_FEMALE", "af_sarah")
    KOKORO_NARRATOR = os.environ.get("KOKORO_NARRATOR", "male").lower()
    GTTS_LANG = os.environ.get("GTTS_LANG", "en")
    EDGE_TTS_VOICE = os.environ.get("EDGE_TTS_VOICE", "en-IN-PrabhatNeural")
    EDGE_TTS_VOICE_ALT = os.environ.get("EDGE_TTS_VOICE_ALT", "en-IN-NeerjaNeural")
    EDGE_TTS_RATE = os.environ.get("EDGE_TTS_RATE", "+0%")
    EDGE_TTS_CONNECT_TIMEOUT = int(os.environ.get("EDGE_TTS_CONNECT_TIMEOUT", "4"))
    EDGE_TTS_RECEIVE_TIMEOUT = int(os.environ.get("EDGE_TTS_RECEIVE_TIMEOUT", "12"))
    EDGE_TTS_CLI_TIMEOUT = int(os.environ.get("EDGE_TTS_CLI_TIMEOUT", "20"))
    VOICE_MODE = os.environ.get("VOICE_MODE", "demo")

    CHANNEL_STYLE = os.environ.get("CHANNEL_STYLE", "standard").lower()
    VISUAL_BEAT_MAX_SEC = float(os.environ.get("VISUAL_BEAT_MAX_SEC", "4.0"))
    VISUAL_BEAT_MIN_SEC = float(os.environ.get("VISUAL_BEAT_MIN_SEC", "2.5"))
    VISUAL_DEBUG = os.environ.get("VISUAL_DEBUG", "false").lower() == "true"
    MEME_ASSET_DIR = os.environ.get("MEME_ASSET_DIR", "")

    CAPTIONS_ENABLED = os.environ.get(
        "CAPTIONS_ENABLED",
        "true" if CHANNEL_STYLE == "ten_minute_finance" else "false",
    ).lower() == "true"
    MUSIC_ENABLED = os.environ.get("MUSIC_ENABLED", "false").lower() == "true"
    REMOTION_ENABLED = os.environ.get("REMOTION_ENABLED", "true").lower() == "true"
    REMOTION_PROJECT_PATH = Path(
        os.environ.get("REMOTION_PROJECT_PATH", str(BASE_DIR.parent / "remotion_templates"))
    )
    REMOTION_ENTRY = os.environ.get("REMOTION_ENTRY", "src/index.ts")
    REMOTION_CLI = os.environ.get("REMOTION_CLI", "npx")
    WHISPER_CLI = os.environ.get("WHISPER_CLI", "whisper")
    CAPTION_TOOL = os.environ.get("CAPTION_TOOL", "whisper").lower()
    BACKGROUND_MUSIC_PATH = os.environ.get("BACKGROUND_MUSIC_PATH")
    BACKGROUND_MUSIC_VOLUME = float(os.environ.get("BACKGROUND_MUSIC_VOLUME", "0.08"))
    DEMO_MODE = os.environ.get("DEMO_MODE", "true").lower() == "true"

    TOPIC_LOOKBACK_DAYS = 7
    TOPIC_RESULT_LIMIT = 5
    DYNAMIC_VISUAL_THRESHOLD = 0.6
    ALLOWED_VISUAL_TYPES = ("graph", "broll", "motion_text")
    ALLOWED_SCENE_KINDS = ("hook", "body", "outro")
