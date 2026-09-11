# -*- coding: utf-8 -*-
"""
dejaVu Service
Entry point for xbmc.service – runs in the background for the lifetime of Kodi.
Instantiates the scrobbler and drives the tick loop.
"""

import xbmc
from resources.lib.cache import warm_tick
from resources.lib.scrobbler import DejaVuPlayer
from resources.lib.monitor import DejaVuMonitor
from resources.lib.session import sync_settings_from_session
from resources.lib.util import publish_auth_window

SESSION_SYNC_EVERY = 30


def run():
    monitor = DejaVuMonitor()
    player = DejaVuPlayer()
    ticks = 0

    xbmc.log("[dejaVu] Service started.", xbmc.LOGINFO)
    publish_auth_window()

    while not monitor.abortRequested():
        try:
            player.tick()
        except Exception as exc:
            xbmc.log("[dejaVu] tick failed: %s" % exc, xbmc.LOGWARNING)
        try:
            monitor.drain_rpc(budget_s=0.2)
        except Exception as exc:
            xbmc.log("[dejaVu] RPC drain failed: %s" % exc, xbmc.LOGWARNING)
        try:
            warm_tick(monitor.api)
        except Exception as exc:
            xbmc.log("[dejaVu] cache warm failed: %s" % exc, xbmc.LOGDEBUG)
        ticks += 1
        if ticks >= SESSION_SYNC_EVERY:
            ticks = 0
            try:
                sync_settings_from_session()
            except Exception as exc:
                xbmc.log("[dejaVu] session sync failed: %s" % exc, xbmc.LOGWARNING)
        if monitor.waitForAbort(1):
            break

    xbmc.log("[dejaVu] Service stopped.", xbmc.LOGINFO)


if __name__ == "__main__":
    run()
