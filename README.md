# BSC Radio Studio

Application Windows de création de podcasts au format radio pour Brewers Social Club.
La première version inclut les imports, les dialogues, les voix OpenAI, les exports et les mises à jour GitHub.

L’interface 0.1.1 reprend l’identité de brewerssocialclub.com : logo noir et blanc,
bandeau violet à vagues, navigation blanche, typographie Roboto et accents turquoise/magenta.
La [matrice de couverture fonctionnelle](docs/FUNCTIONAL_COVERAGE.md) indique les
fonctions du moteur Houblon FM effectivement accessibles dans Windows et celles restant à intégrer.

## Installer

Dans [Releases](https://github.com/colonelchaboumm/BSC-radio/releases), télécharger
**BSC-Radio-Studio-Setup-x64.exe** et suivre l’assistant. Windows 10 1809 ou plus récent,
architecture x64. Python et FFmpeg sont inclus ; aucun terminal n’est nécessaire.
Une archive portable est également disponible.

L’installation est propre à l’utilisateur, dans `%LOCALAPPDATA%\Programs\BSC Radio Studio`.
Les données sont conservées séparément, dans `%LOCALAPPDATA%\BSC Radio Studio\Data`.
Les mises à jour et la désinstallation conservent ce dossier de données.

L’installeur initial est non signé. Les empreintes de téléchargement figurent dans
`SHA256SUMS.txt`. La vérification de l’empreinte assure l’intégrité ; elle ne remplace pas
une signature d’éditeur Windows.

## Première utilisation

1. Dans **Imports**, ajouter du texte, une page web ou un fichier TXT/Markdown.
2. Cocher les informations à utiliser.
3. Dans **Studio**, choisir un titre et un format, puis générer le dialogue.
4. Relire et modifier les répliques de Camille, Marcel, Jeanne et Noé.
5. Dans **Paramètres**, renseigner une clé API OpenAI et attribuer les voix.
6. Générer les voix, écouter puis exporter en MP3 ou WAV. Le script s’exporte en JSON.

Pour tester sans clé : **Imports → Ajouter un exemple de démonstration**, puis
**Studio → Brouillon sans API · démo**. Ce mode ne produit aucune voix réelle.

Les appels d’écriture utilisent l’API Responses ; la voix utilise Realtime.
Les modèles sont configurables. La voix **Rivage** est souhaitée mais son accès API
n’est pas confirmé ; l’application demande de choisir explicitement une voix disponible.
Les voix API sont distinctes des noms présentés dans ChatGPT.
Les générations peuvent consommer le crédit du compte API. Aucun tarif estimatif fictif
n’est affiché et aucun appel IA ne s’effectue automatiquement au démarrage.

Une modification du dialogue ou des paramètres vocaux rend l’audio final obsolète.
Les prises inchangées sont réutilisées lors de la génération suivante. Le texte est
conservé avant les opérations longues. L’audio produit doit être écouté avant diffusion.

## Mises à jour du dépôt privé

Dans **Paramètres**, renseigner un jeton GitHub à accès fin limité à ce dépôt,
avec **Contents: Read-only**. L’application chiffre le jeton avec Windows DPAPI,
pour le compte Windows courant ; il n’est jamais inclus dans l’installeur ou le dépôt.

Dans **Mises à jour**, l’application consulte la dernière Release stable, compare
les versions, télécharge l’installeur et vérifie son empreinte SHA-256 avant
d’ouvrir l’assistant d’installation. Le jeton n’est pas transmis aux domaines CDN
lors des redirections. Les versions préliminaires et les retours en arrière sont ignorés.
La vérification au démarrage peut être désactivée. L’installation reste explicite.

Sans jeton valide, GitHub peut répondre 404 pour le dépôt privé ; le studio affiche
une demande d’accès au lieu de prétendre que le logiciel est à jour.
Le dépôt doit conserver une Release stable avec l’asset exact
`BSC-Radio-Studio-Setup-x64.exe`, et son digest GitHub ou `SHA256SUMS.txt`.

## Développer et compiler

Sur Windows avec Python 3.14 et Inno Setup 6 ou 7 :

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check bsc_studio scripts run_studio.py tests
.venv\Scripts\python.exe run_studio.py
.venv\Scripts\python.exe scripts/build_windows.py --iscc 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
```

Le script écrit l’installeur, l’archive portable et les empreintes dans `release/`.
Pour isoler les données de développement : définir `BSC_STUDIO_DATA_DIR`.
La base peut être sauvegardée depuis Paramètres ; sauvegarder également `audio/`
et `takes/` pour conserver les enregistrements. Les secrets chiffrés ne sont pas
transférables à un autre compte Windows.

## Publier une nouvelle version

1. Modifier `__version__` dans `bsc_studio/__init__.py` et la version de `pyproject.toml`.
2. Mettre à jour `RELEASE_NOTES.md`.
3. Envoyer ces changements sur `main`.

Le workflow **Windows installer** teste et compile sur Windows, vérifie le programme
emballé hors ligne, puis crée la Release `vX.Y.Z` avec les trois fichiers de distribution.
Une Release existante est préservée : incrémenter la version pour publier un correctif.
Le workflow peut aussi être lancé manuellement. Les pull requests compilent et testent
sans publier de Release. GitHub Actions doit être activé pour le dépôt.

## Structure

- `bsc_studio/` : interface, données, OpenAI et mises à jour.
- `engine/bsc_radio/` : moteur éditorial réutilisé de Houblon FM.
- `assets/` : personnages, formats, prompts et icône.
- `packaging/` : installeur Inno Setup.
- `scripts/` : construction des distributions.
- `tests/` : intégrité des mises à jour, versions, données, cache, DPAPI et protocole vocal simulé.

Les modules Imports du site, Statistiques, Bières et Bars sont annoncés dans l’interface
comme **à venir** ; aucune connexion au site Infomaniak n’est encore implémentée.

Licence AGPL-3.0-or-later. Voir `LICENSE`, `UPSTREAM.md` et `THIRD_PARTY_NOTICES.md`.
