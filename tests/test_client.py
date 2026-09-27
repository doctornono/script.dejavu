# -*- coding: utf-8 -*-
"""Regression tests for Kodi RPC client parameter forwarding."""

import sys
import types
import unittest


def load_client():
    xbmc = types.ModuleType("xbmc")
    xbmc.LOGDEBUG = 0
    xbmc.log = lambda *args, **kwargs: None
    xbmc.Monitor = object

    xbmcaddon = types.ModuleType("xbmcaddon")
    xbmcaddon.Addon = lambda *args, **kwargs: None

    xbmcgui = types.ModuleType("xbmcgui")
    xbmcgui.Window = lambda *args, **kwargs: None

    sys.modules["xbmc"] = xbmc
    sys.modules["xbmcaddon"] = xbmcaddon
    sys.modules["xbmcgui"] = xbmcgui

    sys.path.insert(0, ".")
    from resources.lib.client import DejaVuClient
    return DejaVuClient


class ClientRpcParameterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.DejaVuClient = load_client()

    def make_client(self):
        client = object.__new__(self.DejaVuClient)
        calls = []
        client.call = lambda action, params=None: calls.append((action, params)) or {"success": True}
        client._calls = calls
        return client

    def test_call_does_not_mutate_caller_parameters(self):
        client = self.make_client()
        import resources.lib.client as client_module

        sent = []
        class FakeWindow:
            def clearProperty(self, name):
                pass
            def getProperty(self, name):
                return ""
        class FakeMonitor:
            def waitForAbort(self, seconds):
                return True

        client.window = FakeWindow()
        client._monitor = FakeMonitor()
        client.timeout = 1
        client_module.xbmc.executebuiltin = lambda value: sent.append(value)

        params = {"type": "movie", "id": 603}
        client.call("get_media_status", params)

        self.assertEqual(params, {"type": "movie", "id": 603})
        self.assertEqual(len(sent), 1)
        self.assertIn('"result_property"', sent[0])

    def test_delete_rating_forwards_episode_identity(self):
        client = self.make_client()

        result = client.delete_rating(
            "episode",
            tv_show_id=1396,
            season=1,
            episode=2,
        )

        self.assertEqual(result, {"success": True})
        self.assertEqual(
            client._calls,
            [(
                "delete_rating",
                {
                    "type": "episode",
                    "id": None,
                    "tvShowId": 1396,
                    "seasonNumber": 1,
                    "episodeNumber": 2,
                },
            )],
        )

    def test_delete_history_forwards_episode_identity(self):
        client = self.make_client()
        result = client.delete_history("episode", tv_show_id=1396, season=1, episode=2)
        self.assertEqual(result, {"success": True})
        self.assertEqual(client._calls, [("delete_history", {
            "type": "episode", "id": None, "tvShowId": 1396,
            "seasonNumber": 1, "episodeNumber": 2,
        })])

    def test_resolve_media_forwards_episode_identity(self):
        client = self.make_client()
        result = client.resolve_media(media_type="episode", tv_show_id=1396, season=1, episode=2)
        self.assertEqual(result, {"success": True})
        self.assertEqual(client._calls, [("resolve_media", {
            "imdb_id": None, "tmdb_id": None, "type": "episode",
            "title": None, "year": None, "tvShowId": 1396,
            "seasonNumber": 1, "episodeNumber": 2,
        })])

    def test_delete_scrobble_forwards_episode_identity(self):
        client = self.make_client()

        result = client.delete_scrobble(
            "episode",
            tv_show_id=1396,
            season=1,
            episode=2,
        )

        self.assertEqual(result, {"success": True})
        self.assertEqual(
            client._calls,
            [(
                "delete_scrobble",
                {
                    "type": "episode",
                    "id": None,
                    "tvShowId": 1396,
                    "seasonNumber": 1,
                    "episodeNumber": 2,
                },
            )],
        )


if __name__ == "__main__":
    unittest.main()
