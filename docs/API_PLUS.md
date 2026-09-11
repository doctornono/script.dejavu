# dejaVu.plus API additions (Kodi listing layer)

These endpoints are consumed only by `script.dejavu`. Other Kodi addons never call `dejavu.plus` — they use `DejaVuClient`.

Auth: same Bearer / `x-api-key` as the rest of `/api/v1`. All responses use the v1 envelope `{ "success": true, "data": … }`.

The Kodi client **tolerates HTTP 404**: TTL cache, omitted fields, or unitary `POST /media/resolve`. Do not ship Kodi assuming these exist until 404 fallbacks are tested.

---

## `GET /api/v1/sync/last_activities`

Trakt-like sync cursor. Timestamps are UTC ISO-8601. Bump a field when that collection changes for the signed-in user.

```json
{
  "success": true,
  "data": {
    "all": "2026-09-11T19:00:00.000Z",
    "watchlist": "2026-09-11T19:00:00.000Z",
    "history": "2026-09-11T18:40:00.000Z",
    "ratings": "2026-09-10T12:00:00.000Z",
    "favorites": "2026-09-09T09:00:00.000Z",
    "collection": "2026-09-08T08:00:00.000Z",
    "lists": "2026-09-07T07:00:00.000Z",
    "scrobbles": "2026-09-11T19:00:00.000Z"
  }
}
```

`all` is the max of the others. Idempotent. No request body.

Kodi fallback on 404: treat the whole snapshot as stale after 15 minutes and page existing list endpoints.

---

## `POST /api/v1/media/status` (existing, extended)

Request unchanged: `{ "items": [ { "type", "id", "tmdbId?", "seasonNumber?", "episodeNumber?" }, … ] }` max 50. Types: `movie` | `tv` | `episode`.

Each `data` entry may add these **optional** fields (omit when unknown):

| Field | Types | Meaning |
|---|---|---|
| `progress` | movie, episode | Seconds played (continue watching) |
| `duration` | movie, episode | Total runtime seconds |
| `inProgress` | movie, episode | Active scrobble / resume |
| `watchedEpisodes` | tv | Episodes marked watched |
| `airedEpisodes` | tv | Episodes aired so far |
| `lastWatchedAt` | tv | Same idea as show-level `watchedAt` |

Existing fields stay: `watched`, `rewatchCount`, `watchedAt`, `inWatchlist`, `inCollection`, `isFavorite`, `rating`, `watchlistPriority`.

Kodi ignores unknown keys and does not require the new ones.

---

## `POST /api/v1/media/show-progress`

Batch show progress for listing addons (« 4/10 », hide finished seasons). Max **20** TMDB show ids.

```json
{ "ids": [1396, 1399] }
```

```json
{
  "success": true,
  "data": {
    "1396": {
      "watchedEpisodes": 40,
      "airedEpisodes": 62,
      "lastWatchedAt": "2026-09-11T19:00:00.000Z",
      "next": {
        "seasonNumber": 5,
        "episodeNumber": 3,
        "tmdbId": 62099,
        "title": "…"
      },
      "seasons": [
        {
          "seasonNumber": 1,
          "watched": 7,
          "aired": 7,
          "episodes": { "1": true, "2": true }
        }
      ]
    }
  }
}
```

`next` may be `null` when the show is complete. `episodes` maps episode number → watched. Unknown ids are omitted.

Kodi fallback on 404: RPC returns `{ "success": false, "error": "not_found" }`. Hosts must fail soft.

---

## `POST /api/v1/media/resolve/batch`

Max **50** items. Each item is the same shape as unitary resolve: `{ "imdbId?", "tmdbId?", "type?", "title?", "year?" }`.

```json
{
  "items": [
    { "imdbId": "tt0133093", "type": "movie" },
    { "title": "The Matrix", "type": "movie", "year": 1999 }
  ]
}
```

`data` is a map. Prefer `imdbId` as the key when present; otherwise use the **0-based index as a string** (`"0"`, `"1"`).

Each value matches `POST /media/resolve`:

```json
{
  "tmdbId": 603,
  "type": "movie",
  "title": "The Matrix",
  "imdbId": "tt0133093",
  "posterUrl": "https://image.tmdb.org/t/p/w342/…",
  "matchConfidence": "high"
}
```

`matchConfidence`: `high` | `medium` | `low`. Unresolved items are omitted.

Kodi fallback on 404: loop `POST /media/resolve` internally. Hosts always call `resolve_media_batch`.
