from pathlib import Path

from flask import Flask, abort, request, send_file

from .config import Config
from .db import close_db, init_app
from .routes.analytics import analytics_bp
from .routes.media import media_bp
from .routes.projects import projects_bp
from .routes.publish import publish_bp


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        instance_path=str(Path(__file__).resolve().parent / "instance"),
        instance_relative_config=True,
    )
    app.config.from_object(Config())

    if test_config:
        app.config.update(test_config)

    Path(app.config["INSTANCE_PATH"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["STORAGE_ROOT"]).mkdir(parents=True, exist_ok=True)
    for child in ("audio", "video", "images", "downloads"):
        Path(app.config["STORAGE_ROOT"], child).mkdir(parents=True, exist_ok=True)

    init_app(app)
    app.teardown_appcontext(close_db)

    app.register_blueprint(projects_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(publish_bp)
    app.register_blueprint(analytics_bp)

    @app.route("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.route("/local-file")
    def static_file_proxy():
        raw_path = request.args.get("file_path", "").strip()
        if not raw_path:
            abort(404)
        requested_path = Path(raw_path).resolve()
        storage_root = Path(app.config["STORAGE_ROOT"]).resolve()
        try:
            requested_path.relative_to(storage_root)
        except ValueError:
            abort(403)
        if not requested_path.exists():
            abort(404)
        return send_file(requested_path)

    return app
