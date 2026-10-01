# -*- coding: utf-8 -*-
"""Local SQLite cache for get_media_status and plus feature probes."""

import json
import os
import sqlite3
import time

try:
    from .pure import (
        ACTIVITIES_TTL,
        PLUS_FEATURES,
        apply_write_flags,
        iso_newer,
        is_not_found,
        list_rows_from_result,
        media_status_keys,
        merge_status_flags,
        row_status_update,
        unwrap_data,
    )
except ImportError:
    from pure import (
        ACTIVITIES_TTL,
        PLUS_FEATURES,
        apply_write_flags,
        iso_newer,
        is_not_found,
        list_rows_from_result,
        media_status_keys,
        merge_status_flags,
        row_status_update,
        unwrap_data,
    )

_PATH = None
_CONN = None
_warm = {"scope": None, "page": 1}
_STATUS_MEM_TTL = 8.0
_STATUS_MEM = {}
CONTENT_TTL = 300.0
MEDIA_TTL = 86400.0

SCOPES = (
    "history",
    "watchlist",
    "ratings",
    "favorites",
    "collection",
    "scrobbles",
)


def set_path_for_tests(path):
    """Point the cache at a temp file (unit tests)."""
    global _PATH, _CONN, _warm, _STATUS_MEM
    close()
    _PATH = path
    _warm = {"scope": None, "page": 1}
    _STATUS_MEM = {}


def close():
    global _CONN, _STATUS_MEM
    if _CONN is not None:
        try:
            _CONN.close()
        except Exception:
            pass
    _CONN = None
    _STATUS_MEM = {}


def _default_path():
    import xbmcvfs
    folder = xbmcvfs.translatePath("special://profile/addon_data/script.dejavu")
    try:
        xbmcvfs.mkdirs(folder)
    except Exception:
        pass
    return os.path.join(folder, "cache.sqlite")


def _connect():
    global _CONN
    if _CONN is not None:
        return _CONN
    path = _PATH or _default_path()
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        try:
            os.makedirs(folder)
        except Exception:
            pass
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS status ("
        "key TEXT PRIMARY KEY, json TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cursor ("
        "scope TEXT PRIMARY KEY, iso TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS meta ("
        "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS content_cache ("
        "scope TEXT NOT NULL, item_key TEXT NOT NULL, position INTEGER NOT NULL,"
        "json TEXT NOT NULL, updated_at REAL NOT NULL,"
        "PRIMARY KEY(scope, item_key))"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_content_cache_scope_position "
        "ON content_cache(scope, position)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS content_meta ("
        "scope TEXT PRIMARY KEY, pagination_json TEXT NOT NULL, updated_at REAL NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS media_cache ("
        "key TEXT PRIMARY KEY, json TEXT NOT NULL, updated_at REAL NOT NULL)"
    )
    conn.commit()
    _CONN = conn
    return conn



def _row_identity(row, position=0):
    if not isinstance(row, dict):
        return "position:%s" % position
    info = row.get("info") if isinstance(row.get("info"), dict) else {}
    media_type = str(
        row.get("type") or info.get("mediatype") or info.get("type") or ""
    ).strip().lower()
    if media_type in ("movies", "movie"):
        media_type = "movie"
    elif media_type in ("tv", "tvshow", "show", "series"):
        media_type = "tv"
    elif media_type != "episode":
        media_type = "item"
    tmdb_id = row.get("tmdbId") or row.get("tmdb_id") or info.get("tmdbId")
    if tmdb_id is None:
        raw_id = row.get("id")
        if raw_id is not None and str(raw_id).isdigit():
            tmdb_id = raw_id
    if tmdb_id is not None and str(tmdb_id).strip():
        return "%s:%s" % (media_type, str(tmdb_id).strip())
    imdb_id = row.get("imdbId") or row.get("imdb_id") or info.get("imdbId") or info.get("imdbnumber")
    if imdb_id:
        return "%s:imdb:%s" % (media_type, str(imdb_id).strip())
    return "position:%s" % position


def _media_cache_key(row):
    if not isinstance(row, dict):
        return ""
    info = row.get("info") if isinstance(row.get("info"), dict) else {}
    media_type = str(row.get("type") or info.get("mediatype") or "").strip().lower()
    if media_type in ("movie", "movies"):
        media_type = "movie"
    elif media_type in ("tv", "tvshow", "show", "series"):
        media_type = "tv"
    elif media_type == "episode":
        media_type = "episode"
    else:
        media_type = ""
    tmdb_id = row.get("tmdbId") or row.get("tmdb_id") or info.get("tmdbId")
    if tmdb_id is not None and str(tmdb_id).strip().isdigit() and media_type:
        return "%s:%s" % (media_type, int(tmdb_id))
    return ""


def cache_page(scope, rows, pagination=None, commit=True):
    rows = rows if isinstance(rows, list) else []
    now = time.time()
    conn = _connect()
    conn.execute("DELETE FROM content_cache WHERE scope = ?", (scope,))
    for position, row in enumerate(rows):
        key = _row_identity(row, position)
        conn.execute(
            "INSERT OR REPLACE INTO content_cache(scope, item_key, position, json, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (scope, key, position, json.dumps(row), now),
        )
        media_key = _media_cache_key(row)
        if media_key:
            conn.execute(
                "INSERT OR REPLACE INTO media_cache(key, json, updated_at) VALUES (?, ?, ?)",
                (media_key, json.dumps(row), now),
            )
    conn.execute(
        "INSERT OR REPLACE INTO content_meta(scope, pagination_json, updated_at) VALUES (?, ?, ?)",
        (scope, json.dumps(pagination or {}), now),
    )
    if commit:
        conn.commit()


def get_cached_page(scope, max_age=CONTENT_TTL):
    try:
        row = _connect().execute(
            "SELECT updated_at FROM content_meta WHERE scope = ?", (scope,)
        ).fetchone()
    except Exception:
        return None
    if not row or time.time() - float(row[0]) > max_age:
        return None
    try:
        meta = _connect().execute(
            "SELECT pagination_json FROM content_meta WHERE scope = ?", (scope,)
        ).fetchone()
        pagination = json.loads(meta[0]) if meta and meta[0] else {}
        rows = _connect().execute(
            "SELECT json FROM content_cache WHERE scope = ? ORDER BY position",
            (scope,),
        ).fetchall()
    except Exception:
        return None
    values = []
    for raw, in rows:
        try:
            value = json.loads(raw)
        except Exception:
            continue
        if isinstance(value, dict):
            values.append(value)
    return values, pagination


def get_cached_media(media_type, tmdb_id, max_age=MEDIA_TTL):
    if not media_type or not tmdb_id:
        return None
    key = "%s:%s" % (str(media_type).strip().lower(), int(tmdb_id))
    try:
        row = _connect().execute(
            "SELECT json, updated_at FROM media_cache WHERE key = ?", (key,)
        ).fetchone()
    except Exception:
        return None
    if not row or time.time() - float(row[1]) > max_age:
        return None
    try:
        value = json.loads(row[0])
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def invalidate_content(prefix):
    if not prefix:
        return
    conn = _connect()
    conn.execute("DELETE FROM content_cache WHERE scope = ? OR scope LIKE ?", (prefix, prefix + ":%"))
    conn.execute("DELETE FROM content_meta WHERE scope = ? OR scope LIKE ?", (prefix, prefix + ":%"))
    conn.commit()


def clear_content():
    conn = _connect()
    conn.execute("DELETE FROM content_cache")
    conn.execute("DELETE FROM content_meta")
    conn.execute("DELETE FROM media_cache")
    conn.commit()


def get_meta(key, default=""):
    try:
        row = _connect().execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
    except Exception:
        return default
    return row[0] if row else default


def set_meta(key, value):
    _connect().execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
        (key, "" if value is None else str(value)),
    )
    _connect().commit()


def remember_plus_feature(name, available):
    if name not in PLUS_FEATURES:
        return
    set_meta("plus_%s" % name, "1" if available else "0")


def plus_features_available():
    found = []
    for name in PLUS_FEATURES:
        if get_meta("plus_%s" % name) == "1":
            found.append(name)
    return found


def get_cursor(scope):
    try:
        row = _connect().execute(
            "SELECT iso FROM cursor WHERE scope = ?", (scope,)
        ).fetchone()
    except Exception:
        return ""
    return row[0] if row else ""


def set_cursor(scope, iso, commit=True):
    _connect().execute(
        "INSERT OR REPLACE INTO cursor(scope, iso) VALUES (?, ?)",
        (scope, iso or ""),
    )
    if commit:
        _connect().commit()


def get_many(keys):
    keys = [k for k in (keys or []) if k]
    if not keys:
        return {}
    now = time.time()
    out = {}
    missing = []
    for key in keys:
        cached = _STATUS_MEM.get(key)
        if cached and cached[0] > now:
            out[key] = dict(cached[1])
        else:
            missing.append(key)

    if missing:
        qmarks = ",".join("?" * len(missing))
        try:
            rows = _connect().execute(
                "SELECT key, json FROM status WHERE key IN (%s)" % qmarks, missing
            ).fetchall()
        except Exception:
            rows = []
        for key, raw in rows:
            try:
                data = json.loads(raw)
            except Exception:
                continue
            if isinstance(data, dict):
                out[key] = data
                _STATUS_MEM[key] = (now + _STATUS_MEM_TTL, dict(data))
    return out


def upsert_status(mapping, commit=True):
    if not isinstance(mapping, dict) or not mapping:
        return
    existing = get_many(list(mapping.keys()))
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn = _connect()
    for key, incoming in mapping.items():
        if not key:
            continue
        merged = merge_status_flags(existing.get(key), incoming)
        conn.execute(
            "INSERT OR REPLACE INTO status(key, json, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(merged), now),
        )
        _STATUS_MEM[key] = (time.time() + _STATUS_MEM_TTL, dict(merged))
    if commit:
        conn.commit()


def apply_write(action, params):
    mapping = apply_write_flags(action, params)
    if mapping:
        upsert_status(mapping)
    prefixes = {
        "add_to_watchlist": "watchlist",
        "remove_from_watchlist": "watchlist",
        "add_to_favorites": "favorites",
        "remove_from_favorites": "favorites",
        "add_to_collection": "collection",
        "remove_from_collection": "collection",
        "add_to_history": "history",
        "delete_history": "history",
        "watched": "history",
        "unwatched": "history",
        "rate": "ratings",
        "delete_rating": "ratings",
        "scrobble": "scrobbles",
        "delete_scrobble": "scrobbles",
    }
    prefix = prefixes.get(action)
    if prefix:
        invalidate_content(prefix)


def _scope_fields(scope):
    return {
        "history": ("watched", "watchedAt", "rewatchCount"),
        "watchlist": ("inWatchlist", "watchlistPriority"),
        "ratings": ("rating",),
        "favorites": ("isFavorite",),
        "collection": ("inCollection",),
        "scrobbles": ("inProgress", "progress", "duration"),
    }.get(scope, ())


def _prune_scope(scope, seen_keys, commit=True):
    """Remove flags belonging to a refreshed scope that disappeared remotely."""
    fields = _scope_fields(scope)
    if not fields:
        return
    seen = set(seen_keys or ())
    conn = _connect()
    rows = conn.execute("SELECT key, json FROM status").fetchall()
    now = time.time()
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for key, raw in rows:
        if key in seen:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        changed = False
        for field in fields:
            if field in data:
                data.pop(field, None)
                changed = True
        if not changed:
            continue
        if data:
            conn.execute(
                "UPDATE status SET json = ?, updated_at = ? WHERE key = ?",
                (json.dumps(data), stamp, key),
            )
            _STATUS_MEM[key] = (now + _STATUS_MEM_TTL, dict(data))
        else:
            conn.execute("DELETE FROM status WHERE key = ?", (key,))
            _STATUS_MEM.pop(key, None)
    if commit:
        conn.commit()


def clear():
    global _warm
    conn = _connect()
    conn.execute("DELETE FROM status")
    conn.execute("DELETE FROM cursor")
    conn.execute("DELETE FROM meta")
    conn.execute("DELETE FROM content_cache")
    conn.execute("DELETE FROM content_meta")
    conn.execute("DELETE FROM media_cache")
    conn.commit()
    _warm = {"scope": None, "page": 1}
    _STATUS_MEM.clear()


def cached_status(items):
    """
    Return a get_media_status envelope if every item is in cache.
    Empty items → empty data. Incomplete → None (caller should HTTP).
    """
    data = {}
    for item in items or []:
        keys = media_status_keys(item)
        if not keys:
            continue
        found = get_many(keys)
        hit = None
        for key in keys:
            if key in found:
                hit = found[key]
                break
        if hit is None:
            return None
        for key in keys:
            data[key] = hit
    return {"success": True, "data": data}


def _log(msg, level=None):
    try:
        import xbmc
        xbmc.log("[dejaVu.Cache] %s" % msg, level or xbmc.LOGDEBUG)
    except Exception:
        pass


def _fetch_scope_page(api, scope, page):
    kwargs = {"page": page, "page_size": 100, "minimal": True}
    if scope == "history":
        return api.get_history(**kwargs)
    if scope == "watchlist":
        return api.get_watchlist(**kwargs)
    if scope == "ratings":
        return api.get_ratings(page=page, page_size=100, minimal=True)
    if scope == "favorites":
        return api.get_favorites(page=page, page_size=100, minimal=True)
    if scope == "collection":
        return api.get_collection(**kwargs)
    if scope == "scrobbles":
        return api.get_scrobbles(page=page, page_size=100, minimal=True)
    return None


def _stale_scopes(activities):
    stale = []
    data = unwrap_data(activities) if isinstance(activities, dict) else {}
    if not isinstance(data, dict):
        data = {}
    for scope in SCOPES:
        remote = data.get(scope) or data.get("all")
        if iso_newer(remote, get_cursor(scope)):
            stale.append(scope)
    return stale


def _mark_activities_checked():
    set_meta("activities_checked_at", str(time.time()))


def _probe_activities(api):
    """
    Use the v1 API activity cursor when available.

    The old /sync/last_activities endpoint was removed from DejaVu v1.
    Once unsupported, keep that capability disabled locally and use the
    existing TTL fallback without making a network request on every tick.
    """
    if get_meta("plus_sync_cursor") == "0":
        checked = get_meta("activities_checked_at")
        try:
            age = time.time() - float(checked or 0)
        except (TypeError, ValueError):
            age = ACTIVITIES_TTL + 1
        if age < ACTIVITIES_TTL:
            return {}
        _mark_activities_checked()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return {"success": True, "data": {scope: now for scope in ("all",) + SCOPES}}

    # The legacy endpoint is no longer part of the DejaVu v1 API.
    # Disable it permanently for this cache instance instead of probing it.
    remember_plus_feature("sync_cursor", False)
    _mark_activities_checked()
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {"success": True, "data": {scope: now for scope in ("all",) + SCOPES}}


def warm_tick(api):
    """Advance one page of one stale scope. Safe to call every service loop."""
    global _warm
    try:
        from .session import get_access_token
        if not get_access_token():
            return
    except Exception:
        return

    activities = _probe_activities(api)
    if activities is None:
        return
    stale = _stale_scopes(activities) if activities else []
    if not stale:
        _warm = {"scope": None, "page": 1}
        return

    scope = _warm.get("scope")
    page = int(_warm.get("page") or 1)
    if scope not in stale:
        scope = stale[0]
        page = 1
        _warm = {"scope": scope, "page": page, "seen": set()}

    result = _fetch_scope_page(api, scope, page)
    if result is None or (
        isinstance(result, dict) and result.get("success") is False
    ):
        _log("warm %s page %s failed" % (scope, page))
        _warm = {"scope": None, "page": 1}
        return

    rows, pagination = list_rows_from_result(result)
    mapping = {}
    for row in rows:
        mapping.update(row_status_update(row, scope))
    if mapping:
        upsert_status(mapping, commit=False)
    seen_keys = _warm.get("seen")
    if not isinstance(seen_keys, set):
        seen_keys = set()
    seen_keys.update(mapping.keys())

    has_more = bool(pagination.get("hasMore"))
    if has_more:
        _connect().commit()
        _warm = {"scope": scope, "page": page + 1, "seen": seen_keys}
        return

    data = unwrap_data(activities) if isinstance(activities, dict) else {}
    remote = ""
    if isinstance(data, dict):
        remote = data.get(scope) or data.get("all") or ""
    _prune_scope(scope, seen_keys, commit=False)
    set_cursor(scope, remote or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), commit=False)
    _connect().commit()
    _warm = {"scope": None, "page": 1}
    _log("warmed %s (%s rows last page)" % (scope, len(rows)))
