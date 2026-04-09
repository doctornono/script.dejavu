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

    def _resolve_tmdb_from_external(self, external_id, media_type="movie"):
        """
        Uses TMDB 'find' endpoint to resolve IMDB/TVDB identifiers to TMDB IDs.
        media_type: "movie", "tv" (for shows), or "episode".
        """
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
        Search TMDB by title if no IDs are available.
        media_type: "movie" or "tv"
        """
        if not title:
            return None
            
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
        if media_type == "movie":
            res = {
                "type": "movie",
                "tmdb_id": tmdb_id,
                "title": tag.getTitle(),
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
        """
        try:
            if not ADDON.getSettingBool("enable_scrobble"):
                return
        except Exception:
            pass  # default: enabled
        if not is_logged_in():
            return
        if not self._active:
            return
        if self._watched_sent:
            return

        meta = self._meta or self._get_metadata()
        if not meta:
            return

        # boucler pour logger chaque clé et valeur de meta
        for key, value in meta.items():
            _log(f"+++++{key}: {value}", xbmc.LOGDEBUG)
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

        is_watched_now = (progress / duration * 100) >= watch_pct

        _log(
            f"Sending Scrobble API Call: action={action}, type={meta['type']}, "
            f"tmdb_id={meta['tmdb_id']}, progress={progress}/{duration}s, "
            f"show_id={meta.get('show_tmdb_id')}, S{meta.get('season')}E{meta.get('episode')}",
            xbmc.LOGINFO
        )

        result = self.api.scrobble(
            media_type=meta["type"],
            progress=progress,
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

        if is_watched_now:
            if not self._watched_sent:
                # Explicitly mark as watched in history once when threshold is hit
                _log(f"Threshold reached ({watch_pct}%) – preparing add_to_history call.", xbmc.LOGINFO)
                _log(
                    f"History Payload: type={meta['type']}, tmdb_id={meta['tmdb_id']}, "
                    f"show_id={meta.get('show_tmdb_id')}, S{meta.get('season')}E{meta.get('episode')}",
                    xbmc.LOGDEBUG
                )
                self.api.add_to_history(
                    media_type=meta["type"],
                    tmdb_id=meta["tmdb_id"],
                    tv_show_id=meta.get("show_tmdb_id"),
                    season=meta.get("season"),
                    episode=meta.get("episode"),
                )
                self._watched_sent = True
                
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
        # Detailed dump for discovery
        self._log_player_item_details()
        self._meta = self._get_metadata()
        self._active = True
        self._last_scrobble_ts = 0
        self._watched_sent = False
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
        On stop/end: check the watched threshold and send a final scrobble.
        The API marks as watched automatically at 90%; we respect the user's
        local setting to decide whether to send at all.
        """
        self._scrobble(reason)

        try:
            if ADDON.getSettingBool("prompt_rating") and self._watched_sent and self._meta:
                self._prompt_rating(self._meta)
        except Exception:
            pass

        self._active = False
        self._meta = None
        self._watched_sent = False

    def _prompt_rating(self, meta):
        # Give Kodi a moment to close the player UI
        xbmc.sleep(1000)

        ratings = [str(i) for i in range(10, 0, -1)]
        title = f"{_ls(30017)}: {meta.get('title', '')}"
        selected = xbmcgui.Dialog().select(title, ratings)

        if selected < 0:
            return

        rating = int(ratings[selected])
        media_type = meta.get("type", "movie")
        tmdb_id = meta.get("tmdb_id")
        show_tmdb = meta.get("show_tmdb_id")
        season = meta.get("season")
        episode = meta.get("episode")

        # Allow episodes with show info + S+E even if episode tmdb_id is null
        _log(f"Prompting rating for: {json.dumps(meta)}", xbmc.LOGDEBUG)
        if not tmdb_id:
            if media_type != "episode" or not (show_tmdb and season and episode):
                _log(f"Prompt rating skipped: insufficient IDs (type={media_type}, tmdb_id={tmdb_id}, show_id={show_tmdb})", xbmc.LOGWARNING)
                xbmcgui.Dialog().notification("dejaVu", _ls(30019), xbmcgui.NOTIFICATION_ERROR)
                return

        try:
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

            if ADDON.getSettingBool("show_notifications"):
                xbmcgui.Dialog().notification(
                    "dejaVu",
                    _ls(30018) % rating,
                    xbmcgui.NOTIFICATION_INFO,
                    3000,
                )
        except Exception as e:
            _log(f"Rating error: {e}", xbmc.LOGERROR)

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

