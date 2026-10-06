"""Application constants."""

from __future__ import annotations

import os

from app.resource_manager import resolve_resource

APP_NAME = "TS TextLab"
APP_VERSION = resolve_resource("version.txt").read_text(encoding="utf-8").strip()
APP_AUTHOR = "Taner Sezer"
ORGANIZATION_NAME = "TS Corpus"
VERSION_CHECK_URL = os.environ.get("TS_TEXTLAB_UPDATE_URL", "").strip()
VERSION_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000
VERSION_CHECK_RETRY_MS = 15 * 60 * 1000
VERSION_CHECK_TIMEOUT_SECONDS = 2.5

DEFAULT_SAMPLE_TEXT = "Doğal dil, insan zihninin çok katmanlı ve kaotik bir ürünüdür.\nHer sözcük bir birimdir ancak her birim bir sözcük değildir."

DEFAULT_MAX_INPUT_UNITS = 1_000_000
