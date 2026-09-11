# dejaVu for Kodi — settings

[Français](#français) · [English](#english)

Addon: `script.dejavu`. Overview: [README.md](../README.md) · Features: [FONCTIONNALITES.md](FONCTIONNALITES.md) · Install: [INSTALL.md](INSTALL.md).

Open the settings from `Add-ons > My add-ons > Program add-ons > dejaVu > Configure`, or from the Programs menu.

---

## Français

Quatre onglets : **Compte**, **Kodi**, **Scrobbling**, **Avancé**.

### Compte

| Réglage | Rôle |
|---|---|
| Connecté en tant que | Votre identifiant dejaVu une fois la session ouverte (lecture seule). |
| Connecter dejaVu | Affiché si vous n’êtes pas connecté. Ouvre le dialogue QR (DejaVu Connect). Aucun mot de passe dans Kodi. |
| Se déconnecter de dejaVu | Affiché une fois connecté. Efface la session locale. |
| Afficher le menu contextuel dejaVu | Sous-menu **dejaVu** (noter, vu, liste à voir, favoris, collection, listes) sur les films, séries et épisodes. Désactivez-le si vous ne voulez que le scrobble en arrière-plan. |

L’import de la bibliothèque n’est **pas** dans cet onglet.

### Kodi

| Réglage | Rôle |
|---|---|
| Texte d’aide | Rappel : l’import copie la bibliothèque vidéo Kodi (collection, visionnages, notes) vers dejaVu. |
| Importer la bibliothèque Kodi | Lance l’assistant d’import (voir ci-dessous). |
| Répercuter le statut vu et les notes dans la bibliothèque Kodi | **Miroir** dejaVu → Kodi. Quand vous notez ou marquez vu depuis dejaVu, Kodi met à jour `vu` / la note **si** le titre existe dans votre bibliothèque vidéo. Ce n’est pas l’import. |

### Scrobbling

Ces options concernent les **lectures en cours**, pas l’import.

| Réglage | Défaut | Rôle |
|---|---|---|
| Activer le scrobbling automatique | oui | Envoie la progression vers dejaVu.plus pendant la lecture. |
| Marquer comme vu à (% lu) | 90 | Seuil à partir duquel le titre est marqué vu sur dejaVu. |
| Afficher les notifications (début, vu, noté) | oui | Toasts Kodi. |
| Proposer de noter après visionnage | oui | Dialogue 1–10 après un titre vu. |
| Reprendre à la dernière position | oui | Propose de reprendre là où vous vous étiez arrêté sur dejaVu. |
| Proposer l’épisode suivant en fin de lecture | oui | Prompt « épisode suivant ». |

### Avancé

| Réglage | Défaut | Rôle |
|---|---|---|
| Intervalle de scrobble (secondes) | 30 | Fréquence d’envoi pendant une lecture. Inutile de descendre très bas. |
| URL de l’API | `https://dejavu.plus/api/v1` | Serveur dejaVu. En production l’URL est verrouillée sur dejaVu.plus ; ne la changez que si la **journalisation débogage** est activée et qu’on vous l’a demandé. |
| Journalisation débogage | non | Logs plus verbeux. À laisser désactivé au quotidien. |

---

### Import de la bibliothèque Kodi — ce qui arrive sur dejaVu.plus

L’import est une **copie unique** de votre bibliothèque vidéo Kodi **scrapée** (films et séries avec identifiants TMDB/IMDb) vers votre compte [dejaVu.plus](https://dejavu.plus).

Ce n’est **pas** un scrobble : dejaVu ne recompte pas les relectures. Vous pouvez relancer l’assistant plus tard ; ce qui existe déjà sur dejaVu n’est pas écrasé à tort (une note dejaVu reste, une date de visionnage dejaVu plus récente reste, une reprise déjà active n’est pas remplacée).

**Prérequis :** être connecté, et avoir une bibliothèque vidéo Kodi (MyVideos) avec des fiches scrapées. Les fichiers « bruts » sans métadonnées ne partent pas.

**Où lancer l’assistant :**

- proposition juste après Connect, s’il y a une bibliothèque ;
- **Réglages → Kodi → Importer la bibliothèque Kodi** ;
- menu Programmes (premier item une fois connecté).

Un écran d’**aperçu** (« Nous avons trouvé : X films, Y séries… ») s’affiche avant la confirmation.

#### Étape 1 — mode

Les deux modes envoient **le même** contenu vers dejaVu.plus. Seul l’après-coup dans Kodi change.

| Choix | Sur dejaVu.plus | Ensuite dans Kodi |
|---|---|---|
| Importer uniquement (désactive le scrobble ensuite) | Copie selon les cases de l’étape 2 | Le scrobbling automatique est **coupé**. Les lectures suivantes ne partent plus vers dejaVu tant que vous ne le réactivez pas (onglet Scrobbling). |
| Importer et continuer à synchroniser (le scrobble reste actif) | Copie selon les cases de l’étape 2 | Le scrobbling **reste allumé**. Les prochaines lectures continuent d’alimenter dejaVu.plus. |
| Ne rien importer pour le moment | Rien n’est copié | Vous pourrez relancer plus tard depuis l’onglet Kodi. |

#### Étape 2 — que cochez-vous, et où ça atterrit

Chaque case est indépendante. Décochez ce que vous ne voulez pas envoyer.

##### Collection Kodi → collection dejaVu (Digital)

**Dans Kodi :** tous les films et toutes les séries de la bibliothèque scrapée. Les épisodes ne sont pas ajoutés un par un dans la collection.

**Sur dejaVu.plus :** chaque film et chaque série rejoint votre **collection**, au format **Digital** (comme si vous les aviez en fichier / dématérialisé). C’est l’inventaire de ce que vous « possédez » dans Kodi, pas l’historique de visionnage.

##### Visionnages Kodi → historique dejaVu

**Dans Kodi :** films déjà vus, séries commencées, épisodes vus, avec les dates de lecture Kodi.

**Sur dejaVu.plus :** ces titres rejoignent votre **historique** (visionnages), **avec les dates**. Un visionnage dejaVu plus récent n’est pas reculé. Ce n’est pas un scrobble live : le compteur de relectures n’est pas gonflé.

##### Notes Kodi → notes dejaVu

**Dans Kodi :** notes utilisateur de 1 à 10 sur films, séries et épisodes.

**Sur dejaVu.plus :** la note est copiée **seulement s’il n’y en a pas déjà une** sur ce titre. Une note dejaVu existante n’est jamais écrasée par Kodi.

##### Non vus → liste de suivi dejaVu

**Dans Kodi :** films jamais vus, et séries jamais commencées.

**Sur dejaVu.plus :** ces titres sont ajoutés à votre **liste de suivi** (watchlist). Utile si votre bibliothèque Kodi est une file d’attente, pas seulement un catalogue déjà vu.

##### Positions de reprise → Reprendre la lecture

**Dans Kodi :** films et épisodes avec une position de lecture (vous vous étiez arrêté au milieu).

**Sur dejaVu.plus :** l’item apparaît dans **Reprendre la lecture**, à cette position. Si dejaVu a **déjà** un scrobble actif pour ce titre, la reprise Kodi n’écrase pas.

##### Favoris Kodi → favoris dejaVu

**Dans Kodi :** favoris du menu Kodi qui pointent vers un film ou une série de la bibliothèque (pas un site web, pas un addon quelconque).

**Sur dejaVu.plus :** ils rejoignent vos **favoris**. Ce n’est **pas** une liste personnelle : c’est le drapeau favori dejaVu.

##### Playlists Kodi

**Non importées.** L’option n’apparaît pas dans l’assistant. Vos listes de lecture Kodi restent dans Kodi ; créez des listes sur dejaVu.plus si vous en avez besoin là-bas.

#### Après l’import

Ouvrez [dejaVu.plus](https://dejavu.plus) : collection, historique, notes, liste de suivi, Reprendre la lecture et favoris reflètent les cases cochées. Dans Kodi, le scrobble suit le mode choisi à l’étape 1.

---

## English

Four tabs: **Account**, **Kodi**, **Scrobbling**, **Advanced**.

### Account

| Setting | What it does |
|---|---|
| Logged in as | Your dejaVu username once signed in (read-only). |
| Connect dejaVu | Shown when logged out. Opens the QR dialog (DejaVu Connect). No password in Kodi. |
| Log out of dejaVu | Shown when logged in. Clears the local session. |
| Show dejaVu context menu | **dejaVu** submenu (rate, watched, watchlist, favorites, collection, lists) on movies, TV shows, and episodes. Turn it off if you only want background scrobbling. |

Library import is **not** on this tab.

### Kodi

| Setting | What it does |
|---|---|
| Help text | Reminder: import copies your Kodi video library (collection, watches, ratings) into dejaVu. |
| Import Kodi library | Starts the import wizard (see below). |
| Mirror watched status and ratings to the Kodi library | **Mirror** dejaVu → Kodi. When you rate or mark watched from dejaVu, Kodi updates playcount / rating **if** that title exists in your video library. This is not the import. |

### Scrobbling

These options apply to **live playback**, not to the import.

| Setting | Default | What it does |
|---|---|---|
| Enable automatic scrobbling | on | Sends progress to dejaVu.plus during playback. |
| Mark as watched at (% played) | 90 | Threshold at which the title is marked watched on dejaVu. |
| Show notifications (start, watched, rated) | on | Kodi toasts. |
| Prompt for rating after playback | on | 1–10 dialog after a title is watched. |
| Resume from last position | on | Offers to seek to the last dejaVu position. |
| Offer next episode when playback ends | on | Up Next prompt. |

### Advanced

| Setting | Default | What it does |
|---|---|---|
| Scrobble interval (seconds) | 30 | How often progress is sent during playback. No need to go very low. |
| API URL | `https://dejavu.plus/api/v1` | dejaVu server. In production the URL is locked to dejaVu.plus; change it only with **debug logging** on, if you were asked to. |
| Debug logging | off | Verbose logs. Leave off for daily use. |

---

### Kodi library import — what is added on dejaVu.plus

Import is a **one-shot copy** of your **scraped** Kodi video library (movies and TV shows with TMDB/IMDb ids) onto your [dejaVu.plus](https://dejavu.plus) account.

This is **not** scrobble: dejaVu does not inflate rewatch counts. You can run the wizard again later; existing dejaVu data is not overwritten blindly (an existing dejaVu rating stays, a newer dejaVu watch date stays, an active resume is not replaced).

**Requirements:** signed in, and a Kodi video library (MyVideos) with scraped metadata. Raw files with no scrapes are not sent.

**Where to start the wizard:**

- prompt right after Connect, if a library exists;
- **Settings → Kodi → Import Kodi library**;
- Programs menu (first item when signed in).

A **preview** screen (“We found: X movies, Y TV shows…”) appears before you confirm.

#### Step 1 — mode

Both modes send **the same** payload to dejaVu.plus. Only what happens in Kodi afterwards changes.

| Choice | On dejaVu.plus | Afterwards in Kodi |
|---|---|---|
| Import only (then turn off scrobbling) | Copy according to the step-2 checkboxes | Automatic scrobbling is **turned off**. Later playback is not sent until you re-enable it (Scrobbling tab). |
| Import and keep syncing (scrobbling stays on) | Copy according to the step-2 checkboxes | Scrobbling **stays on**. Later playback keeps feeding dejaVu.plus. |
| Don't import for now | Nothing is copied | You can start it later from the Kodi tab. |

#### Step 2 — checkboxes, and where they land

Each checkbox is independent. Uncheck anything you do not want to send.

##### Kodi collection → dejaVu collection (Digital)

**In Kodi:** every movie and every TV show in the scraped library. Episodes are not added one by one to the collection.

**On dejaVu.plus:** each movie and show is added to your **collection** as **Digital** (as if you owned the file / stream). This is an inventory of what you have in Kodi, not watch history.

##### Kodi watches → dejaVu history

**In Kodi:** watched movies, started shows, watched episodes, including Kodi watch dates.

**On dejaVu.plus:** those titles go into your **watch history**, **with dates**. A newer dejaVu watch date is not moved backwards. This is not live scrobble: rewatch counts are not inflated.

##### Kodi ratings → dejaVu ratings

**In Kodi:** user ratings 1–10 on movies, shows, and episodes.

**On dejaVu.plus:** the rating is copied **only if dejaVu has none** for that title. An existing dejaVu rating is never overwritten by Kodi.

##### Unwatched → dejaVu watchlist

**In Kodi:** movies you have never watched, and TV shows you have never started.

**On dejaVu.plus:** those titles are added to your **watchlist**. Useful if your Kodi library is a backlog, not only already-watched titles.

##### Resume positions → Continue watching

**In Kodi:** movies and episodes with a resume bookmark (you stopped in the middle).

**On dejaVu.plus:** the item appears under **Continue watching** at that position. If dejaVu **already** has an active scrobble for that title, the Kodi resume is not applied.

##### Kodi favorites → dejaVu favorites

**In Kodi:** Kodi menu favorites that point at a library movie or TV show (not a website, not a random add-on).

**On dejaVu.plus:** they become **favorites**. This is **not** a custom list: it is the dejaVu favorite flag.

##### Kodi playlists

**Not imported.** The option is hidden in the wizard. Kodi playlists stay in Kodi; create lists on dejaVu.plus if you need them there.

#### After the import

Open [dejaVu.plus](https://dejavu.plus): collection, history, ratings, watchlist, Continue watching, and favorites reflect the boxes you checked. In Kodi, scrobbling follows the mode you picked in step 1.
