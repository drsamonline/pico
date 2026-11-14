"""files — find the fat, the stale and the duplicated. Read-only unless you say apply."""
import datetime
import hashlib
import pathlib
import shutil

CATALOG = ["dedupe files PATH - report identical files",
           "dedupe files PATH apply - quarantine duplicates",
           "big files [N] - largest files", "old files ND - untouched for N days"]
E = None


def setup(api):
    global E
    E = api["engine"]


def _roots():
    for name in ("Downloads", "Documents", "Desktop", "Pictures"):
        d = pathlib.Path.home() / name
        if d.exists():
            yield d


def _walk(limit=60000):
    seen = 0
    for root in _roots():
        for p in root.rglob("*"):
            if p.is_file():
                yield p
                seen += 1
                if seen >= limit:
                    return


def _sha(p, chunk=1 << 16):
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def big(m):
    n = int(m["n"]) if m["n"] else 15
    rows = []
    for p in _walk():
        try:
            rows.append((p.stat().st_size, str(p)))
        except Exception:
            pass
    rows.sort(reverse=True)
    if not rows:
        return "No files found."
    out = ["%8s  %s" % (_h(s), p) for s, p in rows[:n]]
    total = sum(s for s, _ in rows)
    out.append("%8s  in %d files" % (_h(total), len(rows)))
    return "\n".join(out)


def old(m):
    days = int(m["n"])
    cutoff = datetime.datetime.now().timestamp() - days * 86400
    rows = []
    for p in _walk():
        try:
            st = p.stat()
        except Exception:
            continue
        if st.st_mtime < cutoff:
            rows.append((st.st_mtime, st.st_size, str(p)))
    rows.sort()
    if not rows:
        return "Nothing untouched for %d days." % days
    out = ["%s  %8s  %s" % (datetime.date.fromtimestamp(t).isoformat(), _h(s), p)
           for t, s, p in rows[:25]]
    out.append("%d file(s) untouched for %d+ days" % (len(rows), days))
    return "\n".join(out)


def dedupe(m):
    apply_ = bool(m["apply"])
    by_size = {}
    for p in _walk():
        try:
            sz = p.stat().st_size
        except Exception:
            continue
        if sz == 0:
            continue
        by_size.setdefault(sz, []).append(p)
    groups = []
    for sz, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash = {}
        for p in paths:
            try:
                by_hash.setdefault(_sha(p), []).append(p)
            except Exception:
                pass
        for h, same in by_hash.items():
            if len(same) > 1:
                groups.append(sorted(same))
    if not groups:
        return "No duplicates found."
    wasted = 0
    lines = []
    moves = []
    q = E.home / "quarantine"
    for g in groups:
        keep = g[0]
        lines.append("keep   %s" % keep)
        for dup in g[1:]:
            try:
                wasted += dup.stat().st_size
            except Exception:
                pass
            lines.append("  dup  %s" % dup)
            moves.append((keep, dup))
    head = "%d group(s), %s reclaimable" % (len(groups), _h(wasted))
    if not apply_:
        return head + "\n" + "\n".join(lines[:60]) + \
            "\n\nNothing moved. Run: dedupe files PATH apply"
    q.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    mapping = []
    for keep, dup in moves:
        dest = q / (stamp + "_" + dup.name)
        n = 1
        while dest.exists():
            dest = q / (stamp + "_%d_%s" % (n, dup.name))
            n += 1
        shutil.move(str(dup), str(dest))
        mapping.append([str(dup), str(dest)])
    E.set_inverse("move_back", {"map": mapping})
    return head + "\nMoved %d duplicate(s) to %s\nundo restores them." % (len(mapping), q)


def _h(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return ("%d%s" % (n, unit)) if unit == "B" else ("%.1f%s" % (n, unit))
        n /= 1024.0


RULES = [
    (r"^dedupe files\s+(?P<path>\S+)(?:\s+(?P<apply>apply))?$", dedupe),
    (r"^big files(?:\s+(?P<n>\d+))?$", big),
    (r"^old files\s+(?P<n>\d+)d$", old),
]
