import os

from youtube_ai_system import create_app

app = create_app()


if __name__ == "__main__":
    host = os.environ.get("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_RUN_PORT", "8000"))
    app.run(debug=True, host=host, port=port)
