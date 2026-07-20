# Pourquoi NOVA WALL — et en quoi c'est différent de Cowork / Cursor / Replit

## Le problème (celui que tout dev multi-agents connaît)
Tu lances 5, 10, 40 sessions d'IA en parallèle. Puis :
- tu **ne sais plus** laquelle fait quoi (tu scrolles entre 40 fenêtres de terminal) ;
- deux sessions **éditent le même dossier** sans le savoir → conflits ;
- une session a **déjà résolu** le bug qu'une autre est en train de re-payer ;
- une session est **bloquée** depuis 40 minutes et tu ne l'apprends qu'en la rouvrant ;
- tu quittes ton bureau → **tu perds le contrôle** de tout.

## La réponse : une salle de contrôle, pas un énième IDE
NOVA WALL n'est pas un éditeur. C'est la **couche mission-control au-dessus** de tes agents :
un mur de « caméras » où chaque case est une session vivante, avec ce qu'elle fait, ce qu'elle a
réussi, ce qui la bloque — et de quoi **agir** dessus.

## Tableau comparatif honnête

| | **NOVA WALL** | Claude Cowork | Cursor / Windsurf | Replit Agent | tmux + scripts |
|---|---|---|---|---|---|
| Voir N sessions d'un coup d'œil | ✅ mur de caméras | ❌ 1 fil | ❌ 1 IDE | ❌ 1 workspace | ⚠️ brut |
| **Résumé sémantique** (but / réussites / blocages) | ✅ auto | ❌ | ❌ | ❌ | ❌ |
| Multi-moteurs (Claude **+ Grok** + GLM + local) | ✅ | ❌ Claude only | ⚠️ modèles, pas agents CLI | ❌ | ✅ manuel |
| **Transfert de contexte entre sessions** | ✅ inject / bridge / apprendre | ❌ | ❌ | ❌ | ❌ |
| **Fusion** de 2 sessions en une 3ᵉ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Sous-agents assignés (feature / debug / vérif) | ✅ 1 clic | ⚠️ | ⚠️ | ⚠️ | ❌ |
| Navigateur **authentifié** embarqué (Gemini, NotebookLM, Grok…) | ✅ CDP live | ❌ | ❌ | ❌ | ❌ |
| Fichiers du Mac **à distance** | ✅ | ❌ | ❌ | ⚠️ cloud only | ❌ |
| Pilotable depuis le **téléphone** | ✅ web + Telegram | ⚠️ | ❌ | ⚠️ | ❌ |
| Graphe de connaissances entre sessions | ✅ | ❌ | ❌ | ❌ | ❌ |
| Self-hosted, **0 abonnement**, tes données restent chez toi | ✅ | ❌ SaaS | ❌ SaaS | ❌ SaaS | ✅ |
| Vol de focus | ❌ jamais (tmux + CDP) | — | — | — | ⚠️ |

## Les 3 idées qui font la différence
1. **Le terminal EST l'API.** On pilote les agents par leur TUI (tmux) : aucun SDK requis, donc
   **tout agent CLI présent ou futur** est absorbable — Claude Code, Grok CLI, le prochain.
2. **La couche sémantique.** On ne montre pas des logs bruts : on extrait *but · réussites · blocages ·
   client · tâche en cours* des transcripts, et on les relie en graphe.
3. **Les sessions se parlent.** Injecter, bridger, faire s'apprendre mutuellement, fusionner —
   le savoir cesse d'être prisonnier d'une fenêtre.

## Limites assumées (on préfère le dire)
- Lecture d'état par capture du terminal : à ré-ajuster si un éditeur change son affichage.
- Pas (encore) de signal de fin structuré par agent : on lit l'écran.
- macOS d'abord (tmux + CDP + launchd).
- Accès distant protégé par jeton : **garde ton lien privé** comme un mot de passe.

## Pour qui
Freelances et studios qui font tourner **3 à 50 agents** en parallèle : agences IA, équipes produit,
créateurs de contenu automatisé, chercheurs. Si tu n'as qu'une session à la fois, tu n'as pas besoin
de NOVA WALL — et on te le dit franchement.

## Installer (macOS, 2 lignes)
```bash
curl -fsSL https://raw.githubusercontent.com/CodeNoLimits/nova-wall/main/install.sh -o ~/nova-install.sh
bash ~/nova-install.sh
```
Ça installe le mur, un service permanent, ton **code de connexion** et ton **lien de partage**.
