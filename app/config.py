"""Application constants."""

from __future__ import annotations

from app.resource_manager import resolve_resource

APP_NAME = "TS TextLab"
APP_VERSION = resolve_resource("version.txt").read_text(encoding="utf-8").strip()
APP_AUTHOR = "Taner Sezer"
ORGANIZATION_NAME = "TS Corpus"
VERSION_CHECK_URL = "https://raw.githubusercontent.com/tanerim/TS_TextLab/master/version.txt"
VERSION_CHECK_TIMEOUT_SECONDS = 2.5

DEFAULT_SAMPLE_TEXT = "Doğal dil, insan zihninin çok katmanlı ve kaotik bir ürünüdür.\nHer sözcük bir birimdir ancak her birim bir sözcük değildir."

DEFAULT_MAX_INPUT_UNITS = 1_000_000
