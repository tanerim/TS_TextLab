"""Bounded, unauthenticated checks against a public HTTPS update feed."""
from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.config import APP_VERSION, VERSION_CHECK_TIMEOUT_SECONDS, VERSION_CHECK_URL

logger = logging.getLogger(__name__)
VERSION_PATTERN = re.compile(r'v?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?')


@dataclass(frozen=True)
class VersionCheckResult:
    checked: bool
    update_available: bool = False
    latest_version: str = ''
    error: str = ''
    download_url: str = ''


def valid_update_url(value: str) -> bool:
    try:
        url = urlsplit(value)
        return url.scheme == 'https' and bool(url.hostname) and not url.username and not url.password
    except ValueError:
        return False


def check_for_update(url: str = VERSION_CHECK_URL) -> VersionCheckResult:
    if not valid_update_url(url):
        return VersionCheckResult(checked=False, error='A public HTTPS update URL is required')
    request = Request(url, headers={
        'User-Agent': f'TS TextLab/{APP_VERSION}',
        'Accept': 'application/json, text/plain',
        'Cache-Control': 'no-cache',
    })
    try:
        with urlopen(request, timeout=VERSION_CHECK_TIMEOUT_SECONDS) as response:
            if not valid_update_url(response.geturl()):
                raise ValueError('Update feed must remain on HTTPS')
            payload = response.read(65_537)
            if len(payload) > 65_536:
                raise ValueError('Update feed is too large')
            return parse_update_feed(payload.decode('utf-8-sig'))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        logger.info('Version check skipped/failed: %s', exc)
        return VersionCheckResult(checked=False, error=str(exc))


def parse_update_feed(payload: str) -> VersionCheckResult:
    """Accept a stable version.txt or a version/download_url JSON manifest."""
    payload = payload.strip()
    download = ''
    if payload.startswith('{'):
        manifest = json.loads(payload)
        latest = manifest['version']
        downloads = manifest.get('downloads', {})
        if not isinstance(downloads, dict):
            raise ValueError('Invalid platform downloads')
        download = downloads.get(sys.platform, manifest.get('download_url', ''))
        if not isinstance(download, str) or (download and not valid_update_url(download)):
            raise ValueError('Invalid HTTPS download URL')
    else:
        latest = payload
    if not isinstance(latest, str) or not VERSION_PATTERN.fullmatch(latest):
        raise ValueError('Invalid stable version response')
    return VersionCheckResult(True, _version_tuple(latest) > _version_tuple(APP_VERSION), latest,
                              download_url=download)


def _version_tuple(value: str) -> tuple[int, ...]:
    match = VERSION_PATTERN.fullmatch(value)
    if not match:
        raise ValueError('Invalid version')
    return tuple(int(part or 0) for part in match.groups())
