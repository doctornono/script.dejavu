# -*- coding: utf-8 -*-
"""
dejaVu Scrobbler
Subclasses xbmc.Player to hook playback events and send scrobble updates
to the dejaVu API.
"""

import json
import time
import requests
import xbmc
import xbmcaddon
import xbmcgui
from .api_client import DejaVuAPI
from .auth_handler import is_logged_in
from .util import notify_changed, set_kodi_playcount, unwrap_data

ADDON = xbmcaddon.Addon()


def _log(msg, level=xbmc.LOGDEBUG):
    try:
        debug = ADDON.getSettingBool("debug")
    except Exception:
        debug = False
    if debug or level >= xbmc.LOGINFO:
        xbmc.log(f"[dejaVu] {msg}", level)


def _ls(string_id):
    return ADDON.getLocalizedString(string_id)


class DejaVuPlayer(xbmc.Player):
    """
    Hooks into Kodi's player events to:
      - send scrobble start/pause/resume/stop
      - mark media as watched when the watched_percent threshold is reached
    """

    def __init__(self):
        super().__init__()
        self._active = False
        self._meta = None
        self._last_scrobble_ts = 0
        self._watched_sent = False
        self._login_warned = False
        self._resumed = False
        self._api = None  # lazy: only created when logged in

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def api(self):
        """Lazy API client, refreshed each time (picks up token changes)."""
        self._api = DejaVuAPI()
        return self._api

    # ------------------------------------------------------------------
    # Metadata extraction
    # ------------------------------------------------------------------

    def _resolve_via_api(self, imdb_id=None, title=None, media_type="movie", year=None):
        """Resolve a movie/show TMDB ID through dejaVu POST /media/resolve."""
        if not is_logged_in():
            return None
        resolve_type = "tv" if media_type in ("tv", "episode") else "movie"
        try:
            result = self.api.resolve_media(
                imdb_id=imdb_id,
                media_type=resolve_type,
                title=title,
                year=year,
            )
        except Exception as e:
            _log(f"media/resolve error: {e}", xbmc.LOGWARNING)
            return None
        data = unwrap_data(result)
        if isinstance(data, dict) and data.get("tmdbId"):
            new_id = str(data["tmdbId"])
            _log(f"Resolved via dejaVu media/resolve → {new_id}", xbmc.LOGINFO)
            return new_id
        return None

    def _resolve_tmdb_from_external(self, external_id, media_type="movie"):
        """
        Resolve IMDB/TVDB identifiers to TMDB IDs.
        Prefers POST /media/resolve; falls back to TMDB find if a key is set.
        media_type: "movie", "tv" (for shows), or "episode".
        """
        if external_id and str(external_id).startswith("tt"):
            resolved = self._resolve_via_api(imdb_id=external_id, media_type=media_type)
            if resolved:
                return resolved

        api_key = ADDON.getSetting("tmdb_api_key")
        if not api_key:
            _log("Resolution skipped: No TMDB API key configured.", xbmc.LOGDEBUG)
            return None

        source = "imdb_id" if external_id.startswith("tt") else "unknown"
        if source == "unknown" and external_id.isdigit() and int(external_id) > 1000000:
            # High numeric values are occasionally TVDB IDs in some plugins
            source = "tvdb_id"
        
        if source == "unknown":
            return None

        _log(f"Resolving TMDb ID for {external_id} via '{source}' lookup ({media_type})...", xbmc.LOGDEBUG)
        url = f"https://api.themoviedb.org/3/find/{external_id}"
        
        try:
            r = requests.get(url, params={"api_key": api_key, "external_source": source}, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            results_key = {
                "movie": "movie_results",
                "tv": "tv_results",
                "episode": "tv_episode_results"
            }.get(media_type, "movie_results")

            results = data.get(results_key, [])
            if results:
                new_id = str(results[0].get("id"))
                _log(f"Successfully resolved {external_id} -> {new_id}", xbmc.LOGINFO)
                return new_id
        except Exception as e:
            _log(f"External identifier resolution failed: {e}", xbmc.LOGERROR)
        
        return None

    def _search_tmdb_id(self, title, media_type="movie", year=None):
        """
        Search by title if no IDs are available.
        Prefers POST /media/resolve; falls back to TMDB search if a key is set.
        media_type: "movie" or "tv"
        """
        if not title:
            return None

        resolved = self._resolve_via_api(title=title, media_type=media_type, year=year)
        if resolved:
            return resolved

        api_key = ADDON.getSetting("tmdb_api_key")
        if not api_key:
            _log("Search skipped: No TMDB API key configured.", xbmc.LOGDEBUG)
            return None
            
        _log(f"Searching TMDb for {media_type} via title: '{title}'", xbmc.LOGDEBUG)
        
        path = "search/movie" if media_type == "movie" else "search/tv"
        url = f"https://api.themoviedb.org/3/{path}"
        
        params = {"api_key": api_key, "query": title}
        if year:
            param_year = "year" if media_type == "movie" else "first_air_date_year"
            params[param_year] = year

        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            results = data.get("results", [])
            if results:
                new_id = str(results[0].get("id"))
                _log(f"Search match found for '{title}': {new_id}", xbmc.LOGINFO)
                return new_id
        except Exception as e:
            _log(f"TMDb search error for '{title}': {e}", xbmc.LOGERROR)
            
        return None

    def _log_player_item_details(self):
        """
        Uses JSON-RPC Player.GetItem to dump all internal Kodi metadata.
        """
        try:
            # Give Kodi a moment to populate the player metadata
            xbmc.sleep(1000)
            
            # Try to identify the correct active player ID
            player_req = '{"jsonrpc": "2.0", "method": "Player.GetActivePlayers", "id": 1}'
            player_resp_raw = xbmc.executeJSONRPC(player_req)
            player_resp = json.loads(player_resp_raw)
            active_players = player_resp.get("result", [])
            
            player_id = 1
            if active_players:
                player_id = active_players[0].get("playerid", 1)
            
            req = json.dumps({
                "jsonrpc": "2.0",
                "method": "Player.GetItem",
                "params": {
                    "playerid": player_id,
                    "properties": [
                        "title", "file", "uniqueid", "streamdetails", "art",
                        "season", "episode", "showtitle", "originaltitle"
                    ]
                },
                "id": 16,
            })
            _log(f"Requesting Player.GetItem for playerid: {player_id}", xbmc.LOGINFO)
            resp = xbmc.executeJSONRPC(req)
            _log(f"--- JSON-RPC Player.GetItem DUMP ---", xbmc.LOGINFO)
            _log(resp, xbmc.LOGINFO)
        except Exception as e:
            _log(f"Failed to dump Player.GetItem: {e}", xbmc.LOGWARNING)

    def _log_all_listItem_properties(self):
        """
        Broad scan of common ListItem properties to discover non-standard identifiers.
        """
        _log("--- ListItem Properties DISCOVERY SCAN ---", xbmc.LOGDEBUG)
        common_props = [
            # Standard & common variants
            "tmdb_id", "imdb_id", "tvdb_id", "tvrage_id", "anidb_id", "trakt_id",
            "tmdb", "imdb", "tvdb", "unknown", "tmdbid", "imdbid", "tvdbid",
            # Elementum specific
            "elementum_tmdb_id", "elementum_tvshow_tmdb_id", "elementum_movie_tmdb_id",
            "elementum_imdb_id", "elementum_tvshow_imdb_id",
            # VStream specific
            "vstream_id", "site", "function", "sId", "sH", "sFav",
            # Other identifiers & metadata fallback
            "path", "mediatype", "dbid", "year", "season", "episode",
            "tvshowtitle", "originaltitle", "TVShowID", "TVShowIMDBID"
        ]
        found = []
        for p in common_props:
            val = xbmc.getInfoLabel(f"ListItem.Property({p})")
            if val:
                found.append(f"{p}={val}")
        
        if found:
            _log("Found ListItem Properties: " + " | ".join(found), xbmc.LOGDEBUG)
        else:
            _log("No common ListItem Properties found via InfoLabel scanner.", xbmc.LOGDEBUG)

    def _get_show_tmdb_id(self):
        """
        Resolve the TV show TMDB ID.
        1. Via Kodi JSON-RPC (Library lookup).
        2. Via ListItem Properties (Plugin fallback).
        """
        self._log_all_listItem_properties()
        # --- Attempt 1: Library lookup ---
        try:
            ep_dbid = int(xbmc.getInfoLabel("VideoPlayer.DBID") or 0)
            if ep_dbid > 0:
                _log(f"Resolving show TMDB ID via Library (DBID: {ep_dbid})", xbmc.LOGDEBUG)

                # Step 1: get tvshowid from the episode
                req1 = json.dumps({
                    "jsonrpc": "2.0",
                    "method": "VideoLibrary.GetEpisodeDetails",
                    "params": {"episodeid": ep_dbid, "properties": ["tvshowid", "season", "episode", "uniqueid"]},
                    "id": 1,
                })

                resp1_raw = xbmc.executeJSONRPC(req1)
                resp1 = json.loads(resp1_raw)
                _log(f"Episode details: {resp1}", xbmc.LOGDEBUG)

                tvshowid = (
                    resp1.get("result", {})
                         .get("episodedetails", {})
                         .get("tvshowid", -1)
                )
                
                if tvshowid >= 0:
                    # Step 2: get uniqueid.tmdb from the TV show
                    req2 = json.dumps({
                        "jsonrpc": "2.0",
                        "method": "VideoLibrary.GetTVShowDetails",
                        "params": {"tvshowid": tvshowid, "properties": ["uniqueid"]},
                        "id": 2,
                    })
                    
                    resp2 = json.loads(xbmc.executeJSONRPC(req2))
                    _log(f"TV Show details: {resp2}", xbmc.LOGDEBUG)
                    
                    uniqueids = (
                        resp2.get("result", {})
                             .get("tvshowdetails", {})
                             .get("uniqueid", {})
                    )
                    show_tmdb = uniqueids.get("tmdb") or uniqueids.get("unknown")
                    if show_tmdb:
                        if str(show_tmdb).startswith("tt"):
                            resolved = self._resolve_tmdb_from_external(show_tmdb, "tv")
                            if resolved:
                                return resolved
                            
                        _log(f"Resolved show TMDB ID via Library: {show_tmdb}", xbmc.LOGDEBUG)
                        return str(show_tmdb)

        except Exception as e:
            _log(f"_get_show_tmdb_id Library lookup error: {e}", xbmc.LOGWARNING)

        # --- Attempt 2: ListItem Properties (Common for plugins like Elementum/VStream) ---
        _log("Resolving show TMDB ID via ListItem Properties fallback", xbmc.LOGDEBUG)
        props = [
            "tvshow_tmdb_id", "tmdb_id", "tmdb", "TVShowID", "tmdbid", "imdbid",
            "elementum_tmdb_id", "elementum_tvshow_tmdb_id",
            "imdb_id", "imdb", "TVShowIMDBID", "vstream_id"
        ]
        for prop in props:
            val = xbmc.getInfoLabel(f"ListItem.Property({prop})")
            if val:
                _log(f"  [Property Check] {prop} = {val}", xbmc.LOGDEBUG)
            
            if not val:
                continue
            
            if val.isdigit():
                _log(f"Found show TMDB ID in property '{prop}': {val}", xbmc.LOGDEBUG)
                return val
            elif val.startswith("tt"):
                _log(f"Found show IMDB ID in property '{prop}': {val}. Resolving...", xbmc.LOGDEBUG)
                resolved = self._resolve_tmdb_from_external(val, "tv")
                if resolved:
                    return resolved

        # --- Attempt 3: Check InfoTag for tvshow (Kodi 19+) ---
        try:
            tag = self.getVideoInfoTag()
            _log(f"InfoTag: {tag}", xbmc.LOGDEBUG)
            show_tmdb = tag.getUniqueID("tvshow.tmdb") or tag.getUniqueID("tvshow")
            if show_tmdb:
                if str(show_tmdb).startswith("tt"):
                    resolved = self._resolve_tmdb_from_external(show_tmdb, "tv")
                    if resolved:
                        return resolved
                _log(f"Found show TMDB ID in InfoTag: {show_tmdb}", xbmc.LOGDEBUG)
                return str(show_tmdb)
        except Exception:
            pass

        # --- Attempt 4: Universal Search by Title (Final Resort) ---
        show_title = xbmc.getInfoLabel("VideoPlayer.TVShowTitle") or xbmc.getInfoLabel("ListItem.TVShowTitle")
        if show_title:
            _log(f"Attempting universal search for show title: '{show_title}'", xbmc.LOGDEBUG)
            resolved = self._search_tmdb_id(show_title, "tv")
            if resolved:
                return resolved

        _log("Could not resolve show TMDB ID via any method (Library, Properties, Tag, Search).", xbmc.LOGWARNING)
        return None

    def _resolve_episode_tmdb_id(self, show_id, season, episode):
        """
        Query TMDB API to get the specific episode TMDB ID.
        Requires a valid 'tmdb_api_key' in settings.
        """
        api_key = ADDON.getSetting("tmdb_api_key")
        if not api_key:
            _log("TMDB API Key missing in settings – resolution skipped.", xbmc.LOGWARNING)
            return None

        _log(f"Querying TMDB for episode ID (Show: {show_id}, S{season}E{episode})", xbmc.LOGDEBUG)
        url = f"https://api.themoviedb.org/3/tv/{show_id}/season/{season}/episode/{episode}"
        
        try:
            r = requests.get(url, params={"api_key": api_key}, timeout=10)
            r.raise_for_status()
            data = r.json()
            ep_id = data.get("id")
            if ep_id:
                _log(f"Resolved episode TMDB ID via TMDB API: {ep_id}", xbmc.LOGINFO)
                return str(ep_id)
        except Exception as e:
            _log(f"TMDB resolution error: {e}", xbmc.LOGERROR)
        
        return None

    def _get_metadata(self):
        """
        Reads the current video's metadata from the Kodi player.
        Returns a dict or None if nothing useful is playing.
        """
        if not self.isPlayingVideo():
            return None

        tag = self.getVideoInfoTag()
        media_type = tag.getMediaType()  # "movie" | "episode" | ""

        unique_ids = {}
        try:
            unique_ids = tag.getUniqueIDs()
        except Exception:
            # Fallback for versions/environments where getUniqueIDs() isn't available
            for k in ["tmdb", "imdb", "tvdb", "unknown"]:
                val = tag.getUniqueID(k)
                if val:
                    unique_ids[k] = val

        tmdb_id = tag.getUniqueID("tmdb")
        imdb_id = tag.getUniqueID("imdb") or unique_ids.get("imdb")
        
        _log(f"Extracting metadata. Media type: {media_type}", xbmc.LOGDEBUG)
        _log(f"Detected UniqueIDs: {json.dumps(unique_ids)}", xbmc.LOGDEBUG)
        
        # Comprehensive ID discovery
        self._log_all_listItem_properties()
        
        # Log common potential identifiers from InfoLabels
        _log("--- Identifier Extraction Debug ---", xbmc.LOGDEBUG)
        _log(f"  tag.getUniqueID('tmdb'): {tmdb_id}", xbmc.LOGDEBUG)
        _log(f"  tag.getUniqueID('imdb'): {tag.getUniqueID('imdb')}", xbmc.LOGDEBUG)
        _log(f"  tag.getUniqueID('tvdb'): {tag.getUniqueID('tvdb')}", xbmc.LOGDEBUG)
        _log(f"  VideoPlayer.IMDBNumber: {xbmc.getInfoLabel('VideoPlayer.IMDBNumber')}", xbmc.LOGDEBUG)

        # Fallback to ListItem Properties if tag is missing IDs (common with plugins like Elementum)
        if not tmdb_id or str(tmdb_id).startswith("tt"):
            _log("Checking ListItem properties fallback for media IDs...", xbmc.LOGDEBUG)
            props = ["tmdb_id", "tmdb", "tmdbid", "imdb_id", "imdb", "imdbid", "elementum_tmdb_id", "vstream_id"]
            for prop in props:
                val = xbmc.getInfoLabel(f"ListItem.Property({prop})")
                if val:
                    _log(f"  [Property] {prop} = {val}", xbmc.LOGDEBUG)
                if not val:
                    continue
                if val.isdigit() and (not tmdb_id or str(tmdb_id).startswith("tt")):
                    _log(f"Found TMDB ID in property '{prop}': {val}", xbmc.LOGDEBUG)
                    tmdb_id = val
                elif val.startswith("tt") and not imdb_id:
                    _log(f"Found IMDB ID in property '{prop}': {val}", xbmc.LOGDEBUG)
                    imdb_id = val

        _log(f"IDs after fallback: tmdb_id={tmdb_id}, imdb_id={imdb_id}", xbmc.LOGDEBUG)

        # Resolution for movies and episodes
        if not tmdb_id or str(tmdb_id).startswith("tt"):
            # If TMDB is missing OR it contains an IMDB ID (common in some plugins)
            candidate = tmdb_id if str(tmdb_id).startswith("tt") else imdb_id
            if candidate:
                _log(f"TMDB ID missing or invalid ('{tmdb_id}'), attempting resolution of '{candidate}'", xbmc.LOGDEBUG)
                resolved = self._resolve_tmdb_from_external(
                    candidate, 
                    "movie" if media_type == "movie" else "episode"
                )
                if resolved:
                    tmdb_id = resolved

        # --- Attempt 4: Universal Search by Title (Final Resort for Movies) ---
        if media_type == "movie" and (not tmdb_id or str(tmdb_id).startswith("tt")):
            movie_title = tag.getTitle() or xbmc.getInfoLabel("VideoPlayer.Title")
            if movie_title:
                _log(f"Attempting universal search for movie title: '{movie_title}'", xbmc.LOGDEBUG)
                year = xbmc.getInfoLabel("VideoPlayer.Year") or None
                resolved = self._search_tmdb_id(movie_title, "movie", year)
                if resolved:
                    tmdb_id = resolved

        if not tmdb_id:
            # Try to fallback to 'unknown' or other potential fields
            tmdb_id = unique_ids.get("unknown")
            if tmdb_id:
                if str(tmdb_id).startswith("tt"):
                    tmdb_id = self._resolve_tmdb_from_external(tmdb_id, "movie" if media_type == "movie" else "episode")
                _log(f"Using fallback tmdb_id: {tmdb_id}", xbmc.LOGDEBUG)

        if media_type == "movie" and (not tmdb_id or str(tmdb_id).startswith("tt")):
            _log("No valid numeric TMDB ID found for current movie – scrobble skipped.", xbmc.LOGWARNING)
            return None

        res = None
        dbid = xbmc.getInfoLabel("VideoPlayer.DBID") or ""
        if media_type == "movie":
            res = {
                "type": "movie",
                "tmdb_id": tmdb_id,
                "title": tag.getTitle(),
                "dbid": dbid,
            }

        elif media_type == "episode":
            # tmdb_id here is the episode's own TMDB ID (TMDB scraper behaviour)
            # show_tmdb_id is resolved separately via JSON-RPC or properties
            show_tmdb = self._get_show_tmdb_id()
            season = tag.getSeason()
            episode = tag.getEpisode()

            # Resolution Logic: 
            # If tmdb_id is missing or duplicate of show_tmdb, try to resolve it.
            should_resolve = False
            if not tmdb_id:
                _log("Episode TMDB ID missing – attempting resolution.", xbmc.LOGDEBUG)
                should_resolve = True
            elif tmdb_id == show_tmdb:
                _log(f"Episode TMDB ID is duplicate of Show ID ({tmdb_id}) – attempting resolution.", xbmc.LOGDEBUG)
                should_resolve = True

            if should_resolve and show_tmdb and season > 0 and episode > 0:
                resolved_id = self._resolve_episode_tmdb_id(show_tmdb, season, episode)
                if resolved_id:
                    tmdb_id = resolved_id

            # For episodes, we can proceed if we have a Show ID + S + E, 
            # even if the specific episode TMDB ID is null.
            if not tmdb_id and (not show_tmdb or season <= 0 or episode <= 0):
                _log("Incomplete episode metadata (missing IDs or S/E) – skipped.", xbmc.LOGWARNING)
                return None

            res = {
                "type": "episode",
                "tmdb_id": tmdb_id,           # episode TMDB ID → sent as `id` in API
                "show_tmdb_id": show_tmdb,    # TV show TMDB ID → sent as `tvShowId`
                "season": season,
                "episode": episode,
                "show_title": tag.getTVShowTitle(),
                "dbid": dbid,
                "title": (
                    f"{tag.getTVShowTitle() or 'TV Show'} "
                    f"S{season:02d}E{episode:02d}"
                ),
            }

        if res:
            _log(f"Final Metadata extracted: {json.dumps(res)}", xbmc.LOGDEBUG)
        else:
            _log(f"Unhandled media type: '{media_type}'", xbmc.LOGDEBUG)
        
        return res

    # ------------------------------------------------------------------
    # Core scrobble helper
    # ------------------------------------------------------------------

    def _scrobble(self, action="update"):
        """
        Sends a scrobble request. `action` is informational only (for logs).
        The dejaVu API auto-marks as watched when progress/duration >= 0.9.
        Local watched_percent is respected: progress reported to the API is
        capped under 90% until the user threshold is reached, and history is
        only used when the local threshold is below the API's 90% mark.
        """
        try:
            if not ADDON.getSettingBool("enable_scrobble"):
                return
        except Exception:
            pass  # default: enabled
        if not is_logged_in():
            _log("Scrobble skipped: not logged in.", xbmc.LOGINFO)
            if not self._login_warned:
                try:
                    if ADDON.getSettingBool("show_notifications"):
                        xbmcgui.Dialog().notification(
                            "dejaVu", _ls(30075), xbmcgui.NOTIFICATION_INFO, 4000
                        )
                except Exception:
                    pass
                self._login_warned = True
            return
        if not self._active:
            return
        if self._watched_sent:
            return

        meta = self._meta or self._get_metadata()
        if not meta:
            return

        try:
            progress = int(self.getTime())
            duration = int(self.getTotalTime())
        except Exception:
            return

        if duration <= 0:
            return

        try:
            watch_pct = ADDON.getSettingInt("watched_percent") or 90
        except Exception:
            watch_pct = 90

        ratio = progress / duration
        is_watched_now = (ratio * 100) >= watch_pct

        # Hold the API under its 90% auto-watched mark until the local threshold
        send_progress = progress
        if not is_watched_now and ratio >= 0.9:
            send_progress = max(0, int(duration * 0.89))

        _log(
            f"Sending Scrobble API Call: action={action}, type={meta['type']}, "
            f"tmdb_id={meta['tmdb_id']}, progress={send_progress}/{duration}s, "
            f"show_id={meta.get('show_tmdb_id')}, S{meta.get('season')}E{meta.get('episode')}",
            xbmc.LOGINFO
        )

        result = self.api.scrobble(
            media_type=meta["type"],
            progress=send_progress,
            duration=duration,
            tmdb_id=meta["tmdb_id"],
            tv_show_id=meta.get("show_tmdb_id"),
            season=meta.get("season"),
            episode=meta.get("episode"),
        )
        self._last_scrobble_ts = time.time()

        if result is None:
            _log(f"Scrobble API call failed (no response) [{action}].", xbmc.LOGWARNING)

        if action == "start" and ADDON.getSettingBool("show_notifications"):
            xbmcgui.Dialog().notification(
                "dejaVu", _ls(30053), xbmcgui.NOTIFICATION_INFO, 3000
            )

        if is_watched_now and not self._watched_sent:
            api_marked = isinstance(result, dict) and result.get("action") == "watched"
            # Only POST /history when the local threshold is below the API's 90%
            if not api_marked and (progress / duration) < 0.9:
                _log(
                    f"Local threshold reached ({watch_pct}%) below API 90% – add_to_history.",
                    xbmc.LOGINFO,
                )
                self.api.add_to_history(
                    media_type=meta["type"],
                    tmdb_id=meta["tmdb_id"],
                    tv_show_id=meta.get("show_tmdb_id"),
                    season=meta.get("season"),
                    episode=meta.get("episode"),
                )
            self._watched_sent = True
            set_kodi_playcount(
                meta.get("dbid") or xbmc.getInfoLabel("VideoPlayer.DBID"),
                "episode" if meta.get("type") == "episode" else "movie",
                watched=True,
            )
            notify_changed(
                "watched",
                media_type=meta["type"],
                tmdb_id=meta.get("tmdb_id"),
                extra={"tvShowId": meta.get("show_tmdb_id")},
            )

            if ADDON.getSettingBool("show_notifications"):
                xbmcgui.Dialog().notification(
                    "dejaVu",
                    f"{_ls(30052)}: {meta.get('title', '')}",
                    xbmcgui.NOTIFICATION_INFO,
                    3000,
                )

    # ------------------------------------------------------------------
    # Kodi player event hooks
    # ------------------------------------------------------------------

    def onAVStarted(self):
        _log("onAVStarted", xbmc.LOGINFO)
        self._log_player_item_details()
        self._meta = self._get_metadata()
        self._active = True
        self._last_scrobble_ts = 0
        self._watched_sent = False
        self._resumed = False
        self._maybe_resume()
        self._scrobble("start")

    def onPlayBackPaused(self):
        _log("onPlayBackPaused", xbmc.LOGINFO)
        self._scrobble("pause")

    def onPlayBackResumed(self):
        _log("onPlayBackResumed")
        self._scrobble("resume")

    def onPlayBackStopped(self):
        _log("onPlayBackStopped", xbmc.LOGINFO)
        self._handle_stop("stop")

    def onPlayBackEnded(self):
        _log("onPlayBackEnded", xbmc.LOGINFO)
        self._handle_stop("end")

    def onPlayBackError(self):
        _log("onPlayBackError", xbmc.LOGWARNING)
        self._active = False
        self._meta = None

    # ------------------------------------------------------------------
    # Stop / end logic
    # ------------------------------------------------------------------

    def _handle_stop(self, reason):
        """
        On stop/end: final scrobble, optional rating prompt, session cleanup
        for very short plays, and up-next offer when an episode finishes.
        """
        meta = self._meta
        progress = 0
        try:
            progress = int(self.getTime())
        except Exception:
            pass

        self._scrobble(reason)
        watched = self._watched_sent

        # Drop junk sessions abandoned in the first 30 seconds
        if meta and not watched and progress < 30:
            tmdb_id = meta.get("tmdb_id")
            if tmdb_id and str(tmdb_id).isdigit():
                self.api.delete_scrobble(meta["type"], tmdb_id)
                _log("Deleted short scrobble session (<30s).", xbmc.LOGDEBUG)

        try:
            if ADDON.getSettingBool("prompt_rating") and self._watched_sent and meta:
                self._prompt_rating(meta)
        except Exception:
            pass

        if reason == "end" and watched and meta and meta.get("type") == "episode":
            try:
                self._maybe_play_upnext(meta)
            except Exception as e:
                _log(f"upnext error: {e}", xbmc.LOGWARNING)

        self._active = False
        self._meta = None
        self._watched_sent = False
        self._resumed = False

    def _prompt_rating(self, meta):
        # Give Kodi a moment to close the player UI
        xbmc.sleep(1000)

        media_type = meta.get("type", "movie")
        tmdb_id = meta.get("tmdb_id")
        show_tmdb = meta.get("show_tmdb_id")
        season = meta.get("season")
        episode = meta.get("episode")

        current_rating = self._existing_rating(meta)

        ratings = [str(i) for i in range(10, 0, -1)]
        options = [_ls(30098)] + ratings  # Remove rating first
        preselect = 0
        if current_rating:
            try:
                preselect = options.index(str(int(current_rating)))
            except ValueError:
                preselect = 0

        title = f"{_ls(30017)}: {meta.get('title', '')}"
        try:
            selected = xbmcgui.Dialog().select(title, options, preselect=preselect)
        except TypeError:
            selected = xbmcgui.Dialog().select(title, options)

        if selected < 0:
            return

        # Allow episodes with show info + S+E even if episode tmdb_id is null
        _log(f"Prompting rating for: {json.dumps(meta)}", xbmc.LOGDEBUG)
        if not tmdb_id:
            if media_type != "episode" or not (show_tmdb and season and episode):
                _log(
                    f"Prompt rating skipped: insufficient IDs "
                    f"(type={media_type}, tmdb_id={tmdb_id}, show_id={show_tmdb})",
                    xbmc.LOGWARNING,
                )
                xbmcgui.Dialog().notification("dejaVu", _ls(30019), xbmcgui.NOTIFICATION_ERROR)
                return

        try:
            if selected == 0:
                result = self.api.delete_rating(
                    media_type,
                    tmdb_id=tmdb_id,
                    tv_show_id=show_tmdb,
                    season=int(season) if season is not None else None,
                )
                if result is not None and ADDON.getSettingBool("show_notifications"):
                    xbmcgui.Dialog().notification(
                        "dejaVu", _ls(30076), xbmcgui.NOTIFICATION_INFO, 3000
                    )
                notify_changed("delete_rating", media_type, tmdb_id)
                return

            rating = int(ratings[selected - 1])
            if media_type == "episode":
                result = self.api.rate(
                    "episode",
                    rating,
                    tmdb_id=tmdb_id,
                    tv_show_id=show_tmdb,
                    season=int(season) if season is not None else None,
                    episode=int(episode) if episode is not None else None,
                )
            else:
                result = self.api.rate(media_type, rating, tmdb_id=tmdb_id)

            if result is None:
                _log("Rating API call failed (no response).", xbmc.LOGWARNING)
                xbmcgui.Dialog().notification(
                    "dejaVu", _ls(30019), xbmcgui.NOTIFICATION_ERROR, 3000
                )
                return

            notify_changed("rate", media_type, tmdb_id, extra={"rating": rating})

            if ADDON.getSettingBool("show_notifications"):
                xbmcgui.Dialog().notification(
                    "dejaVu",
                    _ls(30018) % rating,
                    xbmcgui.NOTIFICATION_INFO,
                    3000,
                )

            if media_type == "episode" and show_tmdb:
                if xbmcgui.Dialog().yesno("dejaVu", _ls(30077)):
                    show_result = self.api.rate("tv", rating, tmdb_id=show_tmdb)
                    if show_result is not None:
                        notify_changed("rate", "tv", show_tmdb, extra={"rating": rating})
        except Exception as e:
            _log(f"Rating error: {e}", xbmc.LOGERROR)

    def _existing_rating(self, meta):
        """Look up the current dejaVu rating for a movie, or the show rating for an episode."""
        status_type = "movie" if meta.get("type") == "movie" else "tv"
        status_id = meta.get("tmdb_id") if status_type == "movie" else meta.get("show_tmdb_id")
        if not status_id or not str(status_id).isdigit():
            return None
        try:
            result = self.api.get_media_status([{"type": status_type, "id": int(status_id)}])
            data = unwrap_data(result) or {}
            entry = data.get(f"{status_type}:{status_id}") or {}
            return entry.get("rating")
        except Exception as e:
            _log(f"existing rating lookup failed: {e}", xbmc.LOGDEBUG)
            return None

    def _maybe_resume(self):
        """Seek to the last dejaVu scrobble position after playback starts."""
        if self._resumed or not self._meta:
            return
        try:
            if not ADDON.getSettingBool("enable_resume"):
                return
        except Exception:
            return
        if not is_logged_in():
            return

        meta = self._meta
        result = self.api.get_scrobbles(media_type=meta["type"], page_size=50, minimal=False)
        items = unwrap_data(result) or []
        if isinstance(items, dict):
            items = items.get("movies") or items.get("episodes") or list(items.values())
        if not isinstance(items, list):
            return

        match = None
        for item in items:
            if not isinstance(item, dict):
                continue
            if meta["type"] == "movie" and str(item.get("tmdbId")) == str(meta.get("tmdb_id")):
                match = item
                break
            if meta["type"] == "episode":
                info = item.get("info") or {}
                same_id = meta.get("tmdb_id") and str(item.get("tmdbId")) == str(meta["tmdb_id"])
                same_ep = (
                    str(item.get("tvShowTmdbId")) == str(meta.get("show_tmdb_id"))
                    and info.get("season") == meta.get("season")
                    and info.get("episode") == meta.get("episode")
                )
                if same_id or same_ep:
                    match = item
                    break

        if not match:
            return

        progress = int(match.get("progress") or 0)
        duration = int(match.get("duration") or 0)
        if progress < 30:
            return
        if duration > 0 and (progress / duration) >= 0.9:
            return

        minutes, seconds = divmod(progress, 60)
        label = f"{minutes:02d}:{seconds:02d}"
        if xbmcgui.Dialog().yesno("dejaVu", _ls(30073) % label):
            try:
                self.seekTime(float(progress))
                self._resumed = True
                _log(f"Resumed playback at {progress}s", xbmc.LOGINFO)
            except Exception as e:
                _log(f"Player.seekTime failed: {e}", xbmc.LOGWARNING)

    def _maybe_play_upnext(self, meta):
        """Offer the next episode from GET /upnext after an episode finishes."""
        try:
            if not ADDON.getSettingBool("enable_upnext"):
                return
        except Exception:
            return
        if not is_logged_in():
            return

        result = self.api.get_up_next(page=1, page_size=20, minimal=False)
        items = unwrap_data(result) or []
        if not isinstance(items, list):
            return

        current_season = meta.get("season") or 0
        current_episode = meta.get("episode") or 0
        show_id = str(meta.get("show_tmdb_id") or "")

        nxt = None
        for item in items:
            if not isinstance(item, dict):
                continue
            if show_id and str(item.get("tvShowTmdbId")) != show_id:
                continue
            info = item.get("info") or {}
            n_season = info.get("season")
            n_episode = info.get("episode")
            if n_season is None or n_episode is None:
                continue
            if n_season > current_season or (
                n_season == current_season and n_episode > current_episode
            ):
                nxt = item
                break

        if not nxt:
            return

        info = nxt.get("info") or {}
        n_season = info.get("season")
        n_episode = info.get("episode")
        show_title = info.get("tvshowtitle") or meta.get("show_title") or ""
        label = f"{show_title} S{int(n_season):02d}E{int(n_episode):02d}"

        notify_changed(
            "upnext",
            "episode",
            nxt.get("tmdbId"),
            extra={
                "tvShowId": nxt.get("tvShowTmdbId"),
                "seasonNumber": n_season,
                "episodeNumber": n_episode,
                "title": label,
            },
        )

        if not xbmcgui.Dialog().yesno("dejaVu", _ls(30074) % label):
            return

        if self._play_library_episode(meta, n_season, n_episode):
            return
        _log("Next episode is not in the Kodi library; notified other addons via upnext.", xbmc.LOGINFO)

    def _play_library_episode(self, meta, season, episode):
        """Play the next episode from the Kodi library when the current item has a DBID."""
        try:
            ep_dbid = int(meta.get("dbid") or 0)
        except (TypeError, ValueError):
            ep_dbid = 0
        if ep_dbid <= 0:
            return False

        try:
            resp1 = json.loads(xbmc.executeJSONRPC(json.dumps({
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetEpisodeDetails",
                "params": {"episodeid": ep_dbid, "properties": ["tvshowid"]},
                "id": 1,
            })))
            tvshowid = resp1.get("result", {}).get("episodedetails", {}).get("tvshowid")
            if not tvshowid:
                return False

            resp2 = json.loads(xbmc.executeJSONRPC(json.dumps({
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetEpisodes",
                "params": {
                    "tvshowid": tvshowid,
                    "season": int(season),
                    "properties": ["episode"],
                    "filter": {"field": "episode", "operator": "is", "value": str(int(episode))},
                },
                "id": 2,
            })))
            episodes = resp2.get("result", {}).get("episodes") or []
            if not episodes:
                return False
            next_id = episodes[0].get("episodeid")
            if not next_id:
                return False
            xbmc.executeJSONRPC(json.dumps({
                "jsonrpc": "2.0",
                "method": "Player.Open",
                "params": {"item": {"episodeid": next_id}},
                "id": 3,
            }))
            return True
        except Exception as e:
            _log(f"Library upnext play failed: {e}", xbmc.LOGWARNING)
            return False

    # ------------------------------------------------------------------
    # Periodic update (called by service loop)
    # ------------------------------------------------------------------

    def tick(self):
        """
        Called by the service every second.
        Sends a periodic scrobble update according to scrobble_interval.
        """
        if not self._active or not self.isPlayingVideo():
            return
        try:
            interval = ADDON.getSettingInt("scrobble_interval") or 30
        except Exception:
            interval = 30
        if time.time() - self._last_scrobble_ts >= interval:
            self._scrobble("update")

