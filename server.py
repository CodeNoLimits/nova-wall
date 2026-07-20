#!/usr/bin/env python3
"""
NOVA WALL — Command Center for live Claude/Grok sessions.
Mur de vidéosurveillance : chaque case = une "caméra" sur un terminal.
- Caméra lecture-seule : TOUTES les sessions vivantes (synergy.json + tail du .jsonl).
- Caméra live + injection/bridge/fusion/loop/modèle : sessions gérées par NOVA WALL en tmux.
Stdlib only. Anti-vol-de-focus (tmux send-keys = tape DANS le pty, jamais au niveau OS).
"""
import os, re, json, time, glob, subprocess, threading, urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
# launchd donne un PATH minimal → tmux (homebrew) et dn-grok deviendraient introuvables
os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "/usr/bin:/bin")
from urllib.parse import urlparse, parse_qs

HOME     = os.path.expanduser("~")
ROOT     = os.path.join(HOME, "nova-wall")
WEB      = os.path.join(ROOT, "web")
STATE    = os.path.join(ROOT, "state")
SYNERGY  = os.path.join(HOME, "omniscient", "synergy.json")
PROJECTS = os.path.join(HOME, ".claude", "projects")
GROK_BIN = os.path.join(HOME, ".grok", "bin", "grok")
PORT     = int(os.environ.get("NOVA_WALL_PORT", "8790"))
TOKEN    = os.environ.get("NOVA_WALL_TOKEN", "")   # si défini => l'API exige ?k=<token> (pour le tunnel mobile)
LIVE_SEC = 15 * 60

os.makedirs(STATE, exist_ok=True)
MANAGED_F = os.path.join(STATE, "managed.json")
LINKS_F   = os.path.join(STATE, "links.json")

_CL = ["claude", "--dangerously-skip-permissions"]   # managed = skip-permissions (comme l'alias de David)
MODES = {
    "opus":         {"label": "Opus 4.8",       "bin": _CL,                                  "env": {}},
    "sonnet":       {"label": "Sonnet 5",       "bin": _CL + ["--model", "claude-sonnet-5"], "env": {}},
    "fable":        {"label": "Fable 5",        "bin": _CL + ["--model", "claude-fable-5"],  "env": {}},
    "opus-dngrok":  {"label": "Opus + dnGrok",  "bin": _CL,                                  "env": {"NOVA_COPILOT": "dngrok"}},
    "fable-dngrok": {"label": "Fable + dnGrok", "bin": _CL + ["--model", "claude-fable-5"],   "env": {"NOVA_COPILOT": "dngrok"}},
    "grok":         {"label": "Grok 4.5",       "bin": [GROK_BIN],                           "env": {}},
    "grok-dngrok":  {"label": "Grok + dnGrok",  "bin": [GROK_BIN],                           "env": {"NOVA_COPILOT": "dngrok"}},
}

_cache = {"t": 0, "data": None}
_lock  = threading.Lock()
_FS_ROOTS = [os.path.realpath(HOME), "/tmp", "/private/tmp"]
def _fs_ok(rp):
    return any(rp == r or rp.startswith(r + "/") for r in _FS_ROOTS)
LOOPS  = {}   # target -> {"stop": Event, "text": str, "interval": int, "count": int, "thread": Thread}

# ------- helpers --------------------------------------------------------------
def jload(path, default):
    try:
        with open(path) as f: return json.load(f)
    except Exception: return default

def jsave(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f: json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

def tail_bytes(path, n=65536):
    try:
        sz = os.path.getsize(path)
        with open(path, "rb") as f:
            if sz > n: f.seek(sz - n)
            return f.read().decode("utf-8", "replace")
    except Exception:
        return ""

_MODEL_RE = re.compile(r'"model"\s*:\s*"([^"]+)"')
_TS_RE    = re.compile(r'"timestamp"\s*:\s*"([^"]+)"')

def live_meta(jsonl):
    t = tail_bytes(jsonl, 65536)
    models = _MODEL_RE.findall(t); ts = _TS_RE.findall(t)
    model = models[-1] if models else None
    last_ts = ts[-1] if ts else None
    age_s = None
    if last_ts:
        try:
            import datetime
            dt = datetime.datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            age_s = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds()
        except Exception: pass
    if age_s is None:
        try: age_s = time.time() - os.path.getmtime(jsonl)
        except Exception: age_s = 9e9
    return {"model": model, "age_s": age_s}

def pretty_model(m):
    if not m: return "?"
    m = m.lower()
    for k, v in (("opus","Opus"),("sonnet","Sonnet"),("fable","Fable"),("haiku","Haiku"),("grok","Grok"),("glm","GLM")):
        if k in m: return v
    return m.split("-")[0][:8]

_TITLE_STRIP = re.compile(r'^\s*=+\s*QUESTION\s*=+\s*', re.I)
def make_title(goal, clients, project):
    """Un titre humain court et clair, dérivé du but."""
    g = (goal or "").strip()
    g = _TITLE_STRIP.sub("", g)
    g = re.sub(r'https?://\S+', '', g)
    g = re.sub(r'\s+', ' ', g).strip(" :—-.")
    for sep in (". ", " : ", " — ", " - ", ", ", " (", "?", "!"):
        i = g.find(sep)
        if 8 <= i <= 60:
            g = g[:i]; break
    g = g[:58].strip()
    if len(g) < 4:
        g = (clients[0] if clients else project) or "session"
    return g[0].upper() + g[1:] if g else "session"

def sh(cmd, timeout=10):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        class R: returncode = 1; stdout = ""; stderr = str(e)
        return R()

def tmux_ls():
    r = sh(["tmux", "ls", "-F", "#{session_name}"])
    return [l.strip() for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []

def tmux_capture(target, lines=44, ansi=False):
    cmd = ["tmux", "capture-pane", "-t", target, "-p", "-S", f"-{lines}"]
    if ansi: cmd.append("-e")   # -e = garde les séquences d'échappement (couleurs) => terminal fidèle
    r = sh(cmd)
    return r.stdout if r.returncode == 0 else ""

def tmux_send(target, text):
    a = sh(["tmux", "send-keys", "-t", target, "-l", text])
    b = sh(["tmux", "send-keys", "-t", target, "Enter"])
    return a.returncode == 0 and b.returncode == 0

def _accept_first_run(tname):
    # auto-accepte les prompts de 1er lancement (thème, "allow external imports") : « 1 » PUIS Entrée
    for _ in range(14):
        time.sleep(2)
        if tname not in tmux_ls(): return
        scr = tmux_capture(tname, 30); low = scr.lower()
        if ("❯ 1." in scr or "yes, allow" in low or "enter to confirm" in low
                or ("external" in low and "import" in low) or "text style" in low):
            sh(["tmux", "send-keys", "-t", tname, "1"]); time.sleep(0.3)
            sh(["tmux", "send-keys", "-t", tname, "Enter"]); time.sleep(1.2)

def tmux_spawn(name, mode, cwd, initial=None):
    spec = MODES.get(mode, MODES["opus"])
    tname = f"nova-{name}"
    if tname in tmux_ls(): return tname, "exists"
    envs = " ".join(f'{k}={v}' for k, v in spec["env"].items())
    binpart = " ".join(spec["bin"])
    if initial and not mode.startswith("grok"):
        binpart += " '" + initial.replace("'", "'\\''") + "'"   # prompt initial de la sous-session
    inner = f'cd {json.dumps(cwd)} 2>/dev/null; clear; {envs} exec {binpart}'
    r = sh(["tmux", "new-session", "-d", "-s", tname, "-x", "220", "-y", "50",
            os.environ.get("SHELL", "/bin/zsh"), "-lc", inner])
    if r.returncode != 0: return None, r.stderr.strip() or "spawn failed"
    m = jload(MANAGED_F, {}); m[tname] = {"name": name, "mode": mode, "cwd": cwd, "created": time.time()}
    jsave(MANAGED_F, m)
    threading.Thread(target=_accept_first_run, args=(tname,), daemon=True).start()
    return tname, "spawned"

def tmux_setmode(target, mode):
    """Vrai changement de modèle : relance le terminal géré dans le nouveau mode (même dossier)."""
    m = jload(MANAGED_F, {})
    info = m.get(target)
    if not info: return None, "pas un terminal géré"
    name, cwd = info.get("name"), info.get("cwd", HOME)
    loop_stop(target)
    sh(["tmux", "kill-session", "-t", target]); m.pop(target, None); jsave(MANAGED_F, m)
    return tmux_spawn(name, mode, cwd)

# ------- loops ----------------------------------------------------------------
def loop_stop(target):
    lp = LOOPS.pop(target, None)
    if lp: lp["stop"].set()

def loop_start(target, text, interval):
    loop_stop(target)
    interval = max(20, int(interval or 60))
    stop = threading.Event()
    def run():
        while not stop.is_set():
            if target not in tmux_ls(): break
            tmux_send(target, text)
            LOOPS.get(target, {}).__setitem__("count", LOOPS.get(target, {}).get("count", 0) + 1) if target in LOOPS else None
            for _ in range(interval * 2):
                if stop.is_set(): break
                time.sleep(0.5)
    t = threading.Thread(target=run, daemon=True)
    LOOPS[target] = {"stop": stop, "text": text, "interval": interval, "count": 0, "thread": t}
    t.start()
    return True

# ------- sous-sessions assignées + dossiers bridge ---------------------------
BRIDGES = os.path.join(ROOT, "bridges")

def _external_logs(sid, n=25):
    files = glob.glob(os.path.join(PROJECTS, "**", f"{sid}*.jsonl"), recursive=True)
    if not files: return ""
    t = tail_bytes(files[0], 160000); rows = []
    for line in t.splitlines()[-60:]:
        try: o = json.loads(line)
        except Exception: continue
        m = o.get("message", {}); role = m.get("role") if isinstance(m, dict) else None
        c = m.get("content") if isinstance(m, dict) else None; txt = ""
        if isinstance(c, str): txt = c
        elif isinstance(c, list):
            for blk in c:
                if isinstance(blk, dict) and blk.get("type") == "text": txt += blk.get("text", "")
        txt = txt.strip().replace("\n", " ")
        if txt and role: rows.append(f"{role}: {txt[:300]}")
    return "\n".join(rows[-n:])

def parent_context(sid):
    for s in build_sessions():
        if s["id"] == sid:
            logs = tmux_capture(s["tmux"], 140) if s.get("tmux") else _external_logs(sid)
            return {"id": sid, "title": s.get("title", sid), "cwd": s.get("cwd") or HOME,
                    "goal": s.get("goal", ""), "wins": s.get("wins", []), "blockers": s.get("blockers", []),
                    "model": s.get("model", ""), "is_grok": "grok" in (str(s.get("model",""))+str(s.get("mode",""))).lower(),
                    "logs": logs, "managed": bool(s.get("tmux"))}
    return None

def make_bridge(ctx):
    d = os.path.join(BRIDGES, ctx["id"]); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "CONTEXT.md"), "w") as f:
        f.write(f"# CONTEXTE — {ctx['title']} ({ctx['id']})\n\n- Dossier : {ctx['cwd']}\n- Modèle : {ctx['model']}\n\n")
        f.write(f"## But\n{ctx['goal']}\n\n")
        if ctx["wins"]: f.write("## ✅ Réussites\n" + "\n".join(f"- {w}" for w in ctx["wins"]) + "\n\n")
        if ctx["blockers"]: f.write("## ⚠️ Difficultés\n" + "\n".join(f"- {b}" for b in ctx["blockers"]) + "\n\n")
        f.write(f"## Logs récents\n```\n{ctx['logs'][-4000:]}\n```\n")
    for fn in ("INBOX.md", "OUTBOX.md"):
        p = os.path.join(d, fn)
        if not os.path.exists(p): open(p, "w").write(f"# {fn[:-3]} — pont {ctx['id']}\n")
    return d

_SUB = {"troubleshoot": ("trbl", "opus-dngrok", "🔴 TROUBLESHOOT"),
        "feature":      ("feat", "opus-dngrok", "🟢 AJOUT FEATURE"),
        "verify":       ("vrfy", "fable",       "🟡 VÉRIF FABLE 5")}

def make_subsession(parent, kind):
    ctx = parent_context(parent)
    if not ctx: return {"ok": False, "reason": "session introuvable"}
    tag, mode, label = _SUB.get(kind, _SUB["feature"])
    if ctx["is_grok"] and kind != "verify": mode = "opus-dngrok"   # aide un Grok via dn-claude
    bridge = make_bridge(ctx)
    prompts = {
      "troubleshoot": f"Tu es une SOUS-SESSION de troubleshoot assignée à « {ctx['title']} » (projet {ctx['cwd']}). "
        f"Lis {bridge}/CONTEXT.md (but, réussites, difficultés, logs). Diagnostique la difficulté, applique un fix concret et prouve-le. "
        f"Écris tes trouvailles dans {bridge}/OUTBOX.md. Rien de sacré (Breslev/Saba/hébreu), aucun envoi client.",
      "feature": f"Tu es une SOUS-SESSION assignée à « {ctx['title']} » (projet {ctx['cwd']}) pour AJOUTER une fonctionnalité utile. "
        f"Lis {bridge}/CONTEXT.md. Propose 1 amélioration à forte valeur et implémente-la proprement (preuve). "
        f"Écris ce que tu as fait dans {bridge}/OUTBOX.md. Rien de sacré, aucun envoi client.",
      "verify": f"Tu es un agent FABLE 5 de VÉRIFICATION assigné à « {ctx['title']} » (projet {ctx['cwd']}). "
        f"Lis {bridge}/CONTEXT.md. Vérifie ce qui est RÉELLEMENT fait (preuve chiffrée), puis identifie ce qu'on peut AJOUTER "
        f"ou injecter directement dans le contexte pour l'améliorer. Écris tes propositions dans {bridge}/OUTBOX.md. Honnêteté totale, rien de sacré."}
    with open(os.path.join(bridge, "PROMPT.md"), "w") as f:
        f.write(f"# ASSIGNATION {label}\n\n{prompts[kind]}\n")
    name = f"{tag}-{parent.replace('nova-','')[:8]}"
    tname, status = tmux_spawn(name, mode, ctx["cwd"], initial=f"Lis et exécute maintenant le fichier {bridge}/PROMPT.md")
    _cache["t"] = 0
    return {"ok": tname is not None, "tmux": tname, "bridge": bridge, "kind": kind, "mode": mode, "status": status}

# ------- titres générés (dn-grok 0$, batch, cache) ----------------------------
TITLES_F = os.path.join(STATE, "titles.json")
DN_GROK  = os.path.join(HOME, "etz-chaim", "bin", "dn-grok")

def _title_worker():
    time.sleep(8)
    while True:
        try:
            titles = jload(TITLES_F, {})
            now = time.time()
            todo = []
            for s in build_sessions():
                if s["kind"] != "external" or not s["live"]: continue
                tt = titles.get(s["id"], {})
                if now - tt.get("ts", 0) < 1800: continue          # frais 30 min
                tail = ""
                try:
                    files = glob.glob(os.path.join(PROJECTS, "**", f"{s['id']}*.jsonl"), recursive=True)
                    if files:
                        t = tail_bytes(files[0], 30000)
                        for line in reversed(t.splitlines()):
                            try:
                                o = json.loads(line); m = o.get("message", {})
                                if isinstance(m, dict) and m.get("role") == "assistant":
                                    c = m.get("content")
                                    if isinstance(c, list):
                                        tx = " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
                                        if tx.strip(): tail = tx.strip()[:250]; break
                            except Exception: continue
                except Exception: pass
                todo.append({"id": s["id"], "goal": (s["goal"] or "")[:250], "now": tail})
            if todo:
                todo = todo[:20]
                prompt = ("Voici des sessions de travail IA. Pour CHACUNE donne un titre CLAIR (3-6 mots, français, "
                          "qui définit exactement la session) et la tâche EN COURS (4-8 mots, déduite du dernier message). "
                          "Réponds UNIQUEMENT en JSON strict: {\"<id>\": {\"t\": \"titre\", \"k\": \"tâche en cours\"}}\n\n"
                          + json.dumps(todo, ensure_ascii=False))
                r = sh([DN_GROK, prompt], timeout=150)
                m = re.search(r"\{.*\}", r.stdout, re.S)
                if m:
                    try:
                        gen = json.loads(m.group(0))
                        for sid, v in gen.items():
                            if isinstance(v, dict) and v.get("t"):
                                titles[sid] = {"t": str(v.get("t"))[:60], "k": str(v.get("k", ""))[:70], "ts": now}
                        jsave(TITLES_F, titles); _cache["t"] = 0
                    except Exception: pass
        except Exception: pass
        time.sleep(360)

threading.Thread(target=_title_worker, daemon=True).start()

# ------- sessions view --------------------------------------------------------
def build_sessions():
    with _lock:
        if _cache["data"] and time.time() - _cache["t"] < 2:
            return _cache["data"]
    syn = jload(SYNERGY, {"sessions": []})
    managed = jload(MANAGED_F, {})
    gen_titles = jload(TITLES_F, {})
    live_tmux = set(tmux_ls())
    out = []
    for s in syn.get("sessions", []):
        jsonl = s.get("file", "")
        meta = live_meta(jsonl) if jsonl else {"model": None, "age_s": 9e9}
        age = meta["age_s"] if meta["age_s"] is not None else s.get("age_min", 9e9) * 60
        proj = os.path.basename(s.get("cwd", "").rstrip("/")) or "~"
        sid = s.get("session", "")[:8]
        gt = gen_titles.get(sid, {})
        out.append({
            "id": sid, "kind": "external",
            "cwd": s.get("cwd", ""), "project": proj,
            "title": gt.get("t") or make_title(s.get("goal"), s.get("clients", []), proj),
            "task": gt.get("k", ""),
            "branch": s.get("branch", ""), "goal": (s.get("goal") or "").strip()[:260],
            "wins": s.get("wins", [])[:3], "blockers": s.get("blockers", [])[:3],
            "clients": s.get("clients", []), "urls": s.get("urls", [])[:3],
            "n_msgs": s.get("n_msgs", 0), "model": pretty_model(meta["model"]),
            "age_s": round(age), "live": age < LIVE_SEC, "tmux": None, "loop": False,
        })
    for tname, info in managed.items():
        alive = tname in live_tmux
        cap = tmux_capture(tname, 44, ansi=True) if alive else ""
        mode = info.get("mode", "opus")
        out.append({
            "id": tname, "kind": "managed", "cwd": info.get("cwd", ""),
            "project": os.path.basename(info.get("cwd", "").rstrip("/")) or "~",
            "title": info.get("name", tname.replace("nova-", "")),
            "branch": "", "goal": f'terminal géré · {MODES.get(mode, {}).get("label", "?")}',
            "wins": [], "blockers": [], "clients": [], "urls": [], "n_msgs": 0,
            "model": MODES.get(mode, {}).get("label", "?"), "mode": mode,
            "age_s": 0 if alive else 9e9, "live": alive, "tmux": tname,
            "capture": cap[-6000:], "dead": not alive,
            "loop": tname in LOOPS, "loop_info": ({"text": LOOPS[tname]["text"][:60],
                    "interval": LOOPS[tname]["interval"], "count": LOOPS[tname]["count"]} if tname in LOOPS else None),
        })
    out.sort(key=lambda x: (not x["live"], x["age_s"]))
    with _lock:
        _cache["data"] = out; _cache["t"] = time.time()
    return out

# ------- HTTP -----------------------------------------------------------------
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _auth(self, u):
        if not TOKEN: return True
        return parse_qs(u.query).get("k", [""])[0] == TOKEN
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)): body = json.dumps(body, ensure_ascii=False)
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store"); self.end_headers()
        try: self.wfile.write(b)
        except Exception: pass
    def _body(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception: return {}

    def _proxyb(self, method, path, body=None):
        # proxy vers le helper navigateur (8792) => tuiles Chrome accessibles aussi via le tunnel mobile
        try:
            req = urllib.request.Request("http://127.0.0.1:8792" + path, data=body, method=method)
            if body: req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=15) as r:
                return self._send(200, r.read(), r.headers.get("Content-Type", "application/json"))
        except Exception as e:
            return self._send(502, {"error": "browser helper down", "detail": str(e)[:100]})

    def do_GET(self):
        u = urlparse(self.path); p = u.path
        if p in ("/", "/index.html"):
            try:
                with open(os.path.join(WEB, "index.html"), "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            except Exception as e:
                return self._send(500, f"index missing: {e}", "text/plain")
        if p.startswith("/api/") and not self._auth(u):
            return self._send(401, {"error": "token requis"})
        if p == "/api/sessions":
            return self._send(200, {"sessions": build_sessions(),
                                    "modes": {k: v["label"] for k, v in MODES.items()}, "ts": time.time()})
        if p == "/api/tile":
            sid = parse_qs(u.query).get("id", [""])[0]
            for s in build_sessions():
                if s["id"] == sid:
                    s = dict(s)
                    if s.get("tmux"): s["capture"] = tmux_capture(s["tmux"], 200, ansi=True)
                    else: s["tail"] = self._tail_summary(sid)
                    return self._send(200, s)
            return self._send(404, {"error": "not found"})
        if p == "/api/links":
            return self._send(200, jload(LINKS_F, {"edges": []}))
        if p == "/api/fs/list":
            path = parse_qs(u.query).get("path", [HOME])[0] or HOME
            rp = os.path.realpath(os.path.expanduser(path))
            if not _fs_ok(rp): return self._send(403, {"error": "hors zone autorisée"})
            if not os.path.isdir(rp): return self._send(404, {"error": "pas un dossier"})
            dirs, files = [], []
            try:
                for e in sorted(os.listdir(rp)):
                    if e.startswith(".") and e not in (".claude", ".grok"): continue
                    fp = os.path.join(rp, e)
                    try:
                        if os.path.isdir(fp): dirs.append(e)
                        else: files.append({"n": e, "s": os.path.getsize(fp)})
                    except Exception: pass
            except PermissionError:
                return self._send(403, {"error": "permission refusée"})
            return self._send(200, {"path": rp, "parent": os.path.dirname(rp) if rp != "/" else "/",
                                    "dirs": dirs[:400], "files": files[:400]})
        if p == "/api/fs/read":
            path = parse_qs(u.query).get("path", [""])[0]
            rp = os.path.realpath(os.path.expanduser(path))
            if not _fs_ok(rp): return self._send(403, {"error": "hors zone"})
            if not os.path.isfile(rp): return self._send(404, {"error": "introuvable"})
            sz = os.path.getsize(rp)
            if sz > 400_000: return self._send(200, {"path": rp, "big": True, "size": sz})
            raw = open(rp, "rb").read()
            try: return self._send(200, {"path": rp, "size": sz, "text": raw.decode("utf-8")})
            except Exception: return self._send(200, {"path": rp, "binary": True, "size": sz})
        if p == "/api/graph":
            ss = build_sessions()
            nodes = [{"id": s["id"], "title": s["title"], "live": s["live"], "kind": s["kind"],
                      "model": s["model"], "clients": s.get("clients", []), "project": s["project"]} for s in ss]
            edges, seen = [], set()
            def add(a, b, typ, label):
                k = (min(a, b), max(a, b), typ)
                if a != b and k not in seen: seen.add(k); edges.append({"a": a, "b": b, "type": typ, "label": label})
            by_client, by_cwd = {}, {}
            for s in ss:
                for c in s.get("clients", []): by_client.setdefault(c, []).append(s["id"])
                if s.get("cwd") and s["cwd"] != HOME: by_cwd.setdefault(s["cwd"], []).append(s["id"])
            for c, ids in by_client.items():
                for i in range(len(ids)):
                    for j in range(i + 1, len(ids)): add(ids[i], ids[j], "client", c)
            for d, ids in by_cwd.items():
                for i in range(len(ids)):
                    for j in range(i + 1, len(ids)): add(ids[i], ids[j], "folder", os.path.basename(d))
            for e in jload(LINKS_F, {"edges": []}).get("edges", []):
                add(e.get("from", ""), e.get("to", ""), e.get("type", "inject"), e.get("type", ""))
            ids = {n["id"] for n in nodes}
            edges = [e for e in edges if e["a"] in ids and e["b"] in ids]
            return self._send(200, {"nodes": nodes, "edges": edges})
        if p == "/api/browser/tabs":
            return self._proxyb("GET", "/tabs")
        if p == "/api/browser/shot":
            return self._proxyb("GET", "/shot?" + u.query)
        return self._send(404, {"error": "no route"})

    def _tail_summary(self, sid):
        files = glob.glob(os.path.join(PROJECTS, "**", f"{sid}*.jsonl"), recursive=True)
        if not files: return []
        t = tail_bytes(files[0], 140000); rows = []
        for line in t.splitlines()[-50:]:
            try: o = json.loads(line)
            except Exception: continue
            m = o.get("message", {}); role = m.get("role") if isinstance(m, dict) else None
            c = m.get("content") if isinstance(m, dict) else None; txt = ""
            if isinstance(c, str): txt = c
            elif isinstance(c, list):
                for blk in c:
                    if isinstance(blk, dict) and blk.get("type") == "text": txt += blk.get("text", "")
                    elif isinstance(blk, dict) and blk.get("type") == "tool_use": txt += f'[⚙ {blk.get("name","tool")}] '
            txt = txt.strip().replace("\n", " ")
            if txt and role: rows.append({"role": role, "text": txt[:260]})
        return rows[-10:]

    def do_POST(self):
        u = urlparse(self.path); p = u.path
        if not self._auth(u): return self._send(401, {"error": "token requis"})
        d = self._body()
        if p == "/api/spawn":
            name = re.sub(r"[^a-zA-Z0-9_-]", "", d.get("name", "") or f"t{int(time.time())%10000}")
            mode = d.get("mode", "opus"); cwd = d.get("cwd") or HOME
            if not os.path.isdir(cwd): cwd = HOME
            tname, status = tmux_spawn(name, mode, cwd); _cache["t"] = 0
            return self._send(200, {"ok": tname is not None, "tmux": tname, "status": status,
                                    "attach": f"tmux attach -t {tname}" if tname else None})
        if p == "/api/inject":
            target = d.get("target", ""); text = d.get("text", "")
            if target not in tmux_ls():
                return self._send(200, {"ok": False, "managed": False,
                    "reason": "Caméra en lecture seule (session externe, hors tmux). "
                              "Ouvre-la en terminal géré pour écrire dedans."})
            ok = tmux_send(target, text); _cache["t"] = 0
            return self._send(200, {"ok": ok, "managed": True})
        if p == "/api/setmode":
            target = d.get("target", ""); mode = d.get("mode", "opus")
            tname, status = tmux_setmode(target, mode); _cache["t"] = 0
            return self._send(200, {"ok": tname is not None, "tmux": tname, "status": status})
        if p == "/api/loop/start":
            target = d.get("target", ""); text = d.get("text", ""); interval = d.get("interval", 60)
            if target not in tmux_ls(): return self._send(200, {"ok": False, "reason": "cible non gérée"})
            loop_start(target, text, interval); _cache["t"] = 0
            return self._send(200, {"ok": True, "interval": max(20, int(interval))})
        if p == "/api/loop/stop":
            loop_stop(d.get("target", "")); _cache["t"] = 0
            return self._send(200, {"ok": True})
        if p == "/api/fs/write":
            rp = os.path.realpath(os.path.expanduser(d.get("path", "")))
            if not _fs_ok(rp): return self._send(403, {"error": "hors zone"})
            try:
                if os.path.exists(rp):  # backup 1 niveau avant écrasement
                    os.replace(rp, rp + ".bak-wall") if not os.path.exists(rp + ".bak-wall") else None
                with open(rp, "w") as f: f.write(d.get("content", ""))
                return self._send(200, {"ok": True, "size": os.path.getsize(rp)})
            except Exception as e:
                return self._send(200, {"ok": False, "reason": str(e)[:120]})
        if p == "/api/fs/send":
            rp = os.path.realpath(os.path.expanduser(d.get("path", "")))
            target = d.get("target", "")
            if not _fs_ok(rp): return self._send(403, {"error": "hors zone"})
            if target not in tmux_ls(): return self._send(200, {"ok": False, "reason": "terminal non géré"})
            msg = d.get("note") or f"Prends en compte ce fichier : {rp} — lis-le et intègre-le à ton travail en cours."
            return self._send(200, {"ok": tmux_send(target, msg), "path": rp})
        if p == "/api/subsession":
            return self._send(200, make_subsession(d.get("parent", ""), d.get("kind", "feature")))
        if p == "/api/bridge":
            ctx = parent_context(d.get("parent", ""))
            if not ctx: return self._send(200, {"ok": False, "reason": "introuvable"})
            return self._send(200, {"ok": True, "bridge": make_bridge(ctx)})
        if p == "/api/kill":
            target = d.get("target", "")
            if target.startswith("nova-"):
                loop_stop(target); sh(["tmux", "kill-session", "-t", target])
                m = jload(MANAGED_F, {}); m.pop(target, None); jsave(MANAGED_F, m); _cache["t"] = 0
                return self._send(200, {"ok": True})
            return self._send(200, {"ok": False, "reason": "refuse: pas un terminal géré"})
        if p == "/api/link":
            links = jload(LINKS_F, {"edges": []})
            edge = {"from": d.get("from"), "to": d.get("to"), "type": d.get("type", "inject"),
                    "id": f'e{int(time.time()*1000)%100000}'}
            links["edges"].append(edge); jsave(LINKS_F, links)
            return self._send(200, {"ok": True, "edge": edge})
        if p == "/api/unlink":
            links = jload(LINKS_F, {"edges": []})
            links["edges"] = [e for e in links["edges"] if e.get("id") != d.get("id")]
            jsave(LINKS_F, links); return self._send(200, {"ok": True})
        if p == "/api/link/run":
            return self._send(200, self._run_link(d))
        if p.startswith("/api/browser/"):
            return self._proxyb("POST", "/" + p.split("/api/browser/", 1)[1], json.dumps(d).encode())
        return self._send(404, {"error": "no route"})

    def _ctx_of(self, sid):
        for s in build_sessions():
            if s["id"] == sid:
                if s.get("tmux"):
                    return f"[NOVA WALL · contexte de {sid}]\n{tmux_capture(s['tmux'], 60)[-1500:]}"
                bits = [f'BUT: {s.get("goal","")}']
                if s.get("wins"): bits.append("VICTOIRES: " + " · ".join(s["wins"]))
                if s.get("blockers"): bits.append("BLOCAGES: " + " · ".join(s["blockers"]))
                if s.get("urls"): bits.append("URLS: " + " ".join(s["urls"]))
                if s.get("cwd"): bits.append("DOSSIER: " + s["cwd"])
                return f"[NOVA WALL · contexte de {sid}]\n" + "\n".join(bits)
        return f"[contexte {sid} introuvable]"

    def _run_link(self, d):
        typ = d.get("type", "inject"); a = d.get("from"); b = d.get("to")
        def deliver(src, dst):
            ctx = self._ctx_of(src)
            if dst in tmux_ls():
                msg = (f"Une autre session ({src}) partage son contexte via NOVA WALL. "
                       f"Prends-en connaissance et intègre ce qui est utile :\n\n{ctx}")
                return tmux_send(dst, msg)
            with open(os.path.join(STATE, f"inject_to_{dst}.md"), "w") as f: f.write(ctx)
            return False
        res = {}
        if typ == "inject": res["a_to_b"] = deliver(a, b)
        elif typ in ("bridge", "learn"):
            res["a_to_b"] = deliver(a, b); res["b_to_a"] = deliver(b, a)
        res["type"] = typ
        managed_ok = (b in tmux_ls()) or (typ != "inject" and a in tmux_ls())
        return {"ok": True, "result": res, "managed": managed_ok}

def main():
    os.chdir(ROOT)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"NOVA WALL → http://127.0.0.1:{PORT}  (token={'ON' if TOKEN else 'off'})")
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\nbye")

if __name__ == "__main__":
    main()
