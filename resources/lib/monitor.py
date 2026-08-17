# -*- coding: utf-8 -*-
"""
dejaVu Monitor
Handles RPC-style inter-addon communication via Kodi notifications.

Supported actions (method format: 'script.dejavu.ACTION'):
  READ
    get_watchlist         params: page, page_size, type, sort, minimal
    get_history           params: page, page_size, type, sort, minimal
    get_ratings           params: page, page_size, type, minimal
    get_favorites         params: page, page_size, type, minimal
    get_collection        params: page, page_size, type, sort, format, minimal
    get_up_next           params: page, page_size, minimal
    get_lists             params: page, page_size, minimal
    get_list_items        params: list_id, page, page_size, minimal
    get_dashboard         params: (none)
    get_dashboard_widget  params: widget_type, list_id, page, page_size, minimal
    get_scrobbles         params: type, page, page_size, minimal
    get_media_status      params: items  (list of {type, id}, max 50)
    get_me                params: (none)
    resolve_media         params: imdb_id, tmdb_id, type, title, year

  WRITE
    add_to_watchlist      params: type, id, priority, notes
    remove_from_watchlist params: type, id
    add_to_history        params: type, id, count, watched_at, tvShowId, seasonNumber, episodeNumber
    delete_history        params: type, id
    add_to_favorites      params: type, id
    remove_from_favorites params: type, id
    add_to_collection     params: type, id, format, notes
    remove_from_collection params: type, id
    create_list           params: name, description, visibility
    add_to_list           params: list_id, type, id, notes, position
    remove_from_list      params: list_id, type, id
    rate                  params: type, id, rating, tvShowId, seasonNumber, episodeNumber, review
    delete_rating         params: type, id, tvShowId, seasonNumber
    scrobble              params: type, id, progress, duration, tvShowId, seasonNumber, episodeNumber
    delete_scrobble       params: type, id

Data format for notification:
  {
    "result_property": "my.addon.result",   // optional, default: script.dejavu.<ACTION>.result
    // ... action-specific params
  }

After successful write actions, a `script.dejavu.changed` notification is also sent
so calling addons can refresh overlays (watched / rating / watchlist badges).
"""

import json
import xbmc
import xbmcgui
from .api_client import DejaVuAPI
from .util import notify_changed


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
        # Ignore our own change broadcasts
        if method == "script.dejavu.changed":
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

        handler = getattr(self, f"_handle_{action}", None)
        if not callable(handler):
            _log(f"Unknown RPC action: {action}", xbmc.LOGWARNING)
            self._set_result(result_property, {"success": False, "error": f"Unknown action: {action}"})
            return

        try:
            result = handler(params)
            self._set_result(result_property, result)
        except KeyError as e:
            _log(f"{action} RPC missing param: {e}", xbmc.LOGERROR)
            self._set_result(result_property, {"success": False, "error": f"Missing param: {e}"})
        except Exception as e:
            _log(f"{action} RPC error: {e}", xbmc.LOGERROR)
            self._set_result(result_property, {"success": False, "error": str(e)})

    # ------------------------------------------------------------------
    # READ handlers
    # ------------------------------------------------------------------

    def _handle_get_watchlist(self, params):
        return self.api.get_watchlist(
            media_type=params.get("type"),
            page=params.get("page", 1),
            page_size=params.get("page_size", 20),
            sort=params.get("sort", "addedAt:desc"),
            minimal=params.get("minimal", False),
        )

    def _handle_get_history(self, params):
        return self.api.get_history(
            media_type=params.get("type"),
            page=params.get("page", 1),
            page_size=params.get("page_size", 20),
            sort=params.get("sort", "watchedAt:desc"),
            minimal=params.get("minimal", False),
        )

    def _handle_get_ratings(self, params):
        return self.api.get_ratings(
            media_type=params.get("type"),
            page=params.get("page", 1),
            page_size=params.get("page_size", 20),
            minimal=params.get("minimal", False),
        )

    def _handle_get_favorites(self, params):
        return self.api.get_favorites(
            media_type=params.get("type"),
            page=params.get("page", 1),
            page_size=params.get("page_size", 20),
            minimal=params.get("minimal", False),
        )

    def _handle_get_collection(self, params):
        return self.api.get_collection(
            media_type=params.get("type"),
            page=params.get("page", 1),
            page_size=params.get("page_size", 20),
            sort=params.get("sort", "addedAt:desc"),
            fmt=params.get("format"),
            minimal=params.get("minimal", False),
        )

    def _handle_get_up_next(self, params):
        return self.api.get_up_next(
            page=params.get("page", 1),
            page_size=params.get("page_size", 20),
            minimal=params.get("minimal", False),
        )

    def _handle_get_lists(self, params):
        return self.api.get_lists(
            page=params.get("page", 1),
            page_size=params.get("page_size", 20),
            minimal=params.get("minimal", False),
        )

    def _handle_get_list_items(self, params):
        return self.api.get_list_items(
            list_id=params["list_id"],
            page=params.get("page", 1),
            page_size=params.get("page_size", 20),
            minimal=params.get("minimal", False),
        )

    def _handle_get_dashboard(self, params):
        return self.api.get_dashboard()

    def _handle_get_dashboard_widget(self, params):
        return self.api.get_dashboard_widget(
            widget_type=params["widget_type"],
            list_id=params.get("list_id"),
            page=params.get("page", 1),
            page_size=params.get("page_size", 20),
            minimal=params.get("minimal", False),
        )

    def _handle_get_scrobbles(self, params):
        return self.api.get_scrobbles(
            media_type=params.get("type"),
            page=params.get("page", 1),
            page_size=params.get("page_size", 20),
            minimal=params.get("minimal", False),
        )

    def _handle_get_media_status(self, params):
        return self.api.get_media_status(params.get("items") or [])

    def _handle_get_me(self, params):
        return self.api.get_me()

    def _handle_resolve_media(self, params):
        return self.api.resolve_media(
            imdb_id=params.get("imdb_id") or params.get("imdbId"),
            tmdb_id=params.get("tmdb_id") or params.get("tmdbId") or params.get("id"),
            media_type=params.get("type"),
            title=params.get("title"),
            year=params.get("year"),
        )

    # ------------------------------------------------------------------
    # WRITE handlers
    # ------------------------------------------------------------------

    def _handle_add_to_watchlist(self, params):
        result = self.api.add_to_watchlist(
            media_type=params["type"],
            tmdb_id=params["id"],
            priority=params.get("priority"),
            notes=params.get("notes"),
        )
        self._broadcast_write("add_to_watchlist", params, result)
        return result

    def _handle_remove_from_watchlist(self, params):
        result = self.api.remove_from_watchlist(
            media_type=params["type"],
            tmdb_id=params["id"],
        )
        self._broadcast_write("remove_from_watchlist", params, result)
        return result

    def _handle_add_to_history(self, params):
        result = self.api.add_to_history(
            media_type=params["type"],
            tmdb_id=params.get("id"),
            count=params.get("count", 1),
            watched_at=params.get("watched_at"),
            tv_show_id=params.get("tvShowId"),
            season=params.get("seasonNumber"),
            episode=params.get("episodeNumber"),
        )
        self._broadcast_write("add_to_history", params, result)
        return result

    def _handle_delete_history(self, params):
        result = self.api.delete_history(
            media_type=params["type"],
            tmdb_id=params["id"],
        )
        self._broadcast_write("delete_history", params, result)
        return result

    def _handle_remove_from_history(self, params):
        return self._handle_delete_history(params)

    def _handle_add_to_favorites(self, params):
        result = self.api.add_to_favorites(
            media_type=params["type"],
            tmdb_id=params["id"],
        )
        self._broadcast_write("add_to_favorites", params, result)
        return result

    def _handle_remove_from_favorites(self, params):
        result = self.api.remove_from_favorites(
            media_type=params["type"],
            tmdb_id=params["id"],
        )
        self._broadcast_write("remove_from_favorites", params, result)
        return result

    def _handle_add_to_collection(self, params):
        result = self.api.add_to_collection(
            media_type=params["type"],
            tmdb_id=params["id"],
            fmt=params.get("format"),
            notes=params.get("notes"),
        )
        self._broadcast_write("add_to_collection", params, result)
        return result

    def _handle_remove_from_collection(self, params):
        result = self.api.remove_from_collection(
            media_type=params["type"],
            tmdb_id=params["id"],
        )
        self._broadcast_write("remove_from_collection", params, result)
        return result

    def _handle_create_list(self, params):
        result = self.api.create_list(
            name=params["name"],
            description=params.get("description"),
            visibility=params.get("visibility", "PRIVATE"),
        )
        self._broadcast_write("create_list", params, result)
        return result

    def _handle_add_to_list(self, params):
        result = self.api.add_to_list(
            list_id=params["list_id"],
            media_type=params["type"],
            tmdb_id=params["id"],
            notes=params.get("notes"),
            position=params.get("position"),
        )
        self._broadcast_write("add_to_list", params, result)
        return result

    def _handle_remove_from_list(self, params):
        result = self.api.remove_from_list(
            list_id=params["list_id"],
            media_type=params["type"],
            tmdb_id=params["id"],
        )
        self._broadcast_write("remove_from_list", params, result)
        return result

    def _handle_rate(self, params):
        result = self.api.rate(
            media_type=params["type"],
            rating=params["rating"],
            tmdb_id=params.get("id"),
            tv_show_id=params.get("tvShowId"),
            season=params.get("seasonNumber"),
            episode=params.get("episodeNumber"),
            review=params.get("review"),
        )
        self._broadcast_write("rate", params, result)
        return result

    def _handle_delete_rating(self, params):
        result = self.api.delete_rating(
            media_type=params["type"],
            tmdb_id=params.get("id"),
            tv_show_id=params.get("tvShowId"),
            season=params.get("seasonNumber"),
        )
        self._broadcast_write("delete_rating", params, result)
        return result

    def _handle_scrobble(self, params):
        result = self.api.scrobble(
            media_type=params["type"],
            progress=params["progress"],
            duration=params["duration"],
            tmdb_id=params.get("id"),
            tv_show_id=params.get("tvShowId"),
            season=params.get("seasonNumber"),
            episode=params.get("episodeNumber"),
        )
        self._broadcast_write("scrobble", params, result)
        return result

    def _handle_delete_scrobble(self, params):
        result = self.api.delete_scrobble(
            media_type=params["type"],
            tmdb_id=params["id"],
        )
        self._broadcast_write("delete_scrobble", params, result)
        return result

    # ------------------------------------------------------------------
    # Result helper
    # ------------------------------------------------------------------

    def _broadcast_write(self, action, params, result):
        if result is None:
            return
        extra = {}
        if params.get("list_id"):
            extra["list_id"] = params["list_id"]
        notify_changed(
            action,
            media_type=params.get("type"),
            tmdb_id=params.get("id"),
            extra=extra or None,
        )

    def _set_result(self, property_name, data):
        """Sets the JSON result in a Kodi window property (Window 10000)."""
        json_data = json.dumps(data)
        xbmcgui.Window(10000).setProperty(property_name, json_data)
        _log(f"RPC result set → {property_name}", xbmc.LOGDEBUG)
