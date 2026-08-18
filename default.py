# -*- coding: utf-8 -*-
"""
dejaVu default.py
Handles all user-invoked actions:
  - action=login             → device code login flow
  - action=logout            → clear credentials
  - action=rate              → rating dialog (context menu, with remove + preselect)
  - action=toggle_watched    → mark as watched / unwatched
  - action=toggle_watchlist  → add or remove from watchlist
  - action=toggle_favorites  → add or remove from favorites
  - action=toggle_collection → add (format picker) or remove from collection
  - action=add_to_list       → pick a custom list (add or remove)
  - action=add_to_*          → aliases kept for compatibility
  - action=settings          → open addon settings
  - (no args)                → Programs menu
"""


import sys
import xbmc
import xbmcgui
import xbmcaddon

ADDON = xbmcaddon.Addon()

FORMAT_LABELS = ["(none)", "Blu-ray", "DVD", "Digital", "4K UHD", "VHS"]
FORMAT_VALUES = ["",       "bluray",  "dvd", "digital", "uhd",    "vhs"]


def _ls(string_id):
    return ADDON.getLocalizedString(string_id)


def _notify_ok(msg_id):
    xbmcgui.Dialog().notification("dejaVu", _ls(msg_id), xbmcgui.NOTIFICATION_INFO, 3000)


def _notify_err(msg_id):
    xbmcgui.Dialog().notification("dejaVu", _ls(msg_id), xbmcgui.NOTIFICATION_ERROR)


def _api_and_info():
    from resources.lib.api_client import DejaVuAPI
    from resources.lib.util import get_listitem_media_info, resolve_listitem_tmdb

    api = DejaVuAPI()
    info = resolve_listitem_tmdb(api, get_listitem_media_info())
    return api, info


def _require_tmdb(info):
    tmdb_id = info.get("tmdb_id") or info.get("show_tmdb_id")
    if not tmdb_id or not str(tmdb_id).isdigit():
        _notify_err(30019)
        return None
    return tmdb_id


def _status_entry(api, info):
    from resources.lib.util import status_for

    api_type = info.get("api_type") or "movie"
    tmdb_id = info.get("tmdb_id") if api_type == "movie" else (
        info.get("show_tmdb_id") or info.get("tmdb_id")
    )
    if api_type == "tv" and info.get("dbtype") == "episode":
        tmdb_id = info.get("show_tmdb_id") or tmdb_id
    if not tmdb_id or not str(tmdb_id).isdigit():
        return {}, api_type, tmdb_id
    result = api.get_media_status([{"type": api_type, "id": int(tmdb_id)}])
    return status_for(result, api_type, tmdb_id), api_type, tmdb_id


def _list_target(info):
    """movie/tv + TMDB id for list, watchlist, favorites, collection."""
    if info.get("dbtype") == "episode":
        return "tv", info.get("show_tmdb_id") or info.get("tmdb_id")
    api_type = info.get("api_type") or "movie"
    tmdb_id = info.get("tmdb_id")
    if api_type == "tv":
        tmdb_id = info.get("show_tmdb_id") or tmdb_id
    return api_type, tmdb_id


# ---------------------------------------------------------------------------
# Rating dialog (triggered from context menu on a video item)
# ---------------------------------------------------------------------------

def rate_dialog():
    """Shows a 1-10 rating dialog, pre-filled, with an option to remove the rating."""
    api, info = _api_and_info()
    status, api_type, status_id = _status_entry(api, info)

    dbtype = info.get("dbtype") or ""
    tmdb_id = info.get("tmdb_id")
    show_tmdb = info.get("show_tmdb_id")
    season = info.get("season")
    episode = info.get("episode")

    if dbtype == "tvshow":
        rate_type = "tv"
        tmdb_id = tmdb_id or show_tmdb
    elif dbtype == "season":
        rate_type = "season"
        show_tmdb = show_tmdb or tmdb_id
    elif dbtype == "episode":
        rate_type = "episode"
    else:
        rate_type = "movie"

    if not tmdb_id and not (rate_type == "episode" and show_tmdb and season and episode):
        _notify_err(30019)
        return

    current = status.get("rating") if rate_type in ("movie", "tv") else None
    ratings = [str(i) for i in range(10, 0, -1)]
    options = [_ls(30098)] + ratings
    preselect = 0
    if current:
        try:
            preselect = options.index(str(int(current)))
        except ValueError:
            preselect = 0

    try:
        selected = xbmcgui.Dialog().select(_ls(30017), options, preselect=preselect)
    except TypeError:
        selected = xbmcgui.Dialog().select(_ls(30017), options)
    if selected < 0:
        return

    from resources.lib.util import notify_changed, sync_kodi_library

    if selected == 0:
        result = api.delete_rating(
            rate_type,
            tmdb_id=tmdb_id,
            tv_show_id=show_tmdb or None,
            season=season,
        )
        if result is None:
            _notify_err(30019)
            return
        _notify_ok(30076)
        notify_changed("delete_rating", rate_type, tmdb_id)
        sync_kodi_library(info, rating=0)
        return

    rating = int(ratings[selected - 1])
    result = api.rate(
        rate_type,
        rating,
        tmdb_id=tmdb_id,
        tv_show_id=show_tmdb or None,
        season=season,
        episode=episode,
    )
    if result is None:
        _notify_err(30019)
        return

    xbmcgui.Dialog().notification(
        "dejaVu", _ls(30018) % rating, xbmcgui.NOTIFICATION_INFO, 3000
    )
    notify_changed("rate", rate_type, tmdb_id, extra={"rating": rating})
    sync_kodi_library(info, rating=rating)

    if rate_type == "episode" and (show_tmdb or tmdb_id):
        if xbmcgui.Dialog().yesno("dejaVu", _ls(30077)):
            show_id = show_tmdb or tmdb_id
            show_result = api.rate("tv", rating, tmdb_id=show_id)
            if show_result is not None:
                notify_changed("rate", "tv", show_id, extra={"rating": rating})
                sync_kodi_library(
                    {**info, "dbtype": "tvshow", "tmdb_id": show_id, "show_tmdb_id": show_id},
                    rating=rating,
                )


# ---------------------------------------------------------------------------
# Context menu — Watched toggle
# ---------------------------------------------------------------------------

def toggle_watched():
    api, info = _api_and_info()
    from resources.lib.util import notify_changed, sync_kodi_library, status_for

    dbtype = info.get("dbtype") or ""
    tmdb_id = info.get("tmdb_id")
    show_tmdb = info.get("show_tmdb_id")
    season = info.get("season")
    episode = info.get("episode")

    if dbtype == "episode":
        if not (tmdb_id or (show_tmdb and season and episode)):
            _notify_err(30019)
            return
        choice = xbmcgui.Dialog().select(_ls(30078), [_ls(30092), _ls(30093)])
        if choice < 0:
            return
        mark_watched = choice == 0
        if mark_watched:
            result = api.add_to_history(
                "episode",
                tmdb_id=tmdb_id or None,
                tv_show_id=show_tmdb or None,
                season=season,
                episode=episode,
            )
        else:
            if not tmdb_id:
                _notify_err(30019)
                return
            result = api.delete_history("episode", tmdb_id)
        if result is None:
            _notify_err(30097)
            return
        sync_kodi_library(info, watched=mark_watched)
        _notify_ok(30052 if mark_watched else 30079)
        notify_changed("watched" if mark_watched else "unwatched", "episode", tmdb_id)
        return

    tmdb_id = _require_tmdb(info)
    if not tmdb_id:
        return

    if dbtype in ("tvshow", "tv", "season"):
        # History write is per movie/episode, not per series
        _notify_err(30097)
        return

    result = api.get_media_status([{"type": "movie", "id": int(tmdb_id)}])
    watched = bool(status_for(result, "movie", tmdb_id).get("watched"))

    if watched:
        result = api.delete_history("movie", tmdb_id)
        mark_watched = False
    else:
        result = api.add_to_history("movie", tmdb_id=tmdb_id)
        mark_watched = True
    if result is None:
        _notify_err(30097)
        return
    sync_kodi_library(info, watched=mark_watched)
    _notify_ok(30052 if mark_watched else 30079)
    notify_changed("watched" if mark_watched else "unwatched", "movie", tmdb_id)


# ---------------------------------------------------------------------------
# Context menu — Watchlist / Favorites / Collection toggles
# ---------------------------------------------------------------------------

def toggle_watchlist():
    api, info = _api_and_info()
    from resources.lib.util import notify_changed

    status, api_type, tmdb_id = _status_entry(api, info)
    if not tmdb_id:
        _notify_err(30019)
        return
    if info.get("dbtype") == "episode":
        api_type = "tv"
        tmdb_id = info.get("show_tmdb_id") or tmdb_id
        if not tmdb_id:
            _notify_err(30019)
            return
        status, _, _ = _status_entry(api, {**info, "api_type": "tv", "tmdb_id": tmdb_id})

    if status.get("inWatchlist"):
        result = api.remove_from_watchlist(api_type, tmdb_id)
        ok_id, action = 30094, "remove_from_watchlist"
        err_id = 30085
    else:
        result = api.add_to_watchlist(api_type, tmdb_id)
        ok_id, action = 30084, "add_to_watchlist"
        err_id = 30085
    if result is None:
        _notify_err(err_id)
        return
    _notify_ok(ok_id)
    notify_changed(action, api_type, tmdb_id)


def toggle_favorites():
    api, info = _api_and_info()
    from resources.lib.util import notify_changed

    status, api_type, tmdb_id = _status_entry(api, info)
    if not tmdb_id:
        _notify_err(30019)
        return
    if info.get("dbtype") == "episode":
        api_type = "tv"
        tmdb_id = info.get("show_tmdb_id") or tmdb_id
        if not tmdb_id:
            _notify_err(30019)
            return
        status, _, _ = _status_entry(api, {**info, "api_type": "tv", "tmdb_id": tmdb_id})

    if status.get("isFavorite"):
        result = api.remove_from_favorites(api_type, tmdb_id)
        ok_id, action = 30095, "remove_from_favorites"
        err_id = 30088
    else:
        result = api.add_to_favorites(api_type, tmdb_id)
        ok_id, action = 30087, "add_to_favorites"
        err_id = 30088
    if result is None:
        _notify_err(err_id)
        return
    _notify_ok(ok_id)
    notify_changed(action, api_type, tmdb_id)


def toggle_collection():
    api, info = _api_and_info()
    from resources.lib.util import notify_changed

    status, api_type, tmdb_id = _status_entry(api, info)
    if not tmdb_id:
        _notify_err(30019)
        return
    if info.get("dbtype") == "episode":
        api_type = "tv"
        tmdb_id = info.get("show_tmdb_id") or tmdb_id
        if not tmdb_id:
            _notify_err(30019)
            return
        status, _, _ = _status_entry(api, {**info, "api_type": "tv", "tmdb_id": tmdb_id})

    if status.get("inCollection"):
        result = api.remove_from_collection(api_type, tmdb_id)
        if result is None:
            _notify_err(30082)
            return
        _notify_ok(30096)
        notify_changed("remove_from_collection", api_type, tmdb_id)
        return

    sel = xbmcgui.Dialog().select(_ls(30091), FORMAT_LABELS)
    if sel < 0:
        return
    fmt = FORMAT_VALUES[sel] or None
    result = api.add_to_collection(api_type, tmdb_id, fmt=fmt)
    if result is None:
        _notify_err(30082)
        return
    _notify_ok(30081)
    notify_changed("add_to_collection", api_type, tmdb_id)


# ---------------------------------------------------------------------------
# Context menu — custom lists
# ---------------------------------------------------------------------------

def add_to_list_dialog():
    """Add or remove the focused item from a user list."""
    api, info = _api_and_info()
    from resources.lib.util import notify_changed, unwrap_data

    api_type, tmdb_id = _list_target(info)
    if not tmdb_id or not str(tmdb_id).isdigit():
        _notify_err(30019)
        return

    result = api.get_lists(page=1, page_size=50, minimal=True)
    lists = unwrap_data(result) or []
    if isinstance(lists, dict):
        lists = lists.get("lists") or lists.get("data") or []
    if not isinstance(lists, list) or not lists:
        _notify_err(30102)
        return

    entries = [lst for lst in lists if isinstance(lst, dict)]
    labels = []
    for lst in entries:
        name = (
            lst.get("name")
            or (lst.get("info") or {}).get("title")
            or str(lst.get("id") or "")
        )
        labels.append(name)
    if not labels:
        _notify_err(30102)
        return

    sel = xbmcgui.Dialog().select(_ls(30101), labels)
    if sel < 0:
        return

    chosen = entries[sel]
    list_id = chosen.get("id")
    list_name = labels[sel]
    if not list_id:
        _notify_err(30105)
        return

    items_res = api.get_list_items(list_id, page=1, page_size=100, minimal=True)
    items = unwrap_data(items_res) or []
    if isinstance(items, dict):
        items = items.get("items") or items.get("data") or []
    already = False
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id") or item.get("tmdbId")
        item_type = item.get("type")
        if str(item_id) == str(tmdb_id) and (not item_type or item_type == api_type):
            already = True
            break

    if already:
        result = api.remove_from_list(list_id, api_type, tmdb_id)
        if result is None:
            _notify_err(30105)
            return
        xbmcgui.Dialog().notification(
            "dejaVu", _ls(30104) % list_name, xbmcgui.NOTIFICATION_INFO, 3000
        )
        notify_changed("remove_from_list", api_type, tmdb_id, extra={"list_id": list_id})
        return

    result = api.add_to_list(list_id, api_type, tmdb_id)
    if result is None:
        _notify_err(30105)
        return
    xbmcgui.Dialog().notification(
        "dejaVu", _ls(30103) % list_name, xbmcgui.NOTIFICATION_INFO, 3000
    )
    notify_changed("add_to_list", api_type, tmdb_id, extra={"list_id": list_id})


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
    elif "action=toggle_watched" in params:
        toggle_watched()
    elif "action=toggle_watchlist" in params or "action=add_to_watchlist" in params:
        toggle_watchlist()
    elif "action=toggle_favorites" in params or "action=add_to_favorites" in params:
        toggle_favorites()
    elif "action=toggle_collection" in params or "action=add_to_collection" in params:
        toggle_collection()
    elif "action=add_to_list" in params:
        add_to_list_dialog()
    elif "action=settings" in params:
        ADDON.openSettings()
    else:
        main_menu()


if __name__ == "__main__":
    main()
