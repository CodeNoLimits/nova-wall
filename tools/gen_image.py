#!/usr/bin/env python3
"""Robust Grok Imagine IMAGE driver (current UI, 2026-07-20).
Fixes over grok_imagine.py: real focus of the contenteditable, VERIFY text landed,
click the 'Valider' submit button (not Enter), capture results from imagine-public.x.ai
/ assets.grok.com / data:image, download via in-page credentialed fetch, md5 + magic check.

Usage: gen_image.py "<prompt>" <out.png> [ratio=16:9]
"""
import json, urllib.request, base64, hashlib, os, sys, time, fcntl
import websocket

BASE = "http://127.0.0.1:9222"
PROMPT = sys.argv[1]
OUT = os.path.abspath(os.path.expanduser(sys.argv[2]))
RATIO = sys.argv[3] if len(sys.argv) > 3 else "16:9"

def http(path):
    return json.load(urllib.request.urlopen(BASE + path, timeout=10))

def ensure_tab():
    tabs = http("/json")
    for t in tabs:
        if t.get("type") == "page" and "grok.com/imagine" in (t.get("url") or ""):
            return t
    # create background tab via CDP (never /json/new — focus safe)
    ver = http("/json/version")
    bws = websocket.create_connection(ver["webSocketDebuggerUrl"], timeout=20)
    bws.send(json.dumps({"id": 1, "method": "Target.createTarget",
                         "params": {"url": "https://grok.com/imagine", "background": True}}))
    while True:
        r = json.loads(bws.recv())
        if r.get("id") == 1:
            break
    bws.close()
    time.sleep(5)
    for t in http("/json"):
        if t.get("type") == "page" and "grok.com/imagine" in (t.get("url") or ""):
            return t
    raise SystemExit("could not open imagine tab")

class CDP:
    def __init__(self, tab):
        self.ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=120, max_size=None)
        self.i = 0
        self.cmd("Runtime.enable"); self.cmd("Page.enable"); self.cmd("DOM.enable")
        # Un-throttle a background/never-painted tab so images LOAD and React registers input,
        # WITHOUT raising the window (focus-safe — no bringToFront/activateTarget).
        for m, p in (("Emulation.setFocusEmulationEnabled", {"enabled": True}),
                     ("Page.setWebLifecycleState", {"state": "active"})):
            try: self.cmd(m, **p)
            except Exception: pass
    def cmd(self, m, **p):
        self.i += 1
        self.ws.send(json.dumps({"id": self.i, "method": m, "params": p}))
        t0 = time.time()
        while True:
            try:
                self.ws.settimeout(30); r = json.loads(self.ws.recv())
            except Exception:
                if time.time() - t0 > 90: raise TimeoutError(m)
                continue
            if r.get("id") == self.i:
                return r.get("result", {})
    def ev(self, js, aw=True):
        return self.cmd("Runtime.evaluate", expression=js, returnByValue=True, awaitPromise=aw).get("result", {}).get("value")
    def click(self, x, y):
        for t in ("mouseMoved", "mousePressed", "mouseReleased"):
            self.cmd("Input.dispatchMouseEvent", type=t, x=x, y=y, button="left",
                     buttons=1 if t == "mousePressed" else 0, clickCount=1)
        time.sleep(0.2)
    def close(self):
        try: self.ws.close()
        except Exception: pass

def canon(u):
    return u if u.startswith("data:") else u.split("?", 1)[0]

def find_btn(c, want_aria=None, want_text=None):
    return c.ev(r"""(()=>{
      const A=%s, T=%s;
      for (const b of document.querySelectorAll('button,[role=button]')){
        const aria=(b.getAttribute('aria-label')||''); const t=(b.innerText||'').trim();
        const r=b.getBoundingClientRect();
        if (r.width<8||r.height<8) continue;
        if (A && aria===A) return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)});
        if (T && t===T) return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)});
      }
      return null;})()""" % (json.dumps(want_aria), json.dumps(want_text)))

def collect_imgs(c):
    """Return list of {src, w, h} for imgs that could be generation results."""
    raw = c.ev(r"""(()=>{
      const out=[];
      for (const im of document.querySelectorAll('img')){
        const s=im.currentSrc||im.src||'';
        if(!s) continue;
        if(/thumb|icon|avatar|logo/i.test(s)) continue;
        out.push({s, w:im.naturalWidth||0, h:im.naturalHeight||0});
      }
      // data:image big
      return JSON.stringify(out);
    })()""")
    try: return json.loads(raw)
    except Exception: return []

def fetch_bytes(c, url):
    if url.startswith("data:"):
        try: return base64.b64decode(url.split(",", 1)[1])
        except Exception: return None
    b64 = c.ev(r"""(async()=>{try{
      const r=await fetch(%s,{credentials:'include'}); if(!r.ok) return 'HTTP '+r.status;
      const b=new Uint8Array(await r.arrayBuffer()); let s=''; const C=32768;
      for(let i=0;i<b.length;i+=C) s+=String.fromCharCode.apply(null,b.subarray(i,i+C));
      return btoa(s);
    }catch(e){return 'ERR '+e;}})()""" % json.dumps(url))
    if not b64 or (isinstance(b64, str) and (b64.startswith("HTTP") or b64.startswith("ERR"))):
        return None
    try: return base64.b64decode(b64)
    except Exception: return None

def is_image(raw):
    h = raw[:16]
    return h.startswith(b"\x89PNG") or h.startswith(b"\xff\xd8") or h[8:12] == b"WEBP" or h.startswith(b"GIF8")

# ---- run ----
lock = open(os.path.expanduser("~/.grok_imagine.lock"), "w")
print("waiting_lock…", flush=True)
fcntl.flock(lock, fcntl.LOCK_EX)
print("lock_acquired", flush=True)
tab = ensure_tab()
c = CDP(tab)
try:
    # Fresh home state each run (clean generation context, anti-continuation), then wait
    # until the tab actually PAINTS images (naturalWidth>0) — proves it's not throttled.
    try: c.cmd("Page.navigate", url="https://grok.com/imagine")
    except Exception: pass
    painted = False
    for _ in range(50):  # up to ~25s
        txt_len = c.ev("(document.body&&document.body.innerText||'').length") or 0
        nimg = c.ev("[...document.querySelectorAll('img')].filter(x=>(x.naturalWidth||0)>0).length") or 0
        if txt_len > 60 and nimg >= 3:
            painted = True; break
        time.sleep(0.5)
    print(f"painted={painted} imgs_loaded={nimg} txt_len={txt_len}", flush=True)
    c.cmd("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
    c.cmd("Input.dispatchKeyEvent", type="keyUp", key="Escape", code="Escape", windowsVirtualKeyCode=27)
    time.sleep(0.3)

    # ensure IMAGE mode
    b = find_btn(c, want_text="Image")
    if b: c.click(*json.loads(b).values()); time.sleep(0.4)

    # ratio
    cur = c.ev(r"""(()=>{const b=[...document.querySelectorAll('button,[role=button]')].find(x=>(x.getAttribute('aria-label')||'')==='Proportions'||/^\s*\d+:\d+\s*$/.test((x.innerText||'').trim()));return b?(b.innerText||'').trim():'?';})()""")
    print("ratio_now:", cur, flush=True)
    if cur and RATIO not in cur:
        chip = c.ev(r"""(()=>{const b=[...document.querySelectorAll('button,[role=button]')].find(x=>(x.getAttribute('aria-label')||'')==='Proportions');if(!b)return null;const r=b.getBoundingClientRect();return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)});})()""")
        if chip:
            c.click(*json.loads(chip).values()); time.sleep(0.8)
            opt = c.ev(r"""(()=>{for(const el of document.querySelectorAll('span,div,button,[role=menuitem]')){const t=(el.innerText||'').trim();if(t===%s){const r=el.getBoundingClientRect();if(r.width>2&&r.height>2&&r.height<70)return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)});}}return null;})()""" % json.dumps(RATIO))
            if opt: c.click(*json.loads(opt).values()); time.sleep(0.6)
        after = c.ev(r"""(()=>{const b=[...document.querySelectorAll('button,[role=button]')].find(x=>(x.getAttribute('aria-label')||'')==='Proportions');return b?(b.innerText||'').trim():'?';})()""")
        print("ratio_after:", after, flush=True)

    # baseline images
    baseline = {canon(x["s"]) for x in collect_imgs(c)}
    print("baseline_imgs:", len(baseline), flush=True)

    # focus prompt box, insert, VERIFY
    def focus_and_type():
        box = c.ev(r"""(()=>{
          const cs=[...document.querySelectorAll('[contenteditable=true],textarea')].map(x=>{const r=x.getBoundingClientRect();return {x, a:r.width*r.height, r};}).filter(o=>o.a>3000).sort((a,b)=>b.a-a.a);
          if(!cs[0]) return null; const o=cs[0]; o.x.focus();
          return JSON.stringify({x:Math.round(o.r.x+o.r.width/2), y:Math.round(o.r.y+o.r.height/2)});
        })()""")
        if not box: raise SystemExit("no prompt box")
        bx = json.loads(box)
        c.click(bx["x"], bx["y"]); time.sleep(0.2)
        # re-focus via JS too
        c.ev(r"""(()=>{const cs=[...document.querySelectorAll('[contenteditable=true],textarea')].map(x=>{const r=x.getBoundingClientRect();return {x,a:r.width*r.height};}).filter(o=>o.a>3000).sort((a,b)=>b.a-a.a);if(cs[0])cs[0].x.focus();return true;})()""")
        # clear
        c.cmd("Input.dispatchKeyEvent", type="keyDown", key="a", code="KeyA", modifiers=4, windowsVirtualKeyCode=65)
        c.cmd("Input.dispatchKeyEvent", type="keyUp", key="a", code="KeyA", modifiers=4, windowsVirtualKeyCode=65)
        c.cmd("Input.dispatchKeyEvent", type="keyDown", key="Delete", code="Delete", windowsVirtualKeyCode=46)
        c.cmd("Input.dispatchKeyEvent", type="keyUp", key="Delete", code="Delete", windowsVirtualKeyCode=46)
        time.sleep(0.15)
        c.cmd("Input.insertText", text=PROMPT)
        time.sleep(0.6)
        return c.ev(r"""(()=>{const cs=[...document.querySelectorAll('[contenteditable=true],textarea')].map(x=>{const r=x.getBoundingClientRect();return {x,a:r.width*r.height};}).filter(o=>o.a>3000).sort((a,b)=>b.a-a.a);return cs[0]?((cs[0].x.innerText||cs[0].x.value||'')).slice(0,80):'';})()""")

    typed = focus_and_type()
    print("typed_readback:", repr(typed)[:100], flush=True)
    if not typed or len(typed.strip()) < 5:
        print("retry focus/type…", flush=True)
        time.sleep(0.5); typed = focus_and_type()
        print("typed_readback2:", repr(typed)[:100], flush=True)
        if not typed or len(typed.strip()) < 5:
            raise SystemExit("FAIL_TEXT_ENTRY")

    def box_text():
        return (c.ev(r"""(()=>{const cs=[...document.querySelectorAll('[contenteditable=true],textarea')].map(x=>{const r=x.getBoundingClientRect();return {x,a:r.width*r.height};}).filter(o=>o.a>3000).sort((a,b)=>b.a-a.a);return cs[0]?((cs[0].x.innerText||cs[0].x.value||'')).trim():'';})()""") or "")

    # submit via Valider button, then VERIFY box cleared (proof submit registered)
    def do_submit():
        sb = find_btn(c, want_aria="Valider")
        if sb:
            s = json.loads(sb); c.click(s["x"], s["y"]); print("clicked Valider", flush=True)
        time.sleep(2.5)
        if len(box_text()) > 5:  # not submitted → Enter fallback
            c.cmd("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13)
            c.cmd("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13)
            print("box not cleared → pressed Enter", flush=True)
            time.sleep(2.5)
        return len(box_text()) <= 5
    ok = do_submit()
    if not ok:
        # re-focus, ensure text, try once more
        print("submit not confirmed, retrying focus+submit…", flush=True)
        focus_and_type(); do_submit()
    print("submit_confirmed_box_cleared=", box_text() == "", flush=True)
    time.sleep(3)

    # poll for NEW large images
    print("polling results…", flush=True)
    t0 = time.time()
    best = None
    stable = 0
    last_sig = None
    while time.time() - t0 < 300:
        imgs = collect_imgs(c)
        new = [x for x in imgs if canon(x["s"]) not in baseline and (x["w"] >= 640 or x["s"].startswith("data:image"))]
        # prefer landscape (16:9) large ones
        new.sort(key=lambda x: (1 if x["w"] >= x["h"] else 0, x["w"] * x["h"]), reverse=True)
        if new:
            sig = tuple(sorted(canon(x["s"]) for x in new[:4]))
            if sig == last_sig:
                stable += 1
            else:
                stable = 0; last_sig = sig
            if stable >= 2:
                best = new
                break
        time.sleep(5)
    if not best:
        # last attempt: any new imgs at all
        imgs = collect_imgs(c)
        best = [x for x in imgs if canon(x["s"]) not in baseline and (x["w"] >= 400 or x["s"].startswith("data:image"))]
        best.sort(key=lambda x: x["w"] * x["h"], reverse=True)
    if not best:
        raise SystemExit("NO_NEW_IMAGES")
    print("candidates:", [(x["w"], x["h"], canon(x["s"])[:60]) for x in best[:5]], flush=True)

    # Download all viable distinct candidates, then pick the LARGEST bytes as primary
    # (Grok serves a tiny progressive preview + the full-res of each variant; we want full-res).
    downloaded = {}  # md5 -> raw
    for x in best[:6]:
        raw = fetch_bytes(c, x["s"])
        if not raw or len(raw) < 20000 or not is_image(raw):
            continue
        m = hashlib.md5(raw).hexdigest()
        if m not in downloaded:
            downloaded[m] = raw
    if not downloaded:
        raise SystemExit("DOWNLOAD_FAILED")
    ordered = sorted(downloaded.items(), key=lambda kv: len(kv[1]), reverse=True)
    open(OUT, "wb").write(ordered[0][1])
    print(f"SAVED {OUT} bytes={len(ordered[0][1])} md5={ordered[0][0][:12]}", flush=True)
    if len(ordered) > 1 and len(ordered[1][1]) > 40000:
        alt = OUT.replace(".png", "_alt2.png")
        open(alt, "wb").write(ordered[1][1])
        print(f"SAVED {alt} bytes={len(ordered[1][1])} md5={ordered[1][0][:12]}", flush=True)
    print("DONE saved=", len(ordered), flush=True)
finally:
    c.close()
