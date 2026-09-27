# -*- coding: utf-8 -*-
"""HTTP contract tests for the v1 endpoints used by script.dejavu."""

import sys
import types
import unittest


class FakeAddon:
    def getSetting(self, key):
        return ""

    def getSettingBool(self, key):
        return False


class FakeHttpResponse:
    def __init__(self, payload=None, status_code=200, content=b"{}"):
        self._payload = payload if payload is not None else {}
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(response=self)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def _next(self):
        if not self.responses:
            raise AssertionError("No fake HTTP response left")
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self._next()

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self._next()

    def delete(self, url, **kwargs):
        self.calls.append(("DELETE", url, kwargs))
        return self._next()


def load_api_client():
    xbmc = types.ModuleType("xbmc")
    xbmc.LOGDEBUG = 0
    xbmc.LOGINFO = 1
    xbmc.LOGWARNING = 2
    xbmc.LOGERROR = 3
    xbmc.ISO_639_1 = 0
    xbmc.log = lambda *args, **kwargs: None
    xbmc.getLanguage = lambda *args, **kwargs: "French"

    xbmcaddon = types.ModuleType("xbmcaddon")
    xbmcaddon.Addon = FakeAddon

    # resources.lib.__init__ imports client.py, which imports xbmcgui.
    xbmcgui = types.ModuleType("xbmcgui")
    xbmcgui.Window = lambda *args, **kwargs: None

    xbmcvfs = types.ModuleType("xbmcvfs")

    sys.modules["xbmc"] = xbmc
    sys.modules["xbmcaddon"] = xbmcaddon
    sys.modules["xbmcgui"] = xbmcgui
    sys.modules["xbmcvfs"] = xbmcvfs

    sys.path.insert(0, ".")
    from resources.lib.api_client import DejaVuAPI
    return DejaVuAPI


class ApiClientContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.DejaVuAPI = load_api_client()

    def make_api(self, responses):
        api = self.DejaVuAPI(api_url="https://dejavu.plus/api/v1")
        api._current_token = lambda: "test-token"
        api._http = FakeSession(responses)
        return api

    def assert_call(self, api, method, path, params=None, payload=None):
        actual_method, url, kwargs = api._http.calls[0]
        self.assertEqual(actual_method, method)
        self.assertEqual(url, "https://dejavu.plus/api/v1" + path)
        if params is not None:
            self.assertEqual(kwargs["params"], params)
        if payload is not None:
            self.assertEqual(kwargs["json"], payload)
        self.assertEqual(kwargs["headers"]["x-api-key"], "test-token")

    def test_get_me(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.get_me()
        self.assert_call(api, "GET", "/me")

    def test_scrobble_posts_movie_payload(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.scrobble("movie", 120, 3600, tmdb_id=603)
        self.assert_call(
            api, "POST", "/scrobble",
            payload={"type": "movie", "progress": 120, "duration": 3600, "id": 603},
        )

    def test_get_scrobbles_uses_filters(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.get_scrobbles("episode", page=2, page_size=50, minimal=True)
        self.assert_call(
            api, "GET", "/scrobble",
            params={"page": 2, "pageSize": 50, "minimal": "true", "type": "episode"},
        )

    def test_delete_scrobble_uses_episode_identity(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.delete_scrobble("episode", tv_show_id=1396, season=1, episode=2)
        self.assert_call(
            api, "DELETE", "/scrobble",
            params={"type": "episode", "tvShowId": 1396, "seasonNumber": 1, "episodeNumber": 2},
        )

    def test_get_ratings_uses_filters(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.get_ratings("tv", page=3, page_size=25, minimal=True)
        self.assert_call(
            api, "GET", "/ratings",
            params={"page": 3, "pageSize": 25, "minimal": "true", "type": "tv"},
        )

    def test_rate_posts_episode_identity_and_review(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.rate(
            "episode", 9, tv_show_id=1396, season=1, episode=2, review="Excellent",
        )
        self.assert_call(
            api, "POST", "/ratings",
            payload={
                "type": "episode",
                "rating": 9,
                "tvShowId": 1396,
                "seasonNumber": 1,
                "episodeNumber": 2,
                "review": "Excellent",
            },
        )

    def test_delete_rating_uses_query_parameters(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.delete_rating("movie", tmdb_id=603)
        self.assert_call(
            api, "DELETE", "/ratings",
            params={"type": "movie", "id": 603},
        )

    def test_get_history_uses_sort_and_minimal(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.get_history(
            "episode", page=2, page_size=40, sort="watchedAt:asc", minimal=True,
        )
        self.assert_call(
            api, "GET", "/history",
            params={
                "page": 2, "pageSize": 40, "sort": "watchedAt:asc",
                "minimal": "true", "type": "episode",
            },
        )

    def test_add_to_history_posts_episode_identity(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.add_to_history(
            "episode", count=2, watched_at="2026-09-27T10:00:00Z",
            tv_show_id=1396, season=1, episode=2,
        )
        self.assert_call(
            api, "POST", "/history",
            payload={
                "type": "episode", "count": 2,
                "watchedAt": "2026-09-27T10:00:00Z",
                "tvShowId": 1396, "seasonNumber": 1, "episodeNumber": 2,
            },
        )

    def test_delete_history_uses_episode_identity(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.delete_history("episode", tv_show_id=1396, season=1, episode=2)
        self.assert_call(
            api, "DELETE", "/history",
            params={
                "type": "episode", "tvShowId": 1396,
                "seasonNumber": 1, "episodeNumber": 2,
            },
        )

    def test_get_watchlist_uses_sort(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.get_watchlist("movie", page=2, page_size=30, sort="priority:asc", minimal=True)
        self.assert_call(
            api, "GET", "/watchlist",
            params={
                "page": 2, "pageSize": 30, "sort": "priority:asc",
                "minimal": "true", "type": "movie",
            },
        )

    def test_watchlist_write_routes(self):
        api = self.make_api([
            FakeHttpResponse({"success": True}),
            FakeHttpResponse({"success": True}),
        ])
        api.add_to_watchlist("movie", 603, priority=4, notes="À revoir")
        api.remove_from_watchlist("movie", 603)
        self.assertEqual(
            [(c[0], c[1]) for c in api._http.calls],
            [
                ("POST", "https://dejavu.plus/api/v1/watchlist"),
                ("DELETE", "https://dejavu.plus/api/v1/watchlist"),
            ],
        )
        self.assertEqual(
            api._http.calls[0][2]["json"],
            {"type": "movie", "id": 603, "priority": 4, "notes": "À revoir"},
        )
        self.assertEqual(
            api._http.calls[1][2]["params"], {"type": "movie", "id": 603},
        )

    def test_collection_write_routes(self):
        api = self.make_api([
            FakeHttpResponse({"success": True}),
            FakeHttpResponse({"success": True}),
        ])
        api.add_to_collection("movie", 603, fmt="bluray", notes="Coffret")
        api.remove_from_collection("movie", 603)
        self.assertEqual(
            api._http.calls[0][1], "https://dejavu.plus/api/v1/collection",
        )
        self.assertEqual(
            api._http.calls[0][2]["json"],
            {"type": "movie", "id": 603, "format": "bluray", "notes": "Coffret"},
        )
        self.assertEqual(
            api._http.calls[1][2]["params"], {"type": "movie", "id": 603},
        )

    def test_get_favorites_and_add(self):
        api = self.make_api([
            FakeHttpResponse({"success": True}),
            FakeHttpResponse({"success": True}),
        ])
        api.get_favorites("tv", page=2, page_size=10, minimal=True)
        api.add_to_favorites("tv", 1396)
        self.assertEqual(
            api._http.calls[0][2]["params"],
            {"page": 2, "pageSize": 10, "minimal": "true", "type": "tv"},
        )
        self.assertEqual(
            api._http.calls[1][2]["json"], {"type": "tv", "id": 1396},
        )

    def test_remove_favorite_uses_delete_query_parameters(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.remove_from_favorites("movie", 603)
        self.assert_call(
            api, "DELETE", "/favorites",
            params={"type": "movie", "id": 603},
        )

    def test_get_list_items(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.get_list_items(42, page=2, page_size=50, minimal=True)
        self.assert_call(
            api, "GET", "/lists/42/items",
            params={"page": 2, "pageSize": 50, "minimal": "true"},
        )

    def test_get_channels_normalizes_filters_and_allows_404(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.get_channels(page=2, page_size=10, channel_type=" universe ", scope=" MINE ")
        self.assert_call(
            api, "GET", "/channels",
            params={"page": 2, "pageSize": 10, "type": "UNIVERSE", "scope": "mine"},
        )

    def test_get_channel_missing_id_does_not_call_http(self):
        api = self.make_api([])
        result = api.get_channel("")
        self.assertEqual(result, {"success": False, "error": "missing_channel_id"})
        self.assertEqual(api._http.calls, [])

    def test_get_up_next(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.get_up_next(page=2, page_size=15, minimal=True)
        self.assert_call(
            api, "GET", "/upnext",
            params={"page": 2, "pageSize": 15, "minimal": "true"},
        )

    def test_dashboard_routes(self):
        api = self.make_api([
            FakeHttpResponse({"success": True}),
            FakeHttpResponse({"success": True}),
        ])
        api.get_dashboard()
        api.get_dashboard_widget("list", list_id=42, page=2, page_size=10, minimal=True)
        self.assertEqual(
            api._http.calls[0][1], "https://dejavu.plus/api/v1/dashboard",
        )
        self.assertEqual(
            api._http.calls[1][2]["params"],
            {"type": "list", "page": 2, "pageSize": 10, "minimal": "true", "listId": 42},
        )

    def test_media_status_filters_invalid_entries_and_caps_at_50(self):
        items = [{"type": "invalid", "id": 1}, {"type": "movie", "id": 603}]
        items.extend({"type": "movie", "id": index} for index in range(1, 60))
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.get_media_status(items)
        payload = api._http.calls[0][2]["json"]["items"]
        self.assertEqual(len(payload), 50)
        self.assertEqual(payload[0], {"type": "movie", "id": 603})

    def test_resolve_media_posts_supported_fields(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        api.resolve_media(
            imdb_id="tt0133093", media_type="movie", title="The Matrix",
            year=1999,
        )
        self.assert_call(
            api, "POST", "/media/resolve",
            payload={
                "imdbId": "tt0133093", "type": "movie",
                "title": "The Matrix", "year": 1999,
            },
        )

    def test_show_progress_filters_and_caps_ids(self):
        api = self.make_api([FakeHttpResponse({"success": True, "data": {}})])
        api.get_show_progress([1396, "101", "bad"] + list(range(200, 230)))
        payload = api._http.calls[0][2]["json"]
        self.assertEqual(payload["ids"], [1396, 101] + list(range(200, 218)))

    def test_resolve_media_batch_posts_items(self):
        api = self.make_api([FakeHttpResponse({"success": True, "data": {}})])
        api.resolve_media_batch([
            {"imdbId": "tt0133093", "type": "movie", "title": "The Matrix", "year": 1999},
            {"tmdbId": 1396, "type": "tv"},
        ])
        self.assert_call(
            api, "POST", "/media/resolve/batch",
            payload={
                "items": [
                    {"imdbId": "tt0133093", "type": "movie", "title": "The Matrix", "year": 1999},
                    {"tmdbId": 1396, "type": "tv"},
                ],
            },
        )

    def test_import_kodi_library_uses_long_timeout(self):
        api = self.make_api([FakeHttpResponse({"success": True})])
        payload = {
            "source": "kodi", "importSessionId": "abc",
            "chunk": 1, "totalChunks": 2, "options": {},
            "movies": [], "tvShows": [], "episodes": [],
            "playlists": [], "favorites": [],
        }
        api.import_kodi_library(payload)
        method, url, kwargs = api._http.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://dejavu.plus/api/v1/kodi/import")
        self.assertEqual(kwargs["json"], payload)
        self.assertEqual(kwargs["timeout"], 120)

    def test_legacy_last_activities_is_disabled(self):
        api = self.make_api([])
        self.assertEqual(
            api.get_last_activities(),
            {"success": False, "error": "not_found"},
        )
        self.assertEqual(api._http.calls, [])


if __name__ == "__main__":
    unittest.main()
