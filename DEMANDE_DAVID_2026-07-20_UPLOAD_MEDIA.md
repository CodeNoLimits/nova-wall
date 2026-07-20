# 📎 DEMANDE DAVID — 2026-07-20 17:30 — UPLOAD MÉDIAS & FICHIERS DEPUIS LE TÉLÉPHONE

> Relayée par la session `ad86f886` (David : « dis à la session qui s'occupe de Nova Wall d'ajouter…
> et si elle dort tu la réveilles »). Session propriétaire = `94b2fbde` (externe = lecture seule,
> non injectable) → un terminal géré a été réveillé pour exécuter.

## CE QUE DAVID DEMANDE (mot pour mot)

« Ajouter la possibilité d'envoyer sur le terminal ou d'uploader directement des photos du téléphone,
ou des vidéos, ou des audios, avec aussi upload direct de fichier depuis le tel — autant dans la
fenêtre où on clique sur une session : **en dessous de la barre de texte qui se trouve à gauche du
bouton bleu Injecter**, tu mets tous ces boutons qui permettent ça. »

## EMPLACEMENT EXACT (ne pas se tromper)

`web/index.html` ligne ~565 — la modale de zoom d'une session :

```html
<div class="row" style="margin-top:6px">
  <input id="z-in" placeholder="ton message… (Entrée)" style="flex:3">
  <button class="primary" id="z-send" style="flex:1">Injecter ➤</button>
</div>
```

→ **JUSTE EN DESSOUS de cette `div.row`**, ajouter une barre d'actions média (4 boutons minimum) :

| Bouton | Comportement iPhone attendu |
|---|---|
| 📷 Photo | `<input type="file" accept="image/*" capture="environment">` → ouvre l'appareil photo **ou** la pellicule |
| 🎬 Vidéo | `accept="video/*"` (+ `capture`) |
| 🎤 Audio | enregistrement direct (MediaRecorder) **et** `accept="audio/*"` pour un fichier existant |
| 📎 Fichier | `<input type="file">` sans filtre (PDF, zip, docx, n'importe quoi) — multiple autorisé |

## COMPORTEMENT ATTENDU (bout en bout)

1. David choisit/capture depuis son **téléphone** (Safari iOS, via `wall.dreamnovamcp.com` + token).
2. Le fichier monte sur le Mac → nouvelle route `POST /api/upload` (multipart **ou** base64 JSON,
   Python stdlib uniquement, 0 dépendance — c'est la règle du projet).
3. Stockage : `~/nova-wall/state/uploads/<session_id>/<YYYYMMDD-HHMMSS>_<nom_sanitizé>`
   (chemin **ABSOLU** — piège prouvé : un chemin relatif est introuvable côté service).
4. Puis **injection automatique** dans la session ciblée, exactement comme `/api/fs/send` le fait
   déjà : `"Prends en compte ce fichier : <chemin absolu> — lis-le et intègre-le à ton travail."`
   (adapter la phrase au type : photo / vidéo / audio / document).
5. Retour visuel dans la modale : nom du fichier + taille + ✅/❌, et le chemin copiable.

## CONTRAINTES NON NÉGOCIABLES

- **Session externe = lecture seule** : si la cible n'est pas un terminal tmux géré, le fichier doit
  quand même être **stocké** et le chemin **affiché** (message honnête « caméra en lecture seule,
  fichier enregistré ici : … »), jamais un faux « envoyé ».
- **Auth token** conservée sur la nouvelle route (`_auth`) — sinon trou de sécurité sur le tunnel public.
- **Gros fichiers** : vidéos iPhone = 100 Mo+ → relever la limite de corps, lire en flux, et
  ⛔ JAMAIS dupliquer/empiler sur disque (règle disque AGENTS.md §8). Nettoyer les temporaires.
- **V1 = PROD (`~/nova-wall/`, port 8790, `wall.dreamnovamcp.com`)** : c'est CE que le téléphone de
  David utilise → la feature doit atterrir ICI. Miroir ensuite dans `~/nova-wall-v2/` (lab).
- **PWA** : le `sw.js` ne doit pas mettre les uploads en cache ni casser le `POST`.
- Anti-vol-de-focus : rien qui ouvre une fenêtre, `open -g` uniquement.

## PREUVE EXIGÉE AVANT DE DIRE « FAIT » (X/Y=Z%)

1. `curl -F` (ou base64) d'une image → HTTP 200 + fichier réellement présent sur disque (`ls -l`).
2. Injection réellement reçue par un terminal géré (`tmux capture-pane` montre la ligne).
3. Screenshot du rendu **mobile** (largeur iPhone) montrant les 4 boutons sous la barre de texte.
4. Test des 4 types (photo / vidéo / audio / fichier quelconque) → 4/4.
