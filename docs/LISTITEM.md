# ListItem contract (host addons)

For the native **dejaVu** context item and the scrobbler to see your rows, set these fields on every movie / show / season / episode `ListItem`.

Do **not** add a second dejaVu submenu. Paint badges with `get_media_status`. Listen for `script.dejavu.changed` and refresh. Never call `dejavu.plus`. Treat `None` as “no badges”, not as a crash.

## Required

| Field | Values | Why |
|---|---|---|
| `setUniqueIDs({"tmdb": "603"}, "tmdb")` | numeric TMDB id | Menu + scrobble |
| `mediatype` / property `DBType` | `movie` \| `tvshow` \| `season` \| `episode` | Context XML visibility |

If you have IMDb, also set `imdb` on UniqueIDs (`tt…`).

## Episodes

Set **all** of:

- episode TMDB UniqueID when you have it
- show TMDB: property `tvshow_tmdb_id` and `TVShowID`
- `season` / `episode` numbers

Then overlay with `get_media_status([{"type": "episode", "id": 62085, "tmdbId": 1396, "seasonNumber": 1, "episodeNumber": 1}])`.

## Fallback properties

`sys.listitem` UniqueIDs are often empty in context menus. Also set:

- `tmdb_id` and `TmdbId`
- `imdb_id` when known

Plugin query `tmdb_id=` or path `/tmdb/123` is also accepted.

## Copy-paste

```python
from helpers import get_dejavu, dejavu_flags

item.setUniqueIDs({"tmdb": "603", "imdb": "tt0133093"}, "tmdb")
item.setInfo("video", {"title": title, "mediatype": "movie"})
item.setProperty("DBType", "movie")
item.setProperty("tmdb_id", "603")
item.setProperty("TmdbId", "603")

dv = get_dejavu(timeout=8)
status = dv.get_media_status([{"type": "movie", "id": 603}]) if dv else None
flags = dejavu_flags(status, "movie", 603)
if flags.get("watched"):
    item.setInfo("video", {"title": title, "mediatype": "movie", "playcount": 1})
```

Full RPC catalogue: [DEVELOPERS.md](DEVELOPERS.md). Plus HTTP (script.dejavu only): [API_PLUS.md](API_PLUS.md).
