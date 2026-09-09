# -*- coding: utf-8 -*-
"""WindowXML dialog for the Kodi library import preview."""

import xbmc
import xbmcaddon
import xbmcgui

ADDON = xbmcaddon.Addon()

CLOSE_ACTIONS = (9, 10, 13, 92, 101, 110, 216)

BTN_DETAILS = 8000
BTN_IMPORT = 8001
BTN_CANCEL = 9000


def _ls(string_id):
    return ADDON.getLocalizedString(string_id)


class ImportPreviewDialog(xbmcgui.WindowXMLDialog):
    """Summary of the scanned Kodi library before POST /kodi/import."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.preview = {}
        self.cancelled = False
        self.confirmed = False

    def setup(self, preview):
        self.preview = preview or {}
        self.cancelled = False
        self.confirmed = False

    def onInit(self):
        p = self.preview
        try:
            self.getControl(201).setLabel(_ls(30134))
            self.getControl(202).setLabel(_ls(30135))
            self.getControl(203).setLabel(_ls(30136) % p.get("movie_total", 0))
            self.getControl(204).setLabel(_ls(30137) % p.get("show_total", 0))
            self.getControl(205).setLabel(_ls(30138) % p.get("episode_total", 0))
            self.getControl(206).setLabel(_ls(30139))
            self.getControl(207).setLabel(_ls(30140) % p.get("movies_watched", 0))
            self.getControl(208).setLabel(_ls(30141) % p.get("shows_started", 0))
            self.getControl(209).setLabel(_ls(30142) % p.get("episodes_watched", 0))
            self.getControl(210).setLabel(_ls(30143) % p.get("certain", 0))
            self.getControl(211).setLabel(_ls(30144) % p.get("review", 0))
            self.getControl(212).setLabel(_ls(30145) % p.get("unidentified", 0))
            self.getControl(BTN_DETAILS).setLabel(_ls(30146))
            self.getControl(BTN_IMPORT).setLabel(_ls(30147) % p.get("importable", 0))
            self.getControl(BTN_CANCEL).setLabel(_ls(30118))
            self.setFocusId(BTN_IMPORT)
        except Exception as e:
            xbmc.log(f"[dejaVu] ImportPreviewDialog.onInit: {e}", xbmc.LOGWARNING)

    def onAction(self, action):
        try:
            action_id = action.getId()
        except Exception:
            action_id = 0
        if action_id in CLOSE_ACTIONS:
            self._cancel()

    def onClick(self, control_id):
        if control_id == BTN_CANCEL:
            self._cancel()
        elif control_id == BTN_IMPORT:
            self.confirmed = True
            self.cancelled = False
            self.close()
        elif control_id == BTN_DETAILS:
            self._show_details()

    def _show_details(self):
        rows = self.preview.get("detail_rows") or []
        if not rows:
            xbmcgui.Dialog().ok(_ls(30134), _ls(30151))
            return
        xbmcgui.Dialog().select(_ls(30151), rows)

    def _cancel(self):
        self.cancelled = True
        self.confirmed = False
        self.close()
