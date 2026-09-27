# -*- coding: utf-8 -*-
"""Regression tests for Kodi RPC write result handling."""

import sys
import types
import unittest


def load_monitor():
    xbmc = types.ModuleType("xbmc")
    xbmc.LOGDEBUG = 0
    xbmc.LOGWARNING = 1
    xbmc.LOGERROR = 2
    xbmc.log = lambda *args, **kwargs: None
    xbmc.Monitor = object

    xbmcaddon = types.ModuleType("xbmcaddon")
    xbmcaddon.Addon = lambda *args, **kwargs: None

    xbmcgui = types.ModuleType("xbmcgui")
    xbmcgui.Window = lambda *args, **kwargs: None

    api_client = types.ModuleType("resources.lib.api_client")
    api_client.DejaVuAPI = object

    pure = types.ModuleType("resources.lib.pure")
    pure.capabilities_payload = lambda version, plus: {"version": version, "plus": plus}
    pure.sanitize_result_property = lambda action, value: value

    session = types.ModuleType("resources.lib.session")
    session.sync_settings_from_session = lambda: None

    util = types.ModuleType("resources.lib.util")
    util.notify_changed = lambda *args, **kwargs: None

    sys.modules["xbmc"] = xbmc
    sys.modules["xbmcaddon"] = xbmcaddon
    sys.modules["xbmcgui"] = xbmcgui
    sys.modules["resources.lib.api_client"] = api_client
    sys.modules["resources.lib.pure"] = pure
    sys.modules["resources.lib.session"] = session
    sys.modules["resources.lib.util"] = util

    from resources.lib.monitor import DejaVuMonitor
    return DejaVuMonitor


class MonitorWriteResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.DejaVuMonitor = load_monitor()

    def make_monitor(self):
        monitor = object.__new__(self.DejaVuMonitor)
        return monitor

    def test_failed_write_does_not_update_cache_or_notify(self):
        monitor = self.make_monitor()
        calls = []

        cache = types.ModuleType("resources.lib.cache")
        cache.apply_write = lambda *args, **kwargs: calls.append(("cache", args, kwargs))
        sys.modules["resources.lib.cache"] = cache

        import resources.lib.monitor as monitor_module
        monitor_module.notify_changed = lambda *args, **kwargs: calls.append(("notify", args, kwargs))

        monitor._broadcast_write(
            "remove_from_watchlist",
            {"type": "movie", "id": 603},
            {"success": False, "error": "not_found"},
        )

        self.assertEqual(calls, [])

    def test_successful_write_updates_cache_and_notifies(self):
        monitor = self.make_monitor()
        calls = []

        cache = types.ModuleType("resources.lib.cache")
        cache.apply_write = lambda *args, **kwargs: calls.append(("cache", args, kwargs))
        sys.modules["resources.lib.cache"] = cache

        import resources.lib.util as util
        util.notify_changed = lambda *args, **kwargs: calls.append(("notify", args, kwargs))

        monitor._broadcast_write(
            "add_to_watchlist",
            {"type": "movie", "id": 603},
            {"success": True},
        )

        self.assertEqual([item[0] for item in calls], ["cache", "notify"])


if __name__ == "__main__":
    unittest.main()
