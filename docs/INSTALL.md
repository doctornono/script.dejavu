# Installing dejaVu on Kodi

[Français](#français) · [English](#english)

Overview: [README.md](../README.md) · Settings: [PARAMETRES.md](PARAMETRES.md).

---

## Français

Guide d’installation de l’extension **dejaVu** (`script.dejavu`) depuis le dépôt officiel.

**Prérequis :** Kodi 19 ou plus (Python 3). Autorisez les **sources inconnues** : `Paramètres > Système > Extensions > Sources inconnues`.

### 1. Ajouter la source

Kodi a besoin d’une source de fichiers pour télécharger le zip du dépôt.

1. Aller dans `Paramètres > Gestionnaire de fichiers`.
   ![Gestionnaire de fichiers](https://dejavu.plus/kodi/01-file-manager.png)
2. Choisir `Ajouter une source`.
   ![Ajouter une source](https://dejavu.plus/kodi/02-add-source.png)
3. Saisir l’URL : `https://doctornono.github.io/`.
   ![URL et nom de la source](https://dejavu.plus/kodi/03-source-url.png)
   ![URL et nom de la source](https://dejavu.plus/kodi/04-source-url-2.png)
4. Donner un nom à la source, par exemple : `dejaVu`.
   ![URL et nom de la source](https://dejavu.plus/kodi/05-source-name.png)
5. Valider.

### 2. Installer le dépôt

Le dépôt permet ensuite d’installer et de mettre à jour dejaVu automatiquement.

1. Aller dans `Extensions`.
   ![URL et nom de la source](https://dejavu.plus/kodi/06-extensions.png)
2. Choisir `Installer depuis un fichier ZIP`
   ![URL et nom de la source](https://dejavu.plus/kodi/07-install-from-zip.png)
3. Si Kodi le demande, confirmer l’autorisation des sources inconnues.
4. Ouvrir la source `dejaVu`.
   ![URL et nom de la source](https://dejavu.plus/kodi/08-install-from-zip-2.png)
5. Installer `repository.dejavu-1.0.0.zip`.
   ![URL et nom de la source](https://dejavu.plus/kodi/09-install-from-zip-3.png)

### 3. Installer l’extension

1. Aller dans `Extensions > Installer depuis un dépôt`.
   ![URL et nom de la source](https://dejavu.plus/kodi/10-install-from-repo.png)
2. Ouvrir `Dépôt dejaVu`.
   ![URL et nom de la source](https://dejavu.plus/kodi/11-install-from-repo-2.png)

3. Ouvrir la catégorie **Services** (ou la liste des extensions du dépôt).
   ![URL et nom de la source](https://dejavu.plus/kodi/12-install-from-repo-3.png)

4. Installer **dejaVu**.
   ![URL et nom de la source](https://dejavu.plus/kodi/13-install-from-repo-4.png)

Une fois le dépôt installé, Kodi proposera les mises à jour automatiquement.

### 4. Configurer l’extension (connexion à dejaVu)

dejaVu ne fournit pas de films : il synchronise votre compte [dejaVu.plus](https://dejavu.plus). La connexion se fait **depuis les paramètres du script**, pas depuis un autre addon.

1. Aller dans `Extensions > Mes extensions`.
2. Ouvrir **Services** (dejaVu peut aussi apparaître sous **Dépendances**).
3. Sélectionner **dejaVu**, puis **Configurer**.
   ![URL et nom de la source](https://dejavu.plus/kodi/16-configurer.png)

4. Dans l’onglet **Compte**, appuyer sur **Connecter dejaVu**.
   ![URL et nom de la source](https://dejavu.plus/kodi/20-param-compte.png)

5. Un dialogue affiche un **QR code** et un code court.
   ![URL et nom de la source](https://dejavu.plus/kodi/20-param-qr.png)

6. Sur le téléphone, scanner le QR ou ouvrir [dejavu.plus/device](https://dejavu.plus/device) et saisir le code.
7. Se connecter ou **créer un compte** sur le téléphone (Google, GitHub ou code e-mail), puis autoriser Kodi.

Aucun e-mail ni mot de passe n’est saisi dans Kodi. Le compte se crée sur le téléphone.

Après une connexion réussie, dejaVu peut proposer d’**importer votre bibliothèque Kodi** (historique, notes, collection). Vous pouvez aussi lancer l’import plus tard depuis **Réglages → Kodi**. Le détail de ce qui est envoyé vers [dejaVu.plus](https://dejavu.plus) est dans [PARAMETRES.md](PARAMETRES.md).

Le scrobbling automatique démarre ensuite : les lectures dans Kodi sont envoyées à dejaVu.plus.

---

## English

Install the **dejaVu** add-on (`script.dejavu`) from the official repository.

**Requirements:** Kodi 19 or later (Python 3). Enable **Unknown sources**: `Settings > System > Add-ons > Unknown sources`.

### 1. Add the source

Kodi needs a file source to download the repository zip.

1. Go to `Settings > File manager`.
2. Choose `Add source`.
3. Enter the URL: `https://doctornono.github.io/`.
4. Name the source, for example: `dejaVu`.
5. Confirm.

### 2. Install the repository

The repository then installs and updates dejaVu automatically.

1. Go to `Add-ons > Install from zip file`.
2. If Kodi asks, confirm allowing unknown sources.
3. Open the `dejaVu` source.
4. Install `repository.dejavu-1.0.0.zip`.

### 3. Install the add-on

1. Go to `Add-ons > Install from repository`.
2. Open `dejaVu Repository`.
3. Open the **Program add-ons** category (or the repository add-on list).
4. Install **dejaVu**.

Once the repository is installed, Kodi offers updates automatically.

### 4. Configure the add-on (sign in to dejaVu)

dejaVu does not provide streams: it syncs your [dejaVu.plus](https://dejavu.plus) account. Sign in from **this script’s settings**, not from another add-on.

1. Go to `Add-ons > My add-ons`.
2. Open **Program add-ons** (dejaVu may also appear under **Dependencies**).
3. Select **dejaVu**, then **Configure**.
4. On the **Account** tab, press **Login with dejaVu**.
5. A dialog shows a **QR code** and a short code.
6. On your phone, scan the QR or open [dejavu.plus/device](https://dejavu.plus/device) and enter the code.
7. Sign in or **create an account** on the phone (Google, GitHub, or email code), then authorize Kodi.

No email or password is typed in Kodi. The account is created on the phone.

After a successful sign-in, dejaVu may offer to **import your Kodi library** (history, ratings, collection). You can also start the import later from **Settings → Kodi**. What is copied to [dejaVu.plus](https://dejavu.plus) is explained in [PARAMETRES.md](PARAMETRES.md).

Automatic scrobbling then starts: playback in Kodi is sent to dejaVu.plus.
