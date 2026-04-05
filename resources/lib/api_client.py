# -*- coding: utf-8 -*-
"""
dejaVu API Client
Wraps all calls to https://dejavu.plus/api/v1/
Authentication: x-api-key header with secret key (sk_...)
"""

import xbmc
import xbmcaddon
import requests

ADDON = xbmcaddon.Addon()
ADDON_ID = "script.dejavu"


def _log(msg, level=xbmc.LOGDEBUG):
    xbmc.log(f"[dejaVu] {msg}", level)


class DejaVuAPI:
    def __init__(self, api_url=None, token=None):
        self.api_url = (
            api_url
            or ADDON.getSetting("api_url")
            or "https://dejavu.plus/api/v1"
        ).rstrip("/")
        self.token = token or ADDON.getSetting("access_token") or ""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self):
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            h["x-api-key"] = self.token
        return h

    def _get(self, path, params=None):
        url = f"{self.api_url}/{path.lstrip('/')}"
        try:
            r = requests.get(url, headers=self._headers(), params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            _log(f"GET {path} HTTP error: {e.response.status_code} – {e.response.text}", xbmc.LOGERROR)
        except Exception as e:
            _log(f"GET {path} error: {e}", xbmc.LOGERROR)
        return None

    def _post(self, path, payload):
        url = f"{self.api_url}/{path.lstrip('/')}"
        try:
            r = requests.post(url, headers=self._headers(), json=payload, timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            _log(f"POST {path} HTTP error: {e.response.status_code} – {e.response.text}", xbmc.LOGERROR)
        except Exception as e:
            _log(f"POST {path} error: {e}", xbmc.LOGERROR)
        return None

    def _delete(self, path, payload=None):
        """DELETE with a JSON body (used by scrobble)."""
        url = f"{self.api_url}/{path.lstrip('/')}"
        try:
            r = requests.delete(url, headers=self._headers(), json=payload, timeout=10)
            r.raise_for_status()
            return r.json() if r.content else {}
        except requests.HTTPError as e:
            _log(f"DELETE {path} HTTP error: {e.response.status_code} – {e.response.text}", xbmc.LOGERROR)
        except Exception as e:
            _log(f"DELETE {path} error: {e}", xbmc.LOGERROR)
        return None

    def _delete_qs(self, path, params=None):
        """DELETE with query string params (used by watchlist, collection, favorites, ratings, history)."""
        url = f"{self.api_url}/{path.lstrip('/')}"
        try:
            r = requests.delete(url, headers=self._headers(), params=params, timeout=10)
            r.raise_for_status()
            return r.json() if r.content else {}
        except requests.HTTPError as e:
            _log(f"DELETE {path} HTTP error: {e.response.status_code} – {e.response.text}", xbmc.LOGERROR)
        except Exception as e:
            _log(f"DELETE {path} error: {e}", xbmc.LOGERROR)
        return None

    # ------------------------------------------------------------------
    # Auth – Device Code Flow
    # ------------------------------------------------------------------

    def get_device_code(self):
        """Step 1: request a device code + user code from the server."""
        return self._post("/auth/device/code", {"client_id": "dejavu-kodi"})

    def poll_token(self, device_code):
        """Step 2: poll until the user has authorized the device."""
        payload = {
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": "dejavu-kodi",
        }
        url = f"{self.api_url}/auth/device/token"
        try:
            r = requests.post(url, headers=self._headers(), json=payload, timeout=10)
            _log(f"poll_token status={r.status_code}", xbmc.LOGDEBUG)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (400, 428):
                # authorization_pending or slow_down – normal, keep polling
                return None
            # Any other error: log and bail
            _log(f"poll_token unexpected {r.status_code}: {r.text}", xbmc.LOGERROR)
        except Exception as e:
            _log(f"poll_token error: {e}", xbmc.LOGERROR)
        return None

    def get_me(self):
        """Returns the authenticated user's profile."""
        return self._get("/me")

    # ------------------------------------------------------------------
    # Scrobble
    # ------------------------------------------------------------------

    def scrobble(self, media_type, progress, duration, tmdb_id=None, item_id=None,
                 tv_show_id=None, season=None, episode=None):
        """
        Update playback progress.
        If progress/duration >= 0.9 the API automatically marks the item as watched.

        media_type : "movie" | "episode"
        tmdb_id    : TMDB ID of the movie OR episode
        progress   : seconds played (int)
        duration   : total duration in seconds (int)
        """
        payload = {
            "type": media_type,
            "progress": int(progress),
            "duration": int(duration),
        }
        if tmdb_id:
            payload["id"] = int(tmdb_id)
        elif item_id:
            payload["id"] = int(item_id)
            
        if tv_show_id:
            payload["tvShowId"] = int(tv_show_id)
        if season is not None:
            payload["seasonNumber"] = int(season)
        if episode is not None:
            payload["episodeNumber"] = int(episode)

        _log(f"scrobble payload: {payload}", xbmc.LOGDEBUG)
        return self._post("/scrobble", payload)

    def delete_scrobble_session(self, session_id):
        """Delete an active scrobble session by its ID."""
        return self._delete(f"/scrobble/{session_id}")

    # ------------------------------------------------------------------
    # Ratings
    # ------------------------------------------------------------------

    def get_ratings(self, media_type=None, page=1, page_size=20, minimal=False):
        """
        Retrieve the user's ratings.

        media_type : "movie" | "tv" | "season" | "episode" | "all" (default)
        page       : page number (default 1)
        page_size  : items per page, max 100 (default 20)
        minimal    : if True, returns only id/rating/createdAt (default False)
        """
        params = {
            "page": page,
            "pageSize": page_size,
            "minimal": str(minimal).lower(),
        }
        if media_type:
            params["type"] = media_type
        return self._get("/ratings", params)

    def rate(self, media_type, rating, tmdb_id=None, item_id=None,
             tv_show_id=None, season=None, episode=None, review=None):
        """
        Upsert a rating (1-10).

        media_type  : "movie" | "tv" | "season" | "episode"
        rating      : integer 1-10
        tmdb_id     : TMDB ID of the item (movie / tv show / episode)
        tv_show_id  : required for season / episode types
        season      : season number, required for "season" type
        episode     : episode number, used with tv_show_id + season to resolve episode ID
        review      : optional text review
        """
        payload = {
            "type": media_type,
            "rating": int(rating),
        }
        if tmdb_id:
            payload["id"] = int(tmdb_id)
        elif item_id:
            payload["id"] = int(item_id)
        if tv_show_id:
            payload["tvShowId"] = int(tv_show_id)
        if season is not None:
            payload["seasonNumber"] = int(season)
        if episode is not None:
            payload["episodeNumber"] = int(episode)
        if review:
            payload["review"] = str(review)

        _log(f"rate payload: {payload}", xbmc.LOGDEBUG)
        return self._post("/ratings", payload)

    def delete_rating(self, media_type, tmdb_id=None, tv_show_id=None, season=None):
        """
        Delete a rating.

        media_type : "movie" | "tv" | "season" | "episode"
        tmdb_id    : TMDB ID (movie, tv show or episode)
        tv_show_id : required for "season" type
        season     : season number, required for "season" type
        """
        params = {"type": media_type}
        if tmdb_id:
            params["id"] = int(tmdb_id)
        if tv_show_id:
            params["tvShowId"] = int(tv_show_id)
        if season is not None:
            params["seasonNumber"] = int(season)
        return self._delete_qs("/ratings", params)

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_history(self, media_type=None, page=1, page_size=20,
                    sort="watchedAt:desc", minimal=False):
        """
        Retrieve the user's watch history.

        media_type : "movie" | "tv" | "episode" | "all" (default)
        page       : page number (default 1)
        page_size  : items per page, max 100 (default 20)
        sort       : "watchedAt:desc" (default) | "watchedAt:asc"
        minimal    : if True, returns only id/watchedAt/rewatchCount (default False)
        """
        params = {
            "page": page,
            "pageSize": page_size,
            "sort": sort,
            "minimal": str(minimal).lower(),
        }
        if media_type:
            params["type"] = media_type
        return self._get("/history", params)

    def add_to_history(self, media_type, tmdb_id=None, count=1, watched_at=None,
                       tv_show_id=None, season=None, episode=None):
        """
        Add a movie or episode to the watch history.

        media_type  : "movie" | "tv" | "episode"
        tmdb_id     : TMDB ID of the movie or episode
        count       : number of additional views to record (default 1)
        watched_at  : ISO 8601 datetime string (default: now)
        tv_show_id  : TV show TMDB ID (alternative to tmdb_id for episodes)
        season      : season number (used with tv_show_id + episode)
        episode     : episode number (used with tv_show_id + season)
        """
        payload = {"type": media_type, "count": int(count)}
        if tmdb_id:
            payload["id"] = int(tmdb_id)
        if watched_at:
            payload["watchedAt"] = watched_at
        if tv_show_id:
            payload["tvShowId"] = int(tv_show_id)
        if season is not None:
            payload["seasonNumber"] = int(season)
        if episode is not None:
            payload["episodeNumber"] = int(episode)
        return self._post("/history", payload)

    def delete_history(self, media_type, tmdb_id):
        """
        Delete a movie or episode from the watch history.

        media_type : "movie" | "tv" | "episode"
        tmdb_id    : TMDB ID of the movie or episode
        """
        return self._delete_qs("/history", {"type": media_type, "id": int(tmdb_id)})

    # ------------------------------------------------------------------
    # Watchlist
    # ------------------------------------------------------------------

    def get_watchlist(self, media_type=None, page=1, page_size=20,
                      sort="addedAt:desc", minimal=False):
        """
        Retrieve the user's watchlist.

        media_type : "movie" | "tv" | "all" (default)
        page       : page number (default 1)
        page_size  : items per page, max 100 (default 20)
        sort       : "addedAt:desc" (default) | "addedAt:asc" | "priority:desc" | "priority:asc"
        minimal    : if True, returns only id/addedAt/priority (default False)
        """
        params = {
            "page": page,
            "pageSize": page_size,
            "sort": sort,
            "minimal": str(minimal).lower(),
        }
        if media_type:
            params["type"] = media_type
        return self._get("/watchlist", params)

    def add_to_watchlist(self, media_type, tmdb_id, priority=None, notes=None):
        """
        Add an item to the watchlist.

        media_type : "movie" | "tv"
        tmdb_id    : TMDB ID
        priority   : optional integer priority
        notes      : optional text note
        """
        payload = {"type": media_type, "id": int(tmdb_id)}
        if priority is not None:
            payload["priority"] = int(priority)
        if notes:
            payload["notes"] = str(notes)
        return self._post("/watchlist", payload)

    def remove_from_watchlist(self, media_type, tmdb_id):
        """
        Remove an item from the watchlist.

        media_type : "movie" | "tv"
        tmdb_id    : TMDB ID
        """
        return self._delete_qs("/watchlist", {"type": media_type, "id": int(tmdb_id)})

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    def get_collection(self, media_type=None, page=1, page_size=20,
                       sort="addedAt:desc", fmt=None, minimal=False):
        """
        Retrieve the user's collection.

        media_type : "movie" | "tv" | "all" (default)
        page       : page number (default 1)
        page_size  : items per page, max 100 (default 20)
        sort       : "addedAt:desc" (default) | "addedAt:asc"
        fmt        : filter by format string (e.g. "bluray", "dvd")
        minimal    : if True, returns only id/addedAt/format (default False)
        """
        params = {
            "page": page,
            "pageSize": page_size,
            "sort": sort,
            "minimal": str(minimal).lower(),
        }
        if media_type:
            params["type"] = media_type
        if fmt:
            params["format"] = fmt
        return self._get("/collection", params)

    def add_to_collection(self, media_type, tmdb_id, fmt=None, notes=None):
        """
        Add an item to the collection.

        media_type : "movie" | "tv"
        tmdb_id    : TMDB ID
        fmt        : optional format string (e.g. "bluray", "dvd")
        notes      : optional text note
        """
        payload = {"type": media_type, "id": int(tmdb_id)}
        if fmt:
            payload["format"] = fmt
        if notes:
            payload["notes"] = str(notes)
        return self._post("/collection", payload)

    def remove_from_collection(self, media_type, tmdb_id):
        """
        Remove an item from the collection.

        media_type : "movie" | "tv"
        tmdb_id    : TMDB ID
        """
        return self._delete_qs("/collection", {"type": media_type, "id": int(tmdb_id)})

    # ------------------------------------------------------------------
    # Favorites
    # ------------------------------------------------------------------

    def get_favorites(self, media_type=None, page=1, page_size=20, minimal=False):
        """
        Retrieve the user's favorites.

        media_type : "movie" | "tv" | "all" (default)
        page       : page number (default 1)
        page_size  : items per page, max 100 (default 20)
        minimal    : if True, returns only id/addedAt (default False)
        """
        params = {
            "page": page,
            "pageSize": page_size,
            "minimal": str(minimal).lower(),
        }
        if media_type:
            params["type"] = media_type
        return self._get("/favorites", params)

    def add_to_favorites(self, media_type, tmdb_id):
        """
        Add an item to favorites.

        media_type : "movie" | "tv"
        tmdb_id    : TMDB ID
        """
        return self._post("/favorites", {"type": media_type, "id": int(tmdb_id)})

    def remove_from_favorites(self, media_type, tmdb_id):
        """
        Remove an item from favorites.

        media_type : "movie" | "tv"
        tmdb_id    : TMDB ID
        """
        return self._delete_qs("/favorites", {"type": media_type, "id": int(tmdb_id)})

    # ------------------------------------------------------------------
    # Lists
    # ------------------------------------------------------------------

    def get_lists(self, page=1, page_size=20, minimal=False):
        """
        Retrieve the user's custom lists.

        page      : page number (default 1)
        page_size : items per page, max 100 (default 20)
        minimal   : if True, returns only id/name/itemsCount/updatedAt (default False)
        """
        params = {
            "page": page,
            "pageSize": page_size,
            "minimal": str(minimal).lower(),
        }
        return self._get("/lists", params)

    def create_list(self, name, description=None, visibility="PRIVATE"):
        """
        Create a new custom list.

        name        : list name (required)
        description : optional description
        visibility  : "PRIVATE" (default) | "PUBLIC"
        """
        payload = {"name": name, "visibility": visibility}
        if description:
            payload["description"] = description
        return self._post("/lists", payload)

    # ------------------------------------------------------------------
    # Up Next
    # ------------------------------------------------------------------

    def get_up_next(self, page=1, page_size=20, minimal=False):
        """
        Retrieve the user's "Up Next" episodes (in-progress TV shows).

        page      : page number (default 1)
        page_size : items per page, max 100 (default 20)
        minimal   : if True, returns a lightweight payload (default False)

        Note: the API defaults minimal to True server-side when not provided.
              Passing minimal=False explicitly overrides this behaviour.
        """
        params = {
            "page": page,
            "pageSize": page_size,
            "minimal": str(minimal).lower(),
        }
        return self._get("/upnext", params)

