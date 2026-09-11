# dejaVu pour Kodi — fonctionnalités

Addon : `script.dejavu` (Kodi 19+, Python 3).  
Site : [dejavu.plus](https://dejavu.plus)  
Version documentée : **1.11.0**

Installation : [README.md](../README.md) · [INSTALL.md](INSTALL.md).  
Paramètres (détail, y compris l’import Kodi) : [PARAMETRES.md](PARAMETRES.md).  
Créateurs d’extensions : [DEVELOPERS.md](DEVELOPERS.md).

---

## Rôle de l’addon

dejaVu n’est pas un lecteur, ni un scraper, ni un « super-addon ». C’est une **couche d’identité et de données** (comme Trakt) :

- scrobble de lecture ;
- historique, notes, liste de suivi, favoris, collection, listes perso ;
- import one-shot de la bibliothèque vidéo Kodi vers [dejaVu.plus](https://dejavu.plus).

L’extension ne fournit aucun flux. Elle fonctionne avec votre bibliothèque Kodi et avec les addons qui s’y branchent (vStream, alkoFlix, Elementum, etc.). Elle peut coexister avec Trakt.

---

## Connexion — DejaVu Connect

Aucun mot de passe n’est saisi dans Kodi.

1. Lancez **Connecter dejaVu** depuis les réglages (onglet **Compte**) ou le menu Programmes.
2. Un dialogue affiche un **QR code** et un code court. Le compte se crée sur le téléphone.
3. Scannez le QR ou ouvrez [dejavu.plus/device](https://dejavu.plus/device).
4. Connectez-vous ou **créez un compte** (Google, GitHub ou code e-mail), puis autorisez Kodi.

Après succès : écran d’accueil avec quelques stats, et proposition d’**importer la bibliothèque Kodi** s’il y en a une.

Déconnexion : **Réglages → Compte → Se déconnecter de dejaVu**, ou menu Programmes.

---

## Scrobble automatique

Un service démarre avec Kodi et envoie la progression de lecture vers dejaVu.plus.

| Réglage | Onglet | Défaut | Effet |
|---|---|---|---|
| Activer le scrobbling automatique | Scrobbling | oui | Envoie la progression pendant la lecture |
| Marquer comme vu à (% lu) | Scrobbling | 90 % | Le titre est marqué vu à ce seuil |
| Afficher les notifications | Scrobbling | oui | Toasts de début / vu / noté |
| Proposer de noter après visionnage | Scrobbling | oui | Dialogue 1–10 après un titre vu |
| Reprendre à la dernière position | Scrobbling | oui | Propose de reprendre où vous vous étiez arrêté |
| Proposer l’épisode suivant | Scrobbling | oui | Prompt en fin d’épisode |
| Intervalle de scrobble | Avancé | 30 s | Fréquence d’envoi en arrière-plan |

Le scrobble live **n’est pas** l’import bibliothèque. L’import copie l’existant une fois ; le scrobble suit les lectures **ensuite**.

À ≥ 90 % (réglable), un seul chemin « vu » : pas de double comptage.

Pause et stop conservent **Reprendre la lecture** à la dernière position réelle. L’item sort de cette liste seulement si le titre est **terminé** (fin de fichier / seuil « vu ») ou si la lecture a duré **moins de 30 s**. Même règle pour les films et les épisodes.

---

## Menu contextuel dejaVu

Réglage **Afficher le menu contextuel dejaVu** (onglet Compte, activé par défaut). Une entrée **dejaVu** sur un **film**, une **série**, une **saison** ou un **épisode** — bibliothèque Kodi, vStream, Elementum, etc. Pas sur les extensions, « installer un zip », personnes ou dossiers. Le menu Python s’adapte au type et à l’état dejaVu (note, watchlist…).

| Type | Entrées |
|---|---|
| Film | Noter, vu / non vu, liste à voir, favoris, collection, liste perso |
| Série | Noter, liste à voir, favoris, collection, liste perso (pas de « vu » global) |
| Épisode | Noter, marquer vu, marquer non vu |
| Saison | Noter seulement |

| Entrée | Comportement |
|---|---|
| Noter | Dialogue 1–10, pré-rempli, option **retirer la note**. Après un épisode : proposer de noter aussi la série |
| Vu / non vu | Film : une ligne selon l’état. Épisode : les deux actions |
| Liste à voir / favoris / collection | Toggle ; libellé Ajouter ou Retirer. Collection : choix de format à l’ajout (Blu-ray, DVD, Digital, 4K UHD, VHS) |
| Ajouter à une liste | Choix parmi vos listes perso ; ajoute ou retire |

Si le **miroir bibliothèque Kodi** est activé, une note ou un statut vu depuis dejaVu est aussi écrit dans la fiche Kodi lorsque le titre existe dans MyVideos.

Sur une liste plugin (vStream, etc.), le menu contextuel parle à dejaVu.plus. Les badges « vu » sur ces listes dépendent de l’addon listeur, pas du miroir Kodi.

---

## Miroir bibliothèque Kodi

Optionnel (défaut : activé), dans **Réglages → Kodi**.

Quand vous notez ou marquez vu **depuis dejaVu**, Kodi reçoit le statut vu / la note si une fiche correspond. Ça n’importe pas la bibliothèque vers dejaVu : c’est le sens inverse (dejaVu → Kodi).

---

## Import de la bibliothèque Kodi

**Pas un scrobble.** Copie unique de votre bibliothèque vidéo scrapée vers dejaVu.plus (collection, historique, notes, liste de suivi, reprise, favoris — selon les cases cochées).

Lancements :

- après Connect, si une bibliothèque existe ;
- **Réglages → Kodi → Importer la bibliothèque Kodi** ;
- menu Programmes (premier item si vous êtes connecté).

L’assistant propose d’abord un **mode** (importer uniquement, ou importer et continuer à synchroniser), puis les **cases** de contenu, puis un **aperçu** avant confirmation.

Le détail de ce que chaque case ajoute sur [dejaVu.plus](https://dejavu.plus) est dans **[PARAMETRES.md](PARAMETRES.md)**.

---

## Menu Programmes

| État | Items |
|---|---|
| Connecté | Importer la bibliothèque Kodi, Réglages, Déconnexion |
| Déconnecté | Connexion, Réglages |

---

## Pour aller plus loin

- Tous les réglages, case par case : [PARAMETRES.md](PARAMETRES.md)
- Installation pas à pas : [INSTALL.md](INSTALL.md)
- Intégrer dejaVu dans un autre addon : [DEVELOPERS.md](DEVELOPERS.md)
