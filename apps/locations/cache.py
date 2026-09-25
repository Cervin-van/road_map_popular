"""Versioned cache for the shared (user-independent) location list and map.

Keys: ``locations:list:v{version}:{kind}:{md5(sorted query params)}``.
Invalidation bumps the version instead of deleting keys by pattern: old
entries become unreachable at once and expire by TTL.

Only the django.core.cache API is used, so tests run on LocMemCache.
A cache outage never breaks the API: reads miss, writes are skipped.
"""

import hashlib
import logging
import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

VERSION_KEY = "locations:list:version"


def _initial_version() -> int:
    # Neither 1 nor a timestamp: if the version key is evicted while old entries
    # survive, a predictable restart value could resurrect stale pages.
    return secrets.randbits(48)


def _version() -> int:
    version = cache.get(VERSION_KEY)
    if version is None:
        cache.add(VERSION_KEY, _initial_version(), timeout=None)
        version = cache.get(VERSION_KEY)
    return version


def make_key(kind: str, query_params) -> str:
    items = sorted((key, value) for key in query_params for value in query_params.getlist(key))
    digest = hashlib.md5(urlencode(items).encode(), usedforsecurity=False).hexdigest()
    return f"locations:list:v{_version()}:{kind}:{digest}"


def get(kind: str, query_params):
    try:
        return cache.get(make_key(kind, query_params))
    except Exception:
        logger.warning("Location list cache unavailable (read)", exc_info=True)
        return None


def set(kind: str, query_params, data) -> None:  # noqa: A001 - mirrors the cache API
    try:
        cache.set(make_key(kind, query_params), data, timeout=settings.LOCATIONS_LIST_CACHE_TTL)
    except Exception:
        logger.warning("Location list cache unavailable (write)", exc_info=True)


def invalidate() -> None:
    try:
        cache.incr(VERSION_KEY)
    except ValueError:  # version key missing (never set, evicted or flushed)
        cache.add(VERSION_KEY, _initial_version(), timeout=None)
    except Exception:
        logger.warning("Location list cache unavailable (invalidate)", exc_info=True)
