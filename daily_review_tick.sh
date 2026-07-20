#!/bin/bash
# NOVA WALL — collecte de fin de journée (déterministe). Le gros fichier = DAILY_REVIEW_<date>.md
D=$(date +%Y-%m-%d); OUT="$HOME/fable5/DAILY_REVIEW_$D.md"
[ -s "$OUT" ] && exit 0   # déjà écrit aujourd'hui (ex. à la main) → ne pas écraser
{
echo "# 📋 REVUE AUTO — $D"
echo "## Handovers"; echo "- jour: $(find $HOME/fable5 -name '*.md' -mtime -1 | wc -l | tr -d ' ') · semaine: $(find $HOME/fable5 -name 'HANDOVER*' -mtime -7 | wc -l | tr -d ' ') · mois: $(find $HOME/fable5 -name 'HANDOVER*' -mtime -30 | wc -l | tr -d ' ')"
echo "- du jour:"; find $HOME/fable5 -name '*.md' -mtime -1 -exec basename {} \; | sed 's/^/  - /' | head -30
echo "## Clients / WhatsApp"; echo '```'; curl -s -m5 http://127.0.0.1:3010/status; echo; echo '```'
echo "- carto WA: $(stat -f '%Sm' $HOME/infrastructure/communications/_WA_CARTOGRAPHY.md 2>/dev/null)"
echo "## Moniteurs prospection"; launchctl list 2>/dev/null | grep -iE "upwork|prospect|inbox|autopost" | awk '{print "- "$3" exit="$2}'
echo "## Sessions NOVA WALL"; curl -s -m8 "http://127.0.0.1:8790/api/sessions" | /opt/homebrew/bin/python3 -c "import sys,json;d=json.load(sys.stdin);from collections import Counter;print('- total:',len(d['sessions']),'· cats:',dict(Counter(s.get('cat','?') for s in d['sessions'])))" 2>/dev/null
echo "## Plan consolidation (dormantes à blocages)"; curl -s -m8 http://127.0.0.1:8790/api/consolidate/plan | /opt/homebrew/bin/python3 -c "import sys,json;print('-',json.load(sys.stdin).get('totals',{}))" 2>/dev/null
} > "$OUT"
command -v dn-report >/dev/null && PATH="$HOME/etz-chaim/bin:$PATH" dn-report -s "📋 Revue quotidienne $D" --file "$OUT" "Revue auto de fin de journee (handovers, clients/Baileys, prospection, sessions)." >/dev/null 2>&1
