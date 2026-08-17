# dejaVu integration for Kodi

Professional integration of [dejaVu.plus](https://dejavu.plus) for Kodi. Sync your watch history, watchlist, and ratings seamlessly.

## Features

- **Automatic Scrobbling**: Real-time playback synchronization (defaults to 90% threshold for "watched" status).
- **Resume playback**: Offers to continue from the last dejaVu position.
- **Up Next**: Offers the next episode after one finishes (library playback, plus a notification for other addons).
- **Ratings Synchronization**: Rate movies and TV shows from Kodi, including removing a rating.
- **Context toggles**: Mark watched / unwatched, watchlist, favorites, and collection.
- **Unified History**: Keeps your dejavu.plus history in sync with your local playback.
- **Device Code Login**: Secure OAuth 2.0 login flow (no password needed in Kodi).
- **Background Service**: Synchronizes in the background for a seamless experience.

## Installation

1.  Download the repository as a ZIP.
2.  In Kodi, go to **Add-ons** > **Install from zip file**.
3.  Navigate to the downloaded ZIP and install.

## Configuration

1.  Open **Add-on settings**.
2.  Click **Login with dejaVu**.
3.  Visit [dejavu.plus/activate](https://dejavu.plus/activate) and enter the code displayed in Kodi.
4.  Optionally, adjust the **Watched %** threshold, resume, and next-episode options in the Scrobbling section.

## For Developers (RPC API)

This addon exposes a JSON-RPC-style interface over Kodi notifications (`NotifyAll`). Other addons can use `resources/lib/client.py` (`DejaVuClient`) or send notifications directly.

Copy `client.py` into your addon (or import the `script.dejavu` module) and call:

```python
from client import DejaVuClient  # or: from script.dejavu import DejaVuClient

dv = DejaVuClient()
status = dv.get_media_status([
    {"type": "movie", "id": 603},
    {"type": "tv", "id": 1396},
])
```

After write actions, dejaVu also broadcasts `script.dejavu.changed` so overlays can refresh.

### Read actions

| Action | Params |
|---|---|
| `get_media_status` | `items` — list of `{type, id}` (max 50). Returns watched / rating / watchlist / favorite / collection. |
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

Use `minimal=true` for overlay payloads.

### Write actions

| Action | Params |
|---|---|
| `add_to_watchlist` / `remove_from_watchlist` | `type`, `id` |
| `add_to_history` / `delete_history` | `type`, `id` (+ `tvShowId`, `seasonNumber`, `episodeNumber` for add) |
| `add_to_favorites` / `remove_from_favorites` | `type`, `id` |
| `add_to_collection` / `remove_from_collection` | `type`, `id` |
| `create_list` | `name`, `description`, `visibility` |
| `add_to_list` / `remove_from_list` | `list_id`, `type`, `id` |
| `rate` / `delete_rating` | `type`, `id`, `rating` (+ show/season/episode fields) |
| `scrobble` / `delete_scrobble` | `type`, `id`, `progress`, `duration` (+ `tvShowId`, `seasonNumber`, `episodeNumber`) |

## License

This project is licensed under the MIT License - see the [LICENSE.txt](LICENSE.txt) file for details.
