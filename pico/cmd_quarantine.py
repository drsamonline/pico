"""pico quarantine — the delete-safety lifecycle.

Nothing is destroyed by `safe delete`: the file moves here, an index remembers
where it came from, and `restore` puts it back. `sweep` is the only irreversible
command in the pack.
"""
import datetime, json, pathlib, shutil

from .base import unquote

E = None  # engine, rebound by Engine._bind_modules()

def safe_delete(m):
    p = pathlib.Path(unquote(m["path"])).expanduser()
    if not p.exists():
        return "Path not found."
    # moving a directory into a subdirectory of itself is an error shutil raises late,
    # after the user has already confirmed. Refuse before asking.
    try:
        home = E.home.resolve()
        target = p.resolve()
        if target == home or home.is_relative_to(target):
            return ("That is pico's own home, or contains it. Quarantining it would move "
                    "the quarantine into itself. Delete it with your file manager.")
    except Exception:
        pass
    q = E.home / "quarantine"
    q.mkdir(exist_ok=True)
    dest = q / (datetime.datetime.now().strftime("%Y%m%d%H%M%S") + "_" + p.name)
    shutil.move(str(p), str(dest))
    idx = _q_index()
    idx[dest.name] = str(p.resolve())
    _q_save(idx)
    E.set_inverse("move_back", {"map": [[str(p), str(dest)]]})
    return "Quarantined: %s\nundo restores it; nothing was destroyed." % dest


def safe_delete_preview(m):
    p = pathlib.Path(unquote(m["path"])).expanduser()
    # an empty preview runs the handler straight through, which is how the refusal
    # below reaches the user instead of a confirmation prompt for an impossible move
    try:
        home = E.home.resolve()
        target = p.resolve()
        if target == home or home.is_relative_to(target):
            return []
    except Exception:
        pass
    if p.is_file():
        return [str(p)]
    if p.is_dir():
        return [str(x) for x in list(p.rglob("*"))[:200]]
    return []


def _q_index():
    f = E.home / "quarantine" / "index.json"
    if not f.exists():
        return {}
    try:
        d = json.loads(f.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _q_save(idx):
    q = E.home / "quarantine"
    q.mkdir(exist_ok=True)
    (q / "index.json").write_text(json.dumps(idx, indent=1), "utf-8")


def _q_list():
    q = E.home / "quarantine"
    if not q.exists():
        return []
    return sorted(p for p in q.iterdir() if p.is_file() and p.name != "index.json")


def quarantine(m):
    files = _q_list()
    if not files:
        return "Quarantine empty."
    total = sum(f.stat().st_size for f in files)
    lines = ["%d. %s  (%s)" % (i + 1, f.name, _h(f.stat().st_size))
             for i, f in enumerate(files)]
    lines.append("%d file(s), %s. Restore with: restore N" % (len(files), _h(total)))
    return "\n".join(lines)


def restore(m):
    files = _q_list()
    i = int(m["n"]) - 1
    if not (0 <= i < len(files)):
        return "No such item. Run: quarantine"
    src = files[i]
    idx = _q_index()
    dest = idx.get(src.name) or str(pathlib.Path.home() / src.name.split("_", 1)[-1])
    target = pathlib.Path(dest)
    if target.exists():
        return "Already exists: %s. Move it first." % target
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(target))
    idx.pop(src.name, None)
    _q_save(idx)
    E.set_inverse("move_back", {"map": [[str(src), str(target)]]})
    return "Restored to %s" % target


def restore_preview(m):
    files = _q_list()
    i = int(m["n"]) - 1
    return [str(files[i])] if 0 <= i < len(files) else []


def sweep(m):
    days = int(m["n"])
    cut = datetime.datetime.now().timestamp() - days * 86400
    files = [f for f in _q_list() if f.stat().st_mtime < cut]
    if not files:
        return "Nothing older than %d days in quarantine." % days
    freed = sum(f.stat().st_size for f in files)
    idx = _q_index()
    for f in files:
        try:
            f.unlink()
            idx.pop(f.name, None)
        except Exception:
            pass
    _q_save(idx)
    return "Removed %d file(s), %s freed. This is not undoable." % (len(files), _h(freed))


def _h(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%dB" % n) if unit == "B" else ("%.1f%s" % (n, unit))
        n /= 1024.0


safe_delete.preview = safe_delete_preview


restore.preview = restore_preview
