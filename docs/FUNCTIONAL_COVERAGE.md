# Fonctions Houblon FM présentes dans BSC Radio Studio

État de la version 0.1.1. Moteur amont :
[Houblon FM, révision 87042ee](https://github.com/brewers-social-club/houblon-fm/commit/87042ee8f90b2a0888b9e54fa0d46a4a1c07b54b).

**La présence des fichiers du moteur ne signifie pas que toutes ses fonctions sont utilisables dans l’application Windows.**
La V1 a été construite comme un studio de création de podcasts, après la précision de cet objectif.

| Fonction | Disponible dans le studio Windows | Éléments restant à intégrer |
|---|---|---|
| Import de texte, TXT/Markdown, URL et scripts JSON | Oui | Interface adaptée au poste Windows |
| Collecte RSS, YouTube, Facebook, Instagram et veille Google | Non | Collecteurs présents dans le moteur ; gestion des sources et lancement à raccorder à l’interface |
| Extraction de faits depuis les informations choisies | Oui, via OpenAI | Suivi détaillé des faits et provenance à développer |
| Regroupement automatique des sujets | Non | Fonctions du moteur présentes, non appelées par le parcours du studio |
| Écriture des dialogues selon les formats | Oui, via OpenAI | Le format Courrier des auditeurs n’est pas exposé |
| Vérification phrase par phrase, réécriture et rejet éditorial | Non | Logique présente ; le parcours du studio n’appelle pas encore cette étape |
| Personnages Camille, Marcel, Jeanne et Noé | Oui | Réglages de jeu détaillés à exposer |
| Génération vocale OpenAI | Oui, connecteur ajouté | Clé API et choix explicite des voix ; voix Rivage non confirmée dans l’API |
| Fournisseurs vocaux ElevenLabs et Gemini | Non dans l’interface | Code présent ; paramètres et commandes à connecter |
| Fournisseur éditorial Codex | Non dans l’interface | Code présent ; installation et connexion CLI non gérées par le studio |
| Prises en cache, lecture et export MP3/WAV/JSON | Oui | Montage, transitions et habillage à compléter |
| Jingles, identifiants, promos, musiques et horloge d’antenne | Non | Producteurs et configuration présents ; aucun écran de production d’habillage |
| Programmation automatique des émissions | Non | Les durées/formats sont repris ; les timers Linux ne sont pas un planificateur Windows |
| Site statique, transcription publique et RSS podcast | Non | Générateur du moteur présent ; publication non exposée |
| Direct Icecast/Liquidsoap et relais YouTube Live | Non | Services de diffusion du dépôt amont non embarqués dans l’application |
| Administration web, comptes et avis auditeurs | Non | Certains modules Python sont conservés ; le service web n’est pas livré comme fonction active |
| Audience, incidents, budgets et journaux d’exploitation | Non | Le studio affiche uniquement les compteurs locaux d’épisodes, imports et audios prêts |
| Gestion complète du site BSC, bières et bars | Non | Modules distincts à développer et à relier aux API du site |

L’interface 0.1.1 reprend l’identité visuelle de brewerssocialclub.com.
Cette mise à jour ne modifie pas cette couverture fonctionnelle.
