# -*- coding: utf-8 -*-
"""
dejaVu default.py
Handles all user-invoked actions:
  - action=login             → device code login flow
  - action=logout            → clear credentials
  - action=rate              → rating dialog (context menu)
  - action=add_to_collection → add to collection dialog (context menu)
  - action=add_to_watchlist  → add to watchlist (context menu)
  - action=add_to_favorites  → add to favorites (context menu)
  - action=settings          → open addon settings
  - (no args)                → Programs menu
"""

import sys
import xbmc
import xbmcgui
import xbmcaddon

ADDON = xbmcaddon.Addon()


def _ls(string_id):
    return ADDON.getLocalizedString(string_id)


# ---------------------------------------------------------------------------
# Rating dialog (triggered from context menu on a video item)
# ---------------------------------------------------------------------------

def rate_dialog():
    """Shows a 1-10 rating dialog for the currently focused ListItem."""
    ratings = [str(i) for i in range(10, 0, -1)]
    selected = xbmcgui.Dialog().select(_ls(30017), ratings)

    if selected < 0:
        return  # cancelled

    rating = int(ratings[selected])

    media_type = (
        xbmc.getInfoLabel("ListItem.DBType")
        or xbmc.getInfoLabel("ListItem.Property(DBType)")
        or ""
    )
    tmdb_id = xbmc.getInfoLabel("ListItem.UniqueID(tmdb)")

    if not tmdb_id:
        xbmcgui.Dialog().notification("dejaVu", _ls(30019), xbmcgui.NOTIFICATION_ERROR)
        return

    from resources.lib.api_client import DejaVuAPI
    api = DejaVuAPI()
    result = None

    if media_type == "movie":
        result = api.rate("movie", rating, tmdb_id=tmdb_id)

    elif media_type == "tvshow":
        result = api.rate("tv", rating, tmdb_id=tmdb_id)

    elif media_type == "season":
        season = xbmc.getInfoLabel("ListItem.Season")
        show_tmdb = xbmc.getInfoLabel("ListItem.TVShowUniqueID(tmdb)") or tmdb_id
        result = api.rate(
            "season",
            rating,
            tmdb_id=tmdb_id,
            tv_show_id=show_tmdb or None,
            season=int(season) if season else None
        )

    elif media_type == "episode":
        season  = xbmc.getInfoLabel("ListItem.Season")
        episode = xbmc.getInfoLabel("ListItem.Episode")
        show_tmdb = xbmc.getInfoLabel("ListItem.TVShowUniqueID(tmdb)") or xbmc.getInfoLabel("ListItem.UniqueID(tvshow_tmdb)")
        
        result = api.rate(
            "episode",
            rating,
            tmdb_id=tmdb_id,
            tv_show_id=show_tmdb or None,
            season=int(season) if season else None,
            episode=int(episode) if episode else None,
        )
    else:
        # Fallback: treat as movie
        result = api.rate("movie", rating, tmdb_id=tmdb_id)

    if result is None:
        xbmcgui.Dialog().notification("dejaVu", _ls(30019), xbmcgui.NOTIFICATION_ERROR)
        return

    xbmcgui.Dialog().notification(
        "dejaVu",
        _ls(30018) % rating,
        xbmcgui.NOTIFICATION_INFO,
        3000,
    )

# ---------------------------------------------------------------------------
# Shared helper: extract media type + TMDB ID from the current ListItem
# ---------------------------------------------------------------------------

FORMAT_LABELS = ["(none)", "Blu-ray", "DVD", "Digital", "4K UHD", "VHS"]
FORMAT_VALUES = ["",       "bluray",  "dvd", "digital", "uhd",    "vhs"]


def _get_media_info():
    """
    Returns (api_type, tmdb_id) for the currently focused ListItem.
    api_type : "movie" | "tv"  (normalised from Kodi's "tvshow")
    tmdb_id  : string TMDB ID, or empty string if not found
    Reads both the Kodi library fields and custom plugin properties as fallback.
    """
    media_type = (
        xbmc.getInfoLabel("ListItem.DBType")
        or xbmc.getInfoLabel("ListItem.Property(DBType)")
        or xbmc.getInfoLabel("ListItem.Property(media_type)")
        or ""
    )
    tmdb_id = (
        xbmc.getInfoLabel("ListItem.UniqueID(tmdb)")
        or xbmc.getInfoLabel("ListItem.Property(tmdb_id)")
        or ""
    )
    # Kodi uses "tvshow"; the dejaVu API expects "tv"
    api_type = "tv" if media_type == "tvshow" else media_type
    return api_type, tmdb_id


# ---------------------------------------------------------------------------
# Context menu — Add to Collection
# ---------------------------------------------------------------------------

def add_to_collection_dialog():
    """Asks for a physical format then adds the item to the user's collection."""
    api_type, tmdb_id = _get_media_info()

    if not tmdb_id:
        xbmcgui.Dialog().notification("dejaVu", _ls(30019), xbmcgui.NOTIFICATION_ERROR)
        return

    sel = xbmcgui.Dialog().select(_ls(30080), FORMAT_LABELS)
    if sel < 0:
        return  # cancelled

    from resources.lib.api_client import DejaVuAPI
    api = DejaVuAPI()
    fmt = FORMAT_VALUES[sel] or None
    result = api.add_to_collection(api_type, tmdb_id, fmt=fmt)

    if result is not None:
        xbmcgui.Dialog().notification(
            "dejaVu", _ls(30081), xbmcgui.NOTIFICATION_INFO, 3000
        )
    else:
        xbmcgui.Dialog().notification(
            "dejaVu", _ls(30082), xbmcgui.NOTIFICATION_ERROR
        )


# ---------------------------------------------------------------------------
# Context menu — Add to Watchlist
# ---------------------------------------------------------------------------

def add_to_watchlist_dialog():
    """Adds the focused item to the user's watchlist."""
    api_type, tmdb_id = _get_media_info()

    if not tmdb_id:
        xbmcgui.Dialog().notification("dejaVu", _ls(30019), xbmcgui.NOTIFICATION_ERROR)
        return

    from resources.lib.api_client import DejaVuAPI
    api = DejaVuAPI()
    result = api.add_to_watchlist(api_type, tmdb_id)

    if result is not None:
        xbmcgui.Dialog().notification(
            "dejaVu", _ls(30084), xbmcgui.NOTIFICATION_INFO, 3000
        )
    else:
        xbmcgui.Dialog().notification(
            "dejaVu", _ls(30085), xbmcgui.NOTIFICATION_ERROR
        )


# ---------------------------------------------------------------------------
# Context menu — Add to Favorites
# ---------------------------------------------------------------------------

def add_to_favorites_dialog():
    """Adds the focused item to the user's favorites."""
    api_type, tmdb_id = _get_media_info()

    if not tmdb_id:
        xbmcgui.Dialog().notification("dejaVu", _ls(30019), xbmcgui.NOTIFICATION_ERROR)
        return

    from resources.lib.api_client import DejaVuAPI
    api = DejaVuAPI()
    result = api.add_to_favorites(api_type, tmdb_id)

    if result is not None:
        xbmcgui.Dialog().notification(
            "dejaVu", _ls(30087), xbmcgui.NOTIFICATION_INFO, 3000
        )
    else:
        xbmcgui.Dialog().notification(
            "dejaVu", _ls(30088), xbmcgui.NOTIFICATION_ERROR
        )


def main_menu():
    """Simple select dialog shown when the addon is launched from Programs."""
    from resources.lib.auth_handler import is_logged_in

    if is_logged_in():
        username = ADDON.getSetting("username") or "?"
        options = [
            f"{_ls(30003)} ({username})",   # Logout (username)
            _ls(30062),                     # Settings
        ]
        selected = xbmcgui.Dialog().select("dejaVu", options)
        if selected == 0:
            from resources.lib.auth_handler import logout
            logout()
        elif selected == 1:
            ADDON.openSettings()
    else:
        options = [_ls(30002), _ls(30062)]  # Login, Settings
        selected = xbmcgui.Dialog().select("dejaVu", options)
        if selected == 0:
            from resources.lib.auth_handler import login
            login()
        elif selected == 1:
            ADDON.openSettings()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    params = sys.argv[1] if len(sys.argv) > 1 else ""
    xbmc.log(f"[dejaVu] default.py params: '{params}'", xbmc.LOGDEBUG)

    if "action=login" in params:
        from resources.lib.auth_handler import login
        login()
    elif "action=logout" in params:
        from resources.lib.auth_handler import logout
        logout()
    elif "action=rate" in params:
        rate_dialog()
    elif "action=add_to_collection" in params:
        add_to_collection_dialog()
    elif "action=add_to_watchlist" in params:
        add_to_watchlist_dialog()
    elif "action=add_to_favorites" in params:
        add_to_favorites_dialog()
    elif "action=settings" in params:
        ADDON.openSettings()
    else:
        main_menu()


if __name__ == "__main__":
    main()

