# -*- coding: utf-8 -*-
"""
dejaVu Service
Entry point for xbmc.service – runs in the background for the lifetime of Kodi.
Instantiates the scrobbler and drives the tick loop.
"""

import json
import time
import xbmc
from resources.lib.scrobbler import DejaVuPlayer
from resources.lib.monitor import DejaVuMonitor
from resources.lib.session import sync_settings_from_session

SESSION_SYNC_EVERY = 30

# #region agent log
_DBG_LOG = r"D:\Developpement\dejavu-kodi-addons\debug-762a00.log"
_DBG_INGEST = "http://127.0.0.1:7403/ingest/793ea98b-2109-427e-9f7f-ba8b74480cc9"
_DBG_VISIBLE = (
    "String.IsEqual(System.AddonSetting(script.dejavu,enable_context_menu),true)"
    " + [Window.IsVisible(Videos) | Window.IsVisible(VideoPlaylist) | Window.IsVisible(DialogVideoInfo)]"
    " + !Container.Content(addons)"
    " + !String.StartsWith(ListItem.FolderPath,addons://)"
    " + !String.StartsWith(ListItem.FileNameAndPath,addons://)"
    " + [String.IsEqual(ListItem.DBType,movie) | String.IsEqual(ListItem.DBType,tvshow)"
    " | String.IsEqual(ListItem.DBType,season) | String.IsEqual(ListItem.DBType,episode)"
    " | String.IsEqual(ListItem.Property(DBType),movie) | String.IsEqual(ListItem.Property(DBType),tvshow)"
    " | String.IsEqual(ListItem.Property(DBType),season) | String.IsEqual(ListItem.Property(DBType),episode)"
    " | String.IsEqual(ListItem.Property(media_type),movie) | String.IsEqual(ListItem.Property(media_type),tv)"
    " | String.IsEqual(ListItem.Property(media_type),tvshow) | String.IsEqual(ListItem.Property(media_type),episode)"
    " | String.IsEqual(ListItem.Property(sCat),1) | String.IsEqual(ListItem.Property(sCat),2)"
    " | String.IsEqual(ListItem.Property(sCat),3) | String.IsEqual(ListItem.Property(sCat),9)]"
)
_dbg_n = 0
_dbg_last = ""


def _agent_dbg_context_vis():
    global _dbg_n, _dbg_last
    if _dbg_n >= 8:
        return
    title = xbmc.getInfoLabel("ListItem.Title") or xbmc.getInfoLabel("ListItem.Label") or ""
    dbtype = xbmc.getInfoLabel("ListItem.DBType") or ""
    win = xbmc.getInfoLabel("System.CurrentWindow") or ""
    key = "%s|%s|%s" % (win, dbtype, title[:48])
    if not title and not dbtype:
        return
    if key == _dbg_last:
        return
    _dbg_last = key
    _dbg_n += 1
    folder = xbmc.getInfoLabel("ListItem.FolderPath") or ""
    fpath = xbmc.getInfoLabel("ListItem.FileNameAndPath") or ""
    data = {
        "setting_eq_true": xbmc.getCondVisibility(
            "String.IsEqual(System.AddonSetting(script.dejavu,enable_context_menu),true)"
        ),
        "setting_raw": xbmc.getInfoLabel("System.AddonSetting(script.dejavu,enable_context_menu)") or "",
        "win_videos": xbmc.getCondVisibility("Window.IsVisible(Videos)"),
        "win_myvideonav": xbmc.getCondVisibility("Window.IsVisible(MyVideoNav)"),
        "win_playlist": xbmc.getCondVisibility("Window.IsVisible(VideoPlaylist)"),
        "win_info": xbmc.getCondVisibility("Window.IsVisible(DialogVideoInfo)"),
        "win_media": xbmc.getCondVisibility("Window.IsMedia"),
        "content_addons": xbmc.getCondVisibility("Container.Content(addons)"),
        "folder_addons": xbmc.getCondVisibility("String.StartsWith(ListItem.FolderPath,addons://)"),
        "file_addons": xbmc.getCondVisibility("String.StartsWith(ListItem.FileNameAndPath,addons://)"),
        "dbtype_movie": xbmc.getCondVisibility("String.IsEqual(ListItem.DBType,movie)"),
        "full_xml_visible": xbmc.getCondVisibility(_DBG_VISIBLE),
        "dbtype": dbtype,
        "media_type_prop": xbmc.getInfoLabel("ListItem.Property(media_type)") or "",
        "title": title[:80],
        "window": win,
        "folder_prefix": folder[:60],
        "file_prefix": fpath[:60],
    }
    payload = {
        "sessionId": "762a00",
        "timestamp": int(time.time() * 1000),
        "location": "service.py:_agent_dbg_context_vis",
        "message": "context visibility sample",
        "data": data,
        "runId": "pre-fix",
        "hypothesisId": "A-E",
    }
    try:
        line = json.dumps(payload, ensure_ascii=True) + "\n"
        with open(_DBG_LOG, "a", encoding="utf-8") as fh:
            fh.write(line)
        try:
            import urllib.request
            req = urllib.request.Request(
                _DBG_INGEST,
                data=line.encode("utf-8"),
                headers={"Content-Type": "application/json", "X-Debug-Session-Id": "762a00"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=0.4).read()
        except Exception:
            pass
    except Exception as exc:
        xbmc.log("[dejaVu] debug vis log failed: %s" % exc, xbmc.LOGWARNING)
# #endregion


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
        # #region agent log
        try:
            _agent_dbg_context_vis()
        except Exception:
            pass
        # #endregion
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
