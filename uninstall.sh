#!/bin/bash
# NOVA WALL — désinstallation propre (ne supprime PAS tes fichiers de travail).
echo "🧹 Désinstallation NOVA WALL…"
U=$(id -u)
for L in com.novawall.local com.novawall.share; do
  launchctl bootout "gui/$U/$L" 2>/dev/null && echo "  service $L arrêté"
  rm -f "$HOME/Library/LaunchAgents/$L.plist"
done
for P in 8790 8791 8792; do lsof -ti tcp:$P 2>/dev/null | xargs kill 2>/dev/null; done
pkill -f "cloudflared --config /dev/null tunnel --url http://127.0.0.1:8791" 2>/dev/null
echo "✅ Services retirés. Le dossier ~/nova-wall/ est conservé (supprime-le à la main si tu veux)."
