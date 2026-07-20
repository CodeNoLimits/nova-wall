#!/bin/bash
# NOVA WALL — installeur 1 commande (macOS).
#   curl -fsSL https://raw.githubusercontent.com/CodeNoLimits/nova-wall/main/install.sh | bash
# Installe le mur localement + service permanent + lien de partage avec CODE DE CONNEXION.
set -e
echo "🛰️  NOVA WALL — installation…"
H="$HOME"; ROOT="$H/nova-wall"
PY="$(command -v python3 || echo /usr/bin/python3)"

# 1) code
if [ -d "$ROOT/.git" ]; then git -C "$ROOT" pull -q || true
else git clone -q https://github.com/CodeNoLimits/nova-wall.git "$ROOT"; fi
mkdir -p "$ROOT/state"

# 2) tmux (pour les terminaux gérés — facultatif pour la vue caméras)
command -v tmux >/dev/null || { command -v brew >/dev/null && brew install -q tmux || echo "⚠️ tmux absent (brew install tmux) — caméras OK, terminaux gérés indisponibles"; }

# 3) CODE DE CONNEXION (token)
[ -s "$ROOT/state/mobile_token.txt" ] || openssl rand -hex 12 > "$ROOT/state/mobile_token.txt"
TOKEN="$(cat "$ROOT/state/mobile_token.txt")"

# 4) services permanents (launchd)
mkplist() { cat > "$H/Library/LaunchAgents/$1.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$1</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>-c</string><string>$2</string></array>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$ROOT/state/$3.log</string>
  <key>StandardErrorPath</key><string>$ROOT/state/$3.err</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)/$1" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$H/Library/LaunchAgents/$1.plist"
}
mkplist com.novawall.local  "exec $PY $ROOT/server.py" server
mkplist com.novawall.share  "NOVA_WALL_PORT=8791 NOVA_WALL_TOKEN=\$(cat $ROOT/state/mobile_token.txt) exec $PY $ROOT/server.py" server_share
sleep 3

# 5) lien de partage (tunnel si cloudflared, sinon WiFi local)
LAN="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo localhost)"
SHARE="http://$LAN:8791/?k=$TOKEN"
if command -v cloudflared >/dev/null; then
  pkill -f "cloudflared --config /dev/null tunnel --url http://127.0.0.1:8791" 2>/dev/null || true
  nohup cloudflared --config /dev/null tunnel --url http://127.0.0.1:8791 --no-autoupdate > "$ROOT/state/tunnel.log" 2>&1 &
  for i in $(seq 1 25); do U=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" "$ROOT/state/tunnel.log" | head -1); [ -n "$U" ] && break; sleep 1; done
  [ -n "$U" ] && SHARE="$U/?k=$TOKEN"
fi
echo "$SHARE" > "$ROOT/state/mobile_link.txt"

echo
echo "═══════════════════════════════════════════════════════"
echo "✅ NOVA WALL installé !"
echo "   🖥️  Sur CE Mac        : http://127.0.0.1:8790"
echo "   🔑 CODE DE CONNEXION  : $TOKEN"
echo "   📤 LIEN DE PARTAGE    : $SHARE"
echo "   (envoie ce lien à la personne qui doit voir/piloter ton mur — ex. David)"
echo "═══════════════════════════════════════════════════════"
open -g "http://127.0.0.1:8790" 2>/dev/null || true
