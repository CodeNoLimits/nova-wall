#!/usr/bin/env python3
"""Robust Grok Imagine VIDEO driver (current UI, 2026-07-20).
Same proven core as gen_image.py: focus-emulation un-throttle, verify text landed,
click 'Valider', verify box cleared. Collects <video> src / mp4 URLs, downloads via
in-page credentialed fetch (handles blob: and https), verifies mp4 magic (ftyp).

Usage: gen_vid.py "<prompt>" <out.mp4> [ratio=16:9]
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
    for t in http("/json"):
        if t.get("type") == "page" and "grok.com/imagine" in (t.get("url") or ""):
            return t
    ver = http("/json/version")
    bws = websocket.create_connection(ver["webSocketDebuggerUrl"], timeout=20)
    bws.send(json.dumps({"id": 1, "method": "Target.createTarget",
                         "params": {"url": "https://grok.com/imagine", "background": True}}))
    while True:
        r = json.loads(bws.recv())
        if r.get("id") == 1: break
    bws.close(); time.sleep(5)
    for t in http("/json"):
        if t.get("type") == "page" and "grok.com/imagine" in (t.get("url") or ""):
            return t
    raise SystemExit("could not open imagine tab")

class CDP:
    def __init__(self, tab):
        self.ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=180, max_size=None)
        self.i = 0
        self.cmd("Runtime.enable"); self.cmd("Page.enable"); self.cmd("DOM.enable")
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
                self.ws.settimeout(40); r = json.loads(self.ws.recv())
            except Exception:
                if time.time() - t0 > 120: raise TimeoutError(m)
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
    return u if u.startswith("data:") or u.startswith("blob:") else u.split("?", 1)[0]

def find_btn(c, want_aria=None, want_text=None):
    return c.ev(r"""(()=>{
      const A=%s, T=%s;
      for (const b of document.querySelectorAll('button,[role=button]')){
        const aria=(b.getAttribute('aria-label')||''); const t=(b.innerText||'').trim();
        const r=b.getBoundingClientRect(); if (r.width<8||r.height<8) continue;
        if (A && aria===A) return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)});
        if (T && t===T) return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)});
      } return null;})()""" % (json.dumps(want_aria), json.dumps(want_text)))

def collect_vids(c):
    raw = c.ev(r"""(()=>{
      const out=[];
      for (const v of document.querySelectorAll('video')){
        const s=v.currentSrc||v.src||''; if(s) out.push({s, w:v.videoWidth||0, h:v.videoHeight||0});
        for (const src of v.querySelectorAll('source')){ const s2=src.src||''; if(s2) out.push({s:s2,w:0,h:0}); }
      }
      const html=document.documentElement.innerHTML||'';
      const re=/https:\/\/[^"'\s]+\.mp4[^"'\s]*/g; let m;
      while((m=re.exec(html))) out.push({s:m[0].replace(/&amp;/g,'&'), w:0, h:0});
      return JSON.stringify(out);
    })()""")
    try: return json.loads(raw)
    except Exception: return []

def fetch_bytes(c, url):
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

def is_video(raw):
    return (b"ftyp" in raw[:32]) or raw[:4] == b"\x1a\x45\xdf\xa3"

lock = open(os.path.expanduser("~/.grok_imagine.lock"), "w")
print("waiting_lock…", flush=True); fcntl.flock(lock, fcntl.LOCK_EX); print("lock_acquired", flush=True)
tab = ensure_tab()
c = CDP(tab)
try:
    try: c.cmd("Page.navigate", url="https://grok.com/imagine")
    except Exception: pass
    painted = False; nimg = 0
    for _ in range(50):
        txt_len = c.ev("(document.body&&document.body.innerText||'').length") or 0
        nimg = c.ev("[...document.querySelectorAll('img')].filter(x=>(x.naturalWidth||0)>0).length") or 0
        if txt_len > 60 and nimg >= 3: painted = True; break
        time.sleep(0.5)
    print(f"painted={painted} imgs={nimg}", flush=True)
    c.cmd("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
    c.cmd("Input.dispatchKeyEvent", type="keyUp", key="Escape", code="Escape", windowsVirtualKeyCode=27)
    time.sleep(0.3)

    b = find_btn(c, want_text="Vidéo") or find_btn(c, want_text="Video")
    if b:
        c.click(*json.loads(b).values()); time.sleep(0.6); print("clicked Vidéo mode", flush=True)
    else:
        print("WARN: Vidéo button not found", flush=True)

    cur = c.ev(r"""(()=>{const b=[...document.querySelectorAll('button,[role=button]')].find(x=>(x.getAttribute('aria-label')||'')==='Proportions');return b?(b.innerText||'').trim():'?';})()""")
    print("ratio_now:", cur, flush=True)
    if cur and cur != "?" and RATIO not in cur:
        chip = c.ev(r"""(()=>{const b=[...document.querySelectorAll('button,[role=button]')].find(x=>(x.getAttribute('aria-label')||'')==='Proportions');if(!b)return null;const r=b.getBoundingClientRect();return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)});})()""")
        if chip:
            c.click(*json.loads(chip).values()); time.sleep(0.8)
            opt = c.ev(r"""(()=>{for(const el of document.querySelectorAll('span,div,button,[role=menuitem]')){const t=(el.innerText||'').trim();if(t===%s){const r=el.getBoundingClientRect();if(r.width>2&&r.height>2&&r.height<70)return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)});}}return null;})()""" % json.dumps(RATIO))
            if opt: c.click(*json.loads(opt).values()); time.sleep(0.6)
        print("ratio_after:", c.ev(r"""(()=>{const b=[...document.querySelectorAll('button,[role=button]')].find(x=>(x.getAttribute('aria-label')||'')==='Proportions');return b?(b.innerText||'').trim():'?';})()"""), flush=True)

    baseline = {canon(x["s"]) for x in collect_vids(c)}
    print("baseline_vids:", len(baseline), flush=True)

    def focus_and_type():
        box = c.ev(r"""(()=>{const cs=[...document.querySelectorAll('[contenteditable=true],textarea')].map(x=>{const r=x.getBoundingClientRect();return {x,a:r.width*r.height,r};}).filter(o=>o.a>3000).sort((a,b)=>b.a-a.a);if(!cs[0])return null;const o=cs[0];o.x.focus();return JSON.stringify({x:Math.round(o.r.x+o.r.width/2),y:Math.round(o.r.y+o.r.height/2)});})()""")
        if not box: raise SystemExit("no prompt box")
        bx = json.loads(box); c.click(bx["x"], bx["y"]); time.sleep(0.2)
        c.ev(r"""(()=>{const cs=[...document.querySelectorAll('[contenteditable=true],textarea')].map(x=>{const r=x.getBoundingClientRect();return {x,a:r.width*r.height};}).filter(o=>o.a>3000).sort((a,b)=>b.a-a.a);if(cs[0])cs[0].x.focus();return true;})()""")
        c.cmd("Input.dispatchKeyEvent", type="keyDown", key="a", code="KeyA", modifiers=4, windowsVirtualKeyCode=65)
        c.cmd("Input.dispatchKeyEvent", type="keyUp", key="a", code="KeyA", modifiers=4, windowsVirtualKeyCode=65)
        c.cmd("Input.dispatchKeyEvent", type="keyDown", key="Delete", code="Delete", windowsVirtualKeyCode=46)
        c.cmd("Input.dispatchKeyEvent", type="keyUp", key="Delete", code="Delete", windowsVirtualKeyCode=46)
        time.sleep(0.15); c.cmd("Input.insertText", text=PROMPT); time.sleep(0.6)
        return c.ev(r"""(()=>{const cs=[...document.querySelectorAll('[contenteditable=true],textarea')].map(x=>{const r=x.getBoundingClientRect();return {x,a:r.width*r.height};}).filter(o=>o.a>3000).sort((a,b)=>b.a-a.a);return cs[0]?((cs[0].x.innerText||cs[0].x.value||'')).slice(0,80):'';})()""")

    typed = focus_and_type()
    print("typed_readback:", repr(typed)[:90], flush=True)
    if not typed or len(typed.strip()) < 5:
        time.sleep(0.5); typed = focus_and_type(); print("typed2:", repr(typed)[:90], flush=True)
        if not typed or len(typed.strip()) < 5: raise SystemExit("FAIL_TEXT_ENTRY")

    def box_text():
        return (c.ev(r"""(()=>{const cs=[...document.querySelectorAll('[contenteditable=true],textarea')].map(x=>{const r=x.getBoundingClientRect();return {x,a:r.width*r.height};}).filter(o=>o.a>3000).sort((a,b)=>b.a-a.a);return cs[0]?((cs[0].x.innerText||cs[0].x.value||'')).trim():'';})()""") or "")
    def do_submit():
        sb = find_btn(c, want_aria="Valider")
        if sb: c.click(*json.loads(sb).values()); print("clicked Valider", flush=True)
        time.sleep(3)
        if len(box_text()) > 5:
            c.cmd("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13)
            c.cmd("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13)
            print("Enter fallback", flush=True); time.sleep(3)
        return len(box_text()) <= 5
    if not do_submit():
        focus_and_type(); do_submit()
    print("submit_box_cleared=", box_text() == "", flush=True)

    print("polling video (up to 360s)…", flush=True)
    t0 = time.time(); best = None; last = None; stable = 0
    while time.time() - t0 < 360:
        vids = collect_vids(c)
        new = [x for x in vids if canon(x["s"]) not in baseline]
        new = [x for x in new if (".mp4" in x["s"].lower() or x["s"].startswith("blob:"))]
        if new:
            sig = tuple(sorted(canon(x["s"]) for x in new))
            if sig == last: stable += 1
            else: stable = 0; last = sig
            if stable >= 2: best = new; break
        el = int(time.time()-t0)
        if el % 30 < 7: print(f"  … {el}s new_vids={len(new)}", flush=True)
        time.sleep(6)
    if not best:
        vids = collect_vids(c)
        best = [x for x in vids if canon(x["s"]) not in baseline and (".mp4" in x["s"].lower() or x["s"].startswith("blob:"))]
    if not best:
        raise SystemExit("NO_NEW_VIDEO")
    print("video candidates:", [canon(x["s"])[:70] for x in best[:4]], flush=True)

    saved = False
    for x in best:
        raw = fetch_bytes(c, x["s"])
        if raw and len(raw) > 20000 and is_video(raw):
            open(OUT, "wb").write(raw)
            print(f"SAVED {OUT} bytes={len(raw)} md5={hashlib.md5(raw).hexdigest()[:12]}", flush=True)
            saved = True; break
        else:
            print("  skip cand bytes=", (len(raw) if raw else 0), flush=True)
    if not saved:
        raise SystemExit("VIDEO_DOWNLOAD_FAILED")
    print("DONE", flush=True)
finally:
    c.close()
