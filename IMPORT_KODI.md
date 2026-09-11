# Importer l’historique Kodi vers dejaVu

Ce n’est **pas** un scrobble. L’import est un **snapshot unique** de la bibliothèque vidéo Kodi (MyVideos), envoyé à dejaVu.plus par paquets. Il ne gonfle pas `rewatchCount` (contrairement à un scrobble en boucle).

Après connexion, l’addon propose l’import s’il détecte une bibliothèque. On peut aussi le lancer depuis :

- **Réglages → Compte → Importer mon historique Kodi**
- **Réglages → Importer la bibliothèque Kodi**
- le menu **Programmes** (premier item une fois connecté)
- un autre addon via `DejaVuClient.import_kodi_library()`

---

## Étape 1 — Comment importer ?

| Option à l’écran | Effet |
|---|---|
| **Importer mon historique Kodi** | Copie l’historique (et les options choisies ensuite), puis **désactive le scrobble automatique**. Utile si tu ne veux plus que Kodi envoie la lecture en direct. |
| **Importer l’historique et continuer à synchroniser** | Même copie, mais le **scrobble reste activé**. C’est le choix recommandé si tu continues à regarder dans Kodi. |
| **Ne rien importer pour le moment** | Ferme l’assistant et mémorise que l’offre a déjà été faite. Tu pourras relancer l’import plus tard depuis les réglages. |

Annuler le dialogue (retour / Escape) n’importe rien.

---

## Étape 2 — Que souhaitez-vous importer ?

Liste à choix multiples. Par défaut : films vus, séries/épisodes vus, notes, dates de visionnage, positions de reprise.

### Films vus

Inclut les films Kodi avec `playcount > 0`.

Côté dejaVu : ils rejoignent l’**historique**. `playCount` et `lastPlayed` sont envoyés. Un `watchedAt` dejaVu **plus récent** n’est pas écrasé.

### Séries et épisodes vus

Inclut les séries avec au moins un épisode vu (`watchedEpisodes > 0`) et les épisodes avec `playcount > 0`.

Même contrat que les films : historique, sans incrémenter `rewatchCount`.

### Notes Kodi

Inclut les fiches dont `userrating > 0` (échelle 1–10).

Côté dejaVu : la note n’est écrite **que s’il n’y en a pas déjà une**. Une note dejaVu existante n’est pas remplacée.

### Dates de visionnage

N’ajoute pas d’items à elle seule : c’est un **drapeau** (`importWatchDates`) appliqué aux médias déjà inclus (vus, notes, reprise, watchlist…).

Côté dejaVu : conserve `lastPlayed` comme date de visionnage, sans écraser un `watchedAt` plus récent.

### Films non vus (watchlist)

Inclut les films avec `playcount == 0` et les séries jamais commencées (`watchedEpisodes == 0`).

Côté dejaVu : ils vont dans la **watchlist** (`unwatchedToWatchlist`). Si tu laisses cette case décochée, l’assistant peut quand même te proposer d’ajouter les films non vus après l’aperçu.

### Positions de reprise

Inclut les films et épisodes qui ont un **signet de reprise** Kodi.

Côté dejaVu : alimente **Reprendre la lecture** seulement s’il n’y a **pas déjà un scrobble actif** pour ce titre.

### Playlists Kodi

Lit les playlists vidéo de `special://profile/playlists/video/`.

Côté dejaVu : crée des **listes privées** du **même nom**, avec les items identifiés (TMDB).

### Favoris Kodi

Lit les favoris Kodi mappés vers des titres vidéo (`videodb://`…).

Côté dejaVu : ils rejoignent les **favoris** dejaVu (pas une liste perso).

---

## Aperçu, correspondances, envoi

L’addon scanne via JSON-RPC (`VideoLibrary.GetMovies` / `GetTVShows` / `GetEpisodes`, playlists, favoris) puis affiche un aperçu.

| Confiance | Critère | Comportement |
|---|---|---|
| **Certaines** | ID TMDB présent (pour un épisode : série + saison + numéro) | Importées par défaut |
| **À vérifier** | ID IMDb, ou titre + année seulement | Question oui/non avant envoi |
| **Non identifiés** | Pas de métadonnée utilisable | Jamais envoyés |

L’envoi se fait par lots d’environ **200** items (`POST /kodi/import`). L’opération est **idempotente** sur `importSessionId` + item : relancer le même import ne duplique pas l’historique.

---

## Ce que l’import ne fait pas

- Il ne remplace **pas** le scrobble en direct (sauf si tu as choisi « Importer mon historique Kodi », qui coupe le scrobble après coup).
- Il n’écrit pas les `playcount` / notes **depuis** dejaVu vers Kodi (c’est le réglage **Miroir bibliothèque Kodi**, dans l’autre sens).
- Il n’importe pas la musique, les images, ni les addons hors bibliothèque vidéo.

Pour le contrat serveur et le payload JSON, voir aussi [README.md](README.md) (section *Import Kodi library*) et [FONCTIONNALITES.md](FONCTIONNALITES.md) §2.5.
