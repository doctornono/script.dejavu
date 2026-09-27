# -*- coding: utf-8 -*-
"""Regression tests for the Kodi playback/scrobbling lifecycle.

These tests deliberately run without Kodi installed.  The Kodi modules and
dejaVu API dependencies are replaced by small fakes so the real
DejaVuPlayer lifecycle methods are exercised.
"""

import importlib
import sys
import types
import unittest
from unittest.mock import patch


class FakeAddon:
    def __init__(self):
        self.settings = {
            "enable_scrobble": True,
            "enable_resume": False,
            "show_notifications": False,
            "watched_percent": 90,
            "scrobble_interval": 30,
            "debug": False,
        }

    def getSettingBool(self, key):
        return bool(self.settings.get(key, False))

    def getSettingInt(self, key):
        return int(self.settings.get(key, 0))

    def getSetting(self, key):
        return str(self.settings.get(key, ""))

    def getLocalizedString(self, key):
        return str(key)


class FakePlayer:
    def __init__(self):
        self._time = 0
        self._duration = 3600

    def getTime(self):
        return self._time

    def getTotalTime(self):
        return self._duration

    def isPlayingVideo(self):
        return True


def load_scrobbler():
    """Import scrobbler with Kodi/dejaVu dependencies replaced by fakes."""
    xbmc = types.ModuleType("xbmc")
    xbmc.Player = FakePlayer
    xbmc.LOGDEBUG = 0
    xbmc.LOGINFO = 1
    xbmc.LOGWARNING = 2
    xbmc.LOGERROR = 3
    xbmc.log = lambda *args, **kwargs: None
    xbmc.sleep = lambda *args, **kwargs: None
    xbmc.getInfoLabel = lambda *args, **kwargs: ""
    xbmc.executeJSONRPC = lambda *args, **kwargs: "{}"

    xbmcaddon = types.ModuleType("xbmcaddon")
    xbmcaddon.Addon = FakeAddon

    class FakeDialog:
        def notification(self, *args, **kwargs):
            return None

        def yesno(self, *args, **kwargs):
            return False

        def select(self, *args, **kwargs):
            return -1

    xbmcgui = types.ModuleType("xbmcgui")
    xbmcgui.Dialog = FakeDialog
    xbmcgui.NOTIFICATION_INFO = 0
    xbmcgui.NOTIFICATION_ERROR = 1

    api_client = types.ModuleType("resources.lib.api_client")

    class FakeAPI:
        def __init__(self):
            self.calls = []

        def scrobble(self, **kwargs):
            self.calls.append(("scrobble", kwargs))
            return {"success": True}

        def delete_scrobble(self, *args, **kwargs):
            self.calls.append(("delete_scrobble", args, kwargs))
            return {"success": True}

    api_client.DejaVuAPI = FakeAPI

    auth_handler = types.ModuleType("resources.lib.auth_handler")
    auth_handler.is_logged_in = lambda: True

    util = types.ModuleType("resources.lib.util")
    util.notify_changed = lambda *args, **kwargs: None
    util.unwrap_data = lambda value: value
    util.sync_kodi_library = lambda *args, **kwargs: None

    modules = {
        "xbmc": xbmc,
        "xbmcaddon": xbmcaddon,
        "xbmcgui": xbmcgui,
        "resources.lib.api_client": api_client,
        "resources.lib.auth_handler": auth_handler,
        "resources.lib.util": util,
    }

    with patch.dict(sys.modules, modules):
        return importlib.import_module("resources.lib.scrobbler")


class ScrobbleLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scrobbler = load_scrobbler()

    def setUp(self):
        self.player = self.scrobbler.DejaVuPlayer()
        self.player._meta = {
            "type": "movie",
            "tmdb_id": "603",
            "title": "The Matrix",
        }
        self.api = self.player.api
        self.clock = 1000.0
        self.player._time = 120

    def test_start_pause_resume_stop_keeps_continue_watching(self):
        """A real playback session must send start/pause/resume/stop."""
        lifecycle = []
        original_scrobble = self.player._scrobble

        def record_scrobble(action="update"):
            lifecycle.append(action)
            return original_scrobble(action)

        with patch.object(self.player, "_scrobble", side_effect=record_scrobble):
            with patch.object(self.scrobbler.time, "time", side_effect=self._time):
                self.player.onAVStarted()
                self.player.tick()

                self.player._time = 300
                self.player.onPlayBackPaused()

                self.player._time = 420
                self.player.onPlayBackResumed()

                self.player._time = 600
                self.player.onPlayBackStopped()

        self.assertEqual(lifecycle, ["start", "pause", "resume", "stop"])
        self.assertEqual(
            [call[1]["progress"] for call in self.api.calls if call[0] == "scrobble"],
            [120, 300, 420, 600],
        )
        self.assertFalse(
            any(call[0] == "delete_scrobble" for call in self.api.calls)
        )
        self.assertFalse(self.player._active)

    def test_end_clears_continue_watching(self):
        """A natural end at the end of the file must delete the active scrobble."""
        with patch.object(self.scrobbler.time, "time", side_effect=self._time):
            self.player.onAVStarted()
            self.player.tick()

            self.player._time = 3600
            self.player.onPlayBackEnded()

        scrobbles = [call for call in self.api.calls if call[0] == "scrobble"]
        self.assertEqual(len(scrobbles), 2)
        self.assertEqual(scrobbles[0][1]["progress"], 120)
        self.assertEqual(scrobbles[1][1]["progress"], 3600)

        deletes = [call for call in self.api.calls if call[0] == "delete_scrobble"]
        self.assertEqual(len(deletes), 1)
        self.assertFalse(self.player._active)

    def test_short_stop_removes_junk_session(self):
        """Stopping before 30 seconds must not leave a continue-watching item."""
        self.player._time = 10

        with patch.object(self.scrobbler.time, "time", side_effect=self._time):
            self.player.onAVStarted()
            self.player.tick()
            self.player.onPlayBackStopped()

        scrobbles = [call for call in self.api.calls if call[0] == "scrobble"]
        self.assertEqual(scrobbles, [])

        deletes = [call for call in self.api.calls if call[0] == "delete_scrobble"]
        self.assertEqual(len(deletes), 1)
        self.assertFalse(self.player._active)

    def test_first_tick_is_the_start_boundary(self):
        """onAVStarted arms the session; the first service tick performs start."""
        self.player.onAVStarted()

        self.assertTrue(self.player._active)
        self.assertTrue(self.player._pending_start)
        self.assertEqual(self.api.calls, [])

        with patch.object(self.scrobbler.time, "time", return_value=self.clock):
            self.player.tick()

        self.assertFalse(self.player._pending_start)
        self.assertEqual(
            [call[0] for call in self.api.calls],
            ["scrobble"],
        )

    def _time(self):
        self.clock += 1
        return self.clock


if __name__ == "__main__":
    unittest.main()
