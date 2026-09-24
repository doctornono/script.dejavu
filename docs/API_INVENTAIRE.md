# Inventaire des appels HTTP vers dejaVu.plus

Source unique : `script.dejavu/resources/lib/api_client.py` (`DejaVuAPI`).
Base URL : `https://dejavu.plus/api/v1` (verrouillée hors mode debug).

Les autres addons Kodi n’appellent jamais cette API : uniquement `DejaVuClient` / RPC (`NotifyAll`).

**Hors périmètre :** `scrobbler.py` appelle **TMDB** (find / details), pas dejaVu.

---

## Conventions

| Élément | Détail |
|---|---|
| Auth | Header `x-api-key` = access token. Pas d’auth sur `GET /auth/device/qr`. |
| Types | IDs canoniques **TMDB**. `movie` / `tv` / `episode` / `season` selon l’endpoint. |
| Pagination | Query `page`, `pageSize` (max 100). `minimal=true` allège le payload. |
| Écritures | Succès → notification Kodi `script.dejavu.changed` (menu contextuel, overlays, cache). |
| Lectures listes | Listings Kodi / skin / plugin démo : `info`, `art`, `tmdbId`. |
| Erreurs | Timeout / HTTP d’échec → le client retourne `None`. Certains endpoints Plus : HTTP **404** → `{ "success": false, "error": "not_found" }`. |

Enveloppe v1 typique : `{ "success": true, "data": … }` (+ `pagination` sur les listes).

Exemple d’item média (listes, `minimal=false`) :

```json
{
  "type": "movie",
  "tmdbId": 603,
  "imdbId": "tt0133093",
  "title": "The Matrix",
  "year": 1999,
  "info": { "title": "The Matrix", "plot": "…", "mediatype": "movie", "duration": 8160 },
  "art": { "poster": "https://image.tmdb.org/t/p/w342/…", "fanart": "…" }
}
```

Pagination :

```json
{
  "success": true,
  "data": [],
  "pagination": { "page": 1, "pageSize": 20, "total": 42, "totalPages": 3, "hasMore": true }
}
```

---

## 1. Authentification (Device Code / Connect)

### `POST /auth/device/code`

**Paramètres (JSON) :** `{ "client_id": "dejavu-kodi" }` (+ `client_name` optionnel).

**Exemple de retour** (champs lus à la racine par `auth_handler`) :

```json
{
  "device_code": "xxxxxxxx",
  "user_code": "ABCD1234",
  "verification_uri": "https://dejavu.plus/device",
  "expires_in": 300,
  "interval": 5
}
```

**Usage :** afficher le code court + lancer le polling. `user_code` sert aussi au QR.

---

### `GET /auth/device/qr?user_code=ABCD1234`

**Pas d’auth.** Réponse : PNG.

**Usage :** fichier temp `special://temp/dejavu_qr.png` pour la fenêtre Connect.

---

### `POST /auth/device/token`

**Paramètres :**

```json
{
  "device_code": "xxxxxxxx",
  "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
  "client_id": "dejavu-kodi"
}
```

**200 :**

```json
{ "access_token": "sk_…", "token_type": "Bearer" }
```

**400 / 428 :** pending / slow_down → continuer à poller (`None` côté client).

**Usage :** persister le token (`session.json` + settings), puis `GET /me`.

---

### `GET /me`

**Query :** aucune.

**Exemple de retour** (forme acceptée : `user` imbriqué ou objet plat + `stats`) :

```json
{
  "success": true,
  "user": { "name": "alice", "username": "alice", "email": "a@b.c" },
  "stats": {
    "watchlist": { "total": 12 },
    "history": { "total": 340 },
    "lists": { "total": 3 },
    "favorites": { "total": 8 }
  }
}
```

**Usage :** nom d’affichage, dialogue de bienvenue, probe RPC, stats du compte.

---

## 2. Scrobble (Reprendre la lecture)

### `POST /scrobble`

```json
{
  "type": "movie",
  "id": 603,
  "progress": 1200,
  "duration": 8160
}
```

Épisode : `type: "episode"`, `id` (TMDB épisode, optionnel), `tvShowId`, `seasonNumber`, `episodeNumber`.

**Retour :** enveloppe succès (détail peu utilisé). À ≥ 90 % de `progress/duration`, l’API marque **vu** (ne pas appeler aussi `POST /history` pour la même lecture).

**Usage :** service lecteur Kodi ; RPC `scrobble` pour lecteurs tiers.

---

### `GET /scrobble`

Query : `page`, `pageSize`, `minimal`, `type?` (`movie` \| `episode`).

**Usage :** Continue watching (plugin, dashboard, RPC `get_scrobbles`). Items avec `progress` / `duration`.

---

### `DELETE /scrobble?type=movie&id=603`

**Usage :** arrêter une session de reprise (contextuel / RPC).

---

## 3. Notes

### `GET /ratings`

Query : `page`, `pageSize`, `minimal`, `type?` (`movie` \| `tv` \| `season` \| `episode`).

**Usage :** listing notes.

---

### `POST /ratings`

```json
{
  "type": "movie",
  "id": 603,
  "rating": 8,
  "review": "optionnel"
}
```

Saison / épisode : `tvShowId`, `seasonNumber`, `episodeNumber`. Note 1–10.

**Usage :** menu contextuel, RPC `rate`. Met à jour overlays (`rating`).

---

### `DELETE /ratings?type=movie&id=603`

Saison : `type=season&tvShowId=&seasonNumber=`.

**Usage :** retirer la note.

---

## 4. Historique

### `GET /history`

Query : `page`, `pageSize`, `sort` (`watchedAt:desc` \| `asc`), `minimal`, `type?` (`movie` \| `tv` \| `episode`).

**Usage :** listings historique ; widgets skins.

---

### `POST /history`

```json
{
  "type": "movie",
  "id": 603,
  "count": 1,
  "watchedAt": "2026-09-11T19:00:00.000Z"
}
```

Épisode : `tvShowId` + S/E. `count` = vues supplémentaires (`rewatchCount`).

**Usage :** marquer vu (contextuel) ; **pas** en plus du scrobble live.

---

### `DELETE /history?type=movie&id=603`

**Usage :** marquer non vu.

---

## 5. Watchlist / collection / favoris

Même schéma : GET paginé, POST `{ type, id }`, DELETE `?type=&id=`.

| Méthode | Path | Extra |
|---|---|---|
| GET | `/watchlist` | `sort`: `addedAt:*` \| `priority:*` |
| POST | `/watchlist` | `priority?`, `notes?` |
| DELETE | `/watchlist` | |
| GET | `/collection` | `format?` (ex. `bluray`) |
| POST | `/collection` | `format?`, `notes?` |
| DELETE | `/collection` | |
| GET | `/favorites` | |
| POST | `/favorites` | `{ type, id }` |
| DELETE | `/favorites` | |

`type` : `movie` \| `tv`.

**Usage :** menus contextuels, listings, overlays (`inWatchlist`, `inCollection`, `isFavorite`, `watchlistPriority`).

---

## 6. Listes perso

### `GET /lists`

Query : `page`, `pageSize`, `minimal`.

**Usage :** choisir une liste (contextuel « ajouter à une liste »), page Listes.

### `POST /lists`

```json
{ "name": "Cyberpunk", "visibility": "PRIVATE", "description": "…" }
```

`visibility` : `PRIVATE` \| `PUBLIC`. **Usage :** création de liste.

### `GET /lists/{id}/items`

Pagination + `minimal`. **Usage :** contenu d’une liste / sections de channel.

### `POST /lists/{id}/items`

```json
{ "type": "movie", "id": 603, "notes": null, "position": 0 }
```

### `DELETE /lists/{id}/items?type=movie&id=603`

---

## 7. Channels (univers) — 404 toléré

### `GET /channels`

Query : `page`, `pageSize`, `type?` (`UNIVERSE` \| `EDITORIAL` \| `PLATFORM` \| `THEMATIC` \| `CREATOR` \| `AWARDS` \| `FRANCHISE`), `scope?` (`mine` \| `following` ; omit = explore).

**Exemple :**

```json
{
  "success": true,
  "data": [{
    "type": "channel",
    "id": "…",
    "channelType": "universe",
    "slug": "marvel-cinematic-universe",
    "followersCount": 12,
    "listsCount": 3,
    "isVerified": true,
    "owner": { "id": "…", "name": "…" },
    "info": { "title": "Marvel Cinematic Universe", "plot": "…", "mediatype": "set" },
    "art": { "poster": "…", "fanart": "…" }
  }],
  "pagination": { "page": 1, "pageSize": 20, "total": 8, "totalPages": 1, "hasMore": false }
}
```

**Usage :** explorer les chaînes (plugin / skin). 404 → `not_found`, listing vide.

### `GET /channels/{id}`

Détail + listes attachées. Items complets via `GET /lists/{id}/items`.

---

## 8. Up Next & dashboard

### `GET /upnext`

Query : `page`, `pageSize`, `minimal` (le serveur default `minimal=true` si omis ; le client envoie explicitement).

**Usage :** prochains épisodes des séries en cours. Notification `upnext` en fin d’épisode.

### `GET /dashboard`

**Exemple :**

```json
{
  "success": true,
  "data": {
    "widgets": [
      { "id": "up_next-1", "type": "up_next", "title": "Up Next", "props": {}, "apiUrl": "/api/v1/dashboard/widget?type=up_next" }
    ],
    "filters": []
  }
}
```

**Usage :** layout du dashboard (ignore le widget `stats`). Puis charger chaque widget.

### `GET /dashboard/widget`

Query : `type`, `page`, `pageSize`, `minimal`, `listId?`.

`type` : `up_next` \| `recent_watchlist` \| `continue_watching` \| `active_movie_scrobbles` \| `active_tv_scrobbles` \| `upcoming_releases` \| `upcoming_schedule` \| `list` (`listId` requis).

**Usage :** contenu des widgets (proxy vers listes / TMDB Discover côté serveur).

---

## 9. Statut média, resolve, sync Plus

### `POST /media/status` (max 50)

```json
{
  "items": [
    { "type": "movie", "id": 603 },
    { "type": "tv", "id": 1396 },
    { "type": "episode", "id": 62085, "tmdbId": 1396, "seasonNumber": 1, "episodeNumber": 1 }
  ]
}
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
    "tv:1396": { "watched": true, "watchedEpisodes": 40, "airedEpisodes": 62 },
    "episode:62085": { "watched": true, "progress": 800, "duration": 3000, "inProgress": true },
    "episode:1396:1:1": { "watched": true }
  }
}
```

**Usage :** badges / overlays (contextuel, skins, cache SQLite). Champs optionnels : `progress`, `duration`, `inProgress`, `lastWatchedAt`.

---

### `POST /media/show-progress` (max 20) — 404 toléré

```json
{ "ids": [1396, 1399] }
```

**Retour :** map id série → `watchedEpisodes`, `airedEpisodes`, `lastWatchedAt`, `next` (ou `null`), `seasons[]` avec `episodes: { "1": true }`.

**Usage :** « 4/10 », masquer saisons terminées, prochain épisode. Liste vide → pas d’HTTP.

---

### `POST /media/resolve`

```json
{ "imdbId": "tt0133093", "type": "movie", "title": "The Matrix", "year": 1999 }
```

Au moins un de : IMDb, TMDB+type, titre.

**Retour :** `tmdbId`, `type`, `title`, `imdbId`, `posterUrl`, `matchConfidence` (`high` \| `medium` \| `low`).

**Usage :** scrapers / addons sans clé TMDB.

---

### `POST /media/resolve/batch` (max 50) — 404 → boucle `resolve`

```json
{ "items": [{ "imdbId": "tt0133093", "type": "movie" }] }
```

`data` = map (clé `imdbId` ou index `"0"`). Items non résolus omis.

---

### `GET /sync/last_activities` — 404 toléré

```json
{
  "success": true,
  "data": {
    "all": "2026-09-11T19:00:00.000Z",
    "watchlist": "…",
    "history": "…",
    "ratings": "…",
    "favorites": "…",
    "collection": "…",
    "lists": "…",
    "scrobbles": "…"
  }
}
```

**Usage :** curseur de sync (invalider le cache listings). 404 → considérer stale après 15 min.

---

## 10. Import bibliothèque Kodi

### `POST /kodi/import` (timeout 120 s / chunk ~200 items)

```json
{
  "source": "kodi",
  "importSessionId": "uuid",
  "chunk": 1,
  "totalChunks": 3,
  "options": {
    "importCollection": true,
    "collectionFormat": "digital",
    "importWatched": true,
    "importWatchDates": true,
    "importRatings": true,
    "unwatchedToWatchlist": false,
    "importResume": true,
    "importPlaylists": false,
    "importFavorites": true
  },
  "movies": [{
    "title": "The Matrix",
    "tmdbId": 603,
    "imdbId": "tt0133093",
    "year": 1999,
    "playCount": 2,
    "lastPlayed": "2026-01-01T12:00:00.000Z",
    "rating": 9,
    "runtime": 8160,
    "resume": { "position": 1200, "total": 8160 }
  }],
  "tvShows": [],
  "episodes": [],
  "playlists": [],
  "favorites": []
}
```

**Retour** (agrégé par le client) :

```json
{
  "success": true,
  "data": {
    "imported": {
      "movies": 10, "episodes": 40, "ratings": 3, "watchlist": 2,
      "scrobbles": 1, "lists": 0, "favorites": 4, "collection": 12
    },
    "skipped": { "alreadyWatched": 1, "unresolved": 2 },
    "unresolved": []
  }
}
```

**Usage :** snapshot one-shot (pas un scrobble : pas d’incrément `rewatchCount`). Wizard après Connect / réglages Kodi.

---

## Tableau récapitulatif

| Méthode | Path | Rôle du retour |
|---|---|---|
| POST | `/auth/device/code` | Codes Connect |
| GET | `/auth/device/qr` | Image QR |
| POST | `/auth/device/token` | Access token |
| GET | `/me` | Profil + stats |
| POST/GET/DELETE | `/scrobble` | Progress / liste reprise |
| GET/POST/DELETE | `/ratings` | Notes |
| GET/POST/DELETE | `/history` | Vus |
| GET/POST/DELETE | `/watchlist` | Liste de suivi |
| GET/POST/DELETE | `/collection` | Collection |
| GET/POST/DELETE | `/favorites` | Favoris |
| GET/POST | `/lists` | Métadonnées listes |
| GET/POST/DELETE | `/lists/{id}/items` | Contenu listes |
| GET | `/channels`, `/channels/{id}` | Univers |
| GET | `/upnext` | Prochains épisodes |
| GET | `/dashboard`, `/dashboard/widget` | Home widgets |
| POST | `/media/status` | Badges overlays |
| POST | `/media/show-progress` | Progression série |
| POST | `/media/resolve` (+ `/batch`) | TMDB id |
| GET | `/sync/last_activities` | Invalidation cache |
| POST | `/kodi/import` | Compteurs d’import |
