"""
dejaVu default.py
Handles all user-invoked actions:
  - action=login      → device code login flow
  - action=logout     → clear credentials
  - action=rate       → rating dialog (context menu)
  - action=settings   → open addon settings
  - (no args)         → Programs menu
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
# Main Programs menu
# ---------------------------------------------------------------------------

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
    elif "action=settings" in params:
        ADDON.openSettings()
    else:
        main_menu()


if __name__ == "__main__":
    main()
