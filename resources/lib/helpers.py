# -*- coding: utf-8 -*-
"""
Public helpers for host addons (vStream, alkoFlix, skins).

    from helpers import get_dejavu, auth_state, dejavu_flags

Do not call https://dejavu.plus from your addon. Do not copy api_client.py.
"""

import xbmc
import xbmcaddon


def user_display_name(user):
    if not isinstance(user, dict):
        return ""
    return (
        user.get("name")
        or user.get("username")
        or user.get("displayName")
        or user.get("email")
        or ""
    )


def script_session():
    """Read the dejaVu session from session.json (settings as fallback)."""
    if not xbmc.getCondVisibility("System.HasAddon(script.dejavu)"):
        return None
    token = ""
    username = ""
    try:
        import json
        import xbmcvfs
        path = xbmcvfs.translatePath(
            "special://profile/addon_data/script.dejavu/session.json"
        )
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle) or {}
        token = data.get("access_token") or ""
        username = data.get("username") or ""
    except Exception:
        pass
    try:
        script = xbmcaddon.Addon("script.dejavu")
    except Exception:
        if not token:
            return None
        return {"token": token, "username": username}
    return {
        "token": token or script.getSetting("access_token") or "",
        "username": username or script.getSetting("username") or "",
    }


def get_dejavu(timeout=5):
    if not xbmc.getCondVisibility("System.HasAddon(script.dejavu)"):
        return None
    try:
        from client import DejaVuClient
        return DejaVuClient(timeout=timeout)
    except Exception:
        return None


def auth_state(timeout=5, probe_rpc=False):
    """
    One session: script.dejavu. A missing token is logged out.
    An RPC timeout is not a logout — use probe_rpc only for reachability.
    """
    session = script_session()
    if session is None:
        return {
            "installed": False,
            "authenticated": False,
            "name": "",
            "user": {},
            "client": None,
            "reachable": False,
        }

    authenticated = bool(session["token"])
    name = session["username"]
    dv = get_dejavu(timeout=timeout)
    user = {}
    reachable = None

    if probe_rpc and dv and authenticated:
        me = dv.get_me()
        if me is None:
            reachable = False
        else:
            reachable = True
            user, _stats = unwrap_me(me)
            name = user_display_name(user) or name or "?"

    if authenticated and not name:
        name = "?"

    return {
        "installed": True,
        "authenticated": authenticated,
        "name": name,
        "user": user,
        "client": dv,
        "reachable": reachable,
    }


def dejavu_flags(status, media_type, tmdb_id, show_tmdb_id=None, season=None, episode=None):
    from pure import status_flags
    return status_flags(
        status, media_type, tmdb_id,
        show_tmdb_id=show_tmdb_id, season=season, episode=episode,
    )


def unwrap_data(result):
    from pure import unwrap_data as _unwrap
    return _unwrap(result)


def unwrap_list(result):
    from pure import list_rows_from_result
    return list_rows_from_result(result)


def unwrap_me(result):
    if not isinstance(result, dict):
        return {}, {}
    user = result.get("user")
    stats = result.get("stats")
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    if not user:
        user = data.get("user") or data
    if not stats:
        stats = data.get("stats") or {}
    if not isinstance(user, dict):
        user = {}
    if not isinstance(stats, dict):
        stats = {}
    return user, stats


def rpc_ok(result):
    if result is None:
        return False
    if isinstance(result, dict) and result.get("success") is False:
        return False
    return True
