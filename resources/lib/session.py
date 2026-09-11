# -*- coding: utf-8 -*-
"""Persisted dejaVu session, independent of the addon settings dialog.

Kodi's Addon Settings window reloads a snapshot taken when it opened. After
Connect, that window can write empty username/token back over settings.xml.
This JSON file is the source of truth the dialog cannot overwrite.
"""

import json
import os

import xbmc
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = "script.dejavu"


def session_path():
    return xbmcvfs.translatePath(
        "special://profile/addon_data/%s/session.json" % ADDON_ID
    )


def _read_json(path):
    try:
        if not path or not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_session(data):
    path = session_path()
    folder = os.path.dirname(path)
    payload = {
        "access_token": (data or {}).get("access_token") or "",
        "username": (data or {}).get("username") or "",
        "refresh_token": (data or {}).get("refresh_token") or "",
    }
    try:
        xbmcvfs.mkdirs(folder)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
    except Exception as exc:
        xbmc.log("[dejaVu] session.json write failed: %s" % exc, xbmc.LOGERROR)
        return False
    return True


def load_session():
    data = _read_json(session_path())
    token = data.get("access_token") or ""
    username = data.get("username") or ""
    refresh = data.get("refresh_token") or ""
    if not token:
        token = ADDON.getSetting("access_token") or ""
        if token:
            username = username or (ADDON.getSetting("username") or "")
            refresh = refresh or (ADDON.getSetting("refresh_token") or "")
            save_session({
                "access_token": token,
                "username": username,
                "refresh_token": refresh,
            })
    return {
        "access_token": token,
        "username": username,
        "refresh_token": refresh,
    }


def clear_session():
    save_session({})


def get_access_token():
    return load_session().get("access_token") or ""


def get_username():
    return load_session().get("username") or ""


def settings_dialog_open():
    return bool(
        xbmc.getCondVisibility("Window.IsVisible(addonsettings)")
        or xbmc.getCondVisibility("Window.IsVisible(10140)")
    )


def apply_session_to_settings(data=None):
    data = data or load_session()
    ADDON.setSetting("access_token", data.get("access_token") or "")
    ADDON.setSetting("username", data.get("username") or "")
    refresh = data.get("refresh_token") or ""
    if refresh:
        ADDON.setSetting("refresh_token", refresh)


def sync_settings_from_session():
    """Re-apply session.json to addon settings after the dialog overwrites them."""
    if settings_dialog_open():
        return False
    data = load_session()
    token = data.get("access_token") or ""
    username = data.get("username") or ""
    current_token = ADDON.getSetting("access_token") or ""
    current_user = ADDON.getSetting("username") or ""
    if current_token == token and current_user == username:
        return False
    apply_session_to_settings(data)
    xbmc.log("[dejaVu] Restored account settings from session.json", xbmc.LOGINFO)
    return True
