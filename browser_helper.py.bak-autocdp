#!/usr/bin/env python3
"""
NOVA WALL — helper navigateur (raw CDP, léger, thread-safe).
Screenshots + interaction sur les onglets Chrome de David via CDP 9222, PAR ONGLET
(pas d'attache globale = pas de lag). Focus-safe : captureScreenshot/Input ne lèvent
jamais la fenêtre OS ; les nouveaux onglets sont créés via Target.createTarget (background).
"""
import os, json, base64, time, urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import websocket  # websocket-client

CDP_HTTP = os.environ.get("NOVA_WALL_CDP_HTTP", "http://127.0.0.1:9222")
PORT     = int(os.environ.get("NOVA_WALL_BROWSER_PORT", "8792"))

def http_json(path):
    with urllib.request.urlopen(CDP_HTTP + path, timeout=5) as r:
        return json.loads(r.read())

def targets():
    try: return [t for t in http_json("/json") if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    except Exception: return []

def find(key):
    ts = targets()
    if not ts: return None
    if key in (None, ""): return ts[0]
    key = str(key)
    if key.lstrip("-").isdigit():
        i = int(key); return ts[i] if -len(ts) <= i < len(ts) else None
    for t in ts:
        if key.lower() in (t.get("url", "") + " " + t.get("title", "")).lower(): return t
    return None

def cdp_seq(ws_url, cmds, timeout=12):
    ws = websocket.create_connection(ws_url, timeout=timeout, max_size=None)
    last = None
    try:
        for i, (m, p) in enumerate(cmds, 1):
            ws.send(json.dumps({"id": i, "method": m, "params": p or {}}))
            end = time.time() + timeout
            while time.time() < end:
                msg = json.loads(ws.recv())
                if msg.get("id") == i: last = msg; break
        return last
    finally:
        try: ws.close()
        except Exception: pass

def shot(key, q=55, scale=0.5):
    t = find(key)
    if not t: return None
    try:
        ws = t["webSocketDebuggerUrl"]
        # réveil onglet d'arrière-plan (sinon rendu gris / capture qui échoue) — focus-safe, pas de raise fenêtre
        try:
            cdp_seq(ws, [("Emulation.setFocusEmulationEnabled", {"enabled": True}),
                         ("Page.setWebLifecycleState", {"state": "active"})], timeout=4)
        except Exception: pass
        m = cdp_seq(ws, [("Page.getLayoutMetrics", {})])["result"]
        vp = m.get("cssVisualViewport") or m.get("visualViewport") or {}
        w, h = vp.get("clientWidth", 1280), vp.get("clientHeight", 800)
        params = {"format": "jpeg", "quality": max(15, min(80, q)), "captureBeyondViewport": False,
                  "clip": {"x": vp.get("pageX", 0), "y": vp.get("pageY", 0),
                           "width": w, "height": h, "scale": max(0.2, min(1.0, scale))}}
        r = cdp_seq(ws, [("Page.captureScreenshot", params)])
        return base64.b64decode(r["result"]["data"])
    except Exception: return None

def nav(key, url):
    t = find(key)
    if not t: return False
    try: cdp_seq(t["webSocketDebuggerUrl"], [("Page.navigate", {"url": url})]); return True
    except Exception: return False

def open_tab(url):
    try:
        bws = http_json("/json/version")["webSocketDebuggerUrl"]
        cdp_seq(bws, [("Target.createTarget", {"url": url or "about:blank"})]); return True
    except Exception: return False

def click(key, x, y, w, h):
    t = find(key)
    if not t: return False
    try:
        ws = t["webSocketDebuggerUrl"]
        r = cdp_seq(ws, [("Runtime.evaluate", {"expression": "JSON.stringify([innerWidth,innerHeight])", "returnByValue": True})])
        dw, dh = json.loads(r["result"]["result"]["value"])
        px = x / max(w, 1) * dw; py = y / max(h, 1) * dh
        cdp_seq(ws, [
            ("Input.dispatchMouseEvent", {"type": "mousePressed", "x": px, "y": py, "button": "left", "clickCount": 1}),
            ("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": px, "y": py, "button": "left", "clickCount": 1})])
        return True
    except Exception: return False

def type_text(key, text):
    t = find(key)
    if not t: return False
    try: cdp_seq(t["webSocketDebuggerUrl"], [("Input.insertText", {"text": text})]); return True
    except Exception: return False

def press(key, k):
    t = find(key)
    if not t: return False
    try:
        ws = t["webSocketDebuggerUrl"]
        cdp_seq(ws, [("Input.dispatchKeyEvent", {"type": "keyDown", "key": k}),
                     ("Input.dispatchKeyEvent", {"type": "keyUp", "key": k})])
        return True
    except Exception: return False

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _s(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)): body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str): body = body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers()
        try: self.wfile.write(body)
        except Exception: pass
    def _b(self):
        try: return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except Exception: return {}
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/tabs":
            return self._s(200, {"tabs": [{"i": i, "url": t.get("url", ""), "title": (t.get("title", "") or "")[:80]}
                                          for i, t in enumerate(targets())]})
        if u.path == "/shot":
            try: qual = int(q.get("q", ["55"])[0]); sc = float(q.get("s", ["0.5"])[0])
            except Exception: qual, sc = 55, 0.5
            img = shot(q.get("t", [""])[0], qual, sc)
            return self._s(200, img, "image/jpeg") if img else self._s(404, {"error": "no shot"})
        if u.path == "/health":
            return self._s(200, {"ok": True, "tabs": len(targets())})
        return self._s(404, {"error": "no route"})
    def do_POST(self):
        u = urlparse(self.path); d = self._b()
        if u.path == "/nav":   return self._s(200, {"ok": nav(d.get("t"), d.get("url", ""))})
        if u.path == "/open":  return self._s(200, {"ok": open_tab(d.get("url", ""))})
        if u.path == "/click": return self._s(200, {"ok": click(d.get("t"), d.get("x", 0), d.get("y", 0), d.get("w", 1), d.get("h", 1))})
        if u.path == "/type":  return self._s(200, {"ok": type_text(d.get("t"), d.get("text", ""))})
        if u.path == "/key":   return self._s(200, {"ok": press(d.get("t"), d.get("key", "Enter"))})
        return self._s(404, {"error": "no route"})

if __name__ == "__main__":
    print(f"NOVA WALL browser helper (raw CDP) → 127.0.0.1:{PORT} · {len(targets())} onglets")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
