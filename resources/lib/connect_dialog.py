# -*- coding: utf-8 -*-
"""WindowXML dialog for DejaVu Connect (QR + short code)."""

import threading
import time
import xbmc
import xbmcaddon
import xbmcgui

ADDON = xbmcaddon.Addon()

# Back / parent / stop / keyboard Esc / mouse back
CLOSE_ACTIONS = (9, 10, 13, 92, 101, 110, 216)


class ConnectDialog(xbmcgui.WindowXMLDialog):
    """QR pairing dialog. Use setup() then doModal() so Back/Cancel work."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.cancelled = False
        self.expired = False
        self.ready = False
        self.token_data = None
        self.display_code = ""
        self.qr_path = ""
        self.device_code = ""
        self.interval = 5
        self.expires_in = 300
        self.api = None
        self._stop = threading.Event()

    def setup(self, display_code, qr_path, device_code, interval, expires_in, api):
        self.display_code = display_code or ""
        self.qr_path = qr_path or ""
        self.device_code = device_code
        self.interval = max(1, int(interval or 5))
        self.expires_in = max(30, int(expires_in or 300))
        self.api = api
        self.cancelled = False
        self.expired = False
        self.token_data = None
        self._stop.clear()

    def onInit(self):
        ls = ADDON.getLocalizedString
        try:
            self.getControl(201).setLabel(ls(30117) or "Connect dejaVu")
            self.getControl(202).setLabel(ls(30107) or "Scan this QR code with your phone")
            self.getControl(207).setLabel(ls(30108) or "or visit")
            self.getControl(203).setLabel("dejavu.plus/device")
            self.getControl(204).setLabel(self.display_code)
            self.getControl(205).setLabel(ls(30109) or "Waiting for connection...")
            self.getControl(9000).setLabel(ls(30118) or "Cancel")
            if self.qr_path:
                self.getControl(100).setImage(self.qr_path)
            self.getControl(206).setPercent(100)
            self.setFocusId(9000)
        except Exception as e:
            xbmc.log(f"[dejaVu] ConnectDialog.onInit: {e}", xbmc.LOGWARNING)

        self.ready = True
        self._thread = threading.Thread(target=self._poll)
        self._thread.daemon = True
        self._thread.start()

    def _poll(self):
        if not self.api or not self.device_code:
            return
        expires_at = time.time() + self.expires_in
        while not self._stop.is_set():
            remaining = expires_at - time.time()
            if remaining <= 0:
                self.expired = True
                self.close()
                return
            try:
                pct = int((remaining / self.expires_in) * 100)
                self.getControl(206).setPercent(max(0, min(100, pct)))
            except Exception:
                pass
            try:
                token = self.api.poll_token(self.device_code)
            except Exception as e:
                xbmc.log(f"[dejaVu] ConnectDialog poll: {e}", xbmc.LOGWARNING)
                token = None
            if token and token.get("access_token"):
                self.token_data = token
                self.close()
                return
            self._stop.wait(self.interval)

    def onAction(self, action):
        try:
            action_id = action.getId()
        except Exception:
            action_id = 0
        if action_id in CLOSE_ACTIONS:
            self._cancel()

    def onClick(self, control_id):
        if control_id == 9000:
            self._cancel()

    def _cancel(self):
        self.cancelled = True
        self._stop.set()
        self.close()

    def stop(self):
        self._stop.set()
