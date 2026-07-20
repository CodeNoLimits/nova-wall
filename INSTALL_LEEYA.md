# 💜 NOVA WALL — installation sur ton Mac (5 minutes)

Bonjour Leeya ! Voici comment installer NOVA WALL — le tableau de bord qui montre tout ce que
les assistants IA font sur ton ordinateur, et qui permet à David de t'aider à distance si tu le souhaites.

## 1) Installer (copie-colle ces 2 lignes dans le Terminal)
Ouvre **Terminal** (Cmd+Espace → tape « Terminal »), puis colle :

```bash
curl -fsSL https://raw.githubusercontent.com/CodeNoLimits/nova-wall/main/install.sh -o ~/nova-install.sh
bash ~/nova-install.sh
```

Ou, si tu as reçu le fichier **NOVA_WALL.zip** : double-clique dessus, puis dans le Terminal :
```bash
cd ~/Downloads/nova-wall && bash install.sh
```

## 2) Ce que tu obtiens à la fin
L'installation affiche 3 choses — **garde-les** :
- 🖥️ **Sur ton Mac** : `http://127.0.0.1:8790` (ouvre-le dans Safari ou Chrome)
- 🔑 **Ton code de connexion** (une suite de lettres/chiffres) — c'est ton mot de passe, garde-le privé
- 📤 **Ton lien de partage** — **c'est ce lien que tu envoies à David** s'il doit voir/aider

## 3) Mettre l'app sur ton téléphone (optionnel)
Ouvre ton lien de partage sur ton iPhone dans **Safari** → bouton **Partager** → **« Sur l'écran d'accueil »**.
L'icône NOVA WALL apparaît comme une vraie application.

## 4) Comment ça marche (l'essentiel)
- Chaque **case** = une session d'IA en cours sur ton Mac (avec son titre et ce qu'elle fait).
- Le bouton **❓** dans l'app explique tout, étape par étape.
- Bouton **＋ Terminal** : lance un nouvel assistant (Claude ou Grok).
- Tu peux **écrire dans une case** pour parler directement à l'assistant.

## 5) Si tu veux tout retirer
```bash
bash ~/nova-wall/uninstall.sh
```
Ça arrête tout proprement (tes fichiers personnels ne sont jamais touchés).

## Confidentialité
Tout tourne **sur ton Mac** — rien n'est envoyé à un service externe. Le lien de partage n'est
accessible qu'avec ton code. Si tu ne partages pas ton lien, personne ne peut voir ton écran.
