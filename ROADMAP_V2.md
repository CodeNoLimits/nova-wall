# NOVA WALL — ROADMAP V2 (demandes David 2026-07-20 après-midi)
> Source de vérité pour la prochaine session de build. Chaque item = demande explicite.

## P0 — Compréhension & adoption
1. **Tutoriel intégré niveau "ouf"** : section Tutoriel dédiée (pas juste ❓) avec **vidéos grok/dn-grok par étape** (Liaisons, Fusion, Studio, Écrans, Graphe, mobile). ✅ v1 texte pas-à-pas livrée le 20/07 (❓ enrichi) ; vidéos à générer (`dn-grok --video`, 1 par feature, embed dans l'app).
2. **Titres à perfectionner** : prompt dn-grok plus riche (inclure cwd+clients+wins), re-titrage plus fréquent des sessions actives, badge de fraîcheur. (v1 livrée, David: « pas assez perfectionnés ».)

## P1 — Canaux & distribution
3. **Pont Telegram ↔ NOVA WALL** : commandes @ClaudeOpusDavidbot (`wall status`, `wall inject <id> <msg>`, `wall spawn <mode>`, screenshot du mur envoyé sur Telegram) — brancher `nova_terminal.py` sur l'API du mur (elle est déjà pilotable en HTTP, preuve nova-wall-ctl).
4. **Paquet téléchargeable** (ex. pour Leeya sur son Mac) : installeur 1 commande (`curl … | bash` ou .dmg) : dépendances (tmux, python3), config token, launchd, onboarding. + mode « client léger » (juste ouvrir l'URL distante).
5. **Argumentaire vs Claude Cowork & co** (page + section README) : nos plus = multi-moteurs (Claude+Grok+GLM+local), N sessions simultanées visibles, injection/fusion inter-sessions, Chrome authentifié embarqué, fichiers du Mac à distance, 0 vol de focus, self-hosted/0 abonnement, extensible.

## P2 — Intelligence
6. **Mode Karpathy par session** : toggle sur chaque case → boucle d'amélioration continue (skill `karpathy-optimization-loop`) injectée périodiquement (réutiliser le moteur loop 🔁 + prompt Karpathy).
7. **Agent superviseur intégré** : un agent connecté à l'app qui surveille TOUS les écrans en continu et poste des **suggestions par session + globales** (réutiliser `halfhour-session-supervisor` + fichiers `~/omniscient/session_suggestions/` → les afficher DANS le mur, badge 💡 par case).
8. **Mine des douleurs développeurs** (Reddit/GitHub/forums Anthropic) : recherche des plaintes récurrentes (perte de contexte, sessions multiples, autocompact…) → features qui y répondent + arguments marketing. (dn-grok/WebSearch.)

## P3 — Utilitaires
9. **Vue Keychain** : écran listant les NOMS de secrets (`dn-secret --list`, jamais les valeurs en clair — révélation à la demande avec confirmation, local uniquement, JAMAIS via le tunnel).
10. **Écrans d'automations** : cases dédiées à l'observation des automations vivantes (daemons launchd, crons, workers nova-bg) — statut, dernier run, log tail, sans alourdir le mur principal (page « Automations » du mode Écrans).
11. **Terminal Grok 1-clic** : ✅ déjà livré (modes grok / grok-dngrok dans ＋ Terminal et Studio) — à montrer dans le tutoriel.

## Notes d'implémentation
- L'app est DÉJÀ une API complète (voir nova-wall-ctl) → le pont Telegram est trivial côté mur.
- Suggestions superviseur : lire `~/omniscient/session_suggestions/<id>.md` et l'afficher dans la tuile correspondante (la donnée existe déjà, daemon /30min actif).
- Paquet : garder stdlib-only côté serveur = installation quasi 0-dépendance.
