# -*- coding: utf-8 -*-
"""
dejaVu Service
Entry point for xbmc.service – runs in the background for the lifetime of Kodi.
Instantiates the scrobbler and drives the tick loop.
"""

import xbmc
from resources.lib.scrobbler import DejaVuPlayer
from resources.lib.monitor import DejaVuMonitor
from resources.lib.session import sync_settings_from_session

SESSION_SYNC_EVERY = 30


def run():
    monitor = DejaVuMonitor()
    player = DejaVuPlayer()
    ticks = 0

    xbmc.log("[dejaVu] Service started.", xbmc.LOGINFO)

    while not monitor.abortRequested():
        try:
            player.tick()
        except Exception as exc:
            xbmc.log("[dejaVu] tick failed: %s" % exc, xbmc.LOGWARNING)
        try:
            monitor.drain_rpc()
        except Exception as exc:
            xbmc.log("[dejaVu] RPC drain failed: %s" % exc, xbmc.LOGWARNING)
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
