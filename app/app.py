import atexit
import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask

from container import AppContainer
from routes import register_routes


def _is_debug_mode_enabled() -> bool:
    return str(os.getenv("FLASK_DEBUG", "0")).strip().lower() in {"1", "true", "yes", "on"}


def _should_start_workers() -> bool:
    debug_enabled = _is_debug_mode_enabled()
    if not debug_enabled:
        return True
    return os.getenv("WERKZEUG_RUN_MAIN") == "true"


def _configure_db_audit_logger(app: Flask):
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, "db_operations.log")

    db_logger = logging.getLogger("db_audit")
    db_logger.setLevel(logging.INFO)
    db_logger.propagate = False

    if not db_logger.handlers:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        db_logger.addHandler(handler)

    app.logger.info("db_audit_log_ready path=%s", log_path)


def create_app():
    app = Flask(__name__)
    _configure_db_audit_logger(app)
    container = AppContainer()
    register_routes(app, container)

    if _should_start_workers():
        container.start_background_jobs(logger=app.logger)

    atexit.register(container.shutdown)
    app.extensions["app_container"] = container
    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        debug=_is_debug_mode_enabled(),
    )
