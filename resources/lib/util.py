# -*- coding: utf-8 -*-
"""Shared helpers for language, media info, Kodi playcount, and change notifications."""

import json
import xbmc
import xbmcaddon

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
        xbmc.executebuiltin(
            f"NotifyAll({ADDON_ID}, {ADDON_ID}.changed, {json.dumps(payload)})"
        )
    except Exception as e:
        _log(f"notify_changed failed: {e}", xbmc.LOGWARNING)


def unwrap_data(result):
    """Return the `data` payload from a v1 `{success, data}` response, or the value as-is."""
    if isinstance(result, dict) and "data" in result:
        return result.get("data")
    return result


def status_for(result, media_type, tmdb_id):
    """Pick the media/status entry for type+id from a v1 response."""
    data = unwrap_data(result) or {}
    if not isinstance(data, dict):
        return {}
    key = f"{media_type}:{tmdb_id}"
    return data.get(key) or data.get(str(tmdb_id)) or {}


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


def get_listitem_media_info():
    """
    Extract identifiers from the currently focused ListItem.

    Returns a dict with:
      dbtype, api_type, history_type, tmdb_id, show_tmdb_id,
      season, episode, dbid, title
    """
    db_type = (
        xbmc.getInfoLabel("ListItem.DBType")
        or xbmc.getInfoLabel("ListItem.Property(DBType)")
        or xbmc.getInfoLabel("ListItem.Property(media_type)")
        or ""
    )
    if not db_type:
        s_cat = xbmc.getInfoLabel("ListItem.Property(sCat)")
        if s_cat == "1":
            db_type = "movie"
        elif s_cat in ("2", "3", "9"):
            db_type = "tvshow"

    tmdb_id = (
        xbmc.getInfoLabel("ListItem.UniqueID(tmdb)")
        or xbmc.getInfoLabel("ListItem.Property(tmdb_id)")
        or xbmc.getInfoLabel("ListItem.Property(TmdbId)")
        or xbmc.getInfoLabel("ListItem.Property(tmdbid)")
        or ""
    )
    imdb_id = (
        xbmc.getInfoLabel("ListItem.UniqueID(imdb)")
        or xbmc.getInfoLabel("ListItem.IMDBNumber")
        or xbmc.getInfoLabel("ListItem.Property(imdb_id)")
        or ""
    )

    show_tmdb = (
        xbmc.getInfoLabel("ListItem.TVShowUniqueID(tmdb)")
        or xbmc.getInfoLabel("ListItem.UniqueID(tvshow_tmdb)")
        or xbmc.getInfoLabel("ListItem.Property(tvshow_tmdb_id)")
        or xbmc.getInfoLabel("ListItem.Property(TVShowID)")
        or ""
    )

    season_raw = xbmc.getInfoLabel("ListItem.Season")
    episode_raw = xbmc.getInfoLabel("ListItem.Episode")
    season = int(season_raw) if season_raw and str(season_raw).lstrip("-").isdigit() else None
    episode = int(episode_raw) if episode_raw and str(episode_raw).lstrip("-").isdigit() else None
    dbid = xbmc.getInfoLabel("ListItem.DBID") or ""

    if tmdb_id and str(tmdb_id).startswith("tt"):
        imdb_id = imdb_id or tmdb_id
        tmdb_id = ""

    api_type = ""
    if db_type in ("tvshow", "tv", "season"):
        api_type = "tv"
    elif db_type == "episode":
        api_type = "tv"
    elif db_type == "movie":
        api_type = "movie"
    elif tmdb_id:
        api_type = "movie"

    history_type = "episode" if db_type == "episode" else ("movie" if api_type == "movie" else "tv")

    return {
        "dbtype": db_type,
        "api_type": api_type,
        "history_type": history_type,
        "tmdb_id": str(tmdb_id) if tmdb_id else "",
        "imdb_id": str(imdb_id) if imdb_id else "",
        "show_tmdb_id": str(show_tmdb) if show_tmdb else "",
        "season": season,
        "episode": episode,
        "dbid": dbid,
        "title": xbmc.getInfoLabel("ListItem.Title") or "",
    }


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
        year = xbmc.getInfoLabel("ListItem.Year") or None
        result = api.resolve_media(
            title=info["title"],
            media_type=payload_type,
            year=int(year) if year and str(year).isdigit() else None,
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
