# -*- coding: utf-8 -*-
"""
dejaVu Service
Entry point for xbmc.service – runs in the background for the lifetime of Kodi.
Instantiates the scrobbler and drives the tick loop.
"""

import xbmc
import xbmcaddon
from resources.lib.scrobbler import DejaVuPlayer
from resources.lib.monitor import DejaVuMonitor

ADDON = xbmcaddon.Addon()


def run():
    monitor = DejaVuMonitor()
    player  = DejaVuPlayer()

    xbmc.log("[dejaVu] Service started.", xbmc.LOGINFO)

    while not monitor.abortRequested():
        player.tick()
        if monitor.waitForAbort(1):
            break

    xbmc.log("[dejaVu] Service stopped.", xbmc.LOGINFO)


if __name__ == "__main__":
    run()

