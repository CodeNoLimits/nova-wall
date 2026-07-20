#!/usr/bin/env python3
"""Nova Wall — garde-disque du dossier d'uploads (photos/vidéos/audios/fichiers du téléphone).

Pourquoi : `/api/upload` accepte jusqu'à 512 Mo par fichier et n'efface jamais rien.
Une vidéo iPhone par jour = ~30 Go/mois qui s'empilent en silence dans state/uploads.
Règle AGENTS.md §8 : ne JAMAIS remplir le disque. Ce script est le seul balai.

Politique (dans cet ordre) :
  1. `.part` orphelins (transferts interrompus) plus vieux que --part-minutes  -> supprimés
  2. fichiers plus vieux que --days                                            -> supprimés
  3. si le total dépasse --max-mb : les plus VIEUX d'abord jusqu'à repasser dessous
  4. si l'espace libre du disque < --min-free-gb : on continue à purger (mode urgence)
  Garde-fou : les --keep fichiers les plus récents de CHAQUE session sont intouchables
  (on ne mange jamais l'upload que David vient d'envoyer).

Sûreté : agit UNIQUEMENT à l'intérieur de state/uploads (realpath vérifié), ignore les
liens symboliques, et NE SUPPRIME RIEN sans --apply (défaut = simulation).

    python3 tools/uploads_gc.py                 # simulation, rapport lisible
    python3 tools/uploads_gc.py --apply         # purge réelle
    python3 tools/uploads_gc.py --apply --json  # pour un daemon / un log
"""
import argparse, json, os, shutil, sys, time

HERE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS = os.path.realpath(os.path.join(HERE, "state", "uploads"))
MB      = 1024 * 1024


def scan():
    """Tous les fichiers réels sous state/uploads, groupés par session."""
    sessions = {}
    if not os.path.isdir(UPLOADS):
        return sessions
    for sub in sorted(os.listdir(UPLOADS)):
        d = os.path.join(UPLOADS, sub)
        if not os.path.isdir(d) or os.path.islink(d):
            continue
        rows = []
        for name in os.listdir(d):
            p = os.path.join(d, name)
            if os.path.islink(p) or not os.path.isfile(p):
                continue                                  # jamais de symlink, jamais de dossier
            if os.path.realpath(p) != p and not os.path.realpath(p).startswith(UPLOADS + os.sep):
                continue                                  # hors zone => on ne touche pas
            try:
                st = os.stat(p)
            except OSError:
                continue
            rows.append({"path": p, "size": st.st_size, "mtime": st.st_mtime,
                         "part": name.endswith(".part")})
        rows.sort(key=lambda r: r["mtime"], reverse=True)  # plus récent d'abord
        if rows:
            sessions[sub] = rows
    return sessions


def plan(sessions, days, max_mb, keep, part_minutes, min_free_gb):
    """Décide quoi supprimer. Retourne (victimes, protégés, stats)."""
    now = time.time()
    protected, pool = set(), []
    for rows in sessions.values():
        for i, r in enumerate(rows):
            if i < keep and not r["part"]:
                protected.add(r["path"])                   # les N derniers de la session
            else:
                pool.append(r)
    pool.sort(key=lambda r: r["mtime"])                    # plus VIEUX d'abord = première victime

    total = sum(r["size"] for rows in sessions.values() for r in rows)
    victims, why = [], {}

    def kill(r, reason):
        if r["path"] in protected or r["path"] in why:
            return
        victims.append(r); why[r["path"]] = reason

    for r in pool:                                          # 1. .part orphelins
        if r["part"] and now - r["mtime"] > part_minutes * 60:
            kill(r, f"transfert interrompu (.part, >{part_minutes} min)")
    for r in pool:                                          # 2. âge
        if now - r["mtime"] > days * 86400:
            kill(r, f"plus vieux que {days} j")

    freed = sum(r["size"] for r in victims)
    try:
        free = shutil.disk_usage(UPLOADS if os.path.isdir(UPLOADS) else HERE).free
    except OSError:
        free = None

    for r in pool:                                          # 3. plafond de taille + 4. urgence disque
        over_cap  = (total - freed) > max_mb * MB
        low_disk  = free is not None and (free + freed) < min_free_gb * 1024 * MB
        if not (over_cap or low_disk):
            break
        if r["path"] in why:
            continue
        kill(r, "plafond dépassé" if over_cap else "disque presque plein")
        freed += r["size"]

    stats = {"total_mb": round(total / MB, 1), "freed_mb": round(freed / MB, 1),
             "files_total": sum(len(v) for v in sessions.values()),
             "files_deleted": len(victims), "protected": len(protected),
             "free_gb_before": round(free / (1024 * MB), 1) if free is not None else None,
             "sessions": len(sessions)}
    return victims, why, stats


def main():
    a = argparse.ArgumentParser(description="Garde-disque des uploads Nova Wall")
    a.add_argument("--apply", action="store_true", help="supprimer pour de vrai (défaut : simulation)")
    a.add_argument("--days", type=int, default=21, help="âge max d'un upload (défaut 21 j)")
    a.add_argument("--max-mb", type=int, default=2048, help="taille totale max (défaut 2048 Mo)")
    a.add_argument("--keep", type=int, default=3, help="derniers fichiers intouchables par session (défaut 3)")
    a.add_argument("--part-minutes", type=int, default=60, help="âge d'un .part orphelin (défaut 60 min)")
    a.add_argument("--min-free-gb", type=int, default=5, help="marge disque à préserver (défaut 5 Go)")
    a.add_argument("--json", action="store_true", help="sortie machine")
    o = a.parse_args()

    sessions = scan()
    victims, why, stats = plan(sessions, o.days, o.max_mb, o.keep, o.part_minutes, o.min_free_gb)

    deleted, errors = [], []
    if o.apply:
        for r in victims:
            p = os.path.realpath(r["path"])
            if not p.startswith(UPLOADS + os.sep):          # ceinture + bretelles
                errors.append({"path": p, "error": "hors zone uploads — refusé"}); continue
            try:
                os.unlink(p); deleted.append(p)
            except OSError as e:
                errors.append({"path": p, "error": str(e)})
        for sub in list(sessions):                          # dossiers de session devenus vides
            d = os.path.join(UPLOADS, sub)
            try:
                if os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
            except OSError:
                pass

    out = {"ok": not errors, "applied": o.apply, **stats,
           "deleted": deleted, "errors": errors,
           "would_delete": [{"path": r["path"], "mb": round(r["size"] / MB, 2),
                             "age_days": round((time.time() - r["mtime"]) / 86400, 1),
                             "why": why[r["path"]]} for r in victims]}
    if o.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        mode = "PURGE" if o.apply else "SIMULATION"
        print(f"[{mode}] uploads : {stats['files_total']} fichiers · {stats['total_mb']} Mo "
              f"· {stats['sessions']} session(s) · {stats['protected']} protégé(s)")
        for v in out["would_delete"]:
            print(f"  - {v['mb']:>7.2f} Mo  {v['age_days']:>5.1f} j  {v['why']:<34} {v['path']}")
        print(f"  => {stats['files_deleted']} fichier(s), {stats['freed_mb']} Mo "
              f"{'libérés' if o.apply else 'libérables'}")
        for e in errors:
            print(f"  ⛔ {e['path']} : {e['error']}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
