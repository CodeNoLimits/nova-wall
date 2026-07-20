#!/usr/bin/env python3
"""
NOVA WALL — Command Center for live Claude/Grok sessions.
Un mur de vidéosurveillance : chaque case = une "caméra" sur un terminal.
- Caméra lecture-seule : TOUTES les sessions vivantes (via synergy.json + tail du .jsonl).
- Caméra live + injection/bridge/fusion : sessions gérées par NOVA WALL en tmux ("containers").
Stdlib only. Anti-vol-de-focus (jamais d'osascript/activate ; tmux send-keys = tape DANS le pty).
"""
import os, re, json, time, glob, html, subprocess, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HOME       = os.path.expanduser("~")
ROOT       = os.path.join(HOME, "nova-wall")
WEB        = os.path.join(ROOT, "web")
STATE      = os.path.join(ROOT, "state")
SYNERGY    = os.path.join(HOME, "omniscient", "synergy.json")
PROJECTS   = os.path.join(HOME, ".claude", "projects")
GROK_BIN   = os.path.join(HOME, ".grok", "bin", "grok")
PORT       = int(os.environ.get("NOVA_WALL_PORT", "8790"))
LIVE_SEC   = 15 * 60   # une session "vivante" si activité < 15 min

os.makedirs(STATE, exist_ok=True)
MANAGED_F  = os.path.join(STATE, "managed.json")
LINKS_F    = os.path.join(STATE, "links.json")

# ------- mode -> commande tmux ------------------------------------------------
MODES = {
    "opus":         {"label": "Opus 4.8",      "bin": ["claude"],                              "env": {}},
    "sonnet":       {"label": "Sonnet 5",      "bin": ["claude", "--model", "claude-sonnet-5"], "env": {}},
    "fable":        {"label": "Fable 5",       "bin": ["claude", "--model", "claude-fable-5"],  "env": {}},
    "opus-dngrok":  {"label": "Opus + dnGrok", "bin": ["claude"],                              "env": {"NOVA_COPILOT": "dngrok"}},
    "fable-dngrok": {"label": "Fable + dnGrok","bin": ["claude", "--model", "claude-fable-5"],  "env": {"NOVA_COPILOT": "dngrok"}},
    "grok":         {"label": "Grok 4.5",      "bin": [GROK_BIN],                              "env": {}},
    "grok-dngrok":  {"label": "Grok + dnGrok", "bin": [GROK_BIN],                              "env": {"NOVA_COPILOT": "dngrok"}},
}

_cache = {"t": 0, "data": None}
_lock = threading.Lock()

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
    """Dernier modèle + dernier timestamp d'un transcript (rapide, lit la queue)."""
    t = tail_bytes(jsonl, 65536)
    models = _MODEL_RE.findall(t)
    ts = _TS_RE.findall(t)
    model = models[-1] if models else None
    last_ts = ts[-1] if ts else None
    age_s = None
    if last_ts:
        try:
            import datetime
            dt = datetime.datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            age_s = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds()
        except Exception:
            pass
    # mtime fallback
    if age_s is None:
        try: age_s = time.time() - os.path.getmtime(jsonl)
        except Exception: age_s = 9e9
    return {"model": model, "age_s": age_s}

def pretty_model(m):
    if not m: return "?"
    m = m.lower()
    if "opus" in m: return "Opus"
    if "sonnet" in m: return "Sonnet"
    if "fable" in m: return "Fable"
    if "haiku" in m: return "Haiku"
    if "grok" in m: return "Grok"
    if "glm" in m: return "GLM"
    return m.split("-")[0][:8]

def sh(cmd, timeout=10):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        class R: returncode = 1; stdout = ""; stderr = str(e)
        return R()

def tmux_ls():
    r = sh(["tmux", "ls", "-F", "#{session_name}"])
    return [l.strip() for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []

def tmux_capture(target, lines=40):
    r = sh(["tmux", "capture-pane", "-t", target, "-p", "-S", f"-{lines}"])
    return r.stdout if r.returncode == 0 else ""

def tmux_send(target, text):
    # tape le texte PUIS Enter — dans le pty, jamais au niveau OS
    a = sh(["tmux", "send-keys", "-t", target, "-l", text])
    b = sh(["tmux", "send-keys", "-t", target, "Enter"])
    return a.returncode == 0 and b.returncode == 0

def tmux_spawn(name, mode, cwd):
    spec = MODES.get(mode, MODES["opus"])
    tname = f"nova-{name}"
    if tname in tmux_ls():
        return tname, "exists"
    envs = " ".join(f'{k}={v}' for k, v in spec["env"].items())
    binpart = " ".join(spec["bin"])
    inner = f'cd {json.dumps(cwd)} 2>/dev/null; clear; {envs} exec {binpart}'
    # login shell -> aliases/PATH de David chargés (claude = skip-permissions)
    r = sh(["tmux", "new-session", "-d", "-s", tname, "-x", "220", "-y", "50",
            os.environ.get("SHELL", "/bin/zsh"), "-lc", inner])
    if r.returncode != 0:
        return None, r.stderr.strip() or "spawn failed"
    m = jload(MANAGED_F, {})
    m[tname] = {"name": name, "mode": mode, "cwd": cwd, "created": time.time()}
    jsave(MANAGED_F, m)
    return tname, "spawned"

# ------- sessions view --------------------------------------------------------
def build_sessions():
    with _lock:
        if _cache["data"] and time.time() - _cache["t"] < 2:
            return _cache["data"]
    syn = jload(SYNERGY, {"sessions": []})
    managed = jload(MANAGED_F, {})
    live_tmux = set(tmux_ls())
    out = []
    seen_cwd_id = set()

    for s in syn.get("sessions", []):
        jsonl = s.get("file", "")
        meta = live_meta(jsonl) if jsonl else {"model": None, "age_s": 9e9}
        age = meta["age_s"] if meta["age_s"] is not None else s.get("age_min", 9e9) * 60
        out.append({
            "id": s.get("session", "")[:8],
            "kind": "external",
            "cwd": s.get("cwd", ""),
            "project": os.path.basename(s.get("cwd", "").rstrip("/")) or "~",
            "branch": s.get("branch", ""),
            "goal": (s.get("goal") or "").strip()[:240],
            "wins": s.get("wins", [])[:3],
            "blockers": s.get("blockers", [])[:3],
            "clients": s.get("clients", []),
            "urls": s.get("urls", [])[:3],
            "n_msgs": s.get("n_msgs", 0),
            "model": pretty_model(meta["model"]),
            "age_s": round(age),
            "live": age < LIVE_SEC,
            "tmux": None,
        })
        seen_cwd_id.add(s.get("session", "")[:8])

    # sessions gérées par NOVA WALL (tmux) — caméra LIVE + injectables
    for tname, info in managed.items():
        alive = tname in live_tmux
        cap = tmux_capture(tname, 40) if alive else ""
        out.append({
            "id": tname,
            "kind": "managed",
            "cwd": info.get("cwd", ""),
            "project": os.path.basename(info.get("cwd", "").rstrip("/")) or "~",
            "branch": "",
            "goal": f'[{MODES.get(info.get("mode","opus"),{}).get("label","?")}] terminal géré',
            "wins": [], "blockers": [], "clients": [], "urls": [],
            "n_msgs": 0,
            "model": MODES.get(info.get("mode", "opus"), {}).get("label", "?"),
            "mode": info.get("mode", "opus"),
            "age_s": 0 if alive else 9e9,
            "live": alive,
            "tmux": tname,
            "capture": cap[-4000:],
            "dead": not alive,
        })

    out.sort(key=lambda x: (not x["live"], x["age_s"]))
    with _lock:
        _cache["data"] = out; _cache["t"] = time.time()
    return out

# ------- HTTP -----------------------------------------------------------------
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)): body = json.dumps(body, ensure_ascii=False)
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try: self.wfile.write(b)
        except Exception: pass

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception: return {}

    def do_GET(self):
        u = urlparse(self.path); p = u.path
        if p in ("/", "/index.html"):
            try:
                with open(os.path.join(WEB, "index.html"), "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            except Exception as e:
                return self._send(500, f"index missing: {e}", "text/plain")
        if p == "/api/sessions":
            return self._send(200, {"sessions": build_sessions(),
                                    "modes": {k: v["label"] for k, v in MODES.items()},
                                    "ts": time.time()})
        if p == "/api/tile":
            sid = parse_qs(u.query).get("id", [""])[0]
            for s in build_sessions():
                if s["id"] == sid:
                    if s.get("tmux"):
                        s = dict(s); s["capture"] = tmux_capture(s["tmux"], 120)
                    else:
                        s = dict(s); s["tail"] = self._tail_summary(sid)
                    return self._send(200, s)
            return self._send(404, {"error": "not found"})
        if p == "/api/links":
            return self._send(200, jload(LINKS_F, {"edges": []}))
        return self._send(404, {"error": "no route"})

    def _tail_summary(self, sid):
        # dernières lignes de texte assistant/user d'un transcript externe
        files = glob.glob(os.path.join(PROJECTS, "**", f"{sid}*.jsonl"), recursive=True)
        if not files: return []
        t = tail_bytes(files[0], 120000)
        rows = []
        for line in t.splitlines()[-40:]:
            try: o = json.loads(line)
            except Exception: continue
            m = o.get("message", {})
            role = m.get("role") if isinstance(m, dict) else None
            c = m.get("content") if isinstance(m, dict) else None
            txt = ""
            if isinstance(c, str): txt = c
            elif isinstance(c, list):
                for blk in c:
                    if isinstance(blk, dict) and blk.get("type") == "text":
                        txt += blk.get("text", "")
                    elif isinstance(blk, dict) and blk.get("type") == "tool_use":
                        txt += f'[⚙ {blk.get("name","tool")}] '
            txt = txt.strip().replace("\n", " ")
            if txt and role: rows.append({"role": role, "text": txt[:220]})
        return rows[-8:]

    def do_POST(self):
        u = urlparse(self.path); p = u.path; d = self._body()
        if p == "/api/spawn":
            name = re.sub(r"[^a-zA-Z0-9_-]", "", d.get("name", "") or f"t{int(time.time())%10000}")
            mode = d.get("mode", "opus")
            cwd = d.get("cwd") or HOME
            if not os.path.isdir(cwd): cwd = HOME
            tname, status = tmux_spawn(name, mode, cwd)
            _cache["t"] = 0
            return self._send(200, {"ok": tname is not None, "tmux": tname, "status": status,
                                    "attach": f"tmux attach -t {tname}" if tname else None})
        if p == "/api/inject":
            target = d.get("target", ""); text = d.get("text", "")
            if not target.startswith("nova-") and target not in tmux_ls():
                return self._send(200, {"ok": False, "reason": "cible non gérée (caméra lecture-seule). "
                                        "Crée un terminal géré pour injecter, ou utilise le bus coord."})
            ok = tmux_send(target, text)
            return self._send(200, {"ok": ok})
        if p == "/api/kill":
            target = d.get("target", "")
            if target.startswith("nova-"):
                sh(["tmux", "kill-session", "-t", target])
                m = jload(MANAGED_F, {}); m.pop(target, None); jsave(MANAGED_F, m)
                _cache["t"] = 0
                return self._send(200, {"ok": True})
            return self._send(200, {"ok": False, "reason": "refuse: pas un terminal géré"})
        if p == "/api/link":
            links = jload(LINKS_F, {"edges": []})
            edge = {"from": d.get("from"), "to": d.get("to"),
                    "type": d.get("type", "inject"), "id": f'e{int(time.time()*1000)%100000}'}
            links["edges"].append(edge); jsave(LINKS_F, links)
            return self._send(200, {"ok": True, "edge": edge})
        if p == "/api/unlink":
            links = jload(LINKS_F, {"edges": []})
            links["edges"] = [e for e in links["edges"] if e.get("id") != d.get("id")]
            jsave(LINKS_F, links)
            return self._send(200, {"ok": True})
        if p == "/api/link/run":
            return self._send(200, self._run_link(d))
        return self._send(404, {"error": "no route"})

    def _ctx_of(self, sid):
        """Résumé transportable d'une session (pour injection/bridge/learn)."""
        for s in build_sessions():
            if s["id"] == sid:
                if s.get("tmux"):
                    cap = tmux_capture(s["tmux"], 60)
                    return f"[NOVA WALL · contexte de {sid}]\n{cap[-1500:]}"
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
            if str(dst).startswith("nova-") or dst in tmux_ls():
                msg = (f"Une autre session ({src}) partage son contexte via NOVA WALL. "
                       f"Prends-en connaissance et intègre ce qui est utile :\n\n{ctx}")
                return tmux_send(dst, msg)
            # fallback bus coord (cible non gérée)
            try:
                sh([os.path.join(HOME, "etz-chaim", "bus", "coord.py") if os.path.exists(
                    os.path.join(HOME, "etz-chaim", "bus", "coord.py")) else "true"])
            except Exception: pass
            outbox = os.path.join(STATE, f"inject_to_{dst}.md")
            with open(outbox, "w") as f: f.write(ctx)
            return False
        res = {}
        if typ in ("inject",):
            res["a_to_b"] = deliver(a, b)
        elif typ in ("bridge", "learn"):
            res["a_to_b"] = deliver(a, b)
            res["b_to_a"] = deliver(b, a)
        res["type"] = typ
        return {"ok": True, "result": res}

def main():
    os.chdir(ROOT)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"NOVA WALL → http://127.0.0.1:{PORT}  (Ctrl-C pour arrêter)")
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\nbye")

if __name__ == "__main__":
    main()
