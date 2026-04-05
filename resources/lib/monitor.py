# -*- coding: utf-8 -*-
"""
dejaVu Monitor
Handles RPC-style inter-addon communication via Kodi notifications.

Supported actions (method format: 'script.dejavu.ACTION'):
  READ
    get_watchlist       params: page, page_size, type
    get_history         params: page, page_size, type, sort
    get_ratings         params: page, page_size, type
    get_favorites       params: page, page_size, type
    get_collection      params: page, page_size, type, sort, format
    get_up_next         params: page, page_size
    get_lists           params: page, page_size

  WRITE
    add_to_watchlist    params: type, id, priority, notes
    remove_from_watchlist params: type, id
    add_to_history      params: type, id, count, watched_at, tvShowId, seasonNumber, episodeNumber
    add_to_favorites    params: type, id
    remove_from_favorites params: type, id
    rate                params: type, id, rating, tvShowId, seasonNumber, episodeNumber, review
    scrobble            params: type, id, progress, duration

Data format for notification:
  {
    "result_property": "my.addon.result",   // optional, default: script.dejavu.<ACTION>.result
    // ... action-specific params
  }
"""

import json
import xbmc
import xbmcgui
from .api_client import DejaVuAPI


def _log(msg, level=xbmc.LOGDEBUG):
    xbmc.log(f"[dejaVu.Monitor] {msg}", level)


class DejaVuMonitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.api = DejaVuAPI()

    # ------------------------------------------------------------------
    # Notification dispatcher
    # ------------------------------------------------------------------

    def onNotification(self, sender, method, data):
        """
        Handles incoming notifications for RPC-like communication.
        Method expected format: 'script.dejavu.ACTION'
        Data expected format: JSON string with 'result_property' and optional params.
        """
        if not method.startswith("script.dejavu."):
            return

        action = method.replace("script.dejavu.", "")
        _log(f"RPC request: {action} from {sender}", xbmc.LOGINFO)

        try:
            params = json.loads(data) if data else {}
        except Exception as e:
            _log(f"Failed to parse notification data: {e}", xbmc.LOGERROR)
            return

        result_property = params.get(
            "result_property", f"script.dejavu.{action}.result"
        )

        # ---- READ actions ----
        if action == "get_watchlist":
            self._handle_get_watchlist(params, result_property)
        elif action == "get_history":
            self._handle_get_history(params, result_property)
        elif action == "get_ratings":
            self._handle_get_ratings(params, result_property)
        elif action == "get_favorites":
            self._handle_get_favorites(params, result_property)
        elif action == "get_collection":
            self._handle_get_collection(params, result_property)
        elif action == "get_up_next":
            self._handle_get_up_next(params, result_property)
        elif action == "get_lists":
            self._handle_get_lists(params, result_property)

        # ---- WRITE actions ----
        elif action == "add_to_watchlist":
            self._handle_add_to_watchlist(params, result_property)
        elif action == "remove_from_watchlist":
            self._handle_remove_from_watchlist(params, result_property)
        elif action == "add_to_history":
            self._handle_add_to_history(params, result_property)
        elif action == "add_to_favorites":
            self._handle_add_to_favorites(params, result_property)
        elif action == "remove_from_favorites":
            self._handle_remove_from_favorites(params, result_property)
        elif action == "rate":
            self._handle_rate(params, result_property)
        elif action == "scrobble":
            self._handle_scrobble(params, result_property)

        else:
            _log(f"Unknown RPC action: {action}", xbmc.LOGWARNING)

    # ------------------------------------------------------------------
    # READ handlers
    # ------------------------------------------------------------------

    def _handle_get_watchlist(self, params, result_property):
        try:
            result = self.api.get_watchlist(
                media_type=params.get("type"),
                page=params.get("page", 1),
                page_size=params.get("page_size", 20),
                sort=params.get("sort", "addedAt:desc"),
                minimal=params.get("minimal", False),
            )
            self._set_result(result_property, result)
        except Exception as e:
            _log(f"get_watchlist RPC error: {e}", xbmc.LOGERROR)

    def _handle_get_history(self, params, result_property):
        try:
            result = self.api.get_history(
                media_type=params.get("type"),
                page=params.get("page", 1),
                page_size=params.get("page_size", 20),
                sort=params.get("sort", "watchedAt:desc"),
                minimal=params.get("minimal", False),
            )
            self._set_result(result_property, result)
        except Exception as e:
            _log(f"get_history RPC error: {e}", xbmc.LOGERROR)

    def _handle_get_ratings(self, params, result_property):
        try:
            result = self.api.get_ratings(
                media_type=params.get("type"),
                page=params.get("page", 1),
                page_size=params.get("page_size", 20),
                minimal=params.get("minimal", False),
            )
            self._set_result(result_property, result)
        except Exception as e:
            _log(f"get_ratings RPC error: {e}", xbmc.LOGERROR)

    def _handle_get_favorites(self, params, result_property):
        try:
            result = self.api.get_favorites(
                media_type=params.get("type"),
                page=params.get("page", 1),
                page_size=params.get("page_size", 20),
                minimal=params.get("minimal", False),
            )
            self._set_result(result_property, result)
        except Exception as e:
            _log(f"get_favorites RPC error: {e}", xbmc.LOGERROR)

    def _handle_get_collection(self, params, result_property):
        try:
            result = self.api.get_collection(
                media_type=params.get("type"),
                page=params.get("page", 1),
                page_size=params.get("page_size", 20),
                sort=params.get("sort", "addedAt:desc"),
                fmt=params.get("format"),
                minimal=params.get("minimal", False),
            )
            self._set_result(result_property, result)
        except Exception as e:
            _log(f"get_collection RPC error: {e}", xbmc.LOGERROR)

    def _handle_get_up_next(self, params, result_property):
        try:
            result = self.api.get_up_next(
                page=params.get("page", 1),
                page_size=params.get("page_size", 20),
                minimal=params.get("minimal", False),
            )
            self._set_result(result_property, result)
        except Exception as e:
            _log(f"get_up_next RPC error: {e}", xbmc.LOGERROR)

    def _handle_get_lists(self, params, result_property):
        try:
            result = self.api.get_lists(
                page=params.get("page", 1),
                page_size=params.get("page_size", 20),
                minimal=params.get("minimal", False),
            )
            self._set_result(result_property, result)
        except Exception as e:
            _log(f"get_lists RPC error: {e}", xbmc.LOGERROR)

    # ------------------------------------------------------------------
    # WRITE handlers
    # ------------------------------------------------------------------

    def _handle_add_to_watchlist(self, params, result_property):
        try:
            result = self.api.add_to_watchlist(
                media_type=params["type"],
                tmdb_id=params["id"],
                priority=params.get("priority"),
                notes=params.get("notes"),
            )
            self._set_result(result_property, result)
        except Exception as e:
            _log(f"add_to_watchlist RPC error: {e}", xbmc.LOGERROR)

    def _handle_remove_from_watchlist(self, params, result_property):
        try:
            result = self.api.remove_from_watchlist(
                media_type=params["type"],
                tmdb_id=params["id"],
            )
            self._set_result(result_property, result)
        except Exception as e:
            _log(f"remove_from_watchlist RPC error: {e}", xbmc.LOGERROR)

    def _handle_add_to_history(self, params, result_property):
        try:
            result = self.api.add_to_history(
                media_type=params["type"],
                tmdb_id=params.get("id"),
                count=params.get("count", 1),
                watched_at=params.get("watched_at"),
                tv_show_id=params.get("tvShowId"),
                season=params.get("seasonNumber"),
                episode=params.get("episodeNumber"),
            )
            self._set_result(result_property, result)
        except Exception as e:
            _log(f"add_to_history RPC error: {e}", xbmc.LOGERROR)

    def _handle_add_to_favorites(self, params, result_property):
        try:
            result = self.api.add_to_favorites(
                media_type=params["type"],
                tmdb_id=params["id"],
            )
            self._set_result(result_property, result)
        except Exception as e:
            _log(f"add_to_favorites RPC error: {e}", xbmc.LOGERROR)

    def _handle_remove_from_favorites(self, params, result_property):
        try:
            result = self.api.remove_from_favorites(
                media_type=params["type"],
                tmdb_id=params["id"],
            )
            self._set_result(result_property, result)
        except Exception as e:
            _log(f"remove_from_favorites RPC error: {e}", xbmc.LOGERROR)

    def _handle_rate(self, params, result_property):
        try:
            result = self.api.rate(
                media_type=params["type"],
                rating=params["rating"],
                tmdb_id=params.get("id"),
                tv_show_id=params.get("tvShowId"),
                season=params.get("seasonNumber"),
                episode=params.get("episodeNumber"),
                review=params.get("review"),
            )
            self._set_result(result_property, result)
        except Exception as e:
            _log(f"rate RPC error: {e}", xbmc.LOGERROR)

    def _handle_scrobble(self, params, result_property):
        try:
            result = self.api.scrobble(
                media_type=params["type"],
                progress=params["progress"],
                duration=params["duration"],
                tmdb_id=params.get("id"),
                season=params.get("seasonNumber"),
                episode=params.get("episodeNumber"),
            )
            self._set_result(result_property, result)
        except Exception as e:
            _log(f"scrobble RPC error: {e}", xbmc.LOGERROR)

    # ------------------------------------------------------------------
    # Result helper
    # ------------------------------------------------------------------

    def _set_result(self, property_name, data):
        """Sets the JSON result in a Kodi window property (Window 10000)."""
        json_data = json.dumps(data)
        xbmcgui.Window(10000).setProperty(property_name, json_data)
        _log(f"RPC result set → {property_name}", xbmc.LOGDEBUG)
