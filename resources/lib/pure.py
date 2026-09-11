# -*- coding: utf-8 -*-
"""Pure helpers with no xbmc / network imports (unit-tested)."""

from urllib.parse import urlparse

DEFAULT_API_URL = "https://dejavu.plus/api/v1"
ALLOWED_API_HOSTS = ("dejavu.plus", "www.dejavu.plus")


def unwrap_data(result):
    """Return the `data` payload from a v1 `{success, data}` response, or the value as-is."""
    if isinstance(result, dict) and "data" in result:
        return result.get("data")
    return result


def extract_ids(uniqueids, imdbnumber=None):
    """Return (tmdb_id:int|None, imdb_id:str|None) from Kodi uniqueid + imdbnumber."""
    uniqueids = uniqueids if isinstance(uniqueids, dict) else {}
    tmdb_raw = uniqueids.get("tmdb") or uniqueids.get("themoviedb") or ""
    imdb_raw = uniqueids.get("imdb") or ""
    unknown = uniqueids.get("unknown") or ""

    tmdb_id = None
    if str(tmdb_raw).isdigit():
        tmdb_id = int(tmdb_raw)
    elif str(unknown).isdigit():
        tmdb_id = int(unknown)

    imdb_id = None
    for candidate in (imdb_raw, imdbnumber, unknown):
        val = str(candidate or "").strip()
        if val.startswith("tt"):
            imdb_id = val
            break

    if tmdb_id is None and imdbnumber and str(imdbnumber).isdigit():
        tmdb_id = int(imdbnumber)

    return tmdb_id, imdb_id


def effective_api_url(raw, debug=False, default=DEFAULT_API_URL):
    text = (raw or default or "").strip().rstrip("/")
    if not text:
        return default
    try:
        parsed = urlparse(text)
    except Exception:
        return default
    if parsed.scheme != "https" or not parsed.netloc:
        return default
    host = (parsed.hostname or "").lower()
    if host in ALLOWED_API_HOSTS:
        return text
    if debug:
        return text
    return default


def sanitize_result_property(action, requested):
    default_prop = "script.dejavu.%s.result" % (action or "unknown")
    if not isinstance(requested, str) or not requested.startswith("script.dejavu."):
        return default_prop
    return requested


def should_migrate_settings_token(session_file_exists, session_token):
    """Copy settings token into session.json only when the file is missing (upgrade)."""
    if session_file_exists:
        return False
    return not bool(session_token)
