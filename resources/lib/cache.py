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
    global _PATH, _CONN, _warm
    close()
    _PATH = path
    _warm = {"scope": None, "page": 1}


def close():
    global _CONN
    if _CONN is not None:
        try:
            _CONN.close()
        except Exception:
            pass
    _CONN = None


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
    conn.commit()
    _CONN = conn
    return conn


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


def set_cursor(scope, iso):
    _connect().execute(
        "INSERT OR REPLACE INTO cursor(scope, iso) VALUES (?, ?)",
        (scope, iso or ""),
    )
    _connect().commit()


def get_many(keys):
    keys = [k for k in (keys or []) if k]
    if not keys:
        return {}
    qmarks = ",".join("?" * len(keys))
    try:
        rows = _connect().execute(
            "SELECT key, json FROM status WHERE key IN (%s)" % qmarks, keys
        ).fetchall()
    except Exception:
        return {}
    out = {}
    for key, raw in rows:
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, dict):
            out[key] = data
    return out


def upsert_status(mapping):
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
    conn.commit()


def apply_write(action, params):
    mapping = apply_write_flags(action, params)
    if mapping:
        upsert_status(mapping)


def clear():
    global _warm
    conn = _connect()
    conn.execute("DELETE FROM status")
    conn.execute("DELETE FROM cursor")
    conn.execute("DELETE FROM meta")
    conn.commit()
    _warm = {"scope": None, "page": 1}


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
    result = api.get_last_activities()
    if result is None:
        return None
    if is_not_found(result):
        remember_plus_feature("sync_cursor", False)
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
    remember_plus_feature("sync_cursor", True)
    _mark_activities_checked()
    return result


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

    result = _fetch_scope_page(api, scope, page)
    if result is None:
        _log("warm %s page %s failed" % (scope, page))
        _warm = {"scope": None, "page": 1}
        return

    rows, pagination = list_rows_from_result(result)
    mapping = {}
    for row in rows:
        mapping.update(row_status_update(row, scope))
    if mapping:
        upsert_status(mapping)

    has_more = bool(pagination.get("hasMore"))
    if has_more:
        _warm = {"scope": scope, "page": page + 1}
        return

    data = unwrap_data(activities) if isinstance(activities, dict) else {}
    remote = ""
    if isinstance(data, dict):
        remote = data.get(scope) or data.get("all") or ""
    set_cursor(scope, remote or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    _warm = {"scope": None, "page": 1}
    _log("warmed %s (%s rows last page)" % (scope, len(rows)))
