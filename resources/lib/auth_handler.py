# -*- coding: utf-8 -*-
"""
dejaVu Auth Handler
OAuth 2.0 Device Authorization Grant (RFC 8628) — DejaVu Connect.

Flow:
  1. POST /auth/device/code  → get user_code + verification_uri
  2. Show QR + short code (WindowXML, with text fallback)
  3. Poll POST /auth/device/token until approved or expired
  4. Save access_token + username in addon settings
"""

import time
import xbmc
import xbmcgui
import xbmcaddon
from .api_client import DejaVuAPI
from .util import notify_changed

ADDON = xbmcaddon.Addon()
AUTH_STATUS_PROP = "script.dejavu.auth.status"
WEB_HOME = "https://dejavu.plus"


def _ls(string_id):
    return ADDON.getLocalizedString(string_id)


def _window():
    return xbmcgui.Window(10000)


def _set_auth_status(status):
    _window().setProperty(AUTH_STATUS_PROP, status)


def format_user_code(code):
    raw = (code or "").replace("-", "").replace(" ", "").upper()
    if len(raw) == 8:
        return f"{raw[:4]}-{raw[4:]}"
    return raw


def _open_web(url):
    try:
        if xbmc.getCondVisibility("System.Platform.Android"):
            xbmc.executebuiltin(f"StartAndroidActivity(,android.intent.action.VIEW,,{url})")
            return
        import webbrowser
        webbrowser.open(url)
    except Exception as e:
        xbmc.log(f"[dejaVu] Could not open browser: {e}", xbmc.LOGWARNING)
        xbmcgui.Dialog().ok("dejaVu", url)


def _welcome_body(username, me):
    stats = {}
    if isinstance(me, dict):
        stats = me.get("stats") or {}
    watchlist = (stats.get("watchlist") or {}).get("total", 0)
    history = (stats.get("history") or {}).get("total", 0)
    lists = (stats.get("lists") or {}).get("total", 0)
    favorites = (stats.get("favorites") or {}).get("total", 0)
    return "\n".join([
        _ls(30032) % username,
        _ls(30112),
        "",
        _ls(30113) % watchlist,
        _ls(30114) % history,
        _ls(30115) % lists,
        _ls(30116) % favorites,
    ])


def _show_welcome(username, me):
    try:
        open_web = xbmcgui.Dialog().yesno(
            _ls(30117),
            _welcome_body(username, me),
            yeslabel=_ls(30110),
            nolabel=_ls(30111),
        )
        if open_web:
            _open_web(WEB_HOME)
            return
    except Exception as e:
        xbmc.log(f"[dejaVu] Welcome dialog failed: {e}", xbmc.LOGWARNING)
    xbmcgui.Dialog().notification(
        "dejaVu",
        _ls(30032) % username,
        xbmcgui.NOTIFICATION_INFO,
        4000,
    )


DISPLAY_URI = "dejavu.plus/device"


def _persist_login(token_data):
    access_token = token_data["access_token"]
    ADDON.setSetting("access_token", access_token)
    refresh_token = token_data.get("refresh_token")
    if refresh_token:
        ADDON.setSetting("refresh_token", refresh_token)

    authed_api = DejaVuAPI(token=access_token)
    me = authed_api.get_me()
    username = "User"
    if me and isinstance(me, dict):
        user = me.get("user") if isinstance(me.get("user"), dict) else me
        username = (
            user.get("name")
            or user.get("username")
            or user.get("email")
            or "User"
        )
    ADDON.setSetting("username", username)
    xbmc.log(f"[dejaVu] Login successful: {username}", xbmc.LOGINFO)
    _set_auth_status("success")
    notify_changed("authenticated")
    _show_welcome(username, me)
    return True


def _login_with_progress(api, device_code, display_code, expires_in, interval):
    """Built-in Kodi progress dialog: Cancel always works."""
    progress = xbmcgui.DialogProgress()
    progress.create(
        _ls(30117) or _ls(30030),
        f"[COLOR gold][B]{display_code}[/B][/COLOR]\n{DISPLAY_URI}\n{_ls(30031)}",
    )
    monitor = xbmc.Monitor()
    expires_at = time.time() + expires_in
    try:
        while time.time() < expires_at:
            if progress.iscanceled() or monitor.abortRequested():
                _set_auth_status("cancelled")
                return False
            remaining = max(0, expires_at - time.time())
            progress.update(
                int((remaining / expires_in) * 100),
                f"[COLOR gold][B]{display_code}[/B][/COLOR]\n{DISPLAY_URI}\n{_ls(30109)}",
            )
            token_data = api.poll_token(device_code)
            if token_data and token_data.get("access_token"):
                progress.close()
                return _persist_login(token_data)
            if monitor.waitForAbort(interval):
                _set_auth_status("cancelled")
                return False
        _set_auth_status("expired")
        xbmcgui.Dialog().ok(_ls(30030), _ls(30035))
        return False
    finally:
        try:
            progress.close()
        except Exception:
            pass


def login():
    """
    Starts the Device Code login flow (DejaVu Connect).
    Returns True on success, False on failure/cancel.
    """
    _set_auth_status("pending")
    api = DejaVuAPI(token="")

    device_info = api.get_device_code()

    if not device_info:
        _set_auth_status("error")
        xbmcgui.Dialog().ok(_ls(30030), _ls(30034))
        return False

    device_code = device_info.get("device_code", "")
    user_code = device_info.get("user_code", "")
    expires_in = int(device_info.get("expires_in", 300))
    interval = int(device_info.get("interval", 5))
    display_code = format_user_code(user_code)

    xbmc.log(
        f"[dejaVu] Device code obtained. user_code={user_code}",
        xbmc.LOGDEBUG,
    )

    qr_path = api.download_device_qr(user_code)

    try:
        from .connect_dialog import ConnectDialog
        dialog = ConnectDialog(
            "script-dejavu-connect.xml",
            ADDON.getAddonInfo("path"),
            "Default",
            "1080i",
        )
        dialog.setup(display_code, qr_path, device_code, interval, expires_in, api)
        dialog.doModal()
        token_data = dialog.token_data
        cancelled = dialog.cancelled
        expired = dialog.expired
        dialog.stop()
        del dialog
    except Exception as e:
        xbmc.log(f"[dejaVu] QR dialog unavailable: {e}", xbmc.LOGWARNING)
        return _login_with_progress(api, device_code, display_code, expires_in, interval)

    if cancelled:
        xbmc.log("[dejaVu] Login cancelled by user.", xbmc.LOGINFO)
        _set_auth_status("cancelled")
        return False

    if token_data and token_data.get("access_token"):
        return _persist_login(token_data)

    if expired:
        _set_auth_status("expired")
        xbmcgui.Dialog().ok(_ls(30030), _ls(30035))
        return False

    _set_auth_status("cancelled")
    return False


def logout():
    """Clears stored credentials."""
    ADDON.setSetting("access_token", "")
    ADDON.setSetting("refresh_token", "")
    ADDON.setSetting("username", "")
    _set_auth_status("")
    xbmc.log("[dejaVu] User logged out.", xbmc.LOGINFO)
    notify_changed("auth")
    xbmcgui.Dialog().notification(
        "dejaVu",
        _ls(30040),
        xbmcgui.NOTIFICATION_INFO,
        3000,
    )


def is_logged_in():
    """Returns True if an access token is stored."""
    return bool(ADDON.getSetting("access_token"))
