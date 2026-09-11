# dejaVu for Kodi

[dejaVu.plus](https://dejavu.plus) · Addon id: `script.dejavu` (Kodi 19+ / Python 3)

[Français](#français) · [English](#english)

---

## Français

dejaVu synchronise vos films et séries Kodi avec [dejaVu.plus](https://dejavu.plus) : historique, notes, liste de suivi, favoris, collection.

Ce n’est **pas** un lecteur ni un scraper : l’extension ne fournit aucun flux. Elle fonctionne avec votre bibliothèque Kodi ou tout addon qui s’y branche.

### Fonctionnalités

- Scrobbling automatique (seuil « vu » réglable, 90 % par défaut)
- Reprise à la dernière position dejaVu
- Proposition de l’épisode suivant en fin de lecture
- Sous-menu contextuel **dejaVu** (films, séries, épisodes) : noter, vu, watchlist, favoris, collection, ajouter à une liste
- Miroir optionnel vers la bibliothèque Kodi (`playcount` / `userrating`)
- Connexion par QR code (**DejaVu Connect**) — aucun mot de passe dans Kodi
- Import one-shot de la bibliothèque Kodi (historique, notes, collection Digital, reprise, favoris)

### Installation

Guide détaillé avec captures : **[INSTALL.md](docs/INSTALL.md)**.  
Fonctionnalités : **[FONCTIONNALITES.md](docs/FONCTIONNALITES.md)**.  
Paramètres (dont l’import Kodi) : **[PARAMETRES.md](docs/PARAMETRES.md)**.

1. Ajouter la source `https://doctornono.github.io/` dans le gestionnaire de fichiers (nom : `dejaVu`).
2. Installer le dépôt : `Extensions > Installer depuis un fichier ZIP` → `repository.dejavu-1.0.0.zip`.
3. Installer l’extension : `Extensions > Installer depuis un dépôt > Dépôt dejaVu` → **dejaVu**.
4. Configurer : paramètres du script → **Connecter dejaVu**.

### Connexion (paramètres du script)

La connexion se fait **depuis dejaVu**, pas depuis un autre addon.

1. `Extensions > Mes extensions > Programmes > dejaVu > Configurer`.
2. Onglet **Compte** → **Connecter dejaVu**.
3. Scanner le QR code (ou ouvrir [dejavu.plus/device](https://dejavu.plus/device) et saisir le code).
4. Se connecter ou créer le compte **sur le téléphone** (Google, GitHub ou code e-mail), puis autoriser Kodi.

Aucun e-mail ni mot de passe n’est saisi dans Kodi.

Après la connexion, dejaVu peut proposer d’importer votre bibliothèque Kodi (**Réglages → Kodi**). Le scrobbling démarre ensuite tout seul. Détail de l’import : [PARAMETRES.md](docs/PARAMETRES.md).

### Utilisation quotidienne

- **Lecture** : le service en arrière-plan envoie la progression à dejaVu.plus. Pause et stop conservent « Reprendre la lecture ».
- **Menu contextuel** : clic droit (ou menu) sur un film / une série / un épisode → sous-menu **dejaVu**. Désactivable dans les réglages.
- **Réglages utiles** : seuil « vu », reprise, épisode suivant, notifications, miroir bibliothèque Kodi. Guide : [PARAMETRES.md](docs/PARAMETRES.md).

Sur une liste plugin (vStream, etc.), le menu contextuel parle à dejaVu.plus. Les badges « vu » sur ces listes nécessitent que l’addon listeur appelle l’API dejaVu. Le miroir `playcount` / `userrating` ne s’écrit que si le titre existe dans la **bibliothèque vidéo Kodi**.

### Pour les créateurs d’extensions

dejaVu est une **couche d’identité** (comme Trakt) pour vStream, alkoFlix, les skins, etc. Les autres addons n’appellent jamais `dejavu.plus/api/v1` : ils utilisent `DejaVuClient`.

```python
from client import DejaVuClient

dv = DejaVuClient()
if not dv.is_authenticated():
    dv.authenticate()  # dialogue QR

status = dv.get_media_status([
    {"type": "movie", "id": 603},
    {"type": "tv", "id": 1396},
])
```

Documentation complète :

- [DEVELOPERS.md](docs/DEVELOPERS.md) — guide développeur (RPC, Connect, import)
- [FONCTIONNALITES.md](docs/FONCTIONNALITES.md) — guide utilisateur
- [PARAMETRES.md](docs/PARAMETRES.md) — réglages et import Kodi

---

## English

dejaVu syncs your Kodi movies and TV shows with [dejaVu.plus](https://dejavu.plus): watch history, ratings, watchlist, favorites, and collection.

This is **not** a player or a scraper: the add-on does not provide streams. It works with your Kodi library, vStream, Elementum, or any addon that integrates with it.

### Features

- Automatic scrobbling (configurable watched threshold, default 90%)
- Resume from the last dejaVu position
- Next-episode prompt at the end of playback
- **dejaVu** context item on movies, TV shows, seasons, and episodes. The Python menu matches the type (full for movie/show; rate + watched for episodes; rate only for seasons)
- Optional mirror of watched status and ratings onto the Kodi library (`playcount` / `userrating`)
- QR sign-in (**DejaVu Connect**) — no password in Kodi
- One-shot Kodi library import (history, ratings, Digital collection, resume, favorites)

### Installation

Full walkthrough with screenshots: **[INSTALL.md](docs/INSTALL.md)**.  
Features: **[FONCTIONNALITES.md](docs/FONCTIONNALITES.md)** (French).  
Settings (including Kodi import): **[PARAMETRES.md](docs/PARAMETRES.md)**.

1. Add the source `https://doctornono.github.io/` in the file manager (name: `dejaVu`).
2. Install the repository: `Add-ons > Install from zip file` → `repository.dejavu-1.0.0.zip`.
3. Install the add-on: `Add-ons > Install from repository > dejaVu Repository` → **dejaVu**.
4. Configure: add-on settings → **Login with dejaVu**.

### Sign in (script settings)

Sign in from **dejaVu itself**, not from another add-on.

1. `Add-ons > My add-ons > Program add-ons > dejaVu > Configure`.
2. **Account** tab → **Login with dejaVu**.
3. Scan the QR code (or open [dejavu.plus/device](https://dejavu.plus/device) and enter the code).
4. Sign in or create the account **on your phone** (Google, GitHub, or email code), then authorize Kodi.

No email or password is typed in Kodi.

After sign-in, dejaVu may offer to import your Kodi library (**Settings → Kodi**). Scrobbling then starts on its own. Import details: [PARAMETRES.md](docs/PARAMETRES.md).

### Daily use

- **Playback**: the background service sends progress to dejaVu.plus. Pause and stop keep Continue watching.
- **Context menu**: right-click (or context) on a movie / show / season / episode → **dejaVu**. The actions depend on the type and your dejaVu status. Can be turned off in settings.
- **Useful settings**: watched %, resume, next episode, notifications, Kodi library mirror. Guide: [PARAMETRES.md](docs/PARAMETRES.md).

On plugin lists (vStream, etc.) the context menu talks to dejaVu.plus. Watched badges on those rows require the listing addon to call the dejaVu API. Kodi `playcount` / `userrating` are only written when the same title exists in the **Kodi video library**.

### For addon developers

dejaVu is an **identity layer** (like Trakt) for vStream, alkoFlix, skins, and others. Other addons never call `dejavu.plus/api/v1`: they use `DejaVuClient`.

```python
from client import DejaVuClient

dv = DejaVuClient()
if not dv.is_authenticated():
    dv.authenticate()  # QR dialog

status = dv.get_media_status([
    {"type": "movie", "id": 603},
    {"type": "tv", "id": 1396},
])
```

Full documentation:

- [DEVELOPERS.md](docs/DEVELOPERS.md) — English developer guide (RPC, Connect, import)
- [PARAMETRES.md](docs/PARAMETRES.md) — settings and Kodi library import
- [FONCTIONNALITES.md](docs/FONCTIONNALITES.md) — French end-user guide

---

## License

MIT — see [LICENSE.txt](LICENSE.txt).
