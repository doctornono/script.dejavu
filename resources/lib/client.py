# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import json
import time


class DejaVuClient:
    """
    Client for interacting with script.dejavu via RPC (Kodi Notifications).
    This allows other addons to query watchlist, history, lists, overlays, etc.,
    without having to manage API keys or direct network calls.
    """

    def __init__(self, timeout=5):
        """
        :param timeout: Maximum time in seconds to wait for a response.
        """
        self.timeout = timeout
        self.window = xbmcgui.Window(10000)

    def _log(self, msg, level=xbmc.LOGDEBUG):
        xbmc.log(f"[script.dejavu.Client] {msg}", level)

    def call(self, action, params=None):
        """
        Sends an RPC request to script.dejavu and waits for the result.

        :param action: The action name (e.g., 'get_watchlist', 'get_media_status')
        :param params: Dictionary of parameters for the action.
        :return: The result (dict/list) or None if error/timeout.
        """
        method = f"script.dejavu.{action}"
        result_property = f"{method}.result"

        self.window.clearProperty(result_property)

        data = params if params else {}
        data["result_property"] = result_property

        sender = xbmc.getAddonInfo("id")
        payload = json.dumps(data)

        self._log(f"Calling {method} with {payload}")
        xbmc.executebuiltin(f"NotifyAll({sender}, {method}, {payload})")

        start_time = time.time()
        while time.time() - start_time < self.timeout:
            if xbmc.Monitor().waitForAbort(0.1):
                return None

            result_raw = self.window.getProperty(result_property)
            if result_raw:
                try:
                    result = json.loads(result_raw)
                    self._log(f"Received result for {action}")
                    return result
                except Exception as e:
                    self._log(f"Failed to parse result for {action}: {e}", xbmc.LOGERROR)
                    return None

        self._log(f"Timeout waiting for {action} result", xbmc.LOGWARNING)
        return None

    # --- Read ---

    def get_watchlist(self, media_type=None, page=1, page_size=20, sort="addedAt:desc", minimal=False):
        return self.call("get_watchlist", {
            "type": media_type, "page": page, "page_size": page_size,
            "sort": sort, "minimal": minimal,
        })

    def get_lists(self, page=1, page_size=20, minimal=False):
        return self.call("get_lists", {
            "page": page, "page_size": page_size, "minimal": minimal,
        })

    def get_list_items(self, list_id, page=1, page_size=20, minimal=False):
        return self.call("get_list_items", {
            "list_id": list_id, "page": page, "page_size": page_size, "minimal": minimal,
        })

    def get_up_next(self, page=1, page_size=20, minimal=False):
        return self.call("get_up_next", {
            "page": page, "page_size": page_size, "minimal": minimal,
        })

    def get_history(self, media_type=None, page=1, page_size=20, sort="watchedAt:desc", minimal=False):
        return self.call("get_history", {
            "type": media_type, "page": page, "page_size": page_size,
            "sort": sort, "minimal": minimal,
        })

    def get_ratings(self, media_type=None, page=1, page_size=20, minimal=False):
        return self.call("get_ratings", {
            "type": media_type, "page": page, "page_size": page_size, "minimal": minimal,
        })

    def get_favorites(self, media_type=None, page=1, page_size=20, minimal=False):
        return self.call("get_favorites", {
            "type": media_type, "page": page, "page_size": page_size, "minimal": minimal,
        })

    def get_collection(self, media_type=None, page=1, page_size=20, sort="addedAt:desc", fmt=None, minimal=False):
        params = {
            "type": media_type, "page": page, "page_size": page_size,
            "sort": sort, "minimal": minimal,
        }
        if fmt:
            params["format"] = fmt
        return self.call("get_collection", params)

    def get_scrobbles(self, media_type=None, page=1, page_size=20, minimal=False):
        return self.call("get_scrobbles", {
            "type": media_type, "page": page, "page_size": page_size, "minimal": minimal,
        })

    def get_media_status(self, items):
        """
        Batch overlay status for other addons (watched, rating, watchlist, favorite, collection).

        :param items: list of dicts {"type": "movie"|"tv", "id": tmdb_id} (max 50)
        """
        return self.call("get_media_status", {"items": items, "minimal": True})

    def get_me(self):
        return self.call("get_me", {})

    def resolve_media(self, imdb_id=None, tmdb_id=None, media_type=None, title=None, year=None):
        return self.call("resolve_media", {
            "imdb_id": imdb_id, "tmdb_id": tmdb_id, "type": media_type,
            "title": title, "year": year,
        })

    def get_dashboard(self):
        """Returns the user's dashboard layout configuration."""
        return self.call("get_dashboard", {})

    def get_dashboard_widget(self, widget_type, list_id=None, page=1, page_size=20, minimal=False):
        """
        widget_type : "up_next" | "recent_watchlist" | "continue_watching" |
                      "active_movie_scrobbles" | "active_tv_scrobbles" |
                      "upcoming_releases" | "upcoming_schedule" | "list"
        list_id     : required when widget_type == "list"
        """
        params = {
            "widget_type": widget_type,
            "page": page,
            "page_size": page_size,
            "minimal": minimal,
        }
        if list_id:
            params["list_id"] = list_id
        return self.call("get_dashboard_widget", params)

    # --- Write ---

    def add_to_watchlist(self, media_type, tmdb_id, priority=None, notes=None):
        return self.call("add_to_watchlist", {
            "type": media_type, "id": tmdb_id, "priority": priority, "notes": notes,
        })

    def remove_from_watchlist(self, media_type, tmdb_id):
        return self.call("remove_from_watchlist", {"type": media_type, "id": tmdb_id})

    def add_to_history(self, media_type, tmdb_id=None, count=1, watched_at=None,
                       tv_show_id=None, season=None, episode=None):
        return self.call("add_to_history", {
            "type": media_type, "id": tmdb_id, "count": count, "watched_at": watched_at,
            "tvShowId": tv_show_id, "seasonNumber": season, "episodeNumber": episode,
        })

    def delete_history(self, media_type, tmdb_id):
        return self.call("delete_history", {"type": media_type, "id": tmdb_id})

    def add_to_favorites(self, media_type, tmdb_id):
        return self.call("add_to_favorites", {"type": media_type, "id": tmdb_id})

    def remove_from_favorites(self, media_type, tmdb_id):
        return self.call("remove_from_favorites", {"type": media_type, "id": tmdb_id})

    def add_to_collection(self, media_type, tmdb_id, fmt=None, notes=None):
        return self.call("add_to_collection", {
            "type": media_type, "id": tmdb_id, "format": fmt, "notes": notes,
        })

    def remove_from_collection(self, media_type, tmdb_id):
        return self.call("remove_from_collection", {"type": media_type, "id": tmdb_id})

    def create_list(self, name, description=None, visibility="PRIVATE"):
        return self.call("create_list", {
            "name": name, "description": description, "visibility": visibility,
        })

    def add_to_list(self, list_id, media_type, tmdb_id, notes=None, position=None):
        return self.call("add_to_list", {
            "list_id": list_id, "type": media_type, "id": tmdb_id,
            "notes": notes, "position": position,
        })

    def remove_from_list(self, list_id, media_type, tmdb_id):
        return self.call("remove_from_list", {
            "list_id": list_id, "type": media_type, "id": tmdb_id,
        })

    def rate(self, media_type, rating, tmdb_id=None, tv_show_id=None,
             season=None, episode=None, review=None):
        return self.call("rate", {
            "type": media_type, "id": tmdb_id, "rating": rating,
            "tvShowId": tv_show_id, "seasonNumber": season,
            "episodeNumber": episode, "review": review,
        })

    def delete_rating(self, media_type, tmdb_id=None, tv_show_id=None, season=None):
        return self.call("delete_rating", {
            "type": media_type, "id": tmdb_id,
            "tvShowId": tv_show_id, "seasonNumber": season,
        })

    def scrobble(self, media_type, progress, duration, tmdb_id=None,
                 tv_show_id=None, season=None, episode=None):
        return self.call("scrobble", {
            "type": media_type, "id": tmdb_id, "progress": progress, "duration": duration,
            "tvShowId": tv_show_id, "seasonNumber": season, "episodeNumber": episode,
        })

    def delete_scrobble(self, media_type, tmdb_id):
        return self.call("delete_scrobble", {"type": media_type, "id": tmdb_id})
