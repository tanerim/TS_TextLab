"""Logging setup for development and packaged application diagnostics."""

from __future__ import annotations

import logging

from app.resource_manager import user_data_root


def configure_logging() -> None:
    log_dir = user_data_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "ts-textlab.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

