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
- demo media generation with local WAV and SVG assets
- 60% dynamic visual gate
- assembly placeholder manifest
- final review metadata flow
- publish record + schedule metadata
- analytics snapshot table

## What still needs external tooling or credentials

- Flask installation
- ffmpeg-backed assembly
- real Claude, YouTube, Pexels, and Pixabay integrations
- real Edge TTS / Whisper / chart rendering

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
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
