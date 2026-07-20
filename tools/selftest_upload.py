#!/usr/bin/env python3
"""Nova Wall — test de non-régression de la voie « upload depuis le téléphone ».

Le mur écoute sur un TUNNEL PUBLIC (wall.dreamnovamcp.com) et accepte désormais
des fichiers de 512 Mo. Chaque assertion ci-dessous correspond à une manière
réelle de casser ça ou de s'en servir contre David — et rien ne les vérifiait.

Ce que le test prouve, en vrai HTTP, contre le serveur qui tourne :
  · les 4 types (photo / vidéo / audio / fichier) montent et atterrissent sur disque
  · le token protège /api/upload ET /api/media (sinon le tunnel est ouvert à tous)
  · un nom de fichier « ../../.. » ne peut pas écrire hors de state/uploads
  · /api/media refuse de servir un fichier hors de state/uploads (ex. /etc/passwd)
  · corps vide → 400 · Content-Length > 512 Mo → 413 SANS écrire un octet
  · transfert coupé en route → 400 et AUCUN .part orphelin laissé sur le disque
  · cible non gérée (session externe) → fichier gardé + refus HONNÊTE (jamais un faux « envoyé »)

N'écrit que sous la cible jetable `nova-selftest`, et nettoie tout derrière lui.
Aucune session réelle n'est touchée, rien n'est injecté dans un terminal de David.

    python3 tools/selftest_upload.py                 # instance mobile (:8791, token)
    python3 tools/selftest_upload.py --port 8790     # instance locale
"""
import argparse, http.client, json, os, socket, sys, time
from urllib.parse import quote

ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET  = "nova-selftest"                      # cible jetable : n'existe pas dans tmux
UPLOADS = DIR = INJECT = ""                    # fixés par set_root() (voir --root)


def set_root(root):
    """Où le serveur testé écrit ses fichiers (projet réel ou bac à sable)."""
    global ROOT, UPLOADS, DIR, INJECT
    ROOT    = os.path.abspath(os.path.expanduser(root))
    UPLOADS = os.path.join(ROOT, "state", "uploads")
    DIR     = os.path.join(UPLOADS, TARGET)
    INJECT  = os.path.join(ROOT, "state", f"inject_to_{TARGET}.md")

R = {"pass": 0, "fail": 0, "lines": []}


def check(name, ok, detail=""):
    R["pass" if ok else "fail"] += 1
    R["lines"].append((ok, name, detail))
    print(f"  {'✅' if ok else '❌'} {name}" + (f"  — {detail}" if detail else ""))
    return ok


def put(host, port, kind, name, body, tok, note="", target=TARGET, timeout=30):
    """PUT /api/upload comme le fait le téléphone : octets bruts + méta en en-têtes."""
    q = f"/api/upload?k={quote(tok)}" if tok else "/api/upload"
    c = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        c.request("POST", q, body=body, headers={
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(body)),
            "X-NW-Target": target, "X-NW-Kind": kind,
            "X-NW-Name": quote(name), "X-NW-Note": quote(note)})
        r = c.getresponse(); raw = r.read()
        try: return r.status, json.loads(raw)
        except Exception: return r.status, {"raw": raw[:200].decode("utf-8", "replace")}
    finally:
        c.close()


def get(host, port, path, tok=None, timeout=15):
    c = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        sep = "&" if "?" in path else "?"
        c.request("GET", path + (f"{sep}k={quote(tok)}" if tok else ""))
        r = c.getresponse()
        return r.status, r.getheader("Content-Type", ""), r.read()
    finally:
        c.close()


def raw_put(host, port, tok, declared, sent, name="coupe.bin", timeout=20):
    """Envoi bas niveau : annonce `declared` octets, n'en envoie que `sent`, puis ferme."""
    s = socket.create_connection((host, port), timeout=timeout)
    try:
        head = (f"POST /api/upload?k={quote(tok)} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                f"Content-Type: application/octet-stream\r\nContent-Length: {declared}\r\n"
                f"X-NW-Target: {TARGET}\r\nX-NW-Kind: file\r\nX-NW-Name: {quote(name)}\r\n"
                f"Connection: close\r\n\r\n").encode()
        s.sendall(head)
        if sent:
            s.sendall(b"x" * sent)
        s.shutdown(socket.SHUT_WR)                  # « je n'enverrai rien de plus »
        buf = b""
        while len(buf) < 4096:
            try:
                b = s.recv(4096)
            except socket.timeout:
                break
            if not b: break
            buf += b
        head_txt = buf.split(b"\r\n", 1)[0].decode("latin-1")
        code = int(head_txt.split()[1]) if len(head_txt.split()) > 1 else 0
        body = buf.split(b"\r\n\r\n", 1)[-1]
        try: return code, json.loads(body[body.find(b"{"):body.rfind(b"}") + 1] or b"{}")
        except Exception: return code, {}
    finally:
        s.close()


def cleanup():
    for p in (DIR, INJECT):
        try:
            if os.path.isdir(p):
                for f in os.listdir(p):
                    os.unlink(os.path.join(p, f))
                os.rmdir(p)
            elif os.path.isfile(p):
                os.unlink(p)
        except OSError:
            pass


def main():
    a = argparse.ArgumentParser(description="Test de non-régression upload Nova Wall")
    a.add_argument("--host", default="127.0.0.1")
    a.add_argument("--port", type=int, default=8791, help="8791 = instance mobile (token), 8790 = locale")
    a.add_argument("--token", default=None, help="défaut : state/mobile_token.txt")
    a.add_argument("--root", default=ROOT, help="racine du serveur visé (défaut : ce projet)")
    a.add_argument("--keep", action="store_true", help="ne pas nettoyer les fichiers de test")
    o = a.parse_args()
    set_root(o.root)

    tok = o.token
    if tok is None:
        try:
            with open(os.path.join(ROOT, "state", "mobile_token.txt")) as f: tok = f.read().strip()
        except OSError: tok = ""

    try:
        st, _, _ = get(o.host, o.port, "/api/sessions", tok)
    except OSError as e:
        print(f"⛔ serveur injoignable sur {o.host}:{o.port} ({e}) — lance-le d'abord.", file=sys.stderr)
        return 2
    if st != 200:
        print(f"⛔ /api/sessions renvoie {st} (token faux ?) — test impossible.", file=sys.stderr)
        return 2

    cleanup()
    print(f"🧪 NOVA WALL — voie upload · {o.host}:{o.port} · cible jetable « {TARGET} »\n")

    # ---- 1-4 : les 4 types que David a demandés ---------------------------------
    print("Les 4 types (photo / vidéo / audio / fichier) :")
    PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)     # entête PNG réelle + rembourrage
    cases = [("photo", "photo iphone.png", PNG),
             ("video", "clip.mp4", b"\x00\x00\x00\x18ftypmp42" + b"\x11" * 2048),
             ("audio", "memo vocal.m4a", b"\x00\x00\x00\x20ftypM4A " + b"\x22" * 1024),
             ("file",  "devis client.pdf", b"%PDF-1.4\n" + b"\x33" * 512)]
    saved = {}
    for kind, name, body in cases:
        st, j = put(o.host, o.port, kind, name, body, tok)
        p = j.get("path", "")
        on_disk = bool(p) and os.path.isfile(p) and os.path.getsize(p) == len(body)
        check(f"{kind:<5} → 200 + {len(body)} octets sur disque",
              st == 200 and j.get("ok") and on_disk,
              f"HTTP {st} · path={p or '∅'} · disque={'ok' if on_disk else 'ABSENT/TAILLE≠'}")
        if on_disk: saved[kind] = p

    # ---- 5 : honnêteté sur une cible non gérée ----------------------------------
    print("\nHonnêteté (cible externe = lecture seule) :")
    st, j = put(o.host, o.port, "photo", "honnetete.png", PNG, tok)
    check("fichier gardé mais injected=false + raison explicite",
          st == 200 and j.get("ok") and j.get("injected") is False and bool(j.get("reason")),
          f"injected={j.get('injected')} · reason={(j.get('reason') or '∅')[:48]}")

    # ---- 6-7 : le token protège vraiment le tunnel public -----------------------
    print("\nAuthentification (le mur est exposé sur un tunnel public) :")
    if tok:
        st, j = put(o.host, o.port, "file", "sans_token.bin", b"x" * 32, "")
        check("POST /api/upload sans token → 401", st == 401, f"HTTP {st}")
        victim = saved.get("photo", "")
        st2, _, _ = get(o.host, o.port, f"/api/media?p={quote(victim)}", None)
        check("GET /api/media sans token → 401", st2 == 401, f"HTTP {st2}")
    else:
        check("POST /api/upload sans token → 401", True, "instance sans token (:8790) — non applicable")
        check("GET /api/media sans token → 401", True, "instance sans token (:8790) — non applicable")

    # ---- 8 : pas d'évasion par le nom de fichier --------------------------------
    print("\nÉtanchéité du stockage :")
    st, j = put(o.host, o.port, "file", "../../../../tmp/nova_evasion.sh", b"#!/bin/sh\necho pwn\n", tok)
    p = j.get("path", "")
    inside = bool(p) and os.path.realpath(p).startswith(os.path.realpath(UPLOADS) + os.sep)
    check("nom « ../../../../tmp/… » reste dans state/uploads",
          st == 200 and inside and not os.path.exists("/tmp/nova_evasion.sh"),
          f"écrit dans {os.path.dirname(p) or '∅'}")
    if p and os.path.isfile(p): saved["evasion"] = p

    # ---- 9-10 : /api/media ne sert que la zone uploads --------------------------
    st, ct, body = get(o.host, o.port, f"/api/media?p={quote('/etc/passwd')}", tok)
    check("/api/media?p=/etc/passwd → 403", st == 403, f"HTTP {st}")
    if saved.get("photo"):
        st, ct, body = get(o.host, o.port, f"/api/media?p={quote(saved['photo'])}", tok)
        check("/api/media sert bien la photo (bons octets + image/png)",
              st == 200 and body == PNG and "image/png" in ct, f"HTTP {st} · {ct} · {len(body)} o")

    # ---- 11-13 : corps invalides -----------------------------------------------
    print("\nCorps invalides (le disque ne doit jamais trinquer) :")
    st, j = put(o.host, o.port, "file", "vide.bin", b"", tok)
    check("corps vide → 400", st == 400, f"HTTP {st}")

    before = set(os.listdir(DIR)) if os.path.isdir(DIR) else set()
    st, j = raw_put(o.host, o.port, tok, declared=600 * 1024 * 1024, sent=0, name="enorme.mov")
    after = set(os.listdir(DIR)) if os.path.isdir(DIR) else set()
    check("Content-Length 600 Mo → 413 sans rien écrire",
          st == 413 and after == before, f"HTTP {st} · nouveaux fichiers={len(after - before)}")

    st, j = raw_put(o.host, o.port, tok, declared=8192, sent=100, name="coupe.bin")
    time.sleep(0.3)
    parts = [f for f in (os.listdir(DIR) if os.path.isdir(DIR) else []) if f.endswith(".part")]
    check("transfert coupé → 400 et aucun .part orphelin",
          st == 400 and not parts, f"HTTP {st} · .part restants={parts or 0}")

    # ---- bilan ------------------------------------------------------------------
    if not o.keep:
        cleanup()
        check("nettoyage : aucune trace de test laissée",
              not os.path.isdir(DIR) and not os.path.isfile(INJECT))

    tot = R["pass"] + R["fail"]
    pct = (100.0 * R["pass"] / tot) if tot else 0
    print(f"\n{'✅' if not R['fail'] else '❌'} BILAN : {R['pass']}/{tot} = {pct:.0f}%")
    if R["fail"]:
        print("   échecs :")
        for ok, name, detail in R["lines"]:
            if not ok: print(f"     · {name} — {detail}")
    return 0 if not R["fail"] else 1


if __name__ == "__main__":
    sys.exit(main())
