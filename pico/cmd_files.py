"""pico sort, archive, find, fill templates, the quarantine lifecycle."""


import datetime, json, pathlib, re, shutil, zipfile


E = None  # engine, rebound by Engine._bind_modules()


def _S():
    return E.S


CATS = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".heic", ".bmp"},
    "Docs": {".pdf", ".doc", ".docx", ".txt", ".md", ".xls", ".xlsx", ".ppt",
             ".pptx", ".csv", ".odt", ".rtf"},
    "Audio": {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"},
    "Video": {".mp4", ".mkv", ".mov", ".avi", ".webm"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "Apps": {".exe", ".msi", ".apk", ".dmg", ".deb", ".AppImage"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".json", ".sh", ".c", ".cpp", ".rs", ".go"},
}


def _dl():
    return pathlib.Path.home() / "Downloads"


def tidy(m):
    d = pathlib.Path(m["path"] or _dl()).expanduser()
    if not d.exists():
        return "Path not found: " + str(d)
    moved = []
    for f in list(d.iterdir()):
        if not f.is_file():
            continue
        cat = next((k for k, v in CATS.items() if f.suffix.lower() in v), "Other")
        dest = d / cat
        dest.mkdir(exist_ok=True)
        target = dest / f.name
        if target.exists():
            target = dest / (f.stem + "_" + datetime.datetime.now().strftime("%H%M%S") + f.suffix)
        shutil.move(str(f), str(target))
        moved.append((str(f), str(target)))
    E.set_inverse("move_back", {"map": moved})
    return "Sorted %d file(s) under %s" % (len(moved), d)


def tidy_preview(m):
    d = pathlib.Path(m["path"] or _dl()).expanduser()
    if not d.exists():
        return []
    return [f.name for f in d.iterdir() if f.is_file()]


def backup(m):
    src = pathlib.Path(m["path"]).expanduser()
    if not src.exists():
        return "Path not found."
    out = E.home / "backups"
    out.mkdir(exist_ok=True)
    z = out / (src.name + "_" + datetime.date.today().isoformat() + ".zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as f:
        if src.is_file():
            f.write(src, src.name)
        else:
            for p in src.rglob("*"):
                if p.is_file() and out not in p.parents:
                    f.write(p, p.relative_to(src))
    E.set_inverse("file_rm", {"path": str(z)})
    return "Backup: %s (%d KB)" % (z, z.stat().st_size // 1024)


def find(m):
    q = m["q"].lower()
    hits = []
    for base in ("Downloads", "Documents", "Desktop"):
        d = pathlib.Path.home() / base
        if not d.exists():
            continue
        try:
            for p in d.rglob("*"):
                if q in p.name.lower():
                    hits.append(str(p))
                    if len(hits) >= 10:
                        return "\n".join(hits)
        except Exception:
            pass
    return "\n".join(hits) or "No matches."


def tpl_dirs():
    dirs = [E.templates]
    try:
        here = pathlib.Path(__file__).resolve().parent.parent / "templates"
        if here.is_dir() and here.resolve() != E.templates.resolve():
            dirs.append(here)
    except Exception:
        pass
    return dirs


def tpl_list(m):
    names = []
    for d in tpl_dirs():
        for p in sorted(d.glob("*.txt")):
            if p.stem not in names:
                names.append(p.stem)
    return "\n".join(names) or "No templates."


def fill(m):
    src = None
    for d in tpl_dirs():
        p = d / (m["tpl"] + ".txt")
        if p.exists():
            src = p
            break
    if src is None:
        return "No template named %s." % m["tpl"]
    text = src.read_text("utf-8")
    for k, v in re.findall(r"(\w+)=(.*?)(?=\s+\w+=|$)", m["args"]):
        text = text.replace("{{" + k + "}}", v.strip())
    out = E.home / ("%s_%s.txt" % (m["tpl"], datetime.date.today()))
    out.write_text(text, "utf-8")
    E.set_inverse("file_rm", {"path": str(out)})
    return "Written: %s" % out


def safe_delete(m):
    p = pathlib.Path(m["path"]).expanduser()
    if not p.exists():
        return "Path not found."
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
    p = pathlib.Path(m["path"]).expanduser()
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


# blast-radius previews: `dry` and the danger gate call these
tidy.preview = tidy_preview
safe_delete.preview = safe_delete_preview
restore.preview = restore_preview
