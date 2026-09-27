# -*- coding: utf-8 -*-
"""
dejaVu Service
Entry point for xbmc.service – runs in the background for the lifetime of Kodi.
Instantiates the scrobbler and drives the tick loop.
"""

import time
import xbmc
import xbmcaddon
from resources.lib.cache import warm_tick
from resources.lib.scrobbler import DejaVuPlayer
from resources.lib.monitor import DejaVuMonitor
from resources.lib.session import sync_settings_from_session
from resources.lib.util import publish_auth_window

SESSION_SYNC_EVERY = 30
CACHE_WARM_EVERY = 15


def _debug_enabled():
    try:
        return xbmcaddon.Addon().getSettingBool("debug")
    except Exception:
        return False


def _log_perf(label, elapsed):
    if _debug_enabled():
        xbmc.log("[dejaVu][PERF] %s: %.1f ms" % (label, elapsed * 1000.0), xbmc.LOGDEBUG)


def run():
    monitor = DejaVuMonitor()
    player = DejaVuPlayer()
    ticks = 0
    cache_ticks = 0

    xbmc.log("[dejaVu] Service started.", xbmc.LOGINFO)
    publish_auth_window()

    while not monitor.abortRequested():
        started = time.monotonic()
        try:
            player.tick()
        except Exception as exc:
            xbmc.log("[dejaVu] tick failed: %s" % exc, xbmc.LOGWARNING)
        finally:
            _log_perf("player.tick", time.monotonic() - started)
        started = time.monotonic()
        try:
            monitor.drain_rpc(budget_s=0.2)
        except Exception as exc:
            xbmc.log("[dejaVu] RPC drain failed: %s" % exc, xbmc.LOGWARNING)
        finally:
            _log_perf("monitor.drain_rpc", time.monotonic() - started)
        cache_ticks += 1
        if cache_ticks >= CACHE_WARM_EVERY:
            cache_ticks = 0
            started = time.monotonic()
            try:
                warm_tick(monitor.api)
            except Exception as exc:
                xbmc.log("[dejaVu] cache warm failed: %s" % exc, xbmc.LOGDEBUG)
            finally:
                _log_perf("cache.warm_tick", time.monotonic() - started)
        ticks += 1
        if ticks >= SESSION_SYNC_EVERY:
            ticks = 0
            started = time.monotonic()
            try:
                sync_settings_from_session()
            except Exception as exc:
                xbmc.log("[dejaVu] session sync failed: %s" % exc, xbmc.LOGWARNING)
            finally:
                _log_perf("session.sync", time.monotonic() - started)
        if monitor.waitForAbort(1):
            break

    xbmc.log("[dejaVu] Service stopped.", xbmc.LOGINFO)


if __name__ == "__main__":
    run()
