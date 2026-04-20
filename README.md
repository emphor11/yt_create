# YTCreate

Personal-use AI-assisted YouTube production app built with Flask and SQLite.

## What works in this scaffold

- project creation and listing
- database schema creation on boot
- append-only run logging
- strict state machine transitions
- manual topic selection with advisory comparable videos
- demo script generation with hook validation
- mandatory human edit before approval
- scene creation on script approval
- V2 media generation with provider-based narration, Remotion render specs, and local fallbacks
- 60% dynamic visual gate
- timeline assembly with intro, transitions, end card, optional captions, and optional music
- final review metadata flow
- publish record + schedule metadata
- analytics snapshot table

## What still needs external tooling or credentials

- Flask installation
- ffmpeg-backed assembly
- real Claude, YouTube, Pexels, and Pixabay integrations
- Kokoro system dependency on macOS: `brew install espeak`
- Remotion browser setup on first render
- optional Whisper CLI for transcription-grade captions

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd remotion_templates && npm install && cd ..
python app.py
```

Kokoro requires Python 3.10-3.12. If your default Python is newer, use Python 3.12:

```bash
python3.12 -m venv .venv312
source .venv312/bin/activate
pip install -r requirements.txt
python app.py
```

Default local URL:

```bash
http://127.0.0.1:8000
```

Optional custom port:

```bash
FLASK_RUN_PORT=8010 python app.py
```

## Local environment

The app loads values from a project-level `.env` file automatically.

1. Open `.env`
2. Add your fresh local keys
3. Restart the app

Example variables:

```bash
YOUTUBE_API_KEY=your_youtube_data_api_key
CLAUDE_API_KEY=your_claude_api_key
VOICE_MODE=demo
FLASK_RUN_PORT=8000
```

## V2 production settings

Use these when you want the production pipeline instead of demo-safe fallbacks:

```bash
VOICE_MODE=production
VOICE_PROVIDER=kokoro
VOICE_FALLBACK_PROVIDER=gtts
KOKORO_NARRATOR=male
KOKORO_VOICE_MALE=am_eric
REMOTION_ENABLED=true
CAPTIONS_ENABLED=true
MUSIC_ENABLED=true
BACKGROUND_MUSIC_PATH=/absolute/path/to/music.mp3
```

If Remotion or Kokoro is unavailable, YTCreate logs the failure and falls back so the project flow can still complete.
