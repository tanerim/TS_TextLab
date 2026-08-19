"""Locate resources in development and PyInstaller builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


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
