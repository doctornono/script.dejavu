# -*- coding: utf-8 -*-
"""Regression tests for the v1 custom-list API contract used by Kodi."""

import sys
import types
import unittest


class FakeAddon:
    def getSetting(self, key):
        return ""

    def getSettingBool(self, key):
        return False


class FakeHttpResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload if payload is not None else {}
        self.status_code = status_code
        self.content = b"{}"

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
    """Import api_client with the small Kodi surface required by its helpers."""
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

    xbmcvfs = types.ModuleType("xbmcvfs")

    xbmcgui = types.ModuleType("xbmcgui")

    sys.modules["xbmc"] = xbmc
    sys.modules["xbmcaddon"] = xbmcaddon
    sys.modules["xbmcvfs"] = xbmcvfs
    sys.modules["xbmcgui"] = xbmcgui

    sys.path.insert(0, ".")
    from resources.lib.api_client import DejaVuAPI
    return DejaVuAPI


class ListApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.DejaVuAPI = load_api_client()

    def make_api(self, responses):
        api = self.DejaVuAPI(api_url="https://dejavu.plus/api/v1")
        api._current_token = lambda: "test-token"
        api._http = FakeSession(responses)
        return api

    def test_get_lists_uses_v1_pagination_contract(self):
        api = self.make_api([FakeHttpResponse({"success": True, "data": {"items": []}})])

        result = api.get_lists(page=2, page_size=50, minimal=True)

        self.assertEqual(result["success"], True)
        method, url, kwargs = api._http.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "https://dejavu.plus/api/v1/lists")
        self.assertEqual(
            kwargs["params"],
            {"page": 2, "pageSize": 50, "minimal": "true"},
        )
        self.assertEqual(kwargs["headers"]["x-api-key"], "test-token")

    def test_create_list_posts_name_description_and_visibility(self):
        api = self.make_api([FakeHttpResponse({"success": True, "data": {"id": 42}})])

        result = api.create_list(
            "Science-fiction",
            description="Films SF à revoir",
            visibility="PUBLIC",
        )

        self.assertEqual(result["data"]["id"], 42)
        method, url, kwargs = api._http.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://dejavu.plus/api/v1/lists")
        self.assertEqual(
            kwargs["json"],
            {
                "name": "Science-fiction",
                "description": "Films SF à revoir",
                "visibility": "PUBLIC",
            },
        )

    def test_add_to_list_posts_media_identifier_and_optional_fields(self):
        api = self.make_api([FakeHttpResponse({"success": True})])

        api.add_to_list(
            42,
            "movie",
            603,
            notes="À revoir",
            position=3,
        )

        method, url, kwargs = api._http.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://dejavu.plus/api/v1/lists/42/items")
        self.assertEqual(
            kwargs["json"],
            {
                "type": "movie",
                "id": 603,
                "notes": "À revoir",
                "position": 3,
            },
        )

    def test_remove_from_list_uses_delete_query_parameters(self):
        api = self.make_api([FakeHttpResponse({"success": True})])

        api.remove_from_list(42, "movie", 603)

        method, url, kwargs = api._http.calls[0]
        self.assertEqual(method, "DELETE")
        self.assertEqual(url, "https://dejavu.plus/api/v1/lists/42/items")
        self.assertEqual(kwargs["params"], {"type": "movie", "id": 603})

    def test_list_lifecycle_uses_create_add_remove_routes(self):
        api = self.make_api(
            [
                FakeHttpResponse({"success": True, "data": {"id": 42}}),
                FakeHttpResponse({"success": True}),
                FakeHttpResponse({"success": True}),
            ]
        )

        created = api.create_list("Ma liste")
        api.add_to_list(created["data"]["id"], "movie", 603)
        api.remove_from_list(created["data"]["id"], "movie", 603)

        self.assertEqual(
            [(call[0], call[1]) for call in api._http.calls],
            [
                ("POST", "https://dejavu.plus/api/v1/lists"),
                ("POST", "https://dejavu.plus/api/v1/lists/42/items"),
                ("DELETE", "https://dejavu.plus/api/v1/lists/42/items"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
