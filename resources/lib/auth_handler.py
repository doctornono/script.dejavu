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

import json
import os
import re
import time
import xbmc
import xbmcgui
import xbmcaddon
from .api_client import DejaVuAPI
from .session import apply_session_to_settings, clear_session, get_access_token, save_session
from .util import notify_changed

ADDON = xbmcaddon.Addon()
AUTH_STATUS_PROP = "script.dejavu.auth.status"
WEB_HOME = "https://dejavu.plus"

# #region agent log
_DBG_PATH = r"D:\Developpement\dejavu-kodi-addons\debug-489f32.log"
_DBG_URL = "http://127.0.0.1:7403/ingest/793ea98b-2109-427e-9f7f-ba8b74480cc9"


def _agent_log(location, message, data, hypothesis_id, run_id="post-fix"):
    payload = {
        "sessionId": "489f32",
        "timestamp": int(time.time() * 1000),
        "location": location,
        "message": message,
        "data": data,
        "hypothesisId": hypothesis_id,
        "runId": run_id,
    }
    try:
        with open(_DBG_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    try:
        import requests
        requests.post(
            _DBG_URL,
            json=payload,
            headers={"Content-Type": "application/json", "X-Debug-Session-Id": "489f32"},
            timeout=1,
        )
    except Exception:
        pass


def _dbg_file_filled(xml, setting_id):
    tagged = re.search(
        r'<setting id="%s"[^>]*>([^<]*)</setting>' % re.escape(setting_id),
        xml,
    )
    if tagged:
        return bool((tagged.group(1) or "").strip())
    if re.search(r'<setting id="%s"[^>]*/>' % re.escape(setting_id), xml):
        return False
    return None


def _dbg_snapshot():
    xml = ""
    xml_path = ""
    try:
        import xbmcvfs
        xml_path = xbmcvfs.translatePath(
            "special://profile/addon_data/script.dejavu/settings.xml"
        )
        with open(xml_path, "r", encoding="utf-8") as handle:
            xml = handle.read()
    except Exception as exc:
        xml = "ERR:%s" % exc
    snap = {
        "win_addonsettings": bool(xbmc.getCondVisibility("Window.IsVisible(addonsettings)")),
        "win_10140": bool(xbmc.getCondVisibility("Window.IsVisible(10140)")),
        "username_len": len(ADDON.getSetting("username") or ""),
        "token_len": len(ADDON.getSetting("access_token") or ""),
        "import_offered": ADDON.getSetting("kodi_import_offered"),
        "file_username": _dbg_file_filled(xml, "username") if xml.startswith("<") else xml[:80],
        "file_token": _dbg_file_filled(xml, "access_token") if xml.startswith("<") else None,
        "file_offered": _dbg_file_filled(xml, "kodi_import_offered") if xml.startswith("<") else None,
        "xml_path_exists": os.path.exists(xml_path) if xml_path else False,
    }
    try:
        from .session import load_session
        sess = load_session()
        snap["session_token_len"] = len(sess.get("access_token") or "")
        snap["session_username_len"] = len(sess.get("username") or "")
    except Exception:
        snap["session_token_len"] = -1
        snap["session_username_len"] = -1
    return snap
# #endregion


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
    """After Connect: offer Kodi import as the primary buttons when a library exists."""
    try:
        from .library_importer import (
            _already_offered,
            _mark_offered,
            run_import_wizard,
            video_library_totals,
        )
        movie_total, show_total = video_library_totals()
        if (movie_total > 0 or show_total > 0) and not _already_offered():
            body = "\n".join([
                _welcome_body(username, me),
                "",
                _ls(30160),
                _ls(30136) % movie_total,
                _ls(30137) % show_total,
            ])
            import_now = xbmcgui.Dialog().yesno(
                _ls(30117),
                body,
                yeslabel=_ls(30120),
                nolabel=_ls(30161),
            )
            if import_now:
                run_import_wizard(allow_skip=False)
            else:
                _mark_offered()
            return
    except Exception as e:
        xbmc.log(f"[dejaVu] Welcome import prompt failed: {e}", xbmc.LOGWARNING)

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
    # #region agent log
    _agent_log(
        "auth_handler.py:_persist_login:before",
        "persist start",
        {**_dbg_snapshot(), "incoming_token_len": len(access_token or ""), "has_refresh": bool(token_data.get("refresh_token"))},
        "A",
    )
    # #endregion
    refresh_token = token_data.get("refresh_token") or ""
    save_session({
        "access_token": access_token,
        "username": "",
        "refresh_token": refresh_token,
    })
    set_token_ok = ADDON.setSetting("access_token", access_token)
    set_refresh_ok = None
    if refresh_token:
        set_refresh_ok = ADDON.setSetting("refresh_token", refresh_token)

    authed_api = DejaVuAPI(token=access_token)
    me = authed_api.get_me()
    username = "User"
    me_ok = bool(me and isinstance(me, dict))
    me_keys = list(me.keys())[:12] if me_ok else []
    if me_ok:
        user = me.get("user") if isinstance(me.get("user"), dict) else me
        username = (
            user.get("name")
            or user.get("username")
            or user.get("email")
            or "User"
        )
    save_session({
        "access_token": access_token,
        "username": username,
        "refresh_token": refresh_token,
    })
    set_user_ok = ADDON.setSetting("username", username)
    # #region agent log
    _agent_log(
        "auth_handler.py:_persist_login:after_set",
        "setSetting results",
        {
            **_dbg_snapshot(),
            "set_token_ok": set_token_ok,
            "set_refresh_ok": set_refresh_ok,
            "set_user_ok": set_user_ok,
            "me_ok": me_ok,
            "me_keys": me_keys,
            "username_len_local": len(username or ""),
        },
        "B",
    )
    # #endregion
    xbmc.log(f"[dejaVu] Login successful: {username}", xbmc.LOGINFO)
    _set_auth_status("success")
    notify_changed("authenticated")
    _show_welcome(username, me)
    apply_session_to_settings()
    # #region agent log
    _agent_log(
        "auth_handler.py:_persist_login:after_welcome",
        "after welcome dialog",
        _dbg_snapshot(),
        "A",
    )
    # #endregion
    xbmc.executebuiltin("Addon.OpenSettings(script.dejavu)")
    return True


def _login_with_progress(api, device_code, display_code, expires_in, interval):
    """Built-in Kodi progress dialog: Cancel always works."""
    progress = xbmcgui.DialogProgress()
    progress.create(
        _ls(30117) or _ls(30030),
        f"[COLOR gold][B]{display_code}[/B][/COLOR]\n{DISPLAY_URI}\n{_ls(30174)}\n{_ls(30031)}",
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
    # #region agent log
    _agent_log("auth_handler.py:login:start", "login() started", _dbg_snapshot(), "A")
    # #endregion
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
        ok = _persist_login(token_data)
        # #region agent log
        _agent_log(
            "auth_handler.py:login:end",
            "login() after persist",
            {**_dbg_snapshot(), "persist_ok": ok},
            "A",
        )
        # #endregion
        return ok

    if expired:
        _set_auth_status("expired")
        xbmcgui.Dialog().ok(_ls(30030), _ls(30035))
        return False

    _set_auth_status("cancelled")
    return False


def logout():
    """Clears stored credentials."""
    clear_session()
    ADDON.setSetting("access_token", "")
    ADDON.setSetting("refresh_token", "")
    ADDON.setSetting("username", "")
    ADDON.setSetting("kodi_import_offered", "false")
    ADDON.setSetting("kodi_import_at", "")
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
    return bool(get_access_token())
