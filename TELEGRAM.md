# 📲 NOVA WALL depuis Telegram (pont natif)
Écris dans **@ClaudeOpusDavidbot** (canal NOVA TERMINAL). Toute commande commence par `wall`.

| Commande | Effet |
|---|---|
| `wall` | état du mur : live/total/gérés + top sessions (titre ▸ tâche) |
| `wall shot` | 📸 **capture du mur** envoyée en photo |
| `wall shot grok` | capture d'un onglet Chrome (grok · gemini · notebooklm · claude · gmail) |
| `wall list` | terminaux gérés |
| `wall new opus [nom]` | crée un terminal (opus·sonnet·fable·opus-dngrok·grok·grok-dngrok) |
| `wall to <id> <message>` | **écrit dans un terminal** (le vrai Claude répond) |
| `wall read <id>` | dernières lignes d'une session |
| `wall sub <id> verify` | sous-session assignée (feature·troubleshoot·verify) |
| `wall link <a> <b> bridge` | liaison + exécution immédiate |
| `wall kill <id>` | ferme un terminal géré |
| `wall link-url` | renvoie le lien web du mur |

`<id>` accepte un **fragment de nom ou d'id** (ex. `wall to hafatsa continue`).

## Technique
- Module : `~/nova-wall-v2/telegram_bridge.py` (stdlib) — appelle l'API HTTP du mur.
- Greffe : `~/etz-chaim/watcher/nova_terminal.py` (branche `low.startswith('wall')`, rechargée à chaud, log `WALL cmd=`).
- Backup du moteur avant greffe : `nova_terminal.py.bak-prewall-*`.
- Pointe sur la **V2 LAB** (8890) ; pour la V1 : `NOVA_WALL_API=http://127.0.0.1:8790`.
- ⚠️ Un bot ne reçoit pas ses propres messages → tester avec `handle_update` simulé, pas `sendMessage`.
