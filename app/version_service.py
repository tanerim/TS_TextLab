"""Online update check infrastructure."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import APP_VERSION, VERSION_CHECK_TIMEOUT_SECONDS, VERSION_CHECK_URL

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VersionCheckResult:
    checked: bool
    update_available: bool = False
    latest_version: str = ""
    error: str = ""


def check_for_update() -> VersionCheckResult:
    request = Request(VERSION_CHECK_URL, headers={"User-Agent": f"TS TextLab/{APP_VERSION}"})
    try:
        with urlopen(request, timeout=VERSION_CHECK_TIMEOUT_SECONDS) as response:
            latest = response.read(128).decode("utf-8", errors="replace").strip()
    except (OSError, URLError) as exc:
        logger.info("Version check skipped/failed: %s", exc)
        return VersionCheckResult(checked=False, error=str(exc))

    latest = latest.splitlines()[0].strip()
    if not latest:
        return VersionCheckResult(checked=False, error="Empty version response")

    return VersionCheckResult(
        checked=True,
        update_available=_version_tuple(latest) > _version_tuple(APP_VERSION),
        latest_version=latest,
    )


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value)
    return tuple(int(part) for part in parts) if parts else (0,)
