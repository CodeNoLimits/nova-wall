#!/usr/bin/env python3
"""
NOVA WALL ↔ TELEGRAM — pont natif (édition PROD-aware).
Greffe pour ~/etz-chaim/watcher/nova_terminal.py : préfixe `wall ...` → pilotage du mur depuis le téléphone.
Zéro dépendance (stdlib), zéro écriture dans les dossiers V1/Grok.

Nouveau (2026-07-20) — pourquoi ce fichier existe :
  L'ancien pont (~/nova-wall-v2/telegram_bridge.py) ciblait EN DUR le LAB (:8890).
  Or le téléphone de David affiche la PROD (:8790 / wall.dreamnovamcp.com).
  → `wall list` montrait 1 terminal au lieu de 24, et `wall to <id>` répondait
    « session introuvable » pour tous les terminaux réellement visibles à l'écran.
  Ici : DÉCOUVERTE AUTOMATIQUE du mur (celui qui a le plus de terminaux gérés = le vrai
  centre de commande, PROD prioritaire à égalité) + toutes les URL signées par le token
  du mur choisi (sinon 401 dès que David active le token pour le tunnel).

Commandes (toutes en langage court) :
  wall                      → état du mur (live/total/gérés + top sessions)
  wall where                → diagnostic : à QUEL mur je parle (port, gérés, token on/off)
  wall shot                 → capture PNG du mur (envoyée sur Telegram)
  wall shot <clé>           → capture d'un onglet Chrome (grok/gemini/notebooklm/claude/gmail)
  wall list                 → liste des terminaux gérés
  wall new <mode> [nom]     → crée un terminal (opus|sonnet|fable|opus-dngrok|grok|grok-dngrok)
  wall to <id> <message>    → écrit dans un terminal géré
  wall read <id>            → dernières lignes d'un terminal
  wall sub <id> <kind>      → sous-session (feature|troubleshoot|verify)
  wall link <a> <b> [type]  → liaison (inject|bridge|learn) + exécution
  wall kill <id>            → ferme un terminal géré
  wall link-url             → renvoie le lien web du mur
"""
import os, json, subprocess, time, urllib.request, urllib.parse

HOME = os.path.expanduser("~")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # …/nova-wall

# (api, racine du dossier — pour lire LE bon token, chaque mur a le sien)
CANDIDATES = [
    ("http://127.0.0.1:8790", os.path.join(HOME, "nova-wall")),      # PROD = ce que le téléphone voit
    ("http://127.0.0.1:8890", os.path.join(HOME, "nova-wall-v2")),   # LAB V2
]
if os.environ.get("NOVA_WALL_API"):                                  # override explicite = prioritaire
    CANDIDATES.insert(0, (os.environ["NOVA_WALL_API"].rstrip("/"), ROOT))

PUB_BY_ROOT = {
    os.path.join(HOME, "nova-wall"):    "https://wall.dreamnovamcp.com",
    os.path.join(HOME, "nova-wall-v2"): "https://wall-v2.dreamnovamcp.com",
}

_CACHE = {"api": None, "root": None, "ts": 0.0, "managed": 0}
_TTL   = 45.0


# ---------------------------------------------------------------- découverte
def _token_of(root):
    for name in ("mobile_token.txt", "token.txt", "token"):
        try:
            t = open(os.path.join(root, "state", name)).read().strip()
            if t:
                return t
        except Exception:
            pass
    return ""


def _probe(api, root, timeout=2.5):
    """Retourne le nb de terminaux gérés, ou -1 si le mur ne répond pas."""
    url = api + "/api/sessions"
    tok = _token_of(root)
    if tok:
        url += "?k=" + urllib.parse.quote(tok)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            d = json.loads(r.read())
        return len([s for s in d.get("sessions", []) if s.get("kind") == "managed"])
    except Exception:
        return -1


def _pick(force=False):
    """Choisit le mur VIVANT qui porte le plus de terminaux gérés (PROD gagne à égalité)."""
    now = time.time()
    if not force and _CACHE["api"] and (now - _CACHE["ts"]) < _TTL:
        return _CACHE["api"], _CACHE["root"]
    best = None
    for api, root in CANDIDATES:
        n = _probe(api, root)
        if n < 0:
            continue
        if best is None or n > best[2]:          # > strict ⇒ le 1er (PROD) garde l'égalité
            best = (api, root, n)
    if best is None:
        best = (CANDIDATES[0][0], CANDIDATES[0][1], 0)   # injoignable : on garde PROD pour le message d'erreur
    _CACHE.update(api=best[0], root=best[1], ts=now, managed=best[2])
    return best[0], best[1]


def API():  return _pick()[0]
def _tok(): return _token_of(_pick()[1])


def _u(path):
    """URL absolue signée par le token du mur choisi (sinon 401 dès que le token est actif)."""
    api = API()
    tok = _tok()
    if not tok:
        return api + path
    return api + path + ("&" if "?" in path else "?") + "k=" + urllib.parse.quote(tok)


def _get(path, raw=False, timeout=20):
    try:
        with urllib.request.urlopen(_u(path), timeout=timeout) as r:
            return r.read() if raw else json.loads(r.read())
    except Exception as e:
        return None if raw else {"error": str(e)[:90]}


def _post(path, data, timeout=25):
    try:
        req = urllib.request.Request(_u(path), data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)[:90]}


def _match(frag):
    """Retrouve une session par fragment d'id ou de titre (tolérant, mobile-friendly)."""
    d = _get("/api/sessions")
    if not d or "sessions" not in d: return None
    f = (frag or "").lower()
    for s in d["sessions"]:                                     # priorité aux gérés
        if s["kind"] == "managed" and (f in s["id"].lower() or f in s["title"].lower()): return s
    for s in d["sessions"]:
        if f in s["id"].lower() or f in s["title"].lower(): return s
    return None


def shot_wall(out="/tmp/nova_wall_shot.png"):
    """Capture du mur via Chrome headless (pas de Playwright : plus léger, jamais de fenêtre)."""
    for chrome in ("/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
                   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if os.path.exists(chrome):
            try:
                subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                                f"--screenshot={out}", "--window-size=1400,1800",
                                "--virtual-time-budget=6000", _u("/")],   # ← token inclus
                               capture_output=True, timeout=70)
                if os.path.exists(out) and os.path.getsize(out) > 8000: return out
            except Exception: pass
    return None


def handle(text):
    """Retourne (reponse_texte, chemin_fichier_ou_None). None,None si ce n'est pas une commande wall."""
    t = (text or "").strip()
    if not t.lower().startswith("wall"): return None, None
    a = t[4:].strip()
    low = a.lower()

    if low in ("where", "ou", "où", "quel mur", "diag"):
        api, root = _pick(force=True)
        return (f"🛰️ Mur ciblé : `{api}`\n"
                f"📁 {root}\n"
                f"🖥️ {_CACHE['managed']} terminaux gérés · token {'ON' if _tok() else 'off'}\n"
                f"🌐 {PUB_BY_ROOT.get(root, '(pas de domaine public connu)')}"), None

    if not a or low in ("status", "état", "etat"):
        d = _get("/api/sessions")
        if not d or "sessions" not in d: return f"🛰️ mur injoignable ({d})", None
        ss = d["sessions"]; live = [s for s in ss if s["live"]]; mgd = [s for s in ss if s["kind"] == "managed"]
        out = [f"🛰️ *NOVA WALL* — {len(live)} live · {len(ss)} sessions · {len(mgd)} gérés", ""]
        for s in mgd[:6]:
            out.append(f"🖥️ `{s['id']}` — {s['title']} ({s['model']})")
        for s in [x for x in live if x["kind"] == "external"][:6]:
            out.append(f"🎥 `{s['id']}` — {s['title']}" + (f" ▸ {s['task']}" if s.get("task") else ""))
        out.append("\n_wall shot · wall to <id> <msg> · wall new opus · wall where · wall link-url_")
        return "\n".join(out), None

    if low == "link-url":
        _, root = _pick()
        return f"📱 {PUB_BY_ROOT.get(root, API())}/?k={_tok()}", None

    if low == "list":
        d = _get("/api/sessions")
        mgd = [s for s in d.get("sessions", []) if s["kind"] == "managed"]
        if not mgd: return "aucun terminal géré — `wall new opus <nom>`", None
        return "\n".join(f"🖥️ `{s['id']}` — {s['title']} ({s['model']}) {'●' if s['live'] else '○'}" for s in mgd), None

    if low.startswith("shot"):
        arg = a[4:].strip()
        if arg:
            img = _get("/api/browser/shot?t=" + urllib.parse.quote(arg) + "&q=55&s=0.6", raw=True, timeout=30)
            if img and len(img) > 5000:
                p = "/tmp/nova_tab_shot.jpg"; open(p, "wb").write(img)
                return f"🌐 {arg}", p
            return f"onglet « {arg} » introuvable (essaie: grok, gemini, notebooklm, claude, gmail)", None
        p = shot_wall()
        return ("🛰️ le mur", p) if p else ("capture impossible", None)

    if low.startswith("new"):
        parts = a.split()
        mode = parts[1] if len(parts) > 1 else "opus"
        name = parts[2] if len(parts) > 2 else f"tg{os.getpid() % 1000}"
        r = _post("/api/spawn", {"name": name, "mode": mode, "cwd": None})
        return (f"✅ terminal `{r.get('tmux')}` lancé ({mode})" if r.get("ok") else f"❌ {r}"), None

    if low.startswith("to "):
        rest = a[3:].strip(); parts = rest.split(None, 1)
        if len(parts) < 2: return "usage: wall to <id> <message>", None
        s = _match(parts[0])
        if not s: return f"session « {parts[0]} » introuvable", None
        if s["kind"] != "managed": return f"« {s['title']} » est une caméra (lecture seule). `wall new opus` pour un terminal pilotable.", None
        r = _post("/api/inject", {"target": s["id"], "text": parts[1]})
        return (f"✅ envoyé à {s['title']}" if r.get("ok") else f"❌ {r.get('reason', r)}"), None

    if low.startswith("read"):
        frag = a[4:].strip()
        s = _match(frag)
        if not s: return f"session « {frag} » introuvable", None
        d = _get("/api/tile?id=" + urllib.parse.quote(s["id"]))
        if d.get("capture"):
            import re as _re
            txt = _re.sub(r"\x1b\[[0-9;]*m", "", d["capture"])
            lines = [l for l in txt.splitlines() if l.strip()][-14:]
            return f"🖥️ *{s['title']}*\n```\n" + "\n".join(lines)[-1400:] + "\n```", None
        rows = d.get("tail", [])[-6:]
        return f"🎥 *{s['title']}*\n" + "\n".join(f"_{r['role']}_ {r['text'][:180]}" for r in rows), None

    if low.startswith("sub"):
        parts = a.split()
        if len(parts) < 2: return "usage: wall sub <id> [feature|troubleshoot|verify]", None
        s = _match(parts[1])
        kind = parts[2] if len(parts) > 2 else "feature"
        if not s: return "session introuvable", None
        r = _post("/api/subsession", {"parent": s["id"], "kind": kind})
        return (f"✅ sous-session {kind} `{r.get('tmux')}` sur {s['title']}" if r.get("ok") else f"❌ {r}"), None

    if low.startswith("link"):
        parts = a.split()
        if len(parts) < 3: return "usage: wall link <a> <b> [inject|bridge|learn]", None
        A, B = _match(parts[1]), _match(parts[2])
        typ = parts[3] if len(parts) > 3 else "inject"
        if not A or not B: return "session(s) introuvable(s)", None
        _post("/api/link", {"from": A["id"], "to": B["id"], "type": typ})
        r = _post("/api/link/run", {"from": A["id"], "to": B["id"], "type": typ})
        return (f"🔗 {typ} : {A['title']} → {B['title']} " + ("✅ exécuté" if r.get("managed") else "⚠️ cible non gérée (écrit en fichier)")), None

    if low.startswith("kill"):
        s = _match(a[4:].strip())
        if not s: return "session introuvable", None
        r = _post("/api/kill", {"target": s["id"]})
        return (f"🗑️ {s['title']} fermé" if r.get("ok") else f"❌ {r.get('reason', r)}"), None

    return ("Commandes : `wall` · `wall where` · `wall shot [onglet]` · `wall list` · `wall new <mode> [nom]` · "
            "`wall to <id> <msg>` · `wall read <id>` · `wall sub <id> <kind>` · `wall link <a> <b> [type]` · "
            "`wall kill <id>` · `wall link-url`"), None


if __name__ == "__main__":
    import sys
    txt, f = handle(" ".join(sys.argv[1:]) or "wall")
    print(txt or "(pas une commande wall)")
    if f: print("FILE:", f)
