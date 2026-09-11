# Import Kodi → dejaVu (spec interne)

Document **interne**. Pour l’explication utilisateur (ce qui arrive sur dejaVu.plus) : [PARAMETRES.md](PARAMETRES.md).

L’assistant part du principe que MyVideos (films / séries scrapés) = **collection personnelle** de l’utilisateur.

Le client envoie `POST /api/v1/kodi/import`. Ce n’est pas un scrobble (pas d’incrément de `rewatchCount`).

## Modes (étape 1)

Les deux modes envoient **le même** payload. Seul l’après-coup change :

| Mode | Effet |
|---|---|
| Importer uniquement (désactive le scrobble ensuite) | Snapshot, puis `enable_scrobble = false` |
| Importer et continuer à synchroniser (le scrobble reste actif) | Snapshot, le scrobble live continue |

---

## Cases (étape 2)

### Importer votre collection Kodi dans votre collection dejaVu (Digital)

**Source Kodi :** tous les films (`GetMovies`) et toutes les séries (`GetTVShows`) de la bibliothèque scrapée. Pas les épisodes.

**Destination dejaVu :** **collection**, format **`digital`**. Flags : `importCollection`, `collectionFormat: "digital"`.

### Importer vos visionnages Kodi dans vos visionnages dejaVu

**Source Kodi :** films `playcount > 0`, séries `watchedepisodes > 0`, épisodes `playcount > 0`, plus `lastplayed`.

**Destination dejaVu :** **historique** + `watchedAt`. Flags : `importWatched` + `importWatchDates` (toujours ensemble).

### Importer vos notes Kodi dans dejaVu

**Source Kodi :** `userrating > 0` sur films, séries et épisodes.

**Destination dejaVu :** **notes** (si dejaVu n’en a pas déjà). Flag : `importRatings`.

### Ajouter les éléments non vus de votre bibliothèque Kodi à votre liste de suivi dejaVu

**Source Kodi :** films `playcount == 0` + séries `watchedepisodes == 0`.

**Destination dejaVu :** **watchlist / liste de suivi**. Flag : `unwatchedToWatchlist`.

### Positions de reprise

**Source Kodi :** `resume.position > 0` sur films et épisodes.

**Destination dejaVu :** **Reprendre la lecture**, sauf scrobble déjà actif. Flag : `importResume`.

### Favoris Kodi

**Source Kodi :** `Favourites.GetFavourites`, chemins `videodb://` seulement.

**Destination dejaVu :** **favoris**. Flag : `importFavorites`.

### Masqué

**Playlists Kodi** : code conservé, pas d’UI, pas de scan, `importPlaylists: false`.

---

## Récap

| Case | Source Kodi | Destination dejaVu |
|---|---|---|
| Collection (Digital) | tous films + toutes séries MyVideos | Collection format `digital` |
| Visionnages | films/épisodes vus, séries commencées, `lastplayed` | Historique + `watchedAt` |
| Notes | `userrating > 0` | Notes |
| Non vus → liste de suivi | films non vus + séries jamais commencées | Watchlist |
| Positions de reprise | `resume` films / épisodes | Reprendre la lecture |
| Favoris Kodi | favoris `videodb://` | Favoris |
