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


def set_kodi_playcount(dbid, dbtype, watched=True):
    """Mirror dejaVu watched status onto the Kodi library item when a DBID is available."""
    if not dbid:
        return
    try:
        dbid = int(dbid)
    except (TypeError, ValueError):
        return

    if dbtype == "movie":
        method, id_key = "VideoLibrary.SetMovieDetails", "movieid"
    elif dbtype == "episode":
        method, id_key = "VideoLibrary.SetEpisodeDetails", "episodeid"
    else:
        return

    req = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": {id_key: dbid, "playcount": 1 if watched else 0},
        "id": 1,
    })
    try:
        xbmc.executeJSONRPC(req)
    except Exception as e:
        _log(f"set_kodi_playcount failed: {e}", xbmc.LOGWARNING)


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
