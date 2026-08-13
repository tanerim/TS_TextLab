"""Locate resources in development and PyInstaller builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from app.errors import ResourceNotFoundError


def app_root() -> Path:
    """Return the filesystem root for dev mode or the PyInstaller temp bundle."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def user_data_root() -> Path:
    """Return a writable app data directory for logs and future settings."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "TS TextLab"


def resolve_resource(*parts: str) -> Path:
    return app_root().joinpath(*parts)


def resolve_model_dir() -> Path:
    """Find the bundled spaCy POS tagger model without absolute machine paths."""
    env_path = os.environ.get("TS_TEXTLAB_MODEL_DIR")
    candidates = []
    if env_path:
        candidates.append(Path(env_path).expanduser())

    candidates.extend(
        [
            resolve_resource("models", "ts_postagger_model"),
            resolve_resource("ts_pos_tagger", "model-best"),
        ]
    )

    for candidate in candidates:
        if (candidate / "config.cfg").is_file() and (candidate / "meta.json").is_file():
            return candidate

    checked = "\n".join(str(path) for path in candidates)
    raise ResourceNotFoundError(
        "TS PosTagger model klasörü bulunamadı. Kontrol edilen yollar:\n" + checked
    )

