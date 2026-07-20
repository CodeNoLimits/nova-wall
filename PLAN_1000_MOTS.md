# NOVA WALL — Le centre de commande de tes IA
### Plan directeur (≈1000 mots) — 2026-07-20

## L'idée, en une image
Un **poste de vidéosurveillance**, mais les caméras ne filment pas des couloirs : elles filment tes
**terminaux Claude et Grok**. Un seul écran — celui en haut à droite de tes trois moniteurs, ou un bureau
dédié si tu n'en as qu'un — affiche une **grille de 9 cases** (extensible), et chaque case est une caméra
vivante braquée sur une session d'IA. En un coup d'œil tu sais **qui travaille sur quoi**, sans jamais
scroller à trois doigts entre quarante fenêtres. Tu ne te perds plus : le mur *est* la carte.

## Ce qui est déjà construit et PROUVÉ (aujourd'hui, pas une maquette)
`~/nova-wall/` — une app locale (Python stdlib, zéro dépendance) servie sur `http://127.0.0.1:8790`.
Lancement : `~/nova-wall/nova-wall`. Au moment où j'écris : **51 sessions détectées, 10 vivantes**,
chacune avec son vrai modèle, son projet, son but, ses victoires et ses blocages. Deux mécaniques
critiques testées end-to-end : l'**injection** (message écrit *dans* le pty d'une session, preuve fichier)
et le **spawn** d'un terminal géré multi-modèle. C'est un produit, pas un slide.

## Les caméras
Le contenu de chaque case ne s'invente pas : il vient de deux sources déjà vivantes sur ta machine.
(1) `synergy.json` (régénéré toutes les 10 min par un daemon) qui lit les transcripts `.jsonl` de chaque
session et en extrait **but, victoires, blocages, client, dossier, URLs**. (2) La **queue du transcript**
lue en direct pour afficher le **modèle réel** (Opus/Sonnet/Fable/Haiku/Grok/GLM) et la fraîcheur
(LED verte = actif < 15 min, ambre = brûlant < 40 s). Pour les terminaux que NOVA WALL lance lui-même,
la caméra montre carrément le **contenu live du terminal** (`tmux capture-pane`) : du vrai texte qui défile.

## Le sélecteur de modèle, par case
Sous chaque caméra, un menu déroulant. Tu choisis le régime de la session : **Opus** (effort max),
**Sonnet**, **Fable**, **Opus + dnGrok**, **Fable + dnGrok** (le pont qu'on a bâti — Claude orchestre,
Grok 4.5 fait la colonne recherche/vérif à 0 $), **Grok** seul, ou **Grok + dnGrok**. Pour un terminal
géré, changer de mode le **relance** dans ce régime, même dossier. Les sessions Grok apparaissent sur le
mur au même titre que les Claude : un seul mur, tous tes cerveaux.

## Les flèches — l'inspiration n8n
C'est là que le mur devient un **atelier**. Tu actives « Liaisons », tu cliques une caméra source puis
une cible, et tu choisis le type de lien — exactement tes trois nuances :
- **→ Injecter** (unidirectionnel) : pousser le contexte/les découvertes du terminal A **dans** le terminal
  B, une fois. « Prends ce que l'autre a trouvé et continue. »
- **⇄ Bridge** (bidirectionnel) : les deux se relaient en continu, chacun nourrit l'autre — le pont.
- **🎓 Apprendre** (bidirectionnel « à échelle ») : les deux **s'échangent leurs leçons et techniques**,
  pas juste des données. A explique à B *comment* il a résolu, B fait pareil. Montée en compétence croisée.
Les flèches se dessinent en SVG au-dessus du mur (cyan/ambre/violet, animées), et un clic sur une flèche
**exécute** le transfert (via `tmux send-keys` pour les cibles gérées, via le bus de coordination sinon).

## La fusion
Le bouton **⧉ Fusion** : tu sélectionnes deux sessions, NOVA WALL **crée un nouveau terminal** (mode
Opus + dnGrok par défaut) et lui **injecte les deux contextes** — un enfant qui hérite des technologies
des deux parents. Idéal quand deux pistes du matin doivent converger en une.

## Les containers — Cursor/Antigravity, mais maison
Chaque terminal lancé depuis le mur vit dans un **tmux détaché** : un conteneur caché, **zéro vol de
focus** (on tape dans le pty, jamais au niveau macOS — ta règle d'or est respectée par construction).
Tu peux t'y attacher dans un vrai terminal (`tmux attach -t nova-<nom>`), le laisser travailler « à côté »
pendant que tu regardes ailleurs, brancher un MCP, ou faire tourner Grok en parallèle de Claude sur la
même tâche. Le mur devient ton IDE d'agents.

## Multi-écrans
Bouton **⧉⧉** : le mur se détache dans une fenêtre qu'on pose sur le moniteur en haut à droite. Neuf
sessions par écran, réaliste et lisible ; au-delà, on multiplie les fenêtres (un mur par écran) ou on passe
en 4×4 / 5× d'un clic. Un champ **filtre** isole instantanément « esther », « ghezi », « hafatsa »…

## Mes ramifications (au-delà de ce que tu as dit)
1. **Alertes** : une caméra dont le blocage contient « DAVID_ACTION_REQUIRED » clignote en rouge — le mur
   te *hèle* au lieu que tu le surveilles.
2. **Détection de collision** : deux sessions qui éditent le même dossier → liseré d'avertissement (on a
   déjà la donnée dans synergy). Fini les conflits git silencieux.
3. **Enregistreur** : bouton « snapshot du mur » → une image horodatée de l'état de tout l'empire, pour tes
   handovers et pour montrer aux investisseurs « voici 40 agents qui tournent ».
4. **Voix** : dire « injecte esther dans keren » depuis Nova Command (déjà branché en Telegram/WhatsApp).
5. **Playback** : rejouer l'historique d'une session en accéléré (les `.jsonl` sont là).

## Commercialisation
C'est un **produit vendable** : « mission control pour flottes d'agents IA ». Le marché des agents explose
et personne n'a le **poste de vidéosurveillance** qui va avec. On le durcit (auth, multi-machine via le pont
Dell, thèmes), on le sort en app macOS signée, et on le vend aux studios/agences qui font tourner 10-50
agents. La démo se vend toute seule : on ouvre le mur, quarante caméras s'allument.

## Prochaines étapes
Protos visuels dn-grok (photos + vidéo) en cours de génération ; variante d'interface via Google Stitch ;
puis, si tu valides : terminal embarqué live (xterm.js), vrais aperçus-écran optionnels, et empaquetage
`.app`. Le squelette est debout et il respire — on ne fait plus qu'ajouter des muscles.
