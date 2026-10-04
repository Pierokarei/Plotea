**Français** · [English below](#english)

{changes_fr}

## Installer Plotea {version}

Aucune installation de Python n'est nécessaire : chaque archive contient tout
ce qu'il faut. Téléchargez celle de votre système dans la liste **Assets**
en bas de cette page.

### Windows 10 / 11 — `Plotea-{version}-windows.zip`

1. Faites un clic droit sur l'archive téléchargée → **Extraire tout…**
   Ne lancez pas Plotea depuis l'intérieur du zip : il ne trouverait pas ses
   fichiers.
2. Ouvrez le dossier `Plotea` obtenu et lancez **`Plotea.exe`**.
3. Au premier lancement, Windows affiche « Windows a protégé votre
   ordinateur ». Cliquez sur **Informations complémentaires**, puis sur
   **Exécuter quand même**. Ce message apparaît parce que Plotea n'est pas
   signé par un certificat payant ; il ne revient pas ensuite.

### macOS (puces Apple M1 et suivantes) — `Plotea-{version}-macos.zip`

1. Ouvrez l'archive : elle donne **`Plotea.app`**. Glissez-la dans le
   dossier **Applications**.
2. Au premier lancement, macOS refuse d'ouvrir une application qu'Apple n'a
   pas vérifiée. Ouvrez **Réglages Système → Confidentialité et sécurité**,
   descendez jusqu'au message concernant Plotea et cliquez sur
   **Ouvrir quand même**. Sur macOS 14 ou plus ancien, un clic droit sur
   Plotea → **Ouvrir** suffit.
3. Si macOS indique que « Plotea est endommagé », ouvrez le Terminal et
   tapez : `xattr -dr com.apple.quarantine /Applications/Plotea.app`

Les Mac à processeur Intel ne sont pas encore pris en charge par cette
archive ; Plotea s'y installe depuis les sources (voir le README).

### Linux — `Plotea-{version}-linux.tar.gz`

Construit sur Ubuntu 24.04 : il demande une distribution de la même
génération ou plus récente.

```bash
tar xzf Plotea-{version}-linux.tar.gz
./Plotea/Plotea
```

Si Qt signale une bibliothèque manquante :
`sudo apt install libxcb-cursor0 libxkbcommon-x11-0`.

### Un problème ?

Signalez-le dans l'onglet [Issues](https://github.com/Pierokarei/Plotea/issues/new/choose).
Le menu **Aide → Journal des erreurs** de Plotea contient le détail
technique à joindre.

---

<a id="english"></a>

{changes_en}

## Installing Plotea {version}

No Python installation is needed: each archive contains everything. Download
the one for your system from the **Assets** list at the bottom of this page.

### Windows 10 / 11 — `Plotea-{version}-windows.zip`

1. Right-click the downloaded archive → **Extract All…**
   Do not run Plotea from inside the zip: it would not find its files.
2. Open the resulting `Plotea` folder and run **`Plotea.exe`**.
3. On first launch, Windows shows "Windows protected your PC". Click
   **More info**, then **Run anyway**. This message appears because Plotea is
   not signed with a paid certificate; it does not come back afterwards.

### macOS (Apple M1 chips and later) — `Plotea-{version}-macos.zip`

1. Open the archive: it contains **`Plotea.app`**. Drag it into the
   **Applications** folder.
2. On first launch, macOS refuses to open an application Apple has not
   checked. Open **System Settings → Privacy & Security**, scroll down to the
   message about Plotea and click **Open Anyway**. On macOS 14 or earlier,
   right-click Plotea → **Open** is enough.
3. If macOS says "Plotea is damaged", open Terminal and type:
   `xattr -dr com.apple.quarantine /Applications/Plotea.app`

Intel Macs are not supported by this archive yet; Plotea installs there from
source (see the README).

### Linux — `Plotea-{version}-linux.tar.gz`

Built on Ubuntu 24.04: it needs a distribution of the same generation or
newer.

```bash
tar xzf Plotea-{version}-linux.tar.gz
./Plotea/Plotea
```

If Qt reports a missing library:
`sudo apt install libxcb-cursor0 libxkbcommon-x11-0`.

### Something wrong?

Report it in the [Issues](https://github.com/Pierokarei/Plotea/issues/new/choose)
tab. Plotea's **Help → Error log** menu holds the technical details to
attach.
