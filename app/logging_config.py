"""Centralized logging configuration for Almanac Africa AI."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask


def configure_logging(app: Flask) -> None:
    """Attach console and/or rotating file handlers based on app config."""
    log_level_name = app.config.get("LOG_LEVEL", "INFO")
    log_level = getattr(logging, str(log_level_name).upper(), logging.INFO)

    # Avoid duplicate handlers when the factory is called more than once
    # (e.g. Flask reloader, tests).
    root = logging.getLogger()
    if root.handlers:
        app.logger.setLevel(log_level)
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handlers: list[logging.Handler] = []

    if app.config.get("LOG_TO_STDOUT", True):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(log_level)
        handlers.append(stream_handler)

    log_dir: Path = app.config.get("LOG_DIR")
    if log_dir and not app.config.get("TESTING"):
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "liminal.log",
            maxBytes=2_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        handlers.append(file_handler)

    for handler in handlers:
        root.addHandler(handler)

    root.setLevel(log_level)
    app.logger.setLevel(log_level)
    app.logger.info("Logging configured (level=%s)", log_level_name)
