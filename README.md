# dejaVu for Kodi

[dejaVu.plus](https://dejavu.plus) integration for Kodi: scrobble playback, sync watched status, ratings, watchlist, favorites, and collection.

Addon id: `script.dejavu` (Kodi 19+ / Python 3).

## Features

- Automatic scrobbling with a configurable watched threshold (default 90%)
- Resume from the last dejaVu position
- Next-episode prompt at the end of playback
- Context menus: rate, watched, watchlist, favorites, collection
- Device-code login (no password in Kodi)
- RPC API so other addons can read/write dejaVu data without an API key

## Install and login

1. Install from ZIP (or from the dejaVu repository).
2. Open **Add-on settings** → **Login with dejaVu**.
3. Open [dejavu.plus/activate](https://dejavu.plus/activate) and enter the code shown in Kodi.

Optional scrobbling settings: watched %, resume, next episode, notifications.

---

## For addon developers

`script.dejavu` is the integration layer for vStream, Elementum, and any other Kodi addon. You never talk to `dejavu.plus/api/v1` yourself: no API key, no OAuth, no HTTP. The background service is already authenticated.

Typical uses:

- Overlay **watched / rating / watchlist / favorite** badges on *your* lists
- Add/remove an item from watchlist, favorites, collection, or history
- Resolve an IMDb id or a title to a TMDB id
- Refresh those badges when the user rates something from the dejaVu context menu

IDs are **TMDB**. Status overlays work for **`movie`** and **`tv`** (the show), not for individual episodes.

### 1. Declare the dependency

In your `addon.xml`:

```xml
<requires>
    <import addon="xbmc.python" version="3.0.0"/>
    <import addon="script.dejavu" version="1.3.0"/>
</requires>
```

Do not copy `api_client.py`. You may copy `resources/lib/client.py` if you prefer not to depend on the addon at import time; keeping the import is simpler.

### 2. Import the client

`script.dejavu` exposes `resources/lib` as a Kodi Python module, so this works once the addon is installed:

```python
from client import DejaVuClient
```

Guard the import so your addon still runs if dejaVu is missing:

```python
import xbmc

def get_dejavu(timeout=5):
    if not xbmc.getCondVisibility("System.HasAddon(script.dejavu)"):
        return None
    try:
        from client import DejaVuClient
        return DejaVuClient(timeout=timeout)
    except Exception:
        return None
```

The user must also be **logged in**. If they are not, calls return `None` or `{ "success": false, ... }` after timeout. Fail soft: hide badges, keep your UI working.

`DejaVuClient(timeout=5)` waits up to 5 seconds on Window 10000 for the service reply. Use `timeout=8` for large `get_media_status` batches.

### 3. Overlay badges — `get_media_status`

This is the call you want for list screens. One round-trip, up to **50** items.

```python
dv = get_dejavu()
if not dv:
    return

status = dv.get_media_status([
    {"type": "movie", "id": 603},    # The Matrix
    {"type": "tv", "id": 1396},      # Breaking Bad
])
```

Response:

```json
{
  "success": true,
  "data": {
    "movie:603": {
      "watched": true,
      "inWatchlist": false,
      "inCollection": true,
      "isFavorite": true,
      "rating": 9,
      "watchlistPriority": null
    },
    "tv:1396": {
      "watched": true,
      "inWatchlist": true,
      "inCollection": false,
      "isFavorite": false,
      "rating": 8,
      "watchlistPriority": 2
    }
  }
}
```

Helper:

```python
def dejavu_flags(status, media_type, tmdb_id):
    data = (status or {}).get("data") or {}
    return data.get("%s:%s" % (media_type, tmdb_id)) or {}

flags = dejavu_flags(status, "movie", 603)
if flags.get("watched"):
    label = "[COLOR green]✔[/COLOR] " + title
if flags.get("rating"):
    label += "  ★%s" % flags["rating"]
if flags.get("inWatchlist"):
    label += "  [COLOR yellow]●[/COLOR]"
```

Rules:

- `type` is `"movie"` or `"tv"` only. For an episode, pass the **show** TMDB id with `"tv"`.
- `id` must be a numeric TMDB id. If you only have IMDb, call `resolve_media` first.
- Batch in chunks of 50. Prefer `minimal=True` on list endpoints when you only need ids.

### 4. Resolve identifiers — `resolve_media`

```python
# IMDb → TMDB
hit = dv.resolve_media(imdb_id="tt0133093", media_type="movie")

# Title search
hit = dv.resolve_media(title="The Matrix", media_type="movie", year=1999)
```

```json
{
  "success": true,
  "data": {
    "tmdbId": 603,
    "type": "movie",
    "title": "The Matrix",
    "imdbId": "tt0133093",
    "posterUrl": "https://image.tmdb.org/t/p/w342/...",
    "matchConfidence": "high"
  }
}
```

`matchConfidence` is `high` | `medium` | `low`. Ignore `low` matches unless you prompt the user.

### 5. Mutations (watchlist, favorites, collection, rating, watched)

Same TMDB ids. `type` is `"movie"` or `"tv"` except for history/scrobble/rate on episodes.

```python
# Toggle watchlist
flags = dejavu_flags(dv.get_media_status([{"type": "movie", "id": 603}]), "movie", 603)
if flags.get("inWatchlist"):
    dv.remove_from_watchlist("movie", 603)
else:
    dv.add_to_watchlist("movie", 603)

dv.add_to_favorites("tv", 1396)
dv.remove_from_collection("movie", 603)

dv.rate("movie", 8, tmdb_id=603)
dv.rate("episode", 7, tmdb_id=None, tv_show_id=1396, season=1, episode=1)
dv.delete_rating("movie", tmdb_id=603)

# Mark watched / unwatched
dv.add_to_history("movie", tmdb_id=603)
dv.delete_history("movie", 603)
dv.add_to_history("episode", tv_show_id=1396, season=1, episode=1)
```

Write calls that succeed also broadcast `script.dejavu.changed` (see below). A `None` return means timeout or the service is down.

### 6. Refresh overlays when dejaVu changes

Listen on a `xbmc.Monitor` so badges update after a context-menu rate/watchlist toggle, including those triggered by *your* addon or by dejaVu itself:

```python
import json
import xbmc

class DejaVuChangeMonitor(xbmc.Monitor):
    def onNotification(self, sender, method, data):
        if "script.dejavu.changed" not in method:
            return
        try:
            payload = json.loads(data) if data else {}
        except Exception:
            return
        # payload: {"action": "rate", "type": "movie", "id": 603, "rating": 8}
        self.refresh_item(payload.get("type"), payload.get("id"))
```

Useful `action` values: `add_to_watchlist`, `remove_from_watchlist`, `add_to_favorites`, `remove_from_favorites`, `add_to_collection`, `remove_from_collection`, `rate`, `delete_rating`, `add_to_history`, `delete_history`, `watched`, `unwatched`, `scrobble`, `upnext`.

At the end of an episode, dejaVu may also send `action: "upnext"` with `tvShowId`, `seasonNumber`, `episodeNumber`, `title` if you want to hook your own player.

### 7. Lists, history, up next, dashboard

Paginated reads return `{ "success": true, "data": [...], "pagination": { "page", "pageSize", "total", "totalPages", "hasMore" } }`.

Pass `minimal=True` when you only need ids (lighter, better for widgets).

```python
lists = dv.get_lists(page=1, page_size=20, minimal=True)
items = dv.get_list_items(list_id="...", page=1, page_size=20, minimal=False)

watchlist = dv.get_watchlist(media_type="movie", page=1, page_size=20, sort="addedAt:desc")
history = dv.get_history(media_type="movie", sort="watchedAt:desc", minimal=True)
upnext = dv.get_up_next(page=1, page_size=10)
scrobbles = dv.get_scrobbles(media_type="movie")  # continue watching

profile = dv.get_me()
layout = dv.get_dashboard()
widget = dv.get_dashboard_widget("continue_watching", page=1, page_size=10, minimal=True)
```

Full list payloads are already shaped for Kodi `ListItem`s (`info.title`, `info.plot`, `art.poster`, `tmdbId`, `imdbId`, …).

Dashboard `widget_type` values: `up_next`, `recent_watchlist`, `continue_watching`, `active_movie_scrobbles`, `active_tv_scrobbles`, `upcoming_releases`, `upcoming_schedule`, `list` (requires `list_id`).

### 8. Scrobble from another player addon

Only needed if you drive playback yourself and want progress on dejaVu without relying on the Kodi player hooks.

```python
# Movie
dv.scrobble("movie", progress=1200, duration=8160, tmdb_id=603)

# Episode — send the show id + S/E even if you lack the episode TMDB id
dv.scrobble(
    "episode",
    progress=800,
    duration=3000,
    tmdb_id=None,
    tv_show_id=1396,
    season=1,
    episode=1,
)
```

`progress` and `duration` are seconds. The API marks the item watched at ≥ 90%. Do **not** also call `add_to_history` for the same playback or `rewatchCount` will increment twice.

### 9. Types, parameters, and return values

| Field | Values |
|---|---|
| `type` on overlays / lists / watchlist / favorites / collection | `movie` \| `tv` |
| `type` on history / scrobble | `movie` \| `episode` |
| `type` on ratings | `movie` \| `tv` \| `season` \| `episode` |
| `id` / `tmdb_id` | numeric TMDB id |
| `tvShowId` | show TMDB id (episodes) |
| `minimal` | `True` for id-only payloads |

Client methods return:

- `dict` — API envelope, usually `{ "success": true, "data": ... }`
- `None` — timeout, addon missing, parse error, or HTTP failure in the service

On unknown RPC actions the service writes `{ "success": false, "error": "Unknown action: ..." }`.

### 10. Raw `NotifyAll` (optional)

You do not need this if you use `DejaVuClient`. The protocol:

1. Caller sends `NotifyAll(<your.addon.id>, script.dejavu.<action>, <json>)`.
2. JSON may include `result_property` (default `script.dejavu.<action>.result`).
3. The service writes the JSON result on **Window 10000**.
4. Poll that property until it is set or you time out.

```python
import json
import time
import xbmc
import xbmcgui

window = xbmcgui.Window(10000)
prop = "my.addon.media_status"
window.clearProperty(prop)
payload = json.dumps({
    "result_property": prop,
    "items": [{"type": "movie", "id": 603}],
})
xbmc.executebuiltin("NotifyAll(plugin.video.myaddon, script.dejavu.get_media_status, %s)" % payload)

deadline = time.time() + 5
result = None
monitor = xbmc.Monitor()
while time.time() < deadline:
    raw = window.getProperty(prop)
    if raw:
        result = json.loads(raw)
        break
    if monitor.waitForAbort(0.1):
        break
```

`DejaVuClient.call("get_media_status", {"items": [...]})` is the same thing.

### Action reference

**Read**

| Action | Params |
|---|---|
| `get_media_status` | `items` — `[{type, id}, ...]` max 50 |
| `get_watchlist` | `type`, `page`, `page_size`, `sort`, `minimal` |
| `get_history` | `type`, `page`, `page_size`, `sort`, `minimal` |
| `get_ratings` | `type`, `page`, `page_size`, `minimal` |
| `get_favorites` | `type`, `page`, `page_size`, `minimal` |
| `get_collection` | `type`, `page`, `page_size`, `sort`, `format`, `minimal` |
| `get_up_next` | `page`, `page_size`, `minimal` |
| `get_scrobbles` | `type`, `page`, `page_size`, `minimal` |
| `get_lists` | `page`, `page_size`, `minimal` |
| `get_list_items` | `list_id`, `page`, `page_size`, `minimal` |
| `get_dashboard` | — |
| `get_dashboard_widget` | `widget_type`, `list_id`, `page`, `page_size`, `minimal` |
| `get_me` | — |
| `resolve_media` | `imdb_id`, `tmdb_id`, `type`, `title`, `year` |

**Write**

| Action | Params |
|---|---|
| `add_to_watchlist` / `remove_from_watchlist` | `type`, `id` (`priority`, `notes` on add) |
| `add_to_history` | `type`, `id`, `count`, `watched_at`, `tvShowId`, `seasonNumber`, `episodeNumber` |
| `delete_history` | `type`, `id` |
| `add_to_favorites` / `remove_from_favorites` | `type`, `id` |
| `add_to_collection` / `remove_from_collection` | `type`, `id` (`format`, `notes` on add) |
| `create_list` | `name`, `description`, `visibility` (`PRIVATE` \| `PUBLIC`) |
| `add_to_list` / `remove_from_list` | `list_id`, `type`, `id` |
| `rate` | `type`, `id`, `rating` (1–10), `tvShowId`, `seasonNumber`, `episodeNumber`, `review` |
| `delete_rating` | `type`, `id`, `tvShowId`, `seasonNumber` |
| `scrobble` | `type`, `id`, `progress`, `duration`, `tvShowId`, `seasonNumber`, `episodeNumber` |
| `delete_scrobble` | `type`, `id` |

### Checklist for a first integration

1. Depend on `script.dejavu` ≥ 1.3.0 and import `DejaVuClient` behind `System.HasAddon`.
2. Map your items to TMDB (`resolve_media` if you only have IMDb or a title).
3. Call `get_media_status` in batches of 50 and paint badges from `data["movie:123"]`.
4. Wire one write (watchlist toggle is enough) and listen for `script.dejavu.changed`.
5. Treat `None` / missing addon / logged-out user as “no badges”, not as a crash.

## License

MIT — see [LICENSE.txt](LICENSE.txt).
