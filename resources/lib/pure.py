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


_DBTYPE_ALIASES = {
    "movie": "movie",
    "movies": "movie",
    "tvshow": "tvshow",
    "tv": "tvshow",
    "show": "tvshow",
    "series": "tvshow",
    "season": "season",
    "episode": "episode",
}

_SCAT_DBTYPE = {
    "1": "movie",
    "2": "tvshow",
    "3": "tvshow",
    "9": "tvshow",
}

CONTEXT_DBTYPES = frozenset(("movie", "tvshow", "season", "episode"))


def normalize_dbtype(db_type, s_cat=""):
    """Canonical Kodi dbtype: movie / tvshow / season / episode, or empty."""
    key = str(db_type or "").strip().lower()
    if key in _DBTYPE_ALIASES:
        return _DBTYPE_ALIASES[key]
    return _SCAT_DBTYPE.get(str(s_cat or "").strip(), "")


def is_context_media(info):
    """True when the focused item is a movie, show, season, or episode."""
    if not isinstance(info, dict):
        return False
    return normalize_dbtype(info.get("dbtype"), info.get("s_cat")) in CONTEXT_DBTYPES


def listitem_api_type(db_type):
    db = normalize_dbtype(db_type)
    if db == "movie":
        return "movie"
    if db in ("tvshow", "season", "episode"):
        return "tv"
    return ""


def listitem_history_type(db_type):
    db = normalize_dbtype(db_type)
    if db == "episode":
        return "episode"
    if db == "movie":
        return "movie"
    if db in ("tvshow", "season"):
        return "tv"
    return ""


def is_addons_path(path):
    """True for Kodi addon-browser rows (not plugin:// video listings)."""
    text = (path or "").replace("\\", "/").lower()
    return text.startswith("addons://")


def parse_optional_int(value):
    """Non-negative int, or None when missing / unknown (-1)."""
    if value is None or value == "":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        if not text.lstrip("-").isdigit():
            return None
        number = int(text)
    return number if number >= 0 else None


# Context-menu action ids + string ids (see strings.po 30016 / 30080+ / 30200+).
_RATE = "rate"
_WATCHED = "watched"
_UNWATCHED = "unwatched"
_WATCHLIST = "watchlist"
_FAVORITES = "favorites"
_COLLECTION = "collection"
_LIST = "list"


def context_actions(dbtype, flags=None):
    """Return [{id, label_id, label_arg?}, ...] for the Python context menu."""
    db = normalize_dbtype(dbtype)
    flags = flags if isinstance(flags, dict) else {}
    actions = []

    if db not in CONTEXT_DBTYPES:
        return actions

    rating = parse_optional_int(flags.get("rating"))
    if db in ("movie", "tvshow") and rating:
        actions.append({"id": _RATE, "label_id": 30200, "label_arg": rating})
    else:
        actions.append({"id": _RATE, "label_id": 30016})

    if db == "movie":
        if flags.get("watched"):
            actions.append({"id": _UNWATCHED, "label_id": 30093})
        else:
            actions.append({"id": _WATCHED, "label_id": 30092})
    elif db == "episode":
        # get_media_status is movie/tv only — offer both watched actions.
        actions.append({"id": _WATCHED, "label_id": 30092})
        actions.append({"id": _UNWATCHED, "label_id": 30093})

    if db in ("movie", "tvshow"):
        if flags.get("inWatchlist"):
            actions.append({"id": _WATCHLIST, "label_id": 30201})
        else:
            actions.append({"id": _WATCHLIST, "label_id": 30083})
        if flags.get("isFavorite"):
            actions.append({"id": _FAVORITES, "label_id": 30202})
        else:
            actions.append({"id": _FAVORITES, "label_id": 30086})
        if flags.get("inCollection"):
            actions.append({"id": _COLLECTION, "label_id": 30203})
        else:
            actions.append({"id": _COLLECTION, "label_id": 30080})
        actions.append({"id": _LIST, "label_id": 30101})

    return actions
