# Origine du moteur

Le dossier `engine/bsc_radio`, les modèles `assets/config` et les prompts `assets/prompts`
proviennent de https://github.com/brewers-social-club/houblon-fm
à la révision 87042ee8f90b2a0888b9e54fa0d46a4a1c07b54b (18 octobre 2026).
Le projet d’origine déclare la licence AGPL-3.0-or-later.
Les noms et les contenus restent ceux de leurs ayants droit.

Adaptations locales : verrous et signaux compatibles Windows ; identifiants d’épisodes
avec précision microseconde ; fermeture déterministe des connexions SQLite. Le studio ajoute son interface, son stockage chiffré Windows,
les connecteurs OpenAI, le cache vocal et les mises à jour GitHub.

Les services de diffusion serveur et la publication automatique du moteur ne sont pas
exposés par l’interface de cette première version du studio.
