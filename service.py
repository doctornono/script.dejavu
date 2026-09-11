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
from resources.lib.session import sync_settings_from_session

ADDON = xbmcaddon.Addon()



def run():
    monitor = DejaVuMonitor()
    player  = DejaVuPlayer()

    xbmc.log("[dejaVu] Service started.", xbmc.LOGINFO)

    while not monitor.abortRequested():
        player.tick()
        try:
            sync_settings_from_session()
        except Exception as exc:
            xbmc.log("[dejaVu] session sync failed: %s" % exc, xbmc.LOGWARNING)
        if monitor.waitForAbort(1):
            break

    xbmc.log("[dejaVu] Service stopped.", xbmc.LOGINFO)


if __name__ == "__main__":
    run()

