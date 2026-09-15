# RPC contenu — `script.dejavu`

Catalogue des actions **JSON-RPC inter-addons** (`NotifyAll` / `DejaVuClient`) qui **fournissent du contenu** (listes, overlays, résolution d’identifiants).

Exclu volontairement (auth / session / meta, pas du contenu) :

| Action | Raison |
|---|---|
| `is_authenticated` | session locale |
| `get_me` | profil / stats compte |
| `logout` | session |
| `authenticate` | pas du RPC `NotifyAll` (`RunScript`) |
| `get_capabilities` | feature-detect, pas de titres |
| `get_last_activities` | curseur de sync, pas de titres |

Les **écritures** (`add_to_*`, `rate`, `scrobble`, …) ne sont pas documentées ici.

IDs canoniques : **TMDB**. Enveloppe typique : `{ "success": true, "data": … }`. Timeout / service down → `DejaVuClient` retourne `None`. HTTP 404 toléré (channels, show-progress, resolve batch, last_activities) → `{ "success": false, "error": "not_found" }`.

Méthode NotifyAll : `script.dejavu.<action>`. Paramètres dans le JSON (plus `result_property` géré par le client).

---

## Enveloppe commune (listes paginées)

```json
{
  "success": true,
  "data": [ ],
  "pagination": {
    "page": 1,
    "pageSize": 20,
    "total": 42,
    "totalPages": 3,
    "hasMore": true
  }
}
```

`data` peut aussi être un objet `{ "items": […], "pagination": {…} }` — `list_rows_from_result` accepte les deux.

`minimal=true` : payload allégé (ids + timestamps). `page` défaut `1`, `page_size` défaut `20` (max API 100).

### Item média (forme ListItem, `minimal=false`)

Les listes de titres (watchlist, history, favorites, collection, ratings, list items, scrobbles, up next, widgets) sont pensées pour Kodi :

```json
{
  "type": "movie",
  "tmdbId": 603,
  "imdbId": "tt0133093",
  "title": "The Matrix",
  "year": 1999,
  "info": {
    "title": "The Matrix",
    "plot": "…",
    "year": 1999,
    "mediatype": "movie",
    "duration": 8160
  },
  "art": {
    "poster": "https://image.tmdb.org/t/p/w342/…",
    "fanart": "https://image.tmdb.org/t/p/w1280/…"
  }
}
```

Épisode (history / scrobbles / up next) — champs extra :

```json
{
  "type": "episode",
  "tmdbId": 62085,
  "tvShowId": 1396,
  "seasonNumber": 1,
  "episodeNumber": 1,
  "title": "Pilot",
  "progress": 800,
  "duration": 3000,
  "info": { "title": "Pilot", "mediatype": "episode", "season": 1, "episode": 1 }
}
```

`type` listes identité : `movie` \| `tv`. History / scrobble / up next : aussi `episode`. Ratings : aussi `season`.

---

## 1. `get_watchlist`

Liste de suivi.

| Paramètre | Type | Défaut | Valeurs |
|---|---|---|---|
| `type` | string | omit = all | `movie` \| `tv` |
| `page` | int | 1 | ≥ 1 |
| `page_size` | int | 20 | ≤ 100 |
| `sort` | string | `addedAt:desc` | `addedAt:desc` \| `addedAt:asc` \| `priority:desc` \| `priority:asc` |
| `minimal` | bool | false | |

**Client :** `dv.get_watchlist(media_type="movie", page=1, page_size=20, sort="addedAt:desc", minimal=False)`

**Retour (extrait) :**

```json
{
  "success": true,
  "data": [
    {
      "type": "movie",
      "tmdbId": 603,
      "addedAt": "2026-09-01T10:00:00.000Z",
      "priority": 2,
      "notes": null,
      "info": { "title": "The Matrix", "mediatype": "movie" },
      "art": { "poster": "https://image.tmdb.org/t/p/w342/…" }
    }
  ],
  "pagination": { "page": 1, "pageSize": 20, "total": 1, "totalPages": 1, "hasMore": false }
}
```

`minimal=true` : `id` / `tmdbId`, `addedAt`, `priority`.

---

## 2. `get_history`

Historique de visionnage.

| Paramètre | Type | Défaut | Valeurs |
|---|---|---|---|
| `type` | string | omit = all | `movie` \| `tv` \| `episode` |
| `page` | int | 1 | |
| `page_size` | int | 20 | |
| `sort` | string | `watchedAt:desc` | `watchedAt:desc` \| `watchedAt:asc` |
| `minimal` | bool | false | |

**Client :** `dv.get_history(media_type="episode", sort="watchedAt:desc")`

**Retour (extrait) :**

```json
{
  "success": true,
  "data": [
    {
      "type": "movie",
      "tmdbId": 603,
      "watchedAt": "2026-09-11T19:00:00.000Z",
      "rewatchCount": 3,
      "info": { "title": "The Matrix", "mediatype": "movie" }
    }
  ],
  "pagination": { "page": 1, "pageSize": 20, "total": 12, "totalPages": 1, "hasMore": false }
}
```

`minimal=true` : `id`, `watchedAt`, `rewatchCount`.

---

## 3. `get_ratings`

Notes utilisateur.

| Paramètre | Type | Défaut | Valeurs |
|---|---|---|---|
| `type` | string | omit = all | `movie` \| `tv` \| `season` \| `episode` |
| `page` | int | 1 | |
| `page_size` | int | 20 | |
| `minimal` | bool | false | |

Pas de `sort` (contrairement à watchlist / history / collection).

**Retour (extrait) :**

```json
{
  "success": true,
  "data": [
    {
      "type": "movie",
      "tmdbId": 603,
      "rating": 9,
      "review": null,
      "createdAt": "2026-08-01T12:00:00.000Z",
      "info": { "title": "The Matrix", "mediatype": "movie" }
    }
  ],
  "pagination": { "page": 1, "pageSize": 20, "total": 5, "totalPages": 1, "hasMore": false }
}
```

`minimal=true` : `id`, `rating`, `createdAt`.

---

## 4. `get_favorites`

| Paramètre | Type | Défaut | Valeurs |
|---|---|---|---|
| `type` | string | omit = all | `movie` \| `tv` |
| `page` | int | 1 | |
| `page_size` | int | 20 | |
| `minimal` | bool | false | |

Pas de `sort`.

**Retour (extrait) :**

```json
{
  "success": true,
  "data": [
    {
      "type": "tv",
      "tmdbId": 1396,
      "addedAt": "2026-07-01T08:00:00.000Z",
      "info": { "title": "Breaking Bad", "mediatype": "tvshow" },
      "art": { "poster": "https://image.tmdb.org/t/p/w342/…" }
    }
  ],
  "pagination": { "page": 1, "pageSize": 20, "total": 1, "totalPages": 1, "hasMore": false }
}
```

`minimal=true` : `id`, `addedAt`.

---

## 5. `get_collection`

Collection physique / digitale.

| Paramètre | Type | Défaut | Valeurs |
|---|---|---|---|
| `type` | string | omit = all | `movie` \| `tv` |
| `page` | int | 1 | |
| `page_size` | int | 20 | |
| `sort` | string | `addedAt:desc` | `addedAt:desc` \| `addedAt:asc` |
| `format` | string | omit | ex. `digital`, `bluray`, `dvd` |
| `minimal` | bool | false | |

**Client :** `dv.get_collection(media_type="movie", fmt="digital")`

**Retour (extrait) :**

```json
{
  "success": true,
  "data": [
    {
      "type": "movie",
      "tmdbId": 603,
      "format": "digital",
      "addedAt": "2026-06-01T00:00:00.000Z",
      "notes": null,
      "info": { "title": "The Matrix", "mediatype": "movie" }
    }
  ],
  "pagination": { "page": 1, "pageSize": 20, "total": 1, "totalPages": 1, "hasMore": false }
}
```

`minimal=true` : `id`, `addedAt`, `format`.

---

## 6. `get_up_next`

Prochains épisodes des séries en cours.

| Paramètre | Type | Défaut | Valeurs |
|---|---|---|---|
| `page` | int | 1 | |
| `page_size` | int | 20 | |
| `minimal` | bool | **false côté RPC** | l’API Plus défaut `minimal=true` si omis ; le client envoie explicitement |

Pas de `type`.

**Retour (extrait) :**

```json
{
  "success": true,
  "data": [
    {
      "type": "episode",
      "tmdbId": 62099,
      "tvShowId": 1396,
      "seasonNumber": 5,
      "episodeNumber": 3,
      "title": "…",
      "info": { "title": "…", "mediatype": "episode" },
      "art": { "poster": "https://image.tmdb.org/t/p/w342/…" }
    }
  ],
  "pagination": { "page": 1, "pageSize": 20, "total": 4, "totalPages": 1, "hasMore": false }
}
```

---

## 7. `get_scrobbles`

Continue watching (sessions de scrobble actives).

| Paramètre | Type | Défaut | Valeurs |
|---|---|---|---|
| `type` | string | omit = all | `movie` \| `episode` (`all`) |
| `page` | int | 1 | |
| `page_size` | int | 20 | |
| `minimal` | bool | false | |

**Retour (extrait) :**

```json
{
  "success": true,
  "data": [
    {
      "type": "movie",
      "tmdbId": 27205,
      "progress": 1200,
      "duration": 8880,
      "info": { "title": "Inception", "mediatype": "movie", "duration": 8880 }
    }
  ],
  "pagination": { "page": 1, "pageSize": 20, "total": 1, "totalPages": 1, "hasMore": false }
}
```

---

## 8. `get_lists`

Listes perso de l’utilisateur (métadonnées, pas les titres).

| Paramètre | Type | Défaut |
|---|---|---|
| `page` | int | 1 |
| `page_size` | int | 20 |
| `minimal` | bool | false |

**Retour (extrait) :**

```json
{
  "success": true,
  "data": [
    {
      "id": "clxxxxxxxx",
      "name": "Cyberpunk",
      "description": "…",
      "visibility": "PRIVATE",
      "itemsCount": 12,
      "updatedAt": "2026-09-01T00:00:00.000Z",
      "info": { "title": "Cyberpunk" }
    }
  ],
  "pagination": { "page": 1, "pageSize": 20, "total": 3, "totalPages": 1, "hasMore": false }
}
```

`minimal=true` : `id`, `name`, `itemsCount`, `updatedAt`.

---

## 9. `get_list_items`

Titres d’une liste. **`list_id` obligatoire.**

| Paramètre | Type | Défaut |
|---|---|---|
| `list_id` | string | **requis** |
| `page` | int | 1 |
| `page_size` | int | 20 |
| `minimal` | bool | false |

**Retour :** même forme que watchlist (items média + pagination).

Manque paramètre : KeyError → `{ "success": false, "error": "Missing param: 'list_id'" }`.

---

## 10. `get_channels`

Chaînes / univers (MCU, éditorial, …). Pas de `minimal`.

| Paramètre | Type | Défaut | Valeurs |
|---|---|---|---|
| `type` | string | omit = tous | `UNIVERSE` \| `EDITORIAL` \| `PLATFORM` \| `THEMATIC` \| `CREATOR` \| `AWARDS` \| `FRANCHISE` (normalisé uppercase) |
| `scope` | string | omit = explore | `mine` \| `following` |
| `page` | int | 1 | |
| `page_size` | int | 20 | |

**Client :** `dv.get_channels(channel_type="UNIVERSE", scope="following")`

**Retour :**

```json
{
  "success": true,
  "data": [
    {
      "type": "channel",
      "id": "…",
      "channelType": "universe",
      "followersCount": 12,
      "listsCount": 3,
      "slug": "marvel-cinematic-universe",
      "isVerified": true,
      "owner": { "id": "…", "name": "…" },
      "info": { "title": "Marvel Cinematic Universe", "plot": "…", "mediatype": "set" },
      "art": { "poster": "https://image.tmdb.org/t/p/w500/…", "fanart": "…" }
    }
  ],
  "pagination": { "page": 1, "pageSize": 20, "total": 8, "totalPages": 1, "hasMore": false }
}
```

404 Plus : `{ "success": false, "error": "not_found" }`.

---

## 11. `get_channel`

Détail d’une chaîne + listes attachées + preview d’items.

| Paramètre | Type | Notes |
|---|---|---|
| `channel_id` | string | **requis** (alias RPC `id`) |

Pas de pagination / `minimal`. Les titres complets d’une section : `get_list_items(list_id)` avec `list.id` du détail.

**Retour (extrait) :**

```json
{
  "success": true,
  "data": {
    "id": "…",
    "slug": "marvel-cinematic-universe",
    "channelType": "universe",
    "info": { "title": "Marvel Cinematic Universe", "plot": "…", "mediatype": "set" },
    "art": { "poster": "…", "fanart": "…" },
    "lists": [
      {
        "id": "clxxxxxxxx",
        "name": "Phase One",
        "itemsCount": 6,
        "preview": [
          { "movieId": 1726 },
          { "tvShowId": null }
        ]
      }
    ]
  }
}
```

`channel_id` vide → `{ "success": false, "error": "missing_channel_id" }`. 404 → `not_found`.

---

## 12. `get_dashboard`

Layout du dashboard (pas les titres).

Aucun paramètre.

**Retour :**

```json
{
  "success": true,
  "data": {
    "widgets": [
      {
        "id": "up_next-1",
        "type": "up_next",
        "title": "Up Next",
        "props": {},
        "apiUrl": "/api/v1/dashboard/widget?type=up_next"
      },
      {
        "id": "list-xyz",
        "type": "list",
        "title": "Cyberpunk",
        "props": { "listId": "clxxxxxxxx" },
        "apiUrl": "/api/v1/dashboard/widget?type=list&listId=clxxxxxxxx"
      }
    ],
    "filters": []
  }
}
```

`data` peut être un tableau de widgets (le démo plugin accepte les deux). Widget `stats` : à ignorer côté listing vidéo.

---

## 13. `get_dashboard_widget`

Contenu d’un widget. **`widget_type` obligatoire.**

| Paramètre | Type | Défaut | Notes |
|---|---|---|---|
| `widget_type` | string | **requis** | voir table |
| `list_id` | string | | requis si `widget_type == "list"` |
| `page` | int | 1 | |
| `page_size` | int | 20 | |
| `minimal` | bool | false | |

| `widget_type` | Contenu |
|---|---|
| `up_next` | = `get_up_next` |
| `recent_watchlist` | derniers ajouts watchlist |
| `continue_watching` | tous scrobbles actifs |
| `active_movie_scrobbles` | scrobbles films |
| `active_tv_scrobbles` | scrobbles TV |
| `upcoming_releases` | films à venir (TMDB Discover) |
| `upcoming_schedule` | séries à venir |
| `list` | items d’une liste perso |

**Retour :** enveloppe paginée d’items média (comme les autres listes).

---

## 14. `get_media_status`

Overlays (vu / note / listes) pour **jusqu’à 50** titres. Servi depuis le cache SQLite si toutes les clés sont présentes.

| Paramètre | Type | Notes |
|---|---|---|
| `items` | array | `{ "type", "id" }` ; épisode : `id` et/ou `tmdbId` (show) + `seasonNumber` + `episodeNumber` |
| `type` | | `movie` \| `tv` \| `episode` |

Le client envoie aussi `"minimal": true` (ignoré par le handler HTTP actuel).

**Client :**

```python
dv.get_media_status([
    {"type": "movie", "id": 603},
    {"type": "tv", "id": 1396},
    {"type": "episode", "id": 62085, "tmdbId": 1396, "seasonNumber": 1, "episodeNumber": 1},
])
```

**Retour :**

```json
{
  "success": true,
  "data": {
    "movie:603": {
      "watched": true,
      "rewatchCount": 3,
      "watchedAt": "2026-09-11T19:00:00.000Z",
      "inWatchlist": false,
      "inCollection": true,
      "isFavorite": true,
      "rating": 9,
      "watchlistPriority": null
    },
    "tv:1396": {
      "watched": true,
      "watchedAt": "2026-09-11T19:00:00.000Z",
      "inWatchlist": true,
      "inCollection": false,
      "isFavorite": false,
      "rating": 8,
      "watchlistPriority": 2,
      "watchedEpisodes": 40,
      "airedEpisodes": 62
    },
    "episode:62085": {
      "watched": true,
      "rewatchCount": 2,
      "watchedAt": "2026-09-11T19:00:00.000Z",
      "progress": 800,
      "duration": 3000,
      "inProgress": true
    },
    "episode:1396:1:1": {
      "watched": true
    }
  }
}
```

Champs optionnels (`progress`, `duration`, `inProgress`, `watchedEpisodes`, `airedEpisodes`) : absents si Plus ne les envoie pas. Jamais vu → pas de `rewatchCount` / `watchedAt`. Série : `watchedAt` sans `rewatchCount`.

---

## 15. `get_show_progress`

Progression saison / épisode pour **max 20** TMDB show ids. Feature Plus (`show_progress`) ; 404 → `not_found`.

| Paramètre | Type |
|---|---|
| `ids` | array d’int (TMDB show) |

Liste vide → `{ "success": true, "data": {} }` (pas d’HTTP).

**Retour :**

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

`next` peut être `null` (série terminée). Ids inconnus omis.

---

## 16. `get_last_activities` (hors catalogue contenu)

Documenté ici seulement pour le gap analysis : timestamps ISO par collection (`all`, `watchlist`, `history`, `ratings`, `favorites`, `collection`, `lists`, `scrobbles`). Pas de titres.

---

## 17. `resolve_media`

Résolution IMDb / titre → TMDB (unitaire). Au moins un de : `imdb_id`, `tmdb_id`+`type`, `title`. Payload vide → `None`.

| Paramètre | Alias | Notes |
|---|---|---|
| `imdb_id` | `imdbId` | `tt…` |
| `tmdb_id` | `tmdbId`, `id` | int |
| `type` | | `movie` \| `tv` |
| `title` | | |
| `year` | | int |

**Retour :**

```json
{
  "success": true,
  "data": {
    "tmdbId": 603,
    "type": "movie",
    "title": "The Matrix",
    "imdbId": "tt0133093",
    "posterUrl": "https://image.tmdb.org/t/p/w342/…",
    "matchConfidence": "high"
  }
}
```

`matchConfidence` : `high` \| `medium` \| `low`.

---

## 18. `resolve_media_batch`

Jusqu’à **50** items. 404 Plus → boucle interne `resolve_media`.

| Paramètre | Type |
|---|---|
| `items` | `[{ imdbId?, tmdbId?, type?, title?, year? }, …]` |

**Retour :** `data` est une **map**. Clé = `imdbId` si présent, sinon index `"0"`, `"1"`, … Valeurs = même objet que `resolve_media`. Items non résolus omis.

```json
{
  "success": true,
  "data": {
    "tt0133093": {
      "tmdbId": 603,
      "type": "movie",
      "title": "The Matrix",
      "imdbId": "tt0133093",
      "posterUrl": "https://image.tmdb.org/t/p/w342/…",
      "matchConfidence": "high"
    }
  }
}
```

---

## Cohérence (constat)

### Paramètres listes (matrice)

| RPC | `type` | `sort` | `format` | `minimal` | pagination |
|---|---|---|---|---|---|
| `get_watchlist` | movie/tv | oui | — | oui | oui |
| `get_history` | movie/tv/**episode** | oui (`watchedAt`) | — | oui | oui |
| `get_ratings` | movie/tv/**season/episode** | **non** | — | oui | oui |
| `get_favorites` | movie/tv | **non** | — | oui | oui |
| `get_collection` | movie/tv | oui | oui | oui | oui |
| `get_scrobbles` | movie/**episode** | **non** | — | oui | oui |
| `get_up_next` | **non** | **non** | — | oui | oui |
| `get_lists` | — | — | — | oui | oui |
| `get_list_items` | — | — | — | oui | oui |
| `get_channels` | type **channel** | — | — | **non** | oui |
| `get_channel` | — | — | — | **non** | **non** |
| `get_dashboard` | — | — | — | — | **non** |
| `get_dashboard_widget` | widget_type | — | — | oui | oui |

Incohérences mineures :

- `type` RPC = type **média** partout, sauf `get_channels` où `type` = type de **chaîne** (`UNIVERSE`…). Le client Python sépare (`channel_type` vs `media_type`) ; le JSON brut ne le fait pas.
- `get_ratings` / `get_favorites` / `get_scrobbles` n’ont pas de `sort` alors que watchlist / history / collection oui.
- `get_channels` n’a pas `minimal`.
- `get_media_status` : le client force `minimal: true` mais le service ne le lit pas.
- History : `type=tv` vs `episode` — les deux existent ; la sémantique « série entière vs épisodes » n’est pas explicitée dans le RPC.
- Alias : `get_channel` accepte `channel_id` **ou** `id` ; `resolve_media` accepte camelCase et snake_case. Les listes n’ont pas d’alias `listId` (seulement `list_id`).

### Surfaces d’UI vs RPC

| Contenu | RPC | `plugin://script.dejavu/` | `plugin.video.dejavu` |
|---|---|---|---|
| watchlist | oui | oui | oui |
| history | oui | oui | oui |
| favorites | oui | oui | oui |
| scrobbles | oui | oui | oui |
| up next | oui | oui | oui |
| collection | oui | **non** | oui |
| ratings | oui | **non** | oui |
| lists / list items | oui | **non** | oui |
| dashboard / widgets | oui | **non** | oui |
| channels | oui | **non** | **non** |
| media status | oui | (interne aux listings) | overlay démo |
| show progress | oui | **non** | **non** |
| resolve / batch | oui | **non** | **non** |

Les widgets skins documentés (`DEVELOPERS.md` § checklist) ne couvrent qu’un sous-ensemble des RPC contenu.

---

## Fonctions potentiellement manquantes

À valider produit (Plus + Kodi). Rien n’est implémenté ci-dessous.

### Listes / catalogue utilisateur

| Manque | Pourquoi |
|---|---|
| `get_list` (une liste par id) | `get_lists` est paginé ; pas de fetch unitaire de métadonnées |
| `update_list` / `delete_list` | `create_list` existe en **write** ; pas de rename / delete / visibilité |
| `reorder_list` | `add_to_list` a `position` ; pas de RPC « reorder all » |
| `search_lists` / listes **suivies** (autres users) | seulement listes **du compte** |

### Channels

| Manque | Pourquoi |
|---|---|
| `follow_channel` / `unfollow_channel` | `scope=following` en lecture seulement |
| `get_channel_items` | aujourd’hui : détail → `lists[]` → N × `get_list_items` |
| Widget `plugin://` channels | RPC existe, aucune surface Kodi |

### Découverte / calendrier

| Manque | Pourquoi |
|---|---|
| RPC dédié `get_upcoming` / `get_calendar` | seulement via widgets dashboard `upcoming_*` (pas filtrable hors dashboard) |
| `search` / `discover` | uniquement `resolve_media` (match 1 titre, pas une grille) |
| `get_recommendations` / `similar` | absent |
| Saison / épisodes d’une série (catalogue) | `get_show_progress` = flags vu, pas une listing TMDB des épisodes |

### Overlays / sync

| Manque | Pourquoi |
|---|---|
| `get_media_status` pour `season` | ratings saison existent ; overlays saison non |
| Pagination / curseur incrémental des listes | `get_last_activities` existe mais n’est **pas** du contenu ; pas de `since=` sur `get_watchlist` etc. |
| Champ `minimal` sur channels / channel | inconsistant avec les autres GET |

### Démo / skins

| Manque | Pourquoi |
|---|---|
| `plugin.video.dejavu` : écrans channels, show progress | le plugin « copy-paste » ne couvre pas tout le RPC contenu |
| `plugin://script.dejavu/` : collection, ratings, lists, dashboard, channels | widgets skins incomplets vs DEVELOPERS.md |

---

## Références code

- Dispatch : `resources/lib/monitor.py` (`_handle_get_*`)
- HTTP : `resources/lib/api_client.py`
- Client public : `resources/lib/client.py`
- Guide addons : [DEVELOPERS.md](DEVELOPERS.md)
- HTTP Plus (script.dejavu only) : [API_PLUS.md](API_PLUS.md)
