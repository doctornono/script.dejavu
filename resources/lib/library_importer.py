# -*- coding: utf-8 -*-
"""
Kodi video-library import (migration into dejaVu).

This is NOT scrobble: it snapshots playcount / lastplayed / userrating / resume
and playlists, then POSTs /kodi/import. Live playback still goes through scrobbler.py.
"""

import re
import uuid
from datetime import datetime

import xbmc
import xbmcaddon
import xbmcgui

from .api_client import DejaVuAPI
from .util import _jsonrpc, notify_changed, unwrap_data

ADDON = xbmcaddon.Addon()
IMPORT_STATUS_PROP = "script.dejavu.import.status"

PAGE_SIZE = 200
CHUNK_SIZE = 200
VIDEO_PLAYLISTS = "special://profile/playlists/video/"

MOVIE_PROPS = [
    "title", "originaltitle", "year", "playcount", "lastplayed",
    "userrating", "uniqueid", "imdbnumber", "dateadded", "runtime", "resume",
]
SHOW_PROPS = [
    "title", "originaltitle", "year", "playcount", "lastplayed",
    "userrating", "uniqueid", "imdbnumber", "dateadded", "episode",
    "watchedepisodes",
]
EPISODE_PROPS = [
    "title", "showtitle", "season", "episode", "playcount", "lastplayed",
    "userrating", "uniqueid", "tvshowid", "runtime", "resume", "dateadded",
]
DIR_PROPS = [
    "title", "year", "uniqueid", "imdbnumber", "playcount", "runtime", "resume",
]


def _ls(string_id):
    return ADDON.getLocalizedString(string_id)


def _log(msg, level=xbmc.LOGDEBUG):
    xbmc.log(f"[dejaVu.Import] {msg}", level)


def _window():
    return xbmcgui.Window(10000)


def set_import_status(status):
    _window().setProperty(IMPORT_STATUS_PROP, status)


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


def kodi_datetime_to_iso(value):
    if not value or str(value) in ("0", "0000-00-00 00:00:00"):
        return None
    text = str(value).strip().replace(" ", "T", 1)
    if len(text) >= 19:
        return text[:19]
    return text or None


def _year(value):
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year if year > 0 else None


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _runtime_seconds(value):
    seconds = _int(value, 0)
    return seconds if seconds > 0 else None


def _resume_obj(item, runtime_seconds):
    resume = item.get("resume") or {}
    if not isinstance(resume, dict):
        return None
    try:
        position = float(resume.get("position") or 0)
    except (TypeError, ValueError):
        position = 0.0
    try:
        total = float(resume.get("total") or 0)
    except (TypeError, ValueError):
        total = 0.0
    if total <= 0 and runtime_seconds:
        total = float(runtime_seconds)
    if position <= 0:
        return None
    return {"position": int(position), "total": int(total) if total else int(position)}


def classify(tmdb_id, imdb_id, title, year, show_tmdb_id=None, season=None, episode=None):
    if tmdb_id:
        return "certain"
    if show_tmdb_id is not None and season is not None and episode is not None:
        return "certain"
    if imdb_id or (title and year):
        return "review"
    if title:
        return "review"
    return "unidentified"


def _item_label(title, year=None, extra=None):
    parts = [title or "?"]
    if year:
        parts[0] = f"{parts[0]} ({year})"
    if extra:
        parts.append(extra)
    return " ".join(parts)


def video_library_totals():
    """Quick (movie, tvshow) counts via JSON-RPC limits.total."""
    movies = _jsonrpc("VideoLibrary.GetMovies", {
        "properties": ["title"],
        "limits": {"start": 0, "end": 0},
    })
    shows = _jsonrpc("VideoLibrary.GetTVShows", {
        "properties": ["title"],
        "limits": {"start": 0, "end": 0},
    })
    movie_total = ((movies.get("result") or {}).get("limits") or {}).get("total", 0)
    show_total = ((shows.get("result") or {}).get("limits") or {}).get("total", 0)
    return _int(movie_total), _int(show_total)


def _paginated(method, result_key, properties, extra_params=None, abort_cb=None, progress_cb=None, label=""):
    items = []
    start = 0
    total = None
    while True:
        if abort_cb and abort_cb():
            return None
        params = dict(extra_params or {})
        params["properties"] = properties
        params["limits"] = {"start": start, "end": start + PAGE_SIZE}
        res = _jsonrpc(method, params)
        if res.get("error"):
            _log(f"{method} error: {res.get('error')}", xbmc.LOGWARNING)
            break
        result = res.get("result") or {}
        batch = result.get(result_key) or []
        limits = result.get("limits") or {}
        if total is None:
            total = _int(limits.get("total"), 0)
        items.extend(batch)
        if progress_cb and total:
            progress_cb(min(100, int(len(items) * 100 / max(total, 1))), label)
        if not batch or len(items) >= total:
            break
        start += PAGE_SIZE
        if xbmc.Monitor().waitForAbort(0.01):
            return None
    return items


def _movie_record(raw):
    tmdb_id, imdb_id = extract_ids(raw.get("uniqueid"), raw.get("imdbnumber"))
    title = (raw.get("title") or "").strip()
    original = (raw.get("originaltitle") or "").strip()
    year = _year(raw.get("year"))
    play_count = _int(raw.get("playcount"))
    rating = _int(raw.get("userrating"))
    runtime = _runtime_seconds(raw.get("runtime"))
    resume = _resume_obj(raw, runtime)
    confidence = classify(tmdb_id, imdb_id, title, year)
    payload = {
        "title": title,
        "playCount": play_count,
    }
    if tmdb_id:
        payload["tmdbId"] = tmdb_id
    if imdb_id:
        payload["imdbId"] = imdb_id
    if original and original != title:
        payload["originalTitle"] = original
    if year:
        payload["year"] = year
    last_played = kodi_datetime_to_iso(raw.get("lastplayed"))
    if last_played:
        payload["lastPlayed"] = last_played
    date_added = kodi_datetime_to_iso(raw.get("dateadded"))
    if date_added:
        payload["dateAdded"] = date_added
    if rating > 0:
        payload["rating"] = min(10, rating)
    if runtime:
        payload["runtime"] = runtime
    if resume:
        payload["resume"] = resume
    return {
        "kind": "movie",
        "dbid": raw.get("movieid"),
        "confidence": confidence,
        "label": _item_label(title, year),
        "watched": play_count > 0,
        "payload": payload,
    }


def _show_record(raw):
    tmdb_id, imdb_id = extract_ids(raw.get("uniqueid"), raw.get("imdbnumber"))
    title = (raw.get("title") or "").strip()
    original = (raw.get("originaltitle") or "").strip()
    year = _year(raw.get("year"))
    watched_eps = _int(raw.get("watchedepisodes"))
    episode_count = _int(raw.get("episode"))
    rating = _int(raw.get("userrating"))
    confidence = classify(tmdb_id, imdb_id, title, year)
    payload = {
        "title": title,
        "watchedEpisodes": watched_eps,
        "episodeCount": episode_count,
        "playCount": _int(raw.get("playcount")),
    }
    if tmdb_id:
        payload["tmdbId"] = tmdb_id
    if imdb_id:
        payload["imdbId"] = imdb_id
    if original and original != title:
        payload["originalTitle"] = original
    if year:
        payload["year"] = year
    last_played = kodi_datetime_to_iso(raw.get("lastplayed"))
    if last_played:
        payload["lastPlayed"] = last_played
    if rating > 0:
        payload["rating"] = min(10, rating)
    return {
        "kind": "tv",
        "dbid": raw.get("tvshowid"),
        "confidence": confidence,
        "label": _item_label(title, year),
        "watched": watched_eps > 0,
        "payload": payload,
        "tmdb_id": tmdb_id,
        "imdb_id": imdb_id,
    }


def _episode_record(raw, shows_by_id):
    tmdb_id, imdb_id = extract_ids(raw.get("uniqueid"), raw.get("imdbnumber"))
    title = (raw.get("title") or "").strip()
    show_title = (raw.get("showtitle") or "").strip()
    season = raw.get("season")
    episode = raw.get("episode")
    try:
        season = int(season) if season is not None else None
    except (TypeError, ValueError):
        season = None
    try:
        episode = int(episode) if episode is not None else None
    except (TypeError, ValueError):
        episode = None
    show = shows_by_id.get(raw.get("tvshowid")) or {}
    show_tmdb = show.get("tmdb_id")
    show_imdb = show.get("imdb_id")
    play_count = _int(raw.get("playcount"))
    rating = _int(raw.get("userrating"))
    runtime = _runtime_seconds(raw.get("runtime"))
    resume = _resume_obj(raw, runtime)
    confidence = classify(
        tmdb_id, imdb_id or show_imdb, title or show_title, None,
        show_tmdb_id=show_tmdb, season=season, episode=episode,
    )
    payload = {
        "title": title,
        "showTitle": show_title,
        "playCount": play_count,
    }
    if tmdb_id:
        payload["tmdbId"] = tmdb_id
    if show_tmdb:
        payload["showTmdbId"] = show_tmdb
    if imdb_id or show_imdb:
        payload["imdbId"] = imdb_id or show_imdb
    if season is not None:
        payload["season"] = season
    if episode is not None:
        payload["episode"] = episode
    last_played = kodi_datetime_to_iso(raw.get("lastplayed"))
    if last_played:
        payload["lastPlayed"] = last_played
    date_added = kodi_datetime_to_iso(raw.get("dateadded"))
    if date_added:
        payload["dateAdded"] = date_added
    if rating > 0:
        payload["rating"] = min(10, rating)
    if runtime:
        payload["runtime"] = runtime
    if resume:
        payload["resume"] = resume
    se = ""
    if season is not None and episode is not None:
        se = f"S{season:02d}E{episode:02d}"
    return {
        "kind": "episode",
        "dbid": raw.get("episodeid"),
        "confidence": confidence,
        "label": _item_label(show_title or title, extra=se),
        "watched": play_count > 0,
        "payload": payload,
    }


def _playlist_item_from_file(entry, movies_by_id, episodes_by_id, shows_by_id):
    entry_type = (entry.get("type") or "").lower()
    dbid = entry.get("id")
    if entry_type == "movie" and dbid in movies_by_id:
        rec = movies_by_id[dbid]
        return _list_item_from_record(rec, "movie")
    if entry_type == "episode" and dbid in episodes_by_id:
        rec = episodes_by_id[dbid]
        return _list_item_from_record(rec, "episode")
    if entry_type in ("tvshow", "tv") and dbid in shows_by_id:
        rec = shows_by_id[dbid]
        return _list_item_from_record(rec, "tv")
    tmdb_id, imdb_id = extract_ids(entry.get("uniqueid"), entry.get("imdbnumber"))
    title = (entry.get("title") or entry.get("label") or "").strip()
    year = _year(entry.get("year"))
    if not tmdb_id and not imdb_id and not title:
        return None
    media_type = "movie"
    if entry_type in ("tvshow", "tv"):
        media_type = "tv"
    elif entry_type == "episode":
        media_type = "episode"
    item = {"type": media_type, "title": title}
    if tmdb_id:
        item["tmdbId"] = tmdb_id
    if imdb_id:
        item["imdbId"] = imdb_id
    if year:
        item["year"] = year
    return item


def _list_item_from_record(rec, media_type):
    payload = rec.get("payload") or {}
    item = {"type": media_type, "title": payload.get("title") or rec.get("label") or ""}
    if payload.get("tmdbId"):
        item["tmdbId"] = payload["tmdbId"]
    if payload.get("showTmdbId") and media_type == "episode":
        item["showTmdbId"] = payload["showTmdbId"]
        item["season"] = payload.get("season")
        item["episode"] = payload.get("episode")
    if payload.get("imdbId"):
        item["imdbId"] = payload["imdbId"]
    if payload.get("year"):
        item["year"] = payload["year"]
    return item


def _scan_playlists(movies_by_id, episodes_by_id, shows_by_id, abort_cb=None, progress_cb=None):
    if abort_cb and abort_cb():
        return None
    if progress_cb:
        progress_cb(0, _ls(30169))
    listing = _jsonrpc("Files.GetDirectory", {
        "directory": VIDEO_PLAYLISTS,
        "media": "video",
    })
    files = (listing.get("result") or {}).get("files") or []
    playlists = []
    for entry in files:
        if abort_cb and abort_cb():
            return None
        path = entry.get("file") or ""
        name = (entry.get("label") or "").strip()
        if not path or not name:
            continue
        if not path.lower().endswith((".xsp", ".m3u", ".pls")):
            if entry.get("filetype") != "file":
                continue
        inner = _jsonrpc("Files.GetDirectory", {
            "directory": path,
            "media": "video",
            "properties": DIR_PROPS,
        })
        inner_files = (inner.get("result") or {}).get("files") or []
        items = []
        for child in inner_files:
            mapped = _playlist_item_from_file(child, movies_by_id, episodes_by_id, shows_by_id)
            if mapped:
                items.append(mapped)
        if items:
            playlists.append({"name": name, "items": items})
        if xbmc.Monitor().waitForAbort(0.01):
            return None
    return playlists


def _parse_videodb_path(path):
    text = (path or "").strip()
    match = re.search(r'videodb://[^"\']+', text)
    if match:
        text = match.group(0)
    text = text.rstrip("/")
    match = re.match(r"videodb://movies/titles/(\d+)", text)
    if match:
        return "movie", int(match.group(1))
    match = re.match(r"videodb://tvshows/titles/(\d+)/(\d+)/(\d+)", text)
    if match:
        return "episode", int(match.group(3))
    match = re.match(r"videodb://tvshows/titles/(\d+)", text)
    if match:
        return "tvshow", int(match.group(1))
    return None, None


def _scan_favorites(movies_by_id, episodes_by_id, shows_by_id, abort_cb=None, progress_cb=None):
    if abort_cb and abort_cb():
        return None
    if progress_cb:
        progress_cb(0, _ls(30170))
    res = _jsonrpc("Favourites.GetFavourites", {
        "properties": ["path", "windowparameter", "thumbnail"],
    })
    favourites = (res.get("result") or {}).get("favourites") or []
    items = []
    seen = set()
    for fav in favourites:
        if abort_cb and abort_cb():
            return None
        path = fav.get("path") or fav.get("windowparameter") or ""
        kind, dbid = _parse_videodb_path(path)
        rec = None
        media_type = None
        if kind == "movie":
            rec, media_type = movies_by_id.get(dbid), "movie"
        elif kind == "episode":
            rec, media_type = episodes_by_id.get(dbid), "episode"
        elif kind == "tvshow":
            rec, media_type = shows_by_id.get(dbid), "tv"
        if not rec:
            continue
        mapped = _list_item_from_record(rec, media_type)
        key = (mapped.get("type"), mapped.get("tmdbId"), mapped.get("imdbId"), mapped.get("title"))
        if key in seen:
            continue
        seen.add(key)
        items.append(mapped)
    return items


def scan_library(progress=None):
    """
    Full library snapshot. Returns a dict or None if cancelled.
    progress: xbmcgui.DialogProgress or None
    """
    monitor = xbmc.Monitor()

    def abort_cb():
        if monitor.abortRequested():
            return True
        if progress is not None:
            try:
                return progress.iscanceled()
            except Exception:
                return False
        return False

    def progress_cb(pct, label):
        if progress is None:
            return
        try:
            progress.update(max(0, min(100, int(pct))), label)
        except Exception:
            pass

    progress_cb(1, _ls(30166))
    raw_movies = _paginated(
        "VideoLibrary.GetMovies", "movies", MOVIE_PROPS,
        abort_cb=abort_cb, progress_cb=progress_cb, label=_ls(30166),
    )
    if raw_movies is None:
        return None

    progress_cb(1, _ls(30167))
    raw_shows = _paginated(
        "VideoLibrary.GetTVShows", "tvshows", SHOW_PROPS,
        abort_cb=abort_cb, progress_cb=progress_cb, label=_ls(30167),
    )
    if raw_shows is None:
        return None

    movies = [_movie_record(m) for m in raw_movies]
    shows = [_show_record(s) for s in raw_shows]
    movies_by_id = {m["dbid"]: m for m in movies if m.get("dbid") is not None}
    shows_by_id = {s["dbid"]: s for s in shows if s.get("dbid") is not None}

    progress_cb(1, _ls(30168))
    raw_episodes = _paginated(
        "VideoLibrary.GetEpisodes", "episodes", EPISODE_PROPS,
        abort_cb=abort_cb, progress_cb=progress_cb, label=_ls(30168),
    )
    if raw_episodes is None:
        return None
    episodes = [_episode_record(e, shows_by_id) for e in raw_episodes]
    episodes_by_id = {e["dbid"]: e for e in episodes if e.get("dbid") is not None}

    playlists = _scan_playlists(
        movies_by_id, episodes_by_id, shows_by_id,
        abort_cb=abort_cb, progress_cb=progress_cb,
    )
    if playlists is None:
        return None

    favorites = _scan_favorites(
        movies_by_id, episodes_by_id, shows_by_id,
        abort_cb=abort_cb, progress_cb=progress_cb,
    )
    if favorites is None:
        return None

    return {
        "movies": movies,
        "tvshows": shows,
        "episodes": episodes,
        "playlists": playlists,
        "favorites": favorites,
    }


def _match_counts(records):
    certain = review = unidentified = 0
    for rec in records:
        conf = rec.get("confidence")
        if conf == "certain":
            certain += 1
        elif conf == "review":
            review += 1
        else:
            unidentified += 1
    return certain, review, unidentified


def build_preview(scan):
    movies = scan.get("movies") or []
    shows = scan.get("tvshows") or []
    episodes = scan.get("episodes") or []
    all_media = movies + shows + episodes
    certain, review, unidentified = _match_counts(all_media)
    detail_rows = []
    for rec in all_media:
        if rec.get("confidence") == "certain":
            continue
        tag = rec.get("confidence") or "unidentified"
        detail_rows.append(f"[{tag}] {rec.get('label') or '?'}")
    return {
        "movie_total": len(movies),
        "show_total": len(shows),
        "episode_total": len(episodes),
        "movies_watched": sum(1 for m in movies if m.get("watched")),
        "shows_started": sum(1 for s in shows if s.get("watched")),
        "episodes_watched": sum(1 for e in episodes if e.get("watched")),
        "movies_unwatched": sum(1 for m in movies if not m.get("watched")),
        "certain": certain,
        "review": review,
        "unidentified": unidentified,
        "importable": certain + review,
        "detail_rows": detail_rows[:400],
        "playlist_count": len(scan.get("playlists") or []),
        "favorite_count": len(scan.get("favorites") or []),
    }


def _include_movie(rec, options):
    payload = rec.get("payload") or {}
    play_count = _int(payload.get("playCount"))
    if options.get("watched_movies") and play_count > 0:
        return True
    if options.get("watchlist") and play_count == 0:
        return True
    if options.get("ratings") and payload.get("rating"):
        return True
    if options.get("resume") and payload.get("resume"):
        return True
    return False


def _include_show(rec, options):
    payload = rec.get("payload") or {}
    watched_eps = _int(payload.get("watchedEpisodes"))
    if options.get("watched_tv") and watched_eps > 0:
        return True
    if options.get("watchlist") and watched_eps == 0:
        return True
    if options.get("ratings") and payload.get("rating"):
        return True
    return False


def _include_episode(rec, options):
    payload = rec.get("payload") or {}
    play_count = _int(payload.get("playCount"))
    if options.get("watched_tv") and play_count > 0:
        return True
    if options.get("ratings") and payload.get("rating"):
        return True
    if options.get("resume") and payload.get("resume"):
        return True
    return False


def _allowed_confidence(rec, include_review):
    conf = rec.get("confidence")
    if conf == "certain":
        return True
    if conf == "review" and include_review:
        return True
    return False


def build_payload_lists(scan, options, include_review):
    movies = [
        rec["payload"] for rec in scan.get("movies") or []
        if _allowed_confidence(rec, include_review) and _include_movie(rec, options)
    ]
    tvshows = [
        rec["payload"] for rec in scan.get("tvshows") or []
        if _allowed_confidence(rec, include_review) and _include_show(rec, options)
    ]
    episodes = [
        rec["payload"] for rec in scan.get("episodes") or []
        if _allowed_confidence(rec, include_review) and _include_episode(rec, options)
    ]
    playlists = scan.get("playlists") or [] if options.get("playlists") else []
    favorites = scan.get("favorites") or [] if options.get("favorites") else []
    return movies, tvshows, episodes, playlists, favorites


def api_options(options):
    return {
        "importWatched": bool(options.get("watched_movies") or options.get("watched_tv")),
        "importRatings": bool(options.get("ratings")),
        "importWatchDates": bool(options.get("dates")),
        "unwatchedToWatchlist": bool(options.get("watchlist")),
        "importResume": bool(options.get("resume")),
        "importPlaylists": bool(options.get("playlists")),
        "importFavorites": bool(options.get("favorites")),
    }


def chunk_payloads(movies, tvshows, episodes, playlists, favorites, options, session_id):
    media = (
        [("movies", item) for item in movies]
        + [("tvShows", item) for item in tvshows]
        + [("episodes", item) for item in episodes]
    )
    if not media:
        chunks = [{
            "source": "kodi",
            "importSessionId": session_id,
            "options": api_options(options),
            "movies": [],
            "tvShows": [],
            "episodes": [],
            "playlists": playlists,
            "favorites": favorites,
        }]
    else:
        chunks = []
        for start in range(0, len(media), CHUNK_SIZE):
            payload = {
                "source": "kodi",
                "importSessionId": session_id,
                "options": api_options(options),
                "movies": [],
                "tvShows": [],
                "episodes": [],
                "playlists": [],
                "favorites": [],
            }
            for kind, item in media[start:start + CHUNK_SIZE]:
                payload[kind].append(item)
            chunks.append(payload)
        chunks[0]["playlists"] = playlists
        chunks[0]["favorites"] = favorites

    total = len(chunks)
    for index, payload in enumerate(chunks, 1):
        payload["chunk"] = index
        payload["totalChunks"] = total
    return chunks


def _empty_totals():
    return {
        "imported": {
            "movies": 0, "episodes": 0, "ratings": 0, "watchlist": 0,
            "scrobbles": 0, "lists": 0, "favorites": 0,
        },
        "skipped": {"alreadyWatched": 0, "unresolved": 0},
        "unresolved": [],
    }


def merge_import_result(acc, result):
    data = unwrap_data(result) or {}
    if not isinstance(data, dict):
        return acc
    imported = data.get("imported") or {}
    skipped = data.get("skipped") or {}
    for key, value in imported.items():
        acc["imported"][key] = acc["imported"].get(key, 0) + _int(value)
    for key, value in skipped.items():
        if key == "unresolved" and isinstance(value, list):
            continue
        acc["skipped"][key] = acc["skipped"].get(key, 0) + _int(value)
    unresolved = data.get("unresolved") or []
    if isinstance(unresolved, list):
        acc["unresolved"].extend(unresolved)
    return acc


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------

OPTION_KEYS = [
    "watched_movies",
    "watched_tv",
    "ratings",
    "dates",
    "watchlist",
    "resume",
    "playlists",
    "favorites",
]
OPTION_LABELS = [30125, 30126, 30127, 30128, 30129, 30130, 30131, 30132]
OPTION_PRESELECT = [0, 1, 2, 3, 5]


def _choose_mode(allow_skip):
    options = [_ls(30121), _ls(30122)]
    if allow_skip:
        options.append(_ls(30123))
    selected = xbmcgui.Dialog().select(_ls(30165), options)
    if selected < 0:
        return None
    if selected == 0:
        return "import_only"
    if selected == 1:
        return "import_and_sync"
    return "skip"


def _choose_options():
    labels = [_ls(sid) for sid in OPTION_LABELS]
    selected = xbmcgui.Dialog().multiselect(_ls(30124), labels, preselect=list(OPTION_PRESELECT))
    if selected is None:
        return None
    flags = {key: (index in selected) for index, key in enumerate(OPTION_KEYS)}
    if not any(flags.values()):
        return None
    return flags


def _preview_body(preview):
    return "\n".join([
        _ls(30135),
        _ls(30136) % preview["movie_total"],
        _ls(30137) % preview["show_total"],
        _ls(30138) % preview["episode_total"],
        "",
        _ls(30139),
        _ls(30140) % preview["movies_watched"],
        _ls(30141) % preview["shows_started"],
        _ls(30142) % preview["episodes_watched"],
        "",
        _ls(30143) % preview["certain"],
        _ls(30144) % preview["review"],
        _ls(30145) % preview["unidentified"],
    ])


def _show_details(preview):
    rows = preview.get("detail_rows") or []
    if not rows:
        xbmcgui.Dialog().ok(_ls(30134), _ls(30151))
        return
    xbmcgui.Dialog().select(_ls(30151), rows)


def _show_preview(preview):
    try:
        from .import_dialog import ImportPreviewDialog
        dialog = ImportPreviewDialog(
            "script-dejavu-import.xml",
            ADDON.getAddonInfo("path"),
            "Default",
            "1080i",
        )
        dialog.setup(preview)
        dialog.doModal()
        confirmed = bool(dialog.confirmed)
        cancelled = bool(dialog.cancelled)
        del dialog
        if cancelled:
            return False
        if confirmed:
            return True
    except Exception as e:
        _log(f"Import preview dialog unavailable: {e}", xbmc.LOGWARNING)

    heading = _ls(30134)
    body = _preview_body(preview)
    choices = [
        _ls(30147) % preview["importable"],
        _ls(30146),
        _ls(30118),
    ]
    while True:
        xbmcgui.Dialog().ok(heading, body)
        selected = xbmcgui.Dialog().select(heading, choices)
        if selected == 0:
            return True
        if selected == 1:
            _show_details(preview)
            continue
        return False


def _apply_mode(mode):
    if mode == "import_only":
        try:
            ADDON.setSettingBool("enable_scrobble", False)
        except Exception:
            ADDON.setSetting("enable_scrobble", "false")


def _mark_offered():
    try:
        ADDON.setSettingBool("kodi_import_offered", True)
    except Exception:
        ADDON.setSetting("kodi_import_offered", "true")


def _already_offered():
    try:
        return ADDON.getSettingBool("kodi_import_offered")
    except Exception:
        return ADDON.getSetting("kodi_import_offered") == "true"


def _finish_success():
    _mark_offered()
    ADDON.setSetting("kodi_import_at", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    notify_changed("kodi_import")
    set_import_status("success")


def _send_chunks(api, chunks, progress):
    monitor = xbmc.Monitor()
    totals = _empty_totals()
    total = len(chunks)
    for index, payload in enumerate(chunks, 1):
        if monitor.abortRequested():
            return None
        if progress is not None:
            try:
                if progress.iscanceled():
                    return None
                pct = int(index * 100 / max(total, 1))
                progress.update(pct, _ls(30171) % (index, total))
            except Exception:
                pass
        result = api.import_kodi_library(payload)
        if not result:
            return False
        merge_import_result(totals, result)
        if monitor.waitForAbort(0.05):
            return None
    return totals


def _summary_text(totals):
    imported = totals.get("imported") or {}
    lines = [
        _ls(30157) % (
            imported.get("movies", 0),
            imported.get("episodes", 0),
            imported.get("ratings", 0),
        ),
        _ls(30164) % (
            imported.get("watchlist", 0),
            imported.get("lists", 0),
            imported.get("favorites", 0),
            imported.get("scrobbles", 0),
        ),
    ]
    skipped = totals.get("skipped") or {}
    unresolved = _int(skipped.get("unresolved")) + len(totals.get("unresolved") or [])
    if unresolved:
        lines.append(_ls(30145) % unresolved)
    return "\n".join(lines)


def run_import_wizard(allow_skip=True):
    """
    Interactive Kodi → dejaVu import.
    Returns True on success, False otherwise.
    """
    set_import_status("pending")

    if not ADDON.getSetting("access_token"):
        set_import_status("error")
        xbmcgui.Dialog().notification("dejaVu", _ls(30075), xbmcgui.NOTIFICATION_ERROR)
        return False

    mode = _choose_mode(allow_skip)
    if mode is None:
        set_import_status("cancelled")
        return False
    if mode == "skip":
        _mark_offered()
        set_import_status("cancelled")
        return False

    options = _choose_options()
    if not options:
        set_import_status("cancelled")
        return False

    progress = xbmcgui.DialogProgress()
    progress.create(_ls(30134), _ls(30133))
    try:
        scan = scan_library(progress)
    finally:
        try:
            progress.close()
        except Exception:
            pass

    if scan is None:
        set_import_status("cancelled")
        return False

    preview = build_preview(scan)
    if preview["movie_total"] == 0 and preview["show_total"] == 0 and preview["episode_total"] == 0:
        if not (scan.get("playlists") or scan.get("favorites")):
            set_import_status("empty")
            xbmcgui.Dialog().ok(_ls(30134), _ls(30159))
            return False

    if not _show_preview(preview):
        set_import_status("cancelled")
        return False

    include_review = False
    if preview["review"] > 0:
        include_review = xbmcgui.Dialog().yesno(
            _ls(30134),
            _ls(30148) % preview["review"],
            yeslabel=_ls(30150),
            nolabel=_ls(30149),
        )

    if not options.get("watchlist") and preview["movies_unwatched"] > 0:
        add_watchlist = xbmcgui.Dialog().yesno(
            _ls(30134),
            _ls(30152) % preview["movies_unwatched"],
            yeslabel=_ls(30153),
            nolabel=_ls(30154),
        )
        if add_watchlist:
            options["watchlist"] = True

    movies, tvshows, episodes, playlists, favorites = build_payload_lists(
        scan, options, include_review,
    )
    if not (movies or tvshows or episodes or playlists or favorites):
        set_import_status("empty")
        xbmcgui.Dialog().ok(_ls(30134), _ls(30162))
        return False

    session_id = str(uuid.uuid4())
    chunks = chunk_payloads(movies, tvshows, episodes, playlists, favorites, options, session_id)

    progress = xbmcgui.DialogProgress()
    progress.create(_ls(30134), _ls(30155))
    try:
        totals = _send_chunks(DejaVuAPI(), chunks, progress)
    finally:
        try:
            progress.close()
        except Exception:
            pass

    if totals is None:
        set_import_status("cancelled")
        return False
    if totals is False:
        set_import_status("error")
        xbmcgui.Dialog().ok(_ls(30134), _ls(30158))
        return False

    _apply_mode(mode)
    _finish_success()
    xbmcgui.Dialog().ok(_ls(30156), _summary_text(totals))
    return True


def offer_after_login():
    """Post-login prompt when a video library exists and import was never offered."""
    if _already_offered():
        return
    movie_total, show_total = video_library_totals()
    if movie_total <= 0 and show_total <= 0:
        return
    body = "\n".join([
        _ls(30160),
        "",
        _ls(30136) % movie_total,
        _ls(30137) % show_total,
    ])
    start = xbmcgui.Dialog().yesno(
        _ls(30134),
        body,
        yeslabel=_ls(30120),
        nolabel=_ls(30161),
    )
    if not start:
        _mark_offered()
        return
    run_import_wizard(allow_skip=False)
