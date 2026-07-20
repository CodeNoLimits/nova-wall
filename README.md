# NOVA WALL — Command Center des sessions IA
> Un poste de vidéosurveillance pour tes terminaux Claude & Grok. Chaque case = une caméra sur une session.

## Lancer
```bash
nova-wall            # démarre le serveur + ouvre le mur (arrière-plan, zéro vol de focus)
# → http://127.0.0.1:8790
```
Pose la fenêtre sur ton écran en haut à droite. Auto-refresh toutes les 4 s.

## Ce que tu vois
- **Grille configurable** (2×2 / 3×3 / 4×4 / 5×) de caméras sur TES sessions vivantes.
- Par case : LED live · projet · id session · **badges client** · **badge modèle réel** (Opus/Sonnet/Fable/Haiku/Grok/GLM) · **but en cours** · victoires ✓ / blocages ⚠ · âge.
- **Filtre** (client/dossier), compteurs live/total/gérés.

## Actions
- **＋ Terminal** : lance une session gérée (tmux caché) dans le mode choisi — Opus, Sonnet, Fable, Opus+dnGrok, Fable+dnGrok, Grok, Grok+dnGrok. Caméra = vrai flux terminal (`tmux capture-pane`).
- **👁** : agrandir une caméra (flux complet) + champ d'injection.
- **🔗 Liaisons** (façon n8n) : clique source → cible → choisis le lien :
  - **→ Injecter** (1 sens) · **⇄ Bridge** (bidirectionnel) · **🎓 Apprendre** (échange de leçons).
  - Clique une flèche pour **exécuter** le transfert (ou la supprimer).
- **⧉ Fusion** : sélectionne 2 sessions → nouveau terminal enfant nourri des deux contextes.
- **⧉⧉** : détacher le mur sur un 2ᵉ écran.
- Sélecteur de modèle par case : relance un terminal géré dans le nouveau régime.

## Architecture
- `server.py` — backend stdlib (aucune dépendance). Sources : `~/omniscient/synergy.json` (but/victoires/blocages/client par session, régénéré /10min) + queue des `.jsonl` (modèle + fraîcheur réels) + `tmux` (spawn/capture/inject) + bus `coord`.
- `web/index.html` — le mur (vanilla JS, offline, flèches SVG).
- `state/` — `managed.json` (terminaux gérés), `links.json` (liaisons), `server.log`.

## Anti-vol-de-focus (12ème JAMAIS)
Injection = `tmux send-keys` (tape DANS le pty, jamais au niveau macOS). Terminaux = tmux détachés cachés.
Aucun `osascript`/`activate`/`open -a` sans `-g`. Jamais de fenêtre volée.

## Sécurité
Écoute sur `127.0.0.1` uniquement (local). `/api/kill` refuse tout ce qui n'est pas un terminal géré `nova-*`.
Lecture seule sur les sessions externes (caméra) ; seules les sessions gérées sont injectables.

## Roadmap
Terminal embarqué live (xterm.js) · aperçus-écran optionnels · alertes DAVID_ACTION_REQUIRED clignotantes ·
détection de collision same-dossier · snapshot du mur · pilotage vocal via Nova Command · app macOS signée.
Vision + commercialisation : `PLAN_1000_MOTS.md`.

## 🏷️ Produit (vision commerciale)
NOVA WALL = **mission control pour flottes d'agents IA** (Claude Code, Grok, tout CLI) : mur de caméras
live, injection/bridge/fusion entre sessions, sous-sessions assignées, mode Écrans (Chrome embarqué),
Studio façon Cursor (fichiers·terminal·agent), graphe de connaissances, contrôle à distance total
(tunnel + token). Cible : studios/agences qui font tourner 10-50 agents. Distribution : repo privé
`CodeNoLimits/nova-wall` → reskin/bundle vendable ou hook open-source vers nos services DreamNova.
