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
    """QR pairing dialog. GUI updates must run on the main thread via pump()."""

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
        self.progress_pct = 100
        self._stop = threading.Event()
        self._closed = False

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
        self.progress_pct = 100
        self._closed = False
        self._stop.clear()

    def onInit(self):
        ls = ADDON.getLocalizedString
        try:
            self.getControl(201).setLabel(ls(30117) or "Connect dejaVu")
            self.getControl(202).setLabel(ls(30107) or "Scan this QR code with your phone")
            self.getControl(208).setLabel(
                ls(30174) or "No account yet? Create one on your phone (Google, GitHub, or email)."
            )
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
                return
            self.progress_pct = int((remaining / self.expires_in) * 100)
            try:
                token = self.api.poll_token(self.device_code)
            except Exception as e:
                xbmc.log(f"[dejaVu] ConnectDialog poll: {e}", xbmc.LOGWARNING)
                token = None
            if token and token.get("access_token"):
                self.token_data = token
                return
            self._stop.wait(self.interval)

    def pump(self):
        """Main-thread GUI: progress bar and close when the worker is done."""
        if not self.ready or self._closed:
            return
        try:
            self.getControl(206).setPercent(max(0, min(100, int(self.progress_pct))))
        except Exception:
            pass
        if self.token_data or self.expired or self.cancelled:
            self._closed = True
            try:
                self.close()
            except Exception:
                pass

    def done(self):
        return bool(self.cancelled or self.expired or self.token_data)

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
        self._closed = True
        try:
            self.close()
        except Exception:
            pass

    def stop(self):
        self._stop.set()
