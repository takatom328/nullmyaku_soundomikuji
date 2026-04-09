from pathlib import Path
from threading import Thread

from .store import TelemetryStore
from ..utils.config import WebConfig


def load_index() -> str:
    static_path = Path(__file__).with_name("static") / "index.html"
    return static_path.read_text(encoding="utf-8")


def create_app(store):
    try:
        from flask import Flask, jsonify
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Flask is not installed. Install it before enabling the dashboard."
        ) from exc

    static_folder = Path(__file__).with_name("static")
    app = Flask(__name__, static_folder=str(static_folder), static_url_path="/static")

    @app.route("/")
    def index() -> str:
        return load_index()

    @app.route("/api/telemetry")
    def telemetry():
        latest = store.latest()
        if not latest:
            latest = {
                "audio_features": {},
                "imu_features": {},
                "state": {},
                "ai": {},
                "session": {},
                "printer": {},
                "history": [],
            }
        latest["history"] = store.history()
        return jsonify(latest)

    return app


def start_server_in_background(store: TelemetryStore, config: WebConfig) -> Thread:
    app = create_app(store)
    thread = Thread(
        target=app.run,
        kwargs={
            "host": config.host,
            "port": config.port,
            "debug": False,
            "use_reloader": False,
        },
        daemon=True,
    )
    thread.start()
    return thread
