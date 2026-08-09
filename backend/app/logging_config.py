"""Structured logging setup: console + rotating file, no secrets logged."""
from __future__ import annotations

import logging
import logging.handlers

from .config import LOG_DIR

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:  # already configured (e.g. under pytest/uvicorn reload)
        return
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(console)

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / "rs3_tracker.log", maxBytes=5 * 1024 * 1024, backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(file_handler)
    except OSError:  # pragma: no cover - log dir not writable
        root.warning("Could not create log file; console logging only.")

    # Quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
