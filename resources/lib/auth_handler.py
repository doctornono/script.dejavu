# -*- coding: utf-8 -*-
"""
dejaVu Auth Handler
Implements the OAuth 2.0 Device Authorization Grant (RFC 8628).

Flow:
  1. POST /auth/device/code  → get user_code + verification_uri
  2. Show the code to the user in a progress dialog
  3. Poll POST /auth/device/token until approved or expired
  4. Save access_token + username in addon settings
"""

import time
import xbmc
import xbmcgui
import xbmcaddon
from .api_client import DejaVuAPI

ADDON = xbmcaddon.Addon()


def _ls(string_id):
    return ADDON.getLocalizedString(string_id)


def login():
    """
    Starts the Device Code login flow.
    Returns True on success, False on failure/cancel.
    """
    # Re-instantiate without token so the initial request is unauthenticated
    api = DejaVuAPI(token="")

    # --- Step 1: request device code ---
    device_info = api.get_device_code()

    if not device_info:
        xbmcgui.Dialog().ok(
            _ls(30030),
            _ls(30034),
        )
        return False

    device_code      = device_info.get("device_code", "")
    user_code        = device_info.get("user_code", "")
    verification_uri = device_info.get("verification_uri", "https://dejavu.plus/activate")
    expires_in       = int(device_info.get("expires_in", 300))
    interval         = int(device_info.get("interval", 5))

    xbmc.log(f"[dejaVu] Device code obtained. user_code={user_code} uri={verification_uri}", xbmc.LOGDEBUG)

    # --- Step 2: show dialog with the code ---
    dialog = xbmcgui.DialogProgress()
    dialog.create(
        _ls(30030),   # "dejaVu Login"
        f"{_ls(30031)}\n[B]{verification_uri}[/B]\n\n[COLOR gold][B]{user_code}[/B][/COLOR]"
    )

    expires_at = time.time() + expires_in

    try:
        # --- Step 3: polling loop ---
        while time.time() < expires_at:
            if dialog.iscanceled():
                xbmc.log("[dejaVu] Login cancelled by user.", xbmc.LOGINFO)
                return False

            # Update progress bar (counts down)
            remaining = max(0, expires_at - time.time())
            pct = int((remaining / expires_in) * 100)
            dialog.update(pct)

            # Poll
            token_data = api.poll_token(device_code)

            if token_data and token_data.get("access_token"):
                access_token = token_data["access_token"]

                # Persist token
                ADDON.setSetting("access_token", access_token)
                
                # Persist refresh_token if provided
                refresh_token = token_data.get("refresh_token")
                if refresh_token:
                    ADDON.setSetting("refresh_token", refresh_token)

                # Fetch username
                authed_api = DejaVuAPI(token=access_token)
                me = authed_api.get_me()
                username = "User"
                if me and isinstance(me, dict):
                    username = (
                        me.get("name")
                        or me.get("username")
                        or me.get("email")
                        or "User"
                    )

                ADDON.setSetting("username", username)

                xbmc.log(f"[dejaVu] Login successful: {username}", xbmc.LOGINFO)
                dialog.close()
                xbmcgui.Dialog().notification(
                    "dejaVu",
                    _ls(30032) % username,
                    xbmcgui.NOTIFICATION_INFO,
                    4000,
                )
                return True

            # Wait interval before next poll, checking for cancel every second
            for _ in range(interval):
                if dialog.iscanceled():
                    return False
                time.sleep(1)
                remaining = max(0, expires_at - time.time())
                pct = int((remaining / expires_in) * 100)
                dialog.update(pct)

        # Loop ended: code expired
        dialog.close()
        xbmcgui.Dialog().ok(_ls(30030), _ls(30035))
        return False

    finally:
        # Always close the dialog, even on exception
        try:
            dialog.close()
        except Exception:
            pass


def logout():
    """
    Clears stored credentials.
    """
    ADDON.setSetting("access_token", "")
    ADDON.setSetting("username", "")
    xbmc.log("[dejaVu] User logged out.", xbmc.LOGINFO)
    xbmcgui.Dialog().notification(
        "dejaVu",
        _ls(30040),
        xbmcgui.NOTIFICATION_INFO,
        3000,
    )


def is_logged_in():
    """Returns True if an access token is stored."""
    return bool(ADDON.getSetting("access_token"))

