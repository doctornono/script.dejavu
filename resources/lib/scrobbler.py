# -*- coding: utf-8 -*-
"""
dejaVu Scrobbler
Subclasses xbmc.Player to hook playback events and send scrobble updates
to the dejaVu API.
"""

import json
import time
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

    def _get_show_tmdb_id(self):
        """
        Resolve the TV show TMDB ID via Kodi JSON-RPC.
        Uses VideoPlayer.DBID → VideoLibrary.GetEpisodeDetails → tvshowid
        → VideoLibrary.GetTVShowDetails → uniqueid.tmdb

        This is the only reliable method with the TMDB scraper, because
        tag.getUniqueID("tmdb") on an episode returns the episode ID,
        not the show ID.
        """
        try:
            ep_dbid = int(xbmc.getInfoLabel("VideoPlayer.DBID") or 0)
            if not ep_dbid:
                _log("No DBID for current episode – show_tmdb_id unavailable", xbmc.LOGWARNING)
                return None

            # Step 1: get tvshowid from the episode
            req1 = json.dumps({
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetEpisodeDetails",
                "params": {"episodeid": ep_dbid, "properties": ["tvshowid"]},
                "id": 1,
            })
            resp1 = json.loads(xbmc.executeJSONRPC(req1))
            tvshowid = (
                resp1.get("result", {})
                     .get("episodedetails", {})
                     .get("tvshowid", -1)
            )
            if tvshowid < 0:
                _log("tvshowid not found in episode details", xbmc.LOGWARNING)
                return None

            # Step 2: get uniqueid.tmdb from the TV show
            req2 = json.dumps({
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetTVShowDetails",
                "params": {"tvshowid": tvshowid, "properties": ["uniqueid"]},
                "id": 2,
            })
            resp2 = json.loads(xbmc.executeJSONRPC(req2))
            uniqueids = (
                resp2.get("result", {})
                     .get("tvshowdetails", {})
                     .get("uniqueid", {})
            )
            show_tmdb = uniqueids.get("tmdb") or uniqueids.get("unknown")
            _log(f"Resolved show TMDB ID: {show_tmdb} (tvshowid={tvshowid})", xbmc.LOGDEBUG)
            return show_tmdb

        except Exception as e:
            _log(f"_get_show_tmdb_id error: {e}", xbmc.LOGWARNING)
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

        tmdb_id = tag.getUniqueID("tmdb")

        if not tmdb_id:
            _log("No TMDB ID found for current item – scrobble skipped.", xbmc.LOGWARNING)
            return None

        if media_type == "movie":
            return {
                "type": "movie",
                "tmdb_id": tmdb_id,
                "title": tag.getTitle(),
            }

        if media_type == "episode":
            # tmdb_id here is the episode's own TMDB ID (TMDB scraper behaviour)
            # show_tmdb_id is resolved separately via JSON-RPC
            show_tmdb = self._get_show_tmdb_id()
            return {
                "type": "episode",
                "tmdb_id": tmdb_id,           # episode TMDB ID → sent as `id` in API
                "show_tmdb_id": show_tmdb,    # TV show TMDB ID → sent as `tvShowId`
                "season": tag.getSeason(),
                "episode": tag.getEpisode(),
                "title": (
                    f"{tag.getTVShowTitle()} "
                    f"S{tag.getSeason():02d}E{tag.getEpisode():02d}"
                ),
            }

        _log(f"Unhandled media type: '{media_type}'", xbmc.LOGDEBUG)
        return None

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
            f"Scrobble [{action}] {meta['title']} – {progress}/{duration}s "
            f"({int(progress / duration * 100)}%)"
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

        if is_watched_now:
            if not self._watched_sent:
                # Explicitly mark as watched in history once when threshold is hit
                _log(f"Threshold reached ({watch_pct}%) – calling add_to_history auto.", xbmc.LOGINFO)
                self.api.add_to_history(
                    media_type=meta["type"],
                    tmdb_id=meta["tmdb_id"],
                    tv_show_id=meta.get("show_tmdb_id"),
                    season=meta.get("season"),
                    episode=meta.get("episode"),
                )
                self._watched_sent = True
                
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

        if not tmdb_id:
            xbmcgui.Dialog().notification("dejaVu", _ls(30019), xbmcgui.NOTIFICATION_ERROR)
            return

        try:
            if media_type == "episode":
                show_tmdb = meta.get("show_tmdb_id")
                season = meta.get("season")
                episode = meta.get("episode")
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

