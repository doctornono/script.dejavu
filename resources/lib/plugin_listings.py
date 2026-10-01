# -*- coding: utf-8 -*-
"""plugin://script.dejavu/ listings for skins. No scrapers, no streams."""

from urllib.parse import parse_qsl, urlencode
import json

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from . import cache
from .api_client import DejaVuAPI
from .auth_handler import is_logged_in
from .pure import list_rows_from_result, status_flags
from .session import get_username
from .util import play_from_library

ADDON = xbmcaddon.Addon()
ADDON_ID = "script.dejavu"


def _ls(string_id):
    return ADDON.getLocalizedString(string_id)


def _plugin_url(**kwargs):
    params = {}
    for key, value in kwargs.items():
        if value is None or value == "":
            continue
        params[key] = str(value)
    return "plugin://%s/?%s" % (ADDON_ID, urlencode(params))


def _end(handle, content="videos"):
    if handle is None or int(handle) < 0:
        return
    try:
        xbmcplugin.setContent(int(handle), content)
    except Exception:
        pass
    xbmcplugin.endOfDirectory(int(handle), succeeded=True, cacheToDisc=False)


def _icon():
    return ADDON.getAddonInfo("icon") or ""


def _fanart():
    return ADDON.getAddonInfo("fanart") or ""


def _add_folder(handle, label, params, plot=""):
    item = xbmcgui.ListItem(label=label, offscreen=True)
    item.setArt({"icon": _icon(), "thumb": _icon(), "fanart": _fanart()})
    if plot:
        item.setInfo("video", {"title": label, "plot": plot})
    xbmcplugin.addDirectoryItem(handle, _plugin_url(**params), item, isFolder=True)


def _add_action(handle, label, params, plot=""):
    item = xbmcgui.ListItem(label=label, offscreen=True)
    item.setArt({"icon": _icon(), "thumb": _icon(), "fanart": _fanart()})
    if plot:
        item.setInfo("video", {"title": label, "plot": plot})
    xbmcplugin.addDirectoryItem(handle, _plugin_url(**params), item, isFolder=False)


def _as_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        return int(text) if text.isdigit() else None


def _normalize(raw):
    if not isinstance(raw, dict):
        return None
    info = raw.get("info") if isinstance(raw.get("info"), dict) else {}
    art = raw.get("art") if isinstance(raw.get("art"), dict) else {}
    tmdb_id = raw.get("tmdbId") or raw.get("tmdb_id") or info.get("tmdbId")
    if tmdb_id is None:
        raw_id = raw.get("id")
        if raw_id is not None and str(raw_id).isdigit():
            tmdb_id = raw_id
    imdb_id = (
        raw.get("imdbId") or raw.get("imdb_id") or info.get("imdbnumber")
        or info.get("imdbId") or ""
    )
    media_type = str(raw.get("type") or info.get("mediatype") or "movie").lower()
    if media_type in ("movie", "movies"):
        media_type = "movie"
    elif media_type in ("tv", "tvshow", "show", "series"):
        media_type = "tv"
    elif media_type != "episode":
        media_type = "movie"
    title = info.get("title") or raw.get("title") or raw.get("name") or ""
    show_tmdb = (
        raw.get("tvShowId") or raw.get("showTmdbId") or raw.get("show_tmdb_id")
        or info.get("tvShowId")
    )
    season = raw.get("seasonNumber") or raw.get("season") or info.get("season")
    episode = raw.get("episodeNumber") or raw.get("episode") or info.get("episode")
    try:
        progress = float(raw.get("progress") if raw.get("progress") is not None else 0)
    except (TypeError, ValueError):
        progress = 0.0
    try:
        duration = float(
            raw.get("duration")
            if raw.get("duration") is not None
            else (info.get("duration") or 0)
        )
    except (TypeError, ValueError):
        duration = 0.0
    kodi_dbtype = "movie"
    if media_type == "tv":
        kodi_dbtype = "tvshow"
    elif media_type == "episode":
        kodi_dbtype = "episode"
    return {
        "tmdb_id": _as_int(tmdb_id),
        "imdb_id": str(imdb_id).strip() if imdb_id else "",
        "media_type": media_type,
        "kodi_dbtype": kodi_dbtype,
        "title": title,
        "plot": info.get("plot") or raw.get("overview") or "",
        "year": _as_int(info.get("year") or raw.get("year")),
        "poster": art.get("poster") or raw.get("posterUrl") or "",
        "fanart": art.get("fanart") or raw.get("backdropUrl") or "",
        "show_tmdb_id": _as_int(show_tmdb),
        "season": _as_int(season),
        "episode": _as_int(episode),
        "progress": progress,
        "duration": duration,
    }


def _status_map(api, media_items):
    payload = []
    seen = set()
    for media in media_items:
        if media.get("media_type") == "episode":
            entry = {"type": "episode"}
            if media.get("tmdb_id"):
                entry["id"] = media["tmdb_id"]
            if media.get("show_tmdb_id"):
                entry["tmdbId"] = media["show_tmdb_id"]
            if media.get("season") is not None:
                entry["seasonNumber"] = media["season"]
            if media.get("episode") is not None:
                entry["episodeNumber"] = media["episode"]
            key = tuple(sorted(entry.items()))
        else:
            overlay_type = media.get("media_type") or "movie"
            overlay_id = media.get("tmdb_id")
            if overlay_type not in ("movie", "tv") or not overlay_id:
                continue
            entry = {"type": overlay_type, "id": overlay_id}
            key = (overlay_type, overlay_id)
        if key in seen:
            continue
        seen.add(key)
        payload.append(entry)
    if not payload:
        return {}
    from .cache import cached_status
    cached = cached_status(payload)
    if cached is not None:
        return cached.get("data") or {}
    result = api.get_media_status(payload)
    data = (result or {}).get("data") if isinstance(result, dict) else {}
    if isinstance(data, dict) and data:
        try:
            from .cache import upsert_status
            upsert_status(data)
        except Exception:
            pass
    return data if isinstance(data, dict) else {}


def _flags_for(status_map, media):
    return status_flags(
        {"data": status_map},
        media.get("media_type"),
        media.get("tmdb_id"),
        show_tmdb_id=media.get("show_tmdb_id"),
        season=media.get("season"),
        episode=media.get("episode"),
    )


def _build_item(media, flags):
    title = media.get("title") or ""
    item = xbmcgui.ListItem(label=title, offscreen=True)
    info = {
        "title": title,
        "plot": media.get("plot") or "",
        "mediatype": media.get("kodi_dbtype") or "movie",
    }
    if media.get("year"):
        info["year"] = media["year"]
    if media.get("imdb_id"):
        info["imdbnumber"] = media["imdb_id"]
    if media.get("season") is not None:
        info["season"] = media["season"]
    if media.get("episode") is not None:
        info["episode"] = media["episode"]
    if flags.get("rating"):
        try:
            info["userrating"] = int(flags["rating"])
        except (TypeError, ValueError):
            pass
    watched = bool(flags.get("watched"))
    info["playcount"] = 1 if watched else 0
    item.setInfo("video", info)
    item.setArt({
        "icon": media.get("poster") or _icon(),
        "thumb": media.get("poster") or _icon(),
        "poster": media.get("poster") or _icon(),
        "fanart": media.get("fanart") or _fanart(),
    })
    unique_ids = {}
    if media.get("tmdb_id"):
        unique_ids["tmdb"] = str(media["tmdb_id"])
    if media.get("imdb_id"):
        unique_ids["imdb"] = media["imdb_id"]
    if unique_ids and hasattr(item, "setUniqueIDs"):
        item.setUniqueIDs(unique_ids, "tmdb" if media.get("tmdb_id") else "imdb")
    if media.get("tmdb_id"):
        item.setProperty("tmdb_id", str(media["tmdb_id"]))
        item.setProperty("TmdbId", str(media["tmdb_id"]))
    if media.get("show_tmdb_id"):
        item.setProperty("tvshow_tmdb_id", str(media["show_tmdb_id"]))
        item.setProperty("TVShowID", str(media["show_tmdb_id"]))
    if media.get("imdb_id"):
        item.setProperty("imdb_id", media["imdb_id"])
    item.setProperty("DBType", media.get("kodi_dbtype") or "movie")
    item.setProperty("media_type", media.get("media_type") or "movie")
    progress = flags.get("progress")
    duration = flags.get("duration")
    try:
        resume_time = float(progress if progress is not None else media.get("progress") or 0)
    except (TypeError, ValueError):
        resume_time = 0.0
    try:
        resume_total = float(duration if duration is not None else media.get("duration") or 0)
    except (TypeError, ValueError):
        resume_total = 0.0
    if resume_total:
        try:
            info_tag_duration = int(resume_total)
            item.setInfo("video", dict(info, duration=info_tag_duration))
        except (TypeError, ValueError):
            pass
    if resume_time >= 30 and resume_total > resume_time:
        item.setProperty("ResumeTime", str(resume_time))
        item.setProperty("TotalTime", str(resume_total))
        try:
            tag = item.getVideoInfoTag()
            if hasattr(tag, "setResumePoint"):
                tag.setResumePoint(float(resume_time), float(resume_total))
        except Exception:
            pass
    return item


def _play_params(media):
    return {
        "action": "play",
        "type": media.get("media_type") or "movie",
        "tmdb_id": media.get("tmdb_id") or "",
        "imdb_id": media.get("imdb_id") or "",
        "title": media.get("title") or "",
        "season": media.get("season") if media.get("season") is not None else "",
        "episode": media.get("episode") if media.get("episode") is not None else "",
        "show_tmdb_id": media.get("show_tmdb_id") or "",
    }


def _media_page(handle, result, limit=None):
    rows, pagination = list_rows_from_result(result)
    if limit is not None:
        rows = rows[:limit]
    media_items = []
    for raw in rows:
        media = _normalize(raw)
        if media and (media.get("title") or media.get("tmdb_id")):
            media_items.append(media)
    api = DejaVuAPI()
    status_map = _status_map(api, media_items)
    for media in media_items:
        flags = _flags_for(status_map, media)
        item = _build_item(media, flags)
        xbmcplugin.addDirectoryItem(
            handle, _plugin_url(**_play_params(media)), item, isFolder=False,
        )
    return pagination


def _page(params):
    try:
        return max(1, int(params.get("page") or 1))
    except ValueError:
        return 1


def _next_page(handle, params, pagination):
    if not pagination.get("hasMore"):
        return
    next_params = dict(params)
    next_params["page"] = int(pagination.get("page") or _page(params)) + 1
    _add_folder(handle, _ls(30221) or "Next page", next_params)


def _require_auth(handle):
    if is_logged_in():
        return True
    xbmcgui.Dialog().notification(
        "dejaVu", _ls(30219) or "Sign in to dejaVu", xbmcgui.NOTIFICATION_INFO, 4000,
    )
    _add_action(handle, _ls(30219) or "Sign in to dejaVu", {"action": "connect"})
    _end(handle, content="files")
    return False


def show_home_actions(handle, params):
    _add_action(handle, "Rafraîchir la skin", {"action": "home_reload"})
    _add_action(handle, "Test bouton 2", {"action": "home_test2"})
    _add_action(handle, "Test bouton 3", {"action": "home_test3"})
    _end(handle, content="videos")


def show_home_test_movies(handle, params):
    if params.get("type") == "episodes":
        path = xbmcvfs.translatePath("special://skin/resources/data/test_episodes.json")
        try:
            with xbmcvfs.File(path, "r") as handle_file:
                payload = json.loads(handle_file.read())
        except Exception as exc:
            xbmc.log("[dejaVu.Plugin] test episodes JSON error: %s" % exc, xbmc.LOGERROR)
            _end(handle, content="videos")
            return
        episodes = payload.get("episodes", []) if isinstance(payload, dict) else []
        for raw in episodes[:3]:
            if not isinstance(raw, dict):
                continue
            title = raw.get("title") or ""
            item = xbmcgui.ListItem(label=title, offscreen=True)
            info = {
                "title": title,
                "tvshowtitle": raw.get("tvshowtitle") or "",
                "plot": raw.get("plot") or "",
                "mediatype": "episode",
                "season": int(raw.get("season") or 0),
                "episode": int(raw.get("episode") or 0),
            }
            if raw.get("year"):
                info["year"] = int(raw["year"])
            item.setInfo("video", info)
            item.setArt({
                "icon": raw.get("poster") or _icon(),
                "thumb": raw.get("poster") or _icon(),
                "poster": raw.get("poster") or _icon(),
                "fanart": raw.get("fanart") or _fanart(),
            })
            if raw.get("tmdb_id"):
                item.setUniqueIDs({"tmdb": str(raw["tmdb_id"])}, "tmdb")
                item.setProperty("tmdb_id", str(raw["tmdb_id"]))
                item.setProperty("TmdbId", str(raw["tmdb_id"]))
            if raw.get("tv_show_id"):
                item.setProperty("tvshow_tmdb_id", str(raw["tv_show_id"]))
                item.setProperty("TVShowID", str(raw["tv_show_id"]))
            item.setProperty("DBType", "episode")
            item.setProperty("media_type", "episode")
            play_params = {
                "action": "play",
                "type": "episode",
                "tmdb_id": raw.get("tmdb_id") or "",
                "show_tmdb_id": raw.get("tv_show_id") or "",
                "title": title,
                "season": raw.get("season") or "",
                "episode": raw.get("episode") or "",
            }
            xbmcplugin.addDirectoryItem(
                handle, _plugin_url(**play_params), item, isFolder=False,
            )
        _end(handle, content="episodes")
        return
    media_items = [
        {
            "tmdb_id": 27205,
            "media_type": "movie",
            "kodi_dbtype": "movie",
            "title": "Inception",
            "plot": "",
            "year": 2010,
            "imdb_id": "tt1375666",
            "poster": "https://image.tmdb.org/t/p/w500/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg",
            "fanart": "",
            "show_tmdb_id": None,
            "season": None,
            "episode": None,
            "progress": 0.0,
            "duration": 0.0,
        },
        {
            "tmdb_id": 603,
            "media_type": "movie",
            "kodi_dbtype": "movie",
            "title": "The Matrix",
            "plot": "",
            "year": 1999,
            "imdb_id": "tt0133093",
            "poster": "https://image.tmdb.org/t/p/w500/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg",
            "fanart": "",
            "show_tmdb_id": None,
            "season": None,
            "episode": None,
            "progress": 0.0,
            "duration": 0.0,
        },
        {
            "tmdb_id": 157336,
            "media_type": "movie",
            "kodi_dbtype": "movie",
            "title": "Interstellar",
            "plot": "",
            "year": 2014,
            "imdb_id": "tt0816692",
            "poster": "https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg",
            "fanart": "",
            "show_tmdb_id": None,
            "season": None,
            "episode": None,
            "progress": 0.0,
            "duration": 0.0,
        },
    ]
    for media in media_items:
        item = _build_item(media, {})
        xbmcplugin.addDirectoryItem(
            handle, _plugin_url(**_play_params(media)), item, isFolder=False,
        )
    _end(handle, content="videos")


def show_lists(handle, params):
    xbmc.log("[dejaVu.Plugin] show_lists handle=%s params=%s" % (handle, params), xbmc.LOGDEBUG)
    if not _require_auth(handle):
        return
    page = _page(params)
    rows, pagination = _cached_page(
        "lists", None, page,
        lambda api, _media_type, current_page: api.get_lists(
            page=current_page, page_size=20, minimal=False,
        ),
    )
    xbmc.log("[dejaVu.Plugin] show_lists rows=%d pagination=%s" % (len(rows), pagination), xbmc.LOGDEBUG)
    for raw in rows:
        if not isinstance(raw, dict):
            xbmc.log("[dejaVu.Plugin] show_lists skip non-dict row=%r" % (raw,), xbmc.LOGWARNING)
            continue
        list_id = raw.get("id")
        if not list_id:
            xbmc.log("[dejaVu.Plugin] show_lists skip row without id=%r" % (raw,), xbmc.LOGWARNING)
            continue
        name = raw.get("name") or "Liste"
        xbmc.log("[dejaVu.Plugin] show_lists add id=%s name=%s" % (list_id, name), xbmc.LOGDEBUG)
        description = raw.get("description") or ""
        item = xbmcgui.ListItem(label=name, offscreen=True)
        item.setInfo("video", {"title": name, "plot": description})
        item.setArt({"icon": _icon(), "thumb": _icon(), "fanart": _fanart()})
        item.setProperty("list_id", str(list_id))
        item.setProperty("listId", str(list_id))
        item.setProperty("node.type", "target_folder")
        xbmcplugin.addDirectoryItem(
            handle, _plugin_url(action="list_items", list_id=list_id, page=1),
            item, isFolder=True,
        )
    if pagination.get("hasMore"):
        _next_page(handle, {"action": "lists"}, pagination)
    _end(handle, content="files")


def show_list_items(handle, params):
    xbmc.log("[dejaVu.Plugin] show_list_items handle=%s params=%s" % (handle, params), xbmc.LOGDEBUG)
    if not _require_auth(handle):
        return
    list_id = params.get("list_id") or ""
    if not list_id:
        xbmc.log("[dejaVu.Plugin] show_list_items missing list_id", xbmc.LOGWARNING)
        _end(handle)
        return
    page = _page(params)
    xbmc.log("[dejaVu.Plugin] show_list_items list_id=%s page=%s" % (list_id, page), xbmc.LOGDEBUG)
    scope_action = "list_items:%s" % list_id
    rows, pagination = _cached_page(
        scope_action, None, page,
        lambda api, _media_type, current_page: api.get_list_items(
            list_id, page=current_page, page_size=20, minimal=False,
        ),
    )
    requested_type = str(params.get("type") or "").strip().lower()
    if requested_type:
        filtered_rows = []
        for raw in rows:
            media = _normalize(raw)
            if media and media.get("media_type") == requested_type:
                filtered_rows.append(raw)
        xbmc.log(
            "[dejaVu.Plugin] show_list_items filter type=%s rows=%d->%d"
            % (requested_type, len(rows), len(filtered_rows)),
            xbmc.LOGDEBUG,
        )
        rows = filtered_rows
    xbmc.log("[dejaVu.Plugin] show_list_items rows=%d pagination=%s" % (len(rows), pagination), xbmc.LOGDEBUG)
    _media_page(handle, {"data": rows, "pagination": pagination})
    if pagination.get("hasMore"):
        _next_page(
            handle,
            {"action": "list_items", "list_id": list_id, "type": requested_type},
            pagination,
        )
    _end(handle)


def show_favorites_widget(handle, params):
    if not _require_auth(handle):
        return
    api = DejaVuAPI()
    fetcher = lambda api, media_type, page: api.get_favorites(
        media_type=media_type, page=page, page_size=5, minimal=False,
    )
    movie_rows, _ = _cached_page("favorites", "movie", 1, fetcher)
    tv_rows, _ = _cached_page("favorites", "tv", 1, fetcher)
    rows = list(movie_rows) + list(tv_rows)
    rows.sort(key=lambda raw: str(raw.get("addedAt") or ""), reverse=True)
    rows = rows[:5]
    media_items = []
    for raw in rows:
        media = _normalize(raw)
        if media and (media.get("title") or media.get("tmdb_id")):
            media_items.append(media)
    status_map = _status_map(api, media_items)
    for media in media_items:
        flags = _flags_for(status_map, media)
        item = _build_item(media, flags)
        xbmcplugin.addDirectoryItem(
            handle, _plugin_url(**_play_params(media)), item, isFolder=False,
        )
    _end(handle, content="videos")


def show_home(handle, params):
    if is_logged_in():
        name = get_username() or "?"
        _add_folder(handle, _ls(30210), {"action": "watchlist"})
        _add_folder(handle, _ls(30211), {"action": "history"})
        _add_folder(handle, _ls(30212), {"action": "favorites"})
        _add_folder(handle, _ls(30213), {"action": "scrobbles"})
        _add_folder(handle, _ls(30214), {"action": "up_next"})
        _add_action(
            handle,
            _ls(30032) % name if "%s" in (_ls(30032) or "") else name,
            {"action": "connect"},
        )
    else:
        _add_action(handle, _ls(30219), {"action": "connect"})
    _end(handle, content="files")


def _type_folders(handle, action, current):
    if current:
        return
    _add_folder(handle, _ls(30215), {"action": action, "type": "movie"})
    _add_folder(handle, _ls(30216), {"action": action, "type": "tv"})
    if action in ("history", "scrobbles"):
        _add_folder(handle, _ls(30217), {"action": action, "type": "episode"})


def _cached_page(action, media_type, page, fetcher):
    scope = "%s:%s:page:%s" % (action, media_type or "all", page)
    cached = cache.get_cached_page(scope)
    if cached is not None:
        rows, pagination = cached
        xbmc.log("[dejaVu.Plugin] cache HIT scope=%s rows=%d page=%s" % (scope, len(rows), page), xbmc.LOGDEBUG)
        return cached
    xbmc.log("[dejaVu.Plugin] cache MISS scope=%s page=%s" % (scope, page), xbmc.LOGDEBUG)
    api = DejaVuAPI()
    result = fetcher(api, media_type, page)
    rows, pagination = list_rows_from_result(result)
    xbmc.log("[dejaVu.Plugin] API result scope=%s rows=%d pagination=%s" % (scope, len(rows), pagination), xbmc.LOGDEBUG)
    cache.cache_page(scope, rows, pagination)
    return rows, pagination

def show_list(handle, params, fetcher):
    if not _require_auth(handle):
        return
    action = params.get("action") or ""
    media_type = params.get("type") or None
    _type_folders(handle, action, media_type)
    page = _page(params)
    limit = _as_int(params.get("limit"))
    rows, pagination = _cached_page(action, media_type, page, fetcher)
    result = {"data": rows, "pagination": pagination}
    _media_page(handle, result, limit=limit)
    if limit is None:
        _next_page(handle, {"action": action, "type": media_type or ""}, pagination)
    _end(handle)


def play_item(handle, params):
    media_type = params.get("type") or "movie"
    dbtype = "movie"
    if media_type in ("tv", "tvshow"):
        dbtype = "tvshow"
    elif media_type == "episode":
        dbtype = "episode"
    info = {
        "dbtype": dbtype,
        "media_type": media_type,
        "history_type": "episode" if dbtype == "episode" else media_type,
        "tmdb_id": params.get("tmdb_id") or "",
        "imdb_id": params.get("imdb_id") or "",
        "show_tmdb_id": params.get("show_tmdb_id") or "",
        "season": _as_int(params.get("season")),
        "episode": _as_int(params.get("episode")),
        "title": params.get("title") or "",
    }
    if play_from_library(info):
        if handle is not None and int(handle) >= 0:
            xbmcplugin.endOfDirectory(int(handle), succeeded=True)
        return
    xbmcgui.Dialog().notification(
        "dejaVu",
        _ls(30218) or "Not in the Kodi library. Use your video addon to play this title.",
        xbmcgui.NOTIFICATION_INFO,
        5000,
    )
    if handle is not None and int(handle) >= 0:
        xbmcplugin.endOfDirectory(int(handle), succeeded=False)


def connect(handle, params):
    xbmc.executebuiltin("RunScript(script.dejavu,action=login)")
    if handle is not None and int(handle) >= 0:
        xbmcplugin.endOfDirectory(int(handle), succeeded=True)


def dispatch(argv):
    handle = int(argv[1]) if len(argv) > 1 else -1
    query = argv[2][1:] if len(argv) > 2 and argv[2].startswith("?") else (
        argv[2] if len(argv) > 2 else ""
    )
    params = dict(parse_qsl(query, keep_blank_values=True))
    action = params.get("action") or ""
    xbmc.log("[dejaVu.Plugin] action=%s" % action, xbmc.LOGDEBUG)

    if action == "play":
        play_item(handle, params)
        return
    if action == "connect":
        connect(handle, params)
        return
    if action == "home_actions":
        show_home_actions(handle, params)
        return
    if action == "home_test_movies":
        show_home_test_movies(handle, params)
        return
    if action == "favorites_widget":
        show_favorites_widget(handle, params)
        return
    if action == "lists":
        show_lists(handle, params)
        return
    if action == "list_items":
        show_list_items(handle, params)
        return
    if action == "home_reload":
        xbmc.executebuiltin("ReloadSkin")
        _end(handle, content="videos")
        return
    if action in ("home_test2", "home_test3"):
        xbmcgui.Dialog().notification("dejaVu", action, xbmcgui.NOTIFICATION_INFO, 2500)
        _end(handle, content="videos")
        return
    if action in ("", "home"):
        show_home(handle, params)
        return

    fetchers = {
        "watchlist": lambda api, media_type, page: api.get_watchlist(
            media_type=media_type, page=page, page_size=20, minimal=False,
        ),
        "history": lambda api, media_type, page: api.get_history(
            media_type=media_type, page=page, page_size=20, sort="watchedAt:desc",
            minimal=False,
        ),
        "favorites": lambda api, media_type, page: api.get_favorites(
            media_type=media_type, page=page, page_size=20, minimal=False,
        ),
        "scrobbles": lambda api, media_type, page: api.get_scrobbles(
            media_type=media_type, page=page, page_size=20, minimal=False,
        ),
        "up_next": lambda api, media_type, page: api.get_up_next(
            page=page, page_size=20, minimal=False,
        ),
    }
    fetcher = fetchers.get(action)
    if fetcher:
        show_list(handle, params, fetcher)
        return
    show_home(handle, params)
