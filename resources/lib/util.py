# -*- coding: utf-8 -*-
"""Shared helpers for language, media info, Kodi playcount, and change notifications."""

import json
import sys
import xbmc
import xbmcaddon

from .pure import (
    ids_from_plugin_path,
    is_addons_path,
    is_context_media,
    listitem_api_type,
    listitem_history_type,
    normalize_dbtype,
    parse_optional_int,
    status_flags,
    strip_kodi_label,
    unwrap_data,
)

ADDON = xbmcaddon.Addon()
ADDON_ID = "script.dejavu"



def _log(msg, level=xbmc.LOGDEBUG):
    xbmc.log(f"[dejaVu] {msg}", level)


def get_accept_language():
    """Map Kodi UI language to an Accept-Language value (dejaVu defaults to fr-FR)."""
    try:
        lang = xbmc.getLanguage(xbmc.ISO_639_1)
    except Exception:
        lang = ""
    if not lang:
        return "fr-FR"
    lang = lang.replace("_", "-").lower()
    if lang.startswith("fr"):
        return "fr-FR"
    if lang.startswith("en"):
        return "en-US"
    if "-" in lang:
        parts = lang.split("-", 1)
        return f"{parts[0]}-{parts[1].upper()}"
    return lang


def notify_changed(action, media_type=None, tmdb_id=None, extra=None):
    """Tell other addons that dejaVu state changed so they can refresh overlays."""
    payload = {"action": action}
    if media_type:
        payload["type"] = media_type
    if tmdb_id is not None:
        payload["id"] = tmdb_id
    if extra:
        payload.update(extra)
    try:
        # Quote the JSON so commas are not treated as NotifyAll argument separators.
        payload_json = json.dumps(payload)
        xbmc.executebuiltin(
            "NotifyAll(%s, %s, %s)" % (ADDON_ID, f"{ADDON_ID}.changed", json.dumps(payload_json))
        )
    except Exception as e:
        _log(f"notify_changed failed: {e}", xbmc.LOGWARNING)


def status_for(result, media_type, tmdb_id):
    """Pick the media/status entry for type+id from a v1 response."""
    return status_flags(result, media_type, tmdb_id)


def _jsonrpc(method, params, req_id=1):
    try:
        raw = xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": req_id,
        }))
        return json.loads(raw)
    except Exception as e:
        _log(f"JSON-RPC {method} failed: {e}", xbmc.LOGWARNING)
        return {}


def _uniqueid_matches(uniqueids, tmdb_id=None, imdb_id=None):
    if not isinstance(uniqueids, dict):
        return False
    values = [str(v) for v in uniqueids.values() if v]
    if tmdb_id and str(tmdb_id) in values:
        return True
    if imdb_id and str(imdb_id) in values:
        return True
    tmdb = uniqueids.get("tmdb") or uniqueids.get("unknown")
    if tmdb_id and str(tmdb) == str(tmdb_id):
        return True
    imdb = uniqueids.get("imdb")
    if imdb_id and str(imdb) == str(imdb_id):
        return True
    return False


def _find_library_movie(info):
    dbid = info.get("dbid")
    if dbid and (info.get("dbtype") or "movie") == "movie":
        try:
            return int(dbid)
        except (TypeError, ValueError):
            pass

    imdb_id = info.get("imdb_id") or ""
    tmdb_id = info.get("tmdb_id") or ""
    candidates = []
    if imdb_id:
        candidates.append({"field": "imdbnumber", "operator": "is", "value": str(imdb_id)})
    if tmdb_id:
        candidates.append({"field": "uniqueid", "operator": "is", "value": str(tmdb_id)})
    for flt in candidates:
        res = _jsonrpc("VideoLibrary.GetMovies", {
            "filter": flt,
            "properties": ["uniqueid", "imdbnumber"],
            "limits": {"start": 0, "end": 5},
        })
        for movie in (res.get("result") or {}).get("movies") or []:
            uniqueids = movie.get("uniqueid") or {}
            if _uniqueid_matches(uniqueids, tmdb_id, imdb_id):
                return movie.get("movieid")
            if imdb_id and str(movie.get("imdbnumber") or "") == str(imdb_id):
                return movie.get("movieid")
    return None


def _find_library_tvshow(info):
    dbtype = info.get("dbtype") or ""
    dbid = info.get("dbid")
    if dbid and dbtype in ("tvshow", "tv"):
        try:
            return int(dbid)
        except (TypeError, ValueError):
            pass

    imdb_id = info.get("imdb_id") or ""
    tmdb_id = info.get("show_tmdb_id") or info.get("tmdb_id") or ""
    filters = []
    if imdb_id:
        filters.append({"field": "imdbnumber", "operator": "is", "value": str(imdb_id)})
    if tmdb_id:
        filters.append({"field": "uniqueid", "operator": "is", "value": str(tmdb_id)})
    for flt in filters:
        res = _jsonrpc("VideoLibrary.GetTVShows", {
            "filter": flt,
            "properties": ["uniqueid", "imdbnumber"],
            "limits": {"start": 0, "end": 5},
        })
        for show in (res.get("result") or {}).get("tvshows") or []:
            uniqueids = show.get("uniqueid") or {}
            if _uniqueid_matches(uniqueids, tmdb_id, imdb_id):
                return show.get("tvshowid")
            if imdb_id and str(show.get("imdbnumber") or "") == str(imdb_id):
                return show.get("tvshowid")
    return None


def _find_library_episode(info):
    dbid = info.get("dbid")
    if dbid and info.get("dbtype") == "episode":
        try:
            return int(dbid)
        except (TypeError, ValueError):
            pass

    season = info.get("season")
    episode = info.get("episode")
    if season is None or episode is None:
        return None

    tvshowid = _find_library_tvshow(info)
    if not tvshowid:
        return None

    res = _jsonrpc("VideoLibrary.GetEpisodes", {
        "tvshowid": tvshowid,
        "season": int(season),
        "properties": ["episode", "season"],
        "filter": {"field": "episode", "operator": "is", "value": str(int(episode))},
        "limits": {"start": 0, "end": 5},
    })
    episodes = (res.get("result") or {}).get("episodes") or []
    if episodes:
        return episodes[0].get("episodeid")
    return None


def _kodi_sync_enabled():
    try:
        return ADDON.getSettingBool("sync_kodi_library")
    except Exception:
        return True


def sync_kodi_library(info, watched=None, rating=None):
    """
    Mirror dejaVu watched/rating onto the Kodi video library.

    Uses ListItem.DBID when present, otherwise looks up the item by TMDB/IMDb
    uniqueid so a vStream context action can still update the scraped library.
    """
    if not info or not _kodi_sync_enabled():
        return
    if watched is None and rating is None:
        return

    dbtype = info.get("dbtype") or ""
    if dbtype in ("tvshow", "tv"):
        method, id_key, lib_id = "VideoLibrary.SetTVShowDetails", "tvshowid", _find_library_tvshow(info)
    elif dbtype == "episode" or info.get("history_type") == "episode":
        method, id_key, lib_id = "VideoLibrary.SetEpisodeDetails", "episodeid", _find_library_episode(info)
    elif dbtype == "season":
        return
    else:
        method, id_key, lib_id = "VideoLibrary.SetMovieDetails", "movieid", _find_library_movie(info)

    if not lib_id:
        _log("Kodi library sync skipped: no matching library item.", xbmc.LOGDEBUG)
        return

    params = {id_key: int(lib_id)}
    if watched is not None and method != "VideoLibrary.SetTVShowDetails":
        params["playcount"] = 1 if watched else 0
    if rating is not None:
        try:
            params["userrating"] = max(0, int(rating))
        except (TypeError, ValueError):
            pass
    if len(params) == 1:
        return

    res = _jsonrpc(method, params)
    if res.get("error"):
        _log(f"Kodi library sync error: {res.get('error')}", xbmc.LOGWARNING)
    else:
        _log(f"Kodi library sync {method} {params}", xbmc.LOGDEBUG)


def set_kodi_playcount(dbid, dbtype, watched=True):
    """Backward-compatible wrapper used by the scrobbler."""
    sync_kodi_library({"dbid": dbid, "dbtype": dbtype}, watched=watched)


def _empty_media_info():
    return {
        "dbtype": "",
        "api_type": "",
        "history_type": "",
        "tmdb_id": "",
        "imdb_id": "",
        "show_tmdb_id": "",
        "season": None,
        "episode": None,
        "dbid": "",
        "title": "",
        "year": None,
        "s_cat": "",
    }


def _tag_unique_id(tag, key):
    if tag is None:
        return ""
    try:
        val = tag.getUniqueID(key)
        if val:
            return str(val)
    except Exception:
        pass
    try:
        ids = tag.getUniqueIDs() or {}
        val = ids.get(key)
        if val:
            return str(val)
    except Exception:
        pass
    return ""


def _item_path(item, tag=None):
    path = ""
    if item is not None:
        try:
            path = item.getPath() or ""
        except Exception:
            path = ""
    if not path and tag is not None:
        for attr in ("getFilenameAndPath", "getPath", "getFile"):
            getter = getattr(tag, attr, None)
            if not getter:
                continue
            try:
                path = getter() or ""
            except Exception:
                path = ""
            if path:
                break
    return path or ""


def _prop(item, key):
    if item is not None:
        try:
            return item.getProperty(key) or ""
        except Exception:
            return ""
    return xbmc.getInfoLabel("ListItem.Property(%s)" % key) or ""


def _first_prop(item, keys):
    for key in keys:
        val = _prop(item, key)
        if val:
            return val
    return ""


def _label(name):
    return xbmc.getInfoLabel("ListItem.%s" % name) or ""


def _assemble_media_info(
    db_type,
    s_cat,
    tmdb_id,
    imdb_id,
    show_tmdb,
    season,
    episode,
    dbid,
    title,
    year,
    path,
):
    if is_addons_path(path):
        return _empty_media_info()

    path_ids = ids_from_plugin_path(path)
    db_type = normalize_dbtype(db_type, s_cat) or path_ids.get("media_type") or ""
    tmdb_id = str(tmdb_id or path_ids.get("tmdb_id") or "")
    imdb_id = str(imdb_id or path_ids.get("imdb_id") or "")
    show_tmdb = str(show_tmdb or path_ids.get("show_tmdb_id") or "")
    if tmdb_id.startswith("tt"):
        imdb_id = imdb_id or tmdb_id
        tmdb_id = ""

    year = parse_optional_int(year)
    dbid = str(dbid or "")
    if dbid in ("-1", "0"):
        dbid = ""

    return {
        "dbtype": db_type,
        "api_type": listitem_api_type(db_type),
        "history_type": listitem_history_type(db_type),
        "tmdb_id": tmdb_id,
        "imdb_id": imdb_id,
        "show_tmdb_id": show_tmdb,
        "season": parse_optional_int(season),
        "episode": parse_optional_int(episode),
        "dbid": dbid,
        "title": strip_kodi_label(title or ""),
        "year": year,
        "s_cat": str(s_cat or ""),
    }


def _media_info_from_listitem(item):
    tag = None
    try:
        tag = item.getVideoInfoTag()
    except Exception:
        tag = None

    path = _item_path(item, tag)
    db_type = ""
    tmdb_id = ""
    imdb_id = ""
    show_tmdb = ""
    season = None
    episode = None
    dbid = ""
    title = ""
    year = None

    if tag is not None:
        try:
            db_type = tag.getMediaType() or ""
        except Exception:
            db_type = ""
        tmdb_id = (
            _tag_unique_id(tag, "tmdb")
            or _tag_unique_id(tag, "themoviedb")
        )
        imdb_id = _tag_unique_id(tag, "imdb")
        if not tmdb_id:
            unknown = _tag_unique_id(tag, "unknown")
            if unknown.isdigit():
                tmdb_id = unknown
            elif unknown.startswith("tt"):
                imdb_id = imdb_id or unknown
        if not imdb_id:
            try:
                imdb_id = tag.getIMDBNumber() or ""
            except Exception:
                imdb_id = ""
        show_tmdb = (
            _tag_unique_id(tag, "tvshow.tmdb")
            or _tag_unique_id(tag, "tvshow_tmdb")
            or _tag_unique_id(tag, "tvshow")
        )
        try:
            season = tag.getSeason()
        except Exception:
            season = None
        try:
            episode = tag.getEpisode()
        except Exception:
            episode = None
        try:
            raw_dbid = tag.getDbId()
            if raw_dbid is not None and int(raw_dbid) > 0:
                dbid = str(int(raw_dbid))
        except Exception:
            dbid = ""
        try:
            title = tag.getTitle() or ""
        except Exception:
            title = ""
        try:
            year = tag.getYear()
        except Exception:
            year = None

    if not title:
        try:
            title = item.getLabel() or ""
        except Exception:
            title = ""

    if not db_type:
        db_type = _prop(item, "DBType") or _prop(item, "media_type")
    s_cat = _prop(item, "sCat")
    tmdb_id = tmdb_id or _first_prop(item, (
        "tmdb_id", "TmdbId", "tmdbid", "tmdb",
        "elementum_tmdb_id", "elementum_movie_tmdb_id",
    ))
    # sys.listitem UniqueIDs are often empty in context menus; infolabels still work.
    tmdb_id = tmdb_id or _label("UniqueID(tmdb)") or _label("UniqueID(themoviedb)")
    unknown = _label("UniqueID(unknown)")
    if not tmdb_id and unknown.isdigit():
        tmdb_id = unknown
    imdb_id = imdb_id or _first_prop(item, (
        "imdb_id", "imdb", "imdbid", "elementum_imdb_id",
    ))
    if unknown.startswith("tt"):
        imdb_id = imdb_id or unknown
    show_tmdb = show_tmdb or _first_prop(item, (
        "tvshow_tmdb_id", "TVShowID", "elementum_tvshow_tmdb_id",
    ))

    return _assemble_media_info(
        db_type,
        s_cat,
        tmdb_id,
        imdb_id,
        show_tmdb,
        season,
        episode,
        dbid,
        title,
        year,
        path,
    )


def _media_info_from_infolabels():
    path = _label("FileNameAndPath") or _label("FolderPath")
    db_type = _label("DBType") or _label("Property(DBType)") or _label("Property(media_type)")
    return _assemble_media_info(
        db_type,
        _label("Property(sCat)"),
        _label("UniqueID(tmdb)")
        or _label("UniqueID(themoviedb)")
        or _label("Property(tmdb_id)")
        or _label("Property(TmdbId)")
        or _label("Property(tmdbid)")
        or _label("Property(tmdb)")
        or _label("Property(elementum_tmdb_id)"),
        _label("UniqueID(imdb)")
        or _label("IMDBNumber")
        or _label("Property(imdb_id)")
        or _label("Property(imdb)"),
        _label("TVShowUniqueID(tmdb)")
        or _label("UniqueID(tvshow_tmdb)")
        or _label("Property(tvshow_tmdb_id)")
        or _label("Property(TVShowID)")
        or _label("Property(elementum_tvshow_tmdb_id)"),
        _label("Season"),
        _label("Episode"),
        _label("DBID"),
        _label("Title"),
        _label("Year"),
        path,
    )


def get_listitem_media_info(listitem=None):
    """
    Extract identifiers from the context-menu ListItem (sys.listitem).

    Falls back to ListItem.* infolabels when sys.listitem is missing.
    Returns a dict with dbtype, api_type, history_type, tmdb_id,
    show_tmdb_id, season, episode, dbid, title, year.
    """
    if listitem is None:
        listitem = getattr(sys, "listitem", None)
    if listitem is not None:
        return _media_info_from_listitem(listitem)
    return _media_info_from_infolabels()


def resolve_listitem_tmdb(api, info):
    """Fill missing numeric TMDB IDs via POST /media/resolve when possible."""
    tmdb_id = info.get("tmdb_id") or ""
    if tmdb_id and str(tmdb_id).isdigit():
        return info

    media_type = info.get("api_type") or "movie"
    payload_type = "tv" if media_type == "tv" else "movie"
    result = None
    if info.get("imdb_id"):
        result = api.resolve_media(imdb_id=info["imdb_id"], media_type=payload_type)
    if not result and info.get("title"):
        year = info.get("year")
        if year is None:
            year_raw = xbmc.getInfoLabel("ListItem.Year") or None
            year = int(year_raw) if year_raw and str(year_raw).isdigit() else None
        result = api.resolve_media(
            title=info["title"],
            media_type=payload_type,
            year=int(year) if year is not None else None,
        )

    data = unwrap_data(result) if result else None
    if isinstance(data, dict) and data.get("tmdbId"):
        resolved = str(data["tmdbId"])
        if info.get("dbtype") == "episode":
            info["show_tmdb_id"] = info.get("show_tmdb_id") or resolved
        else:
            info["tmdb_id"] = resolved
            if data.get("type") in ("movie", "tv"):
                info["api_type"] = data["type"]
    return info
