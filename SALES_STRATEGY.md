# 💰 NOVA WALL — Stratégie de mise en vente (2026-07-20)

## Le positionnement (une phrase)
**« Mission control pour flottes d'agents IA. »** Pas un IDE, pas un chat : la **couche de supervision
au-dessus** de Claude Code / Grok / n'importe quel agent CLI. On ne concurrence pas Cursor — on se pose dessus.

## À qui ça se vend (par ordre de facilité)
1. **Freelances IA / indie hackers** qui lancent 3-10 agents en parallèle (le plus gros volume, achat impulsif).
2. **Petites agences IA / studios** (3-15 personnes) — douleur réelle : personne ne sait ce que font les agents.
3. **Équipes produit** qui font tourner des agents de nuit (migrations, audits, contenu).
4. **Créateurs de contenu automatisé** (le mode Écrans + Chrome authentifié leur parle immédiatement).
Anti-cible assumée : celui qui n'ouvre qu'une session à la fois. Le dire franchement = crédibilité.

## Le modèle de prix (3 offres, ancrage classique)
| Offre | Prix | Contenu |
|---|---|---|
| **Solo** | **39 $/mois** (ou 390 $/an) | 1 machine, sessions illimitées, mobile, Telegram |
| **Studio** | **149 $/mois** | 5 machines, multi-utilisateurs, support prioritaire |
| **Self-hosted (licence perpétuelle)** | **490 $** one-time | code source, install illimitée, 1 an de MAJ |
| **Sur-mesure / intégration** | 2 000-5 000 $ | déploiement + adaptation au workflow du client |
Comparables : Cursor 20 $, Replit Core 25 $, Warp 18 $ — **notre valeur est complémentaire**, pas concurrente.
Le prix 39 $ se justifie dès qu'on économise **1 heure/mois** de confusion entre sessions.

## Modèle de distribution : open-core (le plus rentable ici)
- **Public sur GitHub** (déjà fait) = acquisition. Le repo EST le meilleur canal : les devs qui souffrent
  du problème le trouvent en cherchant « manage multiple claude code sessions ».
- **Gratuit** : le mur, l'écriture, les liaisons, le graphe (assez pour tomber amoureux).
- **Payant (NOVA WALL Pro)** : multi-machines, équipes/rôles, historique & replay, agent superviseur
  avec suggestions, mode Karpathy, sauvegarde cloud chiffrée, support.
- **Hook DreamNova** : dans le README, un bandeau « Besoin d'une flotte d'agents sur mesure ? » → nos services
  (c'est là que sont les vrais tickets 2-5 k$).

## Plan de lancement (4 semaines, 0 $ de budget)
**S1 — Preuve sociale visuelle.** Vidéo 60-90 s (le mur qui s'allume, une fusion, le pilotage depuis le
téléphone). C'est un produit qui *se voit* : la démo vend seule. → X/Twitter, LinkedIn, r/ClaudeAI,
r/LocalLLaMA, Hacker News (« Show HN: I built a video-wall for my 40 AI coding sessions »).
**S2 — Contenu douleur.** 3 posts qui décrivent la douleur avant la solution (« j'ai perdu 2h parce que
2 sessions éditaient le même fichier »). Chaque post finit par le repo.
**S3 — Waitlist Pro.** Landing (on sait faire) + formulaire → mesurer l'intention avant de coder le SaaS.
**S4 — Premiers clients.** DM ciblés aux gens qui ont *déjà* commenté « moi aussi je gère 10 sessions ».
Offre fondateur : **-50 % à vie pour les 20 premiers** (19 $/mois).

## Objectifs chiffrés réalistes
- 500-2 000 ⭐ GitHub en 3 mois si la vidéo tourne (produit très visuel, niche active).
- Conversion open-source → payant : 1-3 % des utilisateurs actifs.
- **300 users payants × 39 $ ≈ 11 700 $/mois.** 1 000 users ≈ 39 000 $/mois.
- Plus réaliste à 3 mois : **20-60 clients (800-2 400 $/mois)** + 1-2 missions sur-mesure (3-8 k$).

## Ce qu'il faut finir AVANT de vendre (honnête)
1. **Sécurité** : le jeton dans l'URL doit devenir un vrai login (au minimum jeton tournant + expiration).
2. **Robustesse** : la lecture d'écran casse si l'UI d'un agent change → détecter et prévenir.
3. **Onboarding** : la vidéo tutoriel intégrée (roadmap P0) — sans elle, 50 % des gens ne comprennent pas
   la fusion/les liaisons (constaté sur David lui-même).
4. **Windows/Linux** : aujourd'hui macOS only (tmux + CDP + launchd). Linux = 80 % du travail déjà portable.
5. **Licence** : passer d'un repo sans licence à **Apache-2.0** (open) + EULA pour le Pro.

## Risques
- Un éditeur (Anthropic/Cursor) sort son propre multiplexeur → notre défense = **multi-moteurs** (eux ne
  supporteront jamais Grok chez Claude, ni l'inverse) + self-hosted.
- Copiabilité du code (2 jours) → notre moat = **la couche sémantique** (titres, victoires/blocages, graphe,
  suggestions) et la vitesse d'itération.

## Prochaine action concrète (la seule qui compte)
**Faire la vidéo de 60 s et la poster.** Tout le reste (pricing, SaaS, licences) se décide APRÈS
avoir mesuré la réaction. Le produit fonctionne déjà — il ne manque que des yeux dessus.
