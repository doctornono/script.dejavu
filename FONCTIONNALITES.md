# dejaVu pour Kodi — fonctionnalités et RPC

Addon : `script.dejavu` (Kodi 19+, Python 3).  
Site : [dejavu.plus](https://dejavu.plus)  
Version documentée : **1.7.x**

Ce document décrit :

1. **Ce que l’addon fait dans Kodi** (utilisateur final).
2. **L’API RPC inter-addons** (alkoFlix, vStream, skins, tout autre addon) — sans clé API, sans HTTP vers dejaVu.plus.

Les autres addons ne parlent **jamais** à `https://dejavu.plus/api/v1`. Ils utilisent `DejaVuClient` (recommandé) ou `NotifyAll`. Le service d’arrière-plan de `script.dejavu` est déjà authentifié.

---

## 1. Rôle de l’addon

dejaVu n’est pas un lecteur, ni un scraper, ni un « super-addon ». C’est une **couche d’identité et de données** (comme Trakt) :

- scrobble de lecture ;
- historique, notes, watchlist, favoris, collection, listes perso ;
- import de la bibliothèque Kodi ;
- contrat RPC pour que d’autres addons affichent des badges et écrivent les mêmes données.

Il peut coexister avec Trakt.

Identifiants canoniques : **TMDB**. Les overlays (`get_media_status`) portent sur **`movie`** et **`tv`** (la série), pas sur un épisode isolé.

---

## 2. Fonctionnalités dans Kodi

### 2.1 Connexion — DejaVu Connect

Pas de mot de passe dans Kodi. Device-code OAuth (RFC 8628) :

1. L’utilisateur lance **Se connecter avec dejaVu** (réglages, menu Programmes, ou `authenticate()` depuis un autre addon).
2. Un dialogue affiche un **QR code** + un code court.
3. Scan / ouverture de [dejavu.plus/device](https://dejavu.plus/device) sur le téléphone.
4. Connexion Google / GitHub / code e-mail, puis autorisation de Kodi.

Après succès : écran d’accueil avec stats (watchlist, historique, listes, favoris) et proposition d’**importer la bibliothèque Kodi** s’il y en a une.

Déconnexion : réglages, menu Programmes, ou RPC `logout`.

### 2.2 Scrobble automatique

Service `xbmc.service` au démarrage de Kodi (`service.py`).

| Réglage | Défaut | Effet |
|---|---|---|
| Activer le scrobble | oui | Envoie la progression pendant la lecture |
| Seuil « vu » | 90 % | L’API marque l’item comme vu à ce seuil |
| Intervalle de scrobble | 30 s | Fréquence des ticks (avancé) |
| Notifications | oui | Toasts de scrobble / vu |
| Proposer une note en fin de lecture | oui | Dialogue 1–10 après un titre vu |
| Reprendre à la dernière position | oui | Seek depuis `GET /scrobble` |
| Épisode suivant | oui | Prompt Up Next en fin d’épisode |
| Miroir bibliothèque Kodi | oui | Écrit `playcount` / `userrating` si le titre est dans MyVideos |

Le scrobble live **n’est pas** l’import bibliothèque. Ne pas envoyer un historique Kodi via `scrobble` / `add_to_history` en boucle : ça fausse `rewatchCount`.

À ≥ 90 % (réglable), un seul chemin « vu » : pas de double incrément.

### 2.3 Menu contextuel **dejaVu**

Visible sur un item vidéo qui a un TMDB, un IMDb, ou une propriété plugin (`TmdbId`, `tmdb_id`, `imdb_id`) — bibliothèque, vStream, Elementum, etc.

| Entrée | Comportement |
|---|---|
| Noter | Dialogue 1–10, pré-rempli, option **retirer la note**. Après un épisode : proposer de noter aussi la série |
| Vu / non vu | Toggle film. Pour un épisode : choix marquer vu ou non vu |
| Watchlist | Toggle (épisode → la **série**) |
| Favoris | Toggle (épisode → la série) |
| Collection | Toggle ; à l’ajout, choix de format : Blu-ray, DVD, Digital, 4K UHD, VHS |
| Ajouter à une liste | Picker des listes perso ; ajoute ou retire |

Les écritures réussies diffusent `script.dejavu.changed` et, si le miroir est actif, mettent à jour la fiche Kodi.

### 2.4 Miroir bibliothèque Kodi

Optionnel (défaut : activé). Quand l’utilisateur note ou marque vu **depuis dejaVu**, Kodi reçoit `playcount` / `userrating` si une fiche correspond (DBID, sinon `uniqueid` TMDB/IMDb).

Les badges sur une liste **plugin** (vStream, etc.) ne viennent **pas** de ce miroir : l’addon listeur doit appeler `get_media_status`.

### 2.5 Import de la bibliothèque Kodi (migration)

**Pas un scrobble.** Snapshot one-shot de MyVideos via JSON-RPC Kodi, puis `POST /kodi/import` par paquets d’environ 200 items.

Sources Kodi :

- `VideoLibrary.GetMovies` / `GetTVShows` / `GetEpisodes`
- playlists vidéo `special://profile/playlists/video/`
- `Favourites.GetFavourites`

Champs lus : titre, année, `uniqueid` (TMDB/IMDb), `playcount`, `lastplayed`, `userrating`, reprise, etc.

**Vu** = `playcount > 0`. **Non vu** = `playcount == 0`.

Lancements :

- après Connect, si une bibliothèque existe ;
- **Réglages → Importer ma bibliothèque Kodi** ;
- menu Programmes (premier item si connecté) ;
- autre addon : `DejaVuClient.import_kodi_library()`.

Options utilisateur (aperçu puis confirmation) :

| Option | Effet côté serveur (contrat) |
|---|---|
| Historique | `playCount` / `lastPlayed` ; n’écrase pas un `watchedAt` dejaVu plus récent |
| Notes | 1–10 seulement si dejaVu n’en a pas |
| Dates de visionnage | conserve `lastPlayed` |
| Non vus → watchlist | films non vus / séries jamais commencées |
| Reprise | continue-watching seulement s’il n’y a pas déjà un scrobble actif |
| Playlists | listes privées dejaVu du même nom |
| Favoris Kodi | favoris dejaVu (pas une liste perso) |

Idempotent sur `importSessionId` + item.

### 2.6 Menu Programmes

| État | Items |
|---|---|
| Connecté | Importer la bibliothèque Kodi, Réglages, Déconnexion (pseudo) |
| Déconnecté | Connexion, Réglages |

### 2.7 Actions `RunScript` (pas du RPC 5 s)

```
RunScript(script.dejavu,action=<nom>)
```

| Action | Rôle |
|---|---|
| `login` | Dialogue QR Connect |
| `logout` | Efface les jetons |
| `import_kodi` | Assistant d’import |
| `rate` | Dialogue de note (item focalisé) |
| `toggle_watched` | Vu / non vu |
| `toggle_watchlist` | Watchlist (`add_to_watchlist` est un alias) |
| `toggle_favorites` | Favoris (`add_to_favorites` alias) |
| `toggle_collection` | Collection (`add_to_collection` alias) |
| `add_to_list` | Picker de liste |
| `settings` | Ouvre les réglages |
| *(sans argument)* | Menu Programmes |

`authenticate()` et `import_kodi_library()` lancent ces scripts et **pollent une propriété Window 10000** (timeouts 5 min / 10 min). Ils ne passent **pas** par le timeout RPC de 5 secondes.

---

## 3. RPC pour les autres addons

Le « JSON-RPC » dejaVu n’est **pas** l’API JSON-RPC native de Kodi (`VideoLibrary.GetMovies`, etc.). C’est un protocole maison :

1. L’appelant envoie `NotifyAll(<addon.id>, script.dejavu.<action>, <json>)`.
2. Le JSON peut contenir `result_property` (défaut : `script.dejavu.<action>.result`).
3. Le service écrit la réponse JSON sur **Window 10000**.
4. L’appelant lit cette propriété jusqu’à timeout (défaut **5 s**).

`DejaVuClient` encapsule tout ça. Copier `resources/lib/client.py` est possible ; l’import Kodi est plus simple.

### 3.1 Dépendance

Dans `addon.xml` de l’autre addon :

```xml
<requires>
    <import addon="xbmc.python" version="3.0.0"/>
    <import addon="script.dejavu" version="1.5.0"/>
</requires>
```

Import bibliothèque : dépendre de **≥ 1.7.0**.

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

`script.dejavu` expose `resources/lib` comme module Python Kodi → `from client import DejaVuClient`.

Règles :

- utilisateur **non connecté** ou addon absent → `None` ou `{ "success": false, ... }` : échouer doucement (pas de badges, UI intacte) ;
- `timeout=8` pour de gros `get_media_status` ;
- IDs **TMDB numériques** ;
- `type` overlays / listes / watchlist / favoris / collection : `movie` \| `tv` ;
- `type` historique / scrobble : `movie` \| `episode` ;
- `type` notes : `movie` \| `tv` \| `season` \| `episode` ;
- lots de **50** max pour `get_media_status` ;
- `minimal=True` sur les listes si seuls les ids suffisent.

### 3.2 Connect depuis un autre addon

```python
dv = DejaVuClient()

if not dv.is_authenticated():
    result = dv.authenticate()
    # { "success": true, "user": {...}, "stats": {...} }
    # ou { "success": false, "error": "cancelled"|"expired"|"timeout"|"aborted"|... }

dv.get_me()
dv.logout()
```

UI suggérée : un bouton **Connecter dejaVu** (à côté de Trakt), pas un formulaire login.

Après login, écouter `script.dejavu.changed` avec `action: "authenticated"` (et `"auth"` à la déconnexion).

Import (séparé, **ne pas** le lancer automatiquement à la fin de `authenticate()` — le script le propose déjà) :

```python
if dv.is_authenticated():
    result = dv.import_kodi_library()
    # { "success": true, "status": "success" }
    # ou { "success": false, "error": "not_authenticated"|"cancelled"|"error"|"empty"|"timeout"|"aborted" }
```

### 3.3 Protocole brut `NotifyAll` (optionnel)

Inutile si on utilise `DejaVuClient`. Équivalent de `dv.call("get_media_status", {"items": [...]})`.

```python
import json, time
import xbmc, xbmcgui

window = xbmcgui.Window(10000)
prop = "my.addon.media_status"
window.clearProperty(prop)
payload = json.dumps({
    "result_property": prop,
    "items": [{"type": "movie", "id": 603}],
})
xbmc.executebuiltin(
    "NotifyAll(plugin.video.myaddon, script.dejavu.get_media_status, %s)" % payload
)

deadline = time.time() + 5
monitor = xbmc.Monitor()
result = None
while time.time() < deadline:
    raw = window.getProperty(prop)
    if raw:
        result = json.loads(raw)
        break
    if monitor.waitForAbort(0.1):
        break
```

Action inconnue → `{ "success": false, "error": "Unknown action: ..." }`.  
Paramètre manquant → `{ "success": false, "error": "Missing param: ..." }`.  
`None` côté client = timeout, parse error, ou HTTP en échec dans le service.

Les lectures paginées renvoient en général :

```json
{
  "success": true,
  "data": [],
  "pagination": {
    "page": 1,
    "pageSize": 20,
    "total": 0,
    "totalPages": 0,
    "hasMore": false
  }
}
```

Les payloads complets sont déjà prêts pour des `ListItem` Kodi (`info.title`, `info.plot`, `art.poster`, `tmdbId`, `imdbId`, …).

---

## 4. Catalogue des actions RPC

Méthode notification : `script.dejavu.<action>`.  
Méthode Python : `DejaVuClient.<même_nom>(...)`.

Paramètre commun optionnel : `result_property`.

### 4.1 Lecture

#### `get_media_status` — overlays (le plus important)

Statut batch jusqu’à **50** films / séries. Pour un épisode, passer le TMDB de la **série** en `"tv"`.

| Paramètre | Type | Défaut | Notes |
|---|---|---|---|
| `items` | `[{type, id}, ...]` | `[]` | `type` = `movie` \| `tv`, `id` = TMDB |

```python
status = dv.get_media_status([
    {"type": "movie", "id": 603},
    {"type": "tv", "id": 1396},
])
```

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

```python
def dejavu_flags(status, media_type, tmdb_id):
    data = (status or {}).get("data") or {}
    return data.get("%s:%s" % (media_type, tmdb_id)) or {}
```

#### `resolve_media` — IMDb / titre → TMDB

Fournir au moins : `imdb_id`, ou `tmdb_id` + `type`, ou `title`.

| Paramètre | Alias acceptés | Notes |
|---|---|---|
| `imdb_id` | `imdbId` | ex. `tt0133093` |
| `tmdb_id` | `tmdbId`, `id` | numérique |
| `type` | | `movie` \| `tv` |
| `title` | | recherche |
| `year` | | affine la recherche |

`matchConfidence` : `high` \| `medium` \| `low`. Ignorer `low` sauf confirmation utilisateur.

#### `get_me`

Profil + stats. Sans session : `{ "success": false, "error": "not_authenticated" }`.

#### `is_authenticated`

```json
{ "success": true, "authenticated": true }
```

Côté client, `dv.is_authenticated()` renvoie un **booléen**.

#### Listes paginées

Paramètres communs : `page` (1), `page_size` (20), `minimal` (false). `type` filtre si fourni.

| Action | Params spécifiques | `type` |
|---|---|---|
| `get_watchlist` | `sort` défaut `addedAt:desc` (`addedAt:asc`, `priority:desc`, `priority:asc`) | `movie` \| `tv` |
| `get_history` | `sort` défaut `watchedAt:desc` (`watchedAt:asc`) | `movie` \| `tv` \| `episode` |
| `get_ratings` | | `movie` \| `tv` \| `season` \| `episode` |
| `get_favorites` | | `movie` \| `tv` |
| `get_collection` | `sort` `addedAt:desc` \| `addedAt:asc` ; `format` (`bluray`, `dvd`, `digital`, `uhd`, `vhs`) | `movie` \| `tv` |
| `get_up_next` | | — (épisodes en cours) |
| `get_scrobbles` | continue watching | `movie` \| `episode` |
| `get_lists` | listes perso | — |
| `get_list_items` | **`list_id` obligatoire** | — |

`minimal=True` : ids / dates / flags, plus léger pour widgets.

#### Dashboard

| Action | Params |
|---|---|
| `get_dashboard` | aucun — layout des widgets (hors stats) |
| `get_dashboard_widget` | **`widget_type` obligatoire**, `list_id` si type `list`, `page`, `page_size`, `minimal` |

`widget_type` :

| Valeur | Contenu |
|---|---|
| `up_next` | Prochains épisodes |
| `recent_watchlist` | Derniers ajouts watchlist |
| `continue_watching` | Tous les scrobbles actifs |
| `active_movie_scrobbles` | Films en cours |
| `active_tv_scrobbles` | Séries en cours |
| `upcoming_releases` | Sorties films (TMDB) |
| `upcoming_schedule` | Planning séries (TMDB) |
| `list` | Items d’une liste (`list_id` requis) |

### 4.2 Écriture

Toute écriture **réussie** (résultat non `None`) déclenche aussi `script.dejavu.changed`.

#### Watchlist / favoris / collection

| Action | Params | Notes |
|---|---|---|
| `add_to_watchlist` | `type`, `id`, `priority?`, `notes?` | `movie` \| `tv` |
| `remove_from_watchlist` | `type`, `id` | |
| `add_to_favorites` | `type`, `id` | |
| `remove_from_favorites` | `type`, `id` | |
| `add_to_collection` | `type`, `id`, `format?`, `notes?` | formats : `bluray`, `dvd`, `digital`, `uhd`, `vhs` |
| `remove_from_collection` | `type`, `id` | |

```python
flags = dejavu_flags(dv.get_media_status([{"type": "movie", "id": 603}]), "movie", 603)
if flags.get("inWatchlist"):
    dv.remove_from_watchlist("movie", 603)
else:
    dv.add_to_watchlist("movie", 603)
```

#### Historique (vu / non vu)

| Action | Params |
|---|---|
| `add_to_history` | `type`, `id?`, `count?` (défaut 1), `watched_at?` ISO-8601, `tvShowId?`, `seasonNumber?`, `episodeNumber?` |
| `delete_history` | `type`, `id` |
| `remove_from_history` | **alias RPC** de `delete_history` (pas de méthode dédiée sur `DejaVuClient`) |

```python
dv.add_to_history("movie", tmdb_id=603)
dv.delete_history("movie", 603)
dv.add_to_history("episode", tv_show_id=1396, season=1, episode=1)
```

Ne pas combiner `scrobble` **et** `add_to_history` pour la même lecture.

#### Notes

| Action | Params |
|---|---|
| `rate` | `type`, `rating` (1–10), `id?`, `tvShowId?`, `seasonNumber?`, `episodeNumber?`, `review?` |
| `delete_rating` | `type`, `id?`, `tvShowId?`, `seasonNumber?` |

```python
dv.rate("movie", 8, tmdb_id=603)
dv.rate("episode", 7, tmdb_id=None, tv_show_id=1396, season=1, episode=1)
dv.delete_rating("movie", tmdb_id=603)
```

#### Listes perso

| Action | Params |
|---|---|
| `create_list` | **`name`**, `description?`, `visibility?` (`PRIVATE` défaut \| `PUBLIC`) |
| `add_to_list` | **`list_id`**, `type`, `id`, `notes?`, `position?` |
| `remove_from_list` | **`list_id`**, `type`, `id` |

#### Scrobble depuis un autre player

Uniquement si **l’addon pilote lui-même** la lecture et ne veut pas s’appuyer sur les hooks player de dejaVu.

`progress` et `duration` en **secondes**. Seuil vu API : 90 %.

| Action | Params |
|---|---|
| `scrobble` | `type` (`movie` \| `episode`), **`progress`**, **`duration`**, `id?`, `tvShowId?`, `seasonNumber?`, `episodeNumber?` |
| `delete_scrobble` | `type`, `id` |

```python
dv.scrobble("movie", progress=1200, duration=8160, tmdb_id=603)
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

#### Session

| Action | Params | Retour |
|---|---|---|
| `logout` | aucun | `{ "success": true }` |

`authenticate` / `import_kodi` ne sont **pas** des actions `NotifyAll`.

---

## 5. Événement `script.dejavu.changed`

Après une écriture (RPC, menu contextuel, scrobble, import, login/logout), dejaVu envoie :

```
NotifyAll(script.dejavu, script.dejavu.changed, <json>)
```

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
        # {"action": "rate", "type": "movie", "id": 603, "rating": 8}
        self.refresh_item(payload.get("type"), payload.get("id"))
```

Le service **ignore** `script.dejavu.changed` en entrée (ce n’est pas une action RPC).

| `action` | Contexte |
|---|---|
| `add_to_watchlist` / `remove_from_watchlist` | Watchlist |
| `add_to_favorites` / `remove_from_favorites` | Favoris |
| `add_to_collection` / `remove_from_collection` | Collection |
| `add_to_list` / `remove_from_list` | Liste perso (`list_id` dans le payload) |
| `create_list` | Nouvelle liste |
| `rate` / `delete_rating` | Note (`rating` parfois présent) |
| `add_to_history` / `delete_history` | Historique RPC |
| `watched` / `unwatched` | Toggle menu contextuel |
| `scrobble` / `delete_scrobble` | Progression |
| `upnext` | Fin d’épisode : `tvShowId`, `seasonNumber`, `episodeNumber`, `title` |
| `authenticated` | Login OK |
| `auth` | Logout |
| `kodi_import` | Fin d’import bibliothèque |

---

## 6. Propriétés Window 10000

| Propriété | Rôle |
|---|---|
| `script.dejavu.<action>.result` | Réponse RPC (sauf `result_property` custom) |
| `script.dejavu.auth.status` | `success` \| `cancelled` \| `expired` \| `error` (Connect) |
| `script.dejavu.import.status` | `success` \| `cancelled` \| `error` \| `empty` (import) |

---

## 7. JSON-RPC Kodi utilisé *en interne*

Ces méthodes **ne sont pas** exposées aux autres addons. dejaVu les appelle via `xbmc.executeJSONRPC` pour le miroir et l’import :

| Méthode | Usage |
|---|---|
| `VideoLibrary.GetMovies` | Scan films (import + lookup miroir) |
| `VideoLibrary.GetTVShows` | Scan séries |
| `VideoLibrary.GetEpisodes` | Scan épisodes |
| `VideoLibrary.SetMovieDetails` / `SetEpisodeDetails` / … | Miroir `playcount` / `userrating` |
| `Files.GetDirectory` | Playlists vidéo |
| `Favourites.GetFavourites` | Favoris Kodi |
| `Player.GetActivePlayers` / `Player.GetItem` | Métadonnées de lecture (scrobble) |

Les autres addons qui veulent l’historique dejaVu utilisent **`get_history` / `get_media_status`**, pas ces appels.

---

## 8. Checklist d’intégration

1. Dépendre de `script.dejavu` ≥ **1.5.0** (Connect) / ≥ **1.7.0** (import).
2. Importer `DejaVuClient` derrière `System.HasAddon`.
3. Bouton **Connecter dejaVu** → `authenticate()` (jamais de mot de passe dans Kodi).
4. Mapper les items en TMDB (`resolve_media` si IMDb ou titre seul).
5. `get_media_status` par lots de 50 → badges `data["movie:123"]`.
6. Au moins une écriture (toggle watchlist) + écoute de `script.dejavu.changed`.
7. Traiter `None` / addon absent / déconnecté comme « pas de badges ».
8. Optionnel : **Importer mon historique Kodi** via `import_kodi_library()`. Ne pas scrobbler la bibliothèque.

---

## 9. Index rapide des méthodes `DejaVuClient`

| Méthode | RPC / script |
|---|---|
| `call(action, params)` | brut |
| `is_authenticated()` | RPC |
| `authenticate(timeout=300)` | `RunScript` login |
| `import_kodi_library(timeout=600)` | `RunScript` import_kodi |
| `logout()` | RPC |
| `get_me()` | RPC |
| `get_media_status(items)` | RPC |
| `resolve_media(...)` | RPC |
| `get_watchlist` / `get_history` / `get_ratings` / `get_favorites` / `get_collection` / `get_up_next` / `get_scrobbles` / `get_lists` / `get_list_items` | RPC lecture |
| `get_dashboard` / `get_dashboard_widget` | RPC lecture |
| `add_to_watchlist` / `remove_from_watchlist` | RPC |
| `add_to_favorites` / `remove_from_favorites` | RPC |
| `add_to_collection` / `remove_from_collection` | RPC |
| `add_to_history` / `delete_history` | RPC |
| `create_list` / `add_to_list` / `remove_from_list` | RPC |
| `rate` / `delete_rating` | RPC |
| `scrobble` / `delete_scrobble` | RPC |

Alias RPC sans wrapper client : `remove_from_history` (= `delete_history`).
