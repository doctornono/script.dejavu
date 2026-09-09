# -*- coding: utf-8 -*-
"""WindowXML dialog for DejaVu Connect (QR + short code)."""

import xbmc
import xbmcgui

ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92
ACTION_STOP = 13


class ConnectDialog(xbmcgui.WindowXMLDialog):
    """QR pairing dialog. Call setup() then show() — do not use doModal()."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.cancelled = False
        self.qr_path = ""
        self.verification_uri = "https://dejavu.plus/device"
        self.display_code = ""

    def setup(self, display_code, verification_uri, qr_path=""):
        self.display_code = display_code or ""
        self.verification_uri = verification_uri or "https://dejavu.plus/device"
        self.qr_path = qr_path or ""
        self.cancelled = False

    def onInit(self):
        try:
            if self.qr_path:
                self.getControl(100).setImage(self.qr_path)
            self.getControl(203).setLabel(self.verification_uri.replace("https://", ""))
            self.getControl(204).setLabel(self.display_code)
            self.getControl(206).setPercent(100)
        except Exception as e:
            xbmc.log(f"[dejaVu] ConnectDialog.onInit: {e}", xbmc.LOGWARNING)

    def onAction(self, action):
        try:
            action_id = action.getId()
        except Exception:
            action_id = 0
        if action_id in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK, ACTION_STOP):
            self.cancelled = True
            self.close()

    def onClick(self, control_id):
        if control_id == 9000:
            self.cancelled = True
            self.close()

    def set_percent(self, pct):
        try:
            self.getControl(206).setPercent(max(0, min(100, int(pct))))
        except Exception:
            pass
