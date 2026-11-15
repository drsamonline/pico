"""pico files — sort, archive, find and fill. Deletion lives in cmd_quarantine."""
import datetime, json, pathlib, re, shutil, zipfile

from .base import unquote

E = None  # engine, rebound by Engine._bind_modules()

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


def _S():
    return E.S


def _dl():
    return pathlib.Path.home() / "Downloads"


def tidy(m):
    d = pathlib.Path(unquote(m["path"]) or _dl()).expanduser()
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
    d = pathlib.Path(unquote(m["path"]) or _dl()).expanduser()
    if not d.exists():
        return []
    return [f.name for f in d.iterdir() if f.is_file()]


def backup(m):
    src = pathlib.Path(unquote(m["path"])).expanduser()
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
    pairs = dict(re.findall(r"(\w+)=(.*?)(?=\s+\w+=|$)", m["args"]))
    # one pass: a value that contains {{something}} is data, not a template
    text = re.sub(r"\{\{(\w+)\}\}",
                  lambda mo: pairs.get(mo.group(1), mo.group(0)).strip(), text)
    out = E.home / ("%s_%s.txt" % (m["tpl"], datetime.date.today()))
    out.write_text(text, "utf-8")
    E.set_inverse("file_rm", {"path": str(out)})
    return "Written: %s" % out


tidy.preview = tidy_preview
