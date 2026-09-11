# -*- coding: utf-8 -*-
"""Pure helpers with no xbmc / network imports (unit-tested)."""

from urllib.parse import parse_qs, urlparse
import re

DEFAULT_API_URL = "https://dejavu.plus/api/v1"
ALLOWED_API_HOSTS = ("dejavu.plus", "www.dejavu.plus")


def unwrap_data(result):
    """Return the `data` payload from a v1 `{success, data}` response, or the value as-is."""
    if isinstance(result, dict) and "data" in result:
        return result.get("data")
    return result


_KODI_TAG_RE = re.compile(r"\[/?[^\]]+\]")
_STAR_RATING_RE = re.compile(r"★\s*\d+")
_BADGE_CHARS = str.maketrans({"✔": " ", "♥": " ", "●": " "})


def strip_kodi_label(text):
    """Remove skin/color tags and dejaVu overlay badges from a ListItem label."""
    cleaned = _KODI_TAG_RE.sub("", str(text or ""))
    cleaned = cleaned.translate(_BADGE_CHARS)
    cleaned = _STAR_RATING_RE.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


_TMDB_QUERY_KEYS = ("tmdb_id", "tmdbid", "tmdb", "themoviedb", "tmdbId")
_IMDB_QUERY_KEYS = ("imdb_id", "imdbid", "imdb", "imdbId")
_SHOW_TMDB_QUERY_KEYS = (
    "show_tmdb_id", "tvshow_tmdb_id", "tvshowid", "tvShowId", "TVShowID", "show_id",
)
_TYPE_QUERY_KEYS = ("type", "media_type", "mediatype", "dbtype")


def _qs_first(query, keys):
    for key in keys:
        values = query.get(key) or query.get(key.lower()) or query.get(key.upper())
        if not values:
            continue
        val = str(values[0] or "").strip()
        if val:
            return val
    return ""


def ids_from_plugin_path(path):
    """Pull TMDB/IMDb/type from plugin:// query strings (alkoFlix, Elementum, …)."""
    text = (path or "").replace("\\", "/")
    if "plugin://" not in text and "?" not in text:
        return {"tmdb_id": "", "imdb_id": "", "show_tmdb_id": "", "media_type": ""}
    try:
        parsed = urlparse(text)
        query = parse_qs(parsed.query or "")
        if not query and "?" in text:
            query = parse_qs(text.split("?", 1)[-1])
    except Exception:
        query = {}
    tmdb_id = _qs_first(query, _TMDB_QUERY_KEYS)
    if not tmdb_id:
        match = re.search(r"/tmdb/(\d+)", text, re.I)
        if match:
            tmdb_id = match.group(1)
    if tmdb_id and not str(tmdb_id).isdigit():
        tmdb_id = ""
    imdb_id = _qs_first(query, _IMDB_QUERY_KEYS)
    show_tmdb = _qs_first(query, _SHOW_TMDB_QUERY_KEYS)
    if show_tmdb and not str(show_tmdb).isdigit():
        show_tmdb = ""
    media_type = normalize_dbtype(_qs_first(query, _TYPE_QUERY_KEYS))
    return {
        "tmdb_id": tmdb_id,
        "imdb_id": imdb_id,
        "show_tmdb_id": show_tmdb,
        "media_type": media_type,
    }


def status_flags(result, media_type, tmdb_id, show_tmdb_id=None, season=None, episode=None):
    """Pick get_media_status flags for type+id from a v1 envelope or a plain map."""
    data = unwrap_data(result)
    if not isinstance(data, dict):
        return {}
    tid = str(tmdb_id or "").strip()
    db = normalize_dbtype(media_type)
    if db == "episode" or str(media_type or "").strip().lower() == "episode":
        kind = "episode"
    else:
        kind = listitem_api_type(media_type) or (
            media_type if media_type in ("movie", "tv") else ""
        )
    keys = []
    if kind and tid:
        keys.append("%s:%s" % (kind, tid))
    show = str(show_tmdb_id or "").strip()
    if kind == "episode" and show and season is not None and episode is not None:
        keys.append("episode:%s:%s:%s" % (show, season, episode))
    if tid:
        keys.append(tid)
    for key in keys:
        entry = data.get(key)
        if isinstance(entry, dict) and entry:
            return entry
    if any(k in data for k in ("isFavorite", "inWatchlist", "inCollection", "watched", "rating")):
        return data
    return {}


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


def _rewatch_action(flags):
    date = flags.get("watched_at_label")
    if date:
        count = parse_optional_int(flags.get("rewatchCount")) or 1
        label_id = 30207 if count == 1 else 30206
        return {"id": _REWATCH, "label_id": label_id, "label_arg": (count, date)}
    return {"id": _REWATCH, "label_id": 30204}


def format_watched_at(value):
    """ISO-8601 (or YYYY-MM-DD prefix) to JJ/MM/AAAA. Empty when unparseable."""
    text = str(value or "").strip()
    if not text:
        return ""
    date_part = text.replace("Z", "").split("T")[0].split(" ")[0]
    bits = date_part.split("-")
    if len(bits) != 3 or len(bits[0]) != 4:
        return ""
    year, month, day = bits
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return ""
    return "%s/%s/%s" % (day.zfill(2), month.zfill(2), year)


# Context-menu action ids + string ids (see strings.po 30016 / 30080+ / 30200+).
_RATE = "rate"
_WATCHED = "watched"
_UNWATCHED = "unwatched"
_REWATCH = "rewatch"
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
            actions.append(_rewatch_action(flags))
        else:
            actions.append({"id": _WATCHED, "label_id": 30092})
    elif db == "episode":
        actions.append({"id": _WATCHED, "label_id": 30092})
        actions.append({"id": _UNWATCHED, "label_id": 30093})
        if flags.get("watched"):
            actions.append(_rewatch_action(flags))

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


# Listing-layer protocol (DejaVuClient / cache / plus probes)

PROTOCOL = 2
CORE_FEATURES = (
    "request_id",
    "episode_status",
    "local_auth",
    "media_status_cache",
    "plugin_widgets",
)
PLUS_FEATURES = ("show_progress", "resolve_batch", "sync_cursor")
ACTIVITIES_TTL = 900
NOT_FOUND_ERROR = "not_found"


def capabilities_payload(addon_version, plus_features=None):
    """Sync get_capabilities body. plus_features = names confirmed on dejaVu.plus."""
    features = list(CORE_FEATURES)
    allowed = set(PLUS_FEATURES)
    for name in plus_features or []:
        if name in allowed and name not in features:
            features.append(name)
    return {
        "success": True,
        "protocol": PROTOCOL,
        "addonVersion": addon_version or "",
        "features": features,
    }


def is_not_found(result):
    return isinstance(result, dict) and result.get("error") == NOT_FOUND_ERROR


def iso_newer(remote, local):
    """True when remote ISO timestamp is newer than the local cursor."""
    if not remote:
        return False
    if not local:
        return True
    return str(remote) > str(local)


def media_status_keys(item):
    """Cache / map keys for a get_media_status request item."""
    if not isinstance(item, dict):
        return []
    media_type = str(item.get("type") or "").strip().lower()
    if media_type not in ("movie", "tv", "episode"):
        return []
    keys = []
    raw_id = item.get("id")
    if raw_id is not None and str(raw_id).isdigit():
        keys.append("%s:%s" % (media_type, int(raw_id)))
    if media_type != "episode":
        return keys
    show = item.get("tmdbId") or item.get("tmdb_id") or item.get("show_tmdb_id")
    season = item.get("seasonNumber", item.get("season"))
    episode = item.get("episodeNumber", item.get("episode"))
    if (
        show is not None and str(show).isdigit()
        and season is not None and str(season).lstrip("-").isdigit()
        and episode is not None and str(episode).lstrip("-").isdigit()
    ):
        keys.append("episode:%s:%s:%s" % (int(show), int(season), int(episode)))
    return keys


def merge_status_flags(existing, incoming):
    """Merge incoming flags into a cached row. None deletes the key."""
    out = dict(existing) if isinstance(existing, dict) else {}
    if not isinstance(incoming, dict):
        return out
    for key, value in incoming.items():
        if value is None:
            out.pop(key, None)
        else:
            out[key] = value
    return out


def list_rows_from_result(result):
    """Normalize a paginated v1 list to (rows, pagination)."""
    pagination = {}
    if isinstance(result, dict):
        pagination = result.get("pagination") or {}
    data = unwrap_data(result)
    if isinstance(data, list):
        return data, pagination
    if not isinstance(data, dict):
        return [], pagination
    pagination = data.get("pagination") or pagination
    for key in (
        "items", "results", "widgets", "lists", "history",
        "movies", "shows", "entries", "scrobbles",
    ):
        value = data.get(key)
        if isinstance(value, list):
            return value, pagination
    inner = data.get("data")
    if isinstance(inner, list):
        return inner, pagination
    return [], pagination


def _row_media(row):
    if not isinstance(row, dict):
        return "", None, {}
    info = row.get("info") if isinstance(row.get("info"), dict) else {}
    media_type = str(
        row.get("type") or info.get("mediatype") or info.get("type") or ""
    ).strip().lower()
    if media_type in ("movie", "movies"):
        media_type = "movie"
    elif media_type in ("tv", "tvshow", "show", "series"):
        media_type = "tv"
    elif media_type != "episode":
        media_type = ""
    tmdb_id = (
        row.get("tmdbId") or row.get("tmdb_id") or info.get("tmdbId")
        or info.get("tmdb_id")
    )
    if tmdb_id is None:
        raw_id = row.get("id")
        if raw_id is not None and str(raw_id).isdigit():
            tmdb_id = raw_id
    extra = {
        "tmdbId": (
            row.get("tvShowId") or row.get("tvShowTmdbId")
            or row.get("showTmdbId") or row.get("show_tmdb_id")
            or info.get("tvShowId")
        ),
        "seasonNumber": row.get("seasonNumber") or row.get("season") or info.get("season"),
        "episodeNumber": row.get("episodeNumber") or row.get("episode") or info.get("episode"),
    }
    return media_type, tmdb_id, extra


def row_status_update(row, scope):
    """Map a list/history/watchlist row to {status_key: flags}."""
    media_type, tmdb_id, extra = _row_media(row)
    item = {"type": media_type, "id": tmdb_id}
    item.update(extra)
    keys = media_status_keys(item)
    if not keys:
        return {}
    flags = {}
    if scope == "history":
        flags = {
            "watched": True,
            "watchedAt": row.get("watchedAt") or row.get("watched_at"),
            "rewatchCount": row.get("rewatchCount"),
        }
    elif scope == "watchlist":
        flags = {
            "inWatchlist": True,
            "watchlistPriority": row.get("priority") or row.get("watchlistPriority"),
        }
    elif scope == "favorites":
        flags = {"isFavorite": True}
    elif scope == "collection":
        flags = {"inCollection": True}
    elif scope == "ratings":
        flags = {"rating": row.get("rating") or row.get("userRating")}
    elif scope == "scrobbles":
        flags = {
            "inProgress": True,
            "progress": row.get("progress"),
            "duration": row.get("duration") or (row.get("info") or {}).get("duration"),
        }
    else:
        return {}
    return {key: dict(flags) for key in keys}


def apply_write_flags(action, params):
    """Optimistic cache patch after a successful write RPC."""
    params = params if isinstance(params, dict) else {}
    media_type = params.get("type")
    item = {
        "type": media_type,
        "id": params.get("id"),
        "tmdbId": params.get("tvShowId"),
        "seasonNumber": params.get("seasonNumber"),
        "episodeNumber": params.get("episodeNumber"),
    }
    keys = media_status_keys(item)
    flags = None
    if action == "add_to_watchlist":
        flags = {"inWatchlist": True}
        if params.get("priority") is not None:
            flags["watchlistPriority"] = params.get("priority")
    elif action == "remove_from_watchlist":
        flags = {"inWatchlist": False, "watchlistPriority": None}
    elif action == "add_to_favorites":
        flags = {"isFavorite": True}
    elif action == "remove_from_favorites":
        flags = {"isFavorite": False}
    elif action == "add_to_collection":
        flags = {"inCollection": True}
    elif action == "remove_from_collection":
        flags = {"inCollection": False}
    elif action in ("add_to_history", "watched"):
        flags = {"watched": True}
        if params.get("watched_at"):
            flags["watchedAt"] = params.get("watched_at")
    elif action in ("delete_history", "unwatched"):
        flags = {"watched": False, "rewatchCount": None}
    elif action == "rate":
        flags = {"rating": params.get("rating")}
    elif action == "delete_rating":
        flags = {"rating": None}
    elif action == "scrobble":
        flags = {
            "inProgress": True,
            "progress": params.get("progress"),
            "duration": params.get("duration"),
        }
    elif action == "delete_scrobble":
        flags = {"inProgress": False, "progress": None}
    if not flags or not keys:
        return {}
    return {key: dict(flags) for key in keys}
