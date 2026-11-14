"""pico core rules — the P0 daily spine. Registered by Engine.register_core()."""
import datetime, pathlib, platform, re, shutil, subprocess, threading, zipfile, webbrowser

E = None  # engine, set in register()

CATALOG = []

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


# ------------------------------------------------------------------ tasks
def tasks_list(m):
    if not _S()["tasks"]:
        return "Nothing pending."
    return "\n".join("[%s] %d. %s" % ("x" if t["done"] else " ", i + 1, t["text"])
                     for i, t in enumerate(_S()["tasks"]))


def task_add(m):
    i = len(_S()["tasks"])
    _S()["tasks"].append({"text": m["text"].strip(), "done": False})
    E.set_inverse("list_rm", {"key": "tasks", "i": i})
    return "Added."


def task_done(m):
    i = int(m["n"]) - 1
    if 0 <= i < len(_S()["tasks"]):
        _S()["tasks"][i]["done"] = True
        E.set_inverse("task_undone", {"i": i})
        return "Done."
    return "No such task."


def task_undone(m):
    i = int(m["n"]) - 1
    if 0 <= i < len(_S()["tasks"]):
        _S()["tasks"][i]["done"] = False
        E.set_inverse("task_done", {"i": i})
        return "Reopened."
    return "No such task."


def task_del(m):
    i = int(m["n"]) - 1
    ts = _S()["tasks"]
    if 0 <= i < len(ts):
        item = ts.pop(i)
        E.set_inverse("list_ins", {"key": "tasks", "i": i, "item": item})
        return "Deleted: " + item["text"]
    return "No such task."


def note_set(m):
    k, v = m["key"], m["val"].strip()
    had = k in _S()["notes"]
    old = _S()["notes"].get(k)
    _S()["notes"][k] = v
    E.set_inverse("note_set" if had else "note_del", {"k": k, "v": old})
    return "Remembered %s." % k


def note_get(m):
    return _S()["notes"].get(m["key"], "I don't have that.")


def note_del(m):
    k = m["key"]
    if k in _S()["notes"]:
        old = _S()["notes"].pop(k)
        E.set_inverse("note_set", {"k": k, "v": old})
        return "Forgot " + k + "."
    return "I don't have that."


# ------------------------------------------------------------------ shopping
def buy(m):
    i = len(_S()["shop"])
    _S()["shop"].append(m["item"].strip())
    E.set_inverse("list_rm", {"key": "shop", "i": i})
    return "On the list."


def shop_list(m):
    return ("\n".join("%d. %s" % (i + 1, x) for i, x in enumerate(_S()["shop"]))
            or "List empty.")


def bought(m):
    i = int(m["n"]) - 1
    sh = _S()["shop"]
    if 0 <= i < len(sh):
        item = sh.pop(i)
        E.set_inverse("list_ins", {"key": "shop", "i": i, "item": item})
        return "Removed: " + item
    return "No such item."


# ------------------------------------------------------------------ events
def event_add(m):
    i = len(_S()["events"])
    _S()["events"].append({"date": m["date"], "text": m["text"].strip()})
    E.set_inverse("list_rm", {"key": "events", "i": i})
    return "Saved."


def brief(m):
    today = datetime.date.today()
    md = today.strftime("%m-%d")
    pend = [t["text"] for t in _S()["tasks"] if not t["done"]]
    ev = [e["text"] for e in _S()["events"]
          if e["date"] in (today.isoformat(), md)]
    spent = sum(r["amt"] for r in _S()["spend"]
                if str(r["d"]).startswith(today.strftime("%Y-%m")))
    return (today.strftime("%A, %d %B %Y")
            + "\nTasks: " + ("; ".join(pend) or "none")
            + "\nToday: " + ("; ".join(ev) or "nothing scheduled")
            + ("\nSpent this month: %.0f" % spent if spent else ""))


# ------------------------------------------------------------------ money
def spend_add(m):
    i = len(_S()["spend"])
    _S()["spend"].append({"d": datetime.date.today().isoformat(),
                          "amt": float(m["amt"]), "cat": (m["cat"] or "misc").lower()})
    E.set_inverse("list_rm", {"key": "spend", "i": i})
    return "Logged."


def spend_sum(m):
    mon = datetime.date.today().strftime("%Y-%m")
    tot = {}
    for r in _S()["spend"]:
        if str(r["d"]).startswith(mon):
            tot[r["cat"]] = tot.get(r["cat"], 0) + r["amt"]
    if not tot:
        return "No expenses this month."
    return ("\n".join("%s: %s" % (k, fmt(v)) for k, v in sorted(tot.items()))
            + "\nTotal: " + fmt(sum(tot.values())))


def fmt(v):
    return "{:,.0f}".format(v)


# ------------------------------------------------------------------ time
def _later(secs, msg):
    t = threading.Timer(secs, lambda: E.notify(msg))
    t.daemon = True
    t.start()


def timer(m):
    unit = m["u"][0].lower()
    secs = int(m["n"]) * {"s": 1, "m": 60, "h": 3600}[unit]
    msg = (m["msg"] or "Timer done").strip()
    _later(secs, msg)
    return "Timer: %s%s - %s" % (m["n"], m["u"], msg)


def remind(m):
    now = datetime.datetime.now()
    t = now.replace(hour=int(m["h"]), minute=int(m["mi"]), second=0, microsecond=0)
    if t <= now:
        t += datetime.timedelta(days=1)
    msg = (m["msg"] or "Reminder").strip()
    _later((t - now).total_seconds(), msg)
    return "Reminder at %s - %s" % (t.strftime("%H:%M"), msg)


def clock(m):
    return datetime.datetime.now().strftime("%a %d %b %Y, %I:%M %p")


def calc(m):
    from .engine import safe_eval
    try:
        v = safe_eval(m["e"])
    except Exception:
        return "Arithmetic only: numbers and + - * / // % ** ."
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v)


def convert_(m):
    from .engine import convert
    try:
        out = convert(float(m["v"]), m["a"], m["b"])
    except Exception:
        return "Unknown or incompatible units."
    return "%s %s = %s %s" % (m["v"], m["a"], "{:,.6g}".format(out), m["b"])


# ------------------------------------------------------------------ files
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


tidy.preview = tidy_preview


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


# ------------------------------------------------------------------ web
def site_set(m):
    k = m["name"]
    had = k in _S()["sites"]
    old = _S()["sites"].get(k)
    _S()["sites"][k] = m["url"]
    E.set_inverse("dict_set" if had else "dict_del", {"key": "sites", "k": k, "v": old})
    return "Shortcut saved."


def open_any(m):
    t = m["t"].strip()
    if t in _S()["sites"]:
        webbrowser.open(_S()["sites"][t])
        return "Opened " + t
    p = pathlib.Path(t).expanduser()
    if p.exists():
        if platform.system() == "Windows":
            os_startfile(p)
        else:
            subprocess.Popen(["xdg-open" if platform.system() == "Linux" else "open", str(p)])
        return "Opened path."
    if re.match(r"^[\w.-]+\.[a-z]{2,}(/.*)?$", t, re.I):
        webbrowser.open("https://" + t)
        return "Opened site."
    return "Unknown target. Save one: site name=https://..."


def os_startfile(p):
    import os
    os.startfile(str(p))


def search(m):
    webbrowser.open("https://duckduckgo.com/?q=" + m["q"].replace(" ", "+"))
    return "Opened search."


def weather(m):
    import urllib.request
    try:
        url = "https://wttr.in/" + (m["city"] or "").strip().replace(" ", "+") + "?format=3"
        with urllib.request.urlopen(url, timeout=6) as r:
            return r.read().decode().strip()
    except Exception:
        return "Weather unavailable (offline?)."


# ------------------------------------------------------------------ meta
def aliases(m):
    a = E.aliases
    return "\n".join("%s -> %s" % (k, v) for k, v in a.items()) or "None learned yet."


def unalias(m):
    k = normalize_key(m["p"])
    if E.aliases.pop(k, None) is not None:
        E.set_inverse("alias_del", {"k": k})
        return "Alias removed."
    return "No such alias."


def normalize_key(t):
    from .engine import normalize
    return normalize(t)


HELP = """CORE
  tasks | add X | done N | undone N | del N | brief
  remember k=v | recall k | forget k
  buy X | shop | bought N | on MM-DD text
  spend AMT [CAT] | expenses | calc EXPR | convert V U to U
  time | timer 10m MSG | remind 18:30 MSG
  tidy [PATH] | backup PATH | find NAME | templates | fill TPL k=v
  site k=URL | open X | search X | weather [CITY]
SAFETY
  dry CMD | why | log | undo [N] | confirm | cancel | aliases | unalias P
PACKS
  emi/sip/fd/si/gst/split/disc | habit add/did/habits | journal [show N]
  contact/wa/mail | daily HH:MM CMD | jobs | unjob N | llm off/local/cloud/auto"""


def help_(m):
    return HELP


def register(engine):
    global E
    E = engine
    R = [
        (r"^(hi|hello|hey|salam)$", lambda m: "Ready. Type 'help'."),
        (r"^(help|\?|start)$", help_),
        (r"^(tasks|todo|list)$", tasks_list),
        (r"^(add|task)\s+(?P<text>.+)$", task_add),
        (r"^done\s+(?P<n>\d+)$", task_done),
        (r"^undone\s+(?P<n>\d+)$", task_undone),
        (r"^del\s+(?P<n>\d+)$", task_del),
        (r"^remember\s+(?P<key>\w+)\s*[:=]\s*(?P<val>.+)$", note_set),
        (r"^(recall|what is)\s+(?P<key>\w+)$", note_get),
        (r"^forget\s+(?P<key>\w+)$", note_del),
        (r"^buy\s+(?P<item>.+)$", buy),
        (r"^shop$", shop_list),
        (r"^bought\s+(?P<n>\d+)$", bought),
        (r"^on\s+(?P<date>\d{4}-\d{2}-\d{2}|\d{2}-\d{2})\s+(?P<text>.+)$", event_add),
        (r"^(brief|today|agenda)$", brief),
        (r"^spend\s+(?P<amt>\d+(?:\.\d+)?)\s*(?P<cat>\w+)?$", spend_add),
        (r"^(spend|expenses)$", spend_sum),
        (r"^calc\s+(?P<e>.+)$", calc),
        (r"^convert\s+(?P<v>-?\d+(?:\.\d+)?)\s*(?P<a>[a-zA-Z]+)\s+(?:to|in)\s+(?P<b>[a-zA-Z]+)$", convert_),
        (r"^timer\s+(?P<n>\d+)\s*(?P<u>sec|min|hr|[smh])\b\s*(?P<msg>.*)$", timer),
        (r"^remind\s+(?P<h>\d{1,2}):(?P<mi>\d{2})\s*(?P<msg>.*)$", remind),
        (r"^(time|date|now)$", clock),
        (r"^tidy(?:\s+(?P<path>.+))?$", tidy),
        (r"^backup\s+(?P<path>.+)$", backup),
        (r"^find\s+(?P<q>.+)$", find),
        (r"^templates$", tpl_list),
        (r"^fill\s+(?P<tpl>\w+)\s+(?P<args>.+)$", fill),
        (r"^site\s+(?P<name>\w+)\s*=\s*(?P<url>\S+)$", site_set),
        (r"^open\s+(?P<t>.+)$", open_any),
        (r"^search\s+(?P<q>.+)$", search),
        (r"^weather(?:\s+(?P<city>.+))?$", weather),
        (r"^aliases$", aliases),
        (r"^unalias\s+(?P<p>.+)$", unalias),
    ]
    engine.add_rules(R)
    CATALOG.extend([
        "tasks - list tasks", "add X - new task", "done N - finish task",
        "undone N - reopen task", "del N - delete task", "brief - daily briefing",
        "remember k=v - store a note", "recall k - read a note",
        "buy X - shopping list", "shop - show list", "bought N - remove item",
        "on MM-DD text - add event", "spend AMT CAT - log expense",
        "expenses - month totals", "calc EXPR - arithmetic",
        "convert V U to U - unit conversion", "time - clock",
        "timer Nm MSG - countdown", "remind HH:MM MSG - reminder",
        "tidy [PATH] - sort files by type", "backup PATH - zip a folder",
        "find NAME - locate files", "templates - list templates",
        "fill TPL k=v - fill a template", "site k=url - save a shortcut",
        "open X - open site/app/path", "search X - web search",
        "weather [city] - forecast", "help - command list",
        "dry CMD - preview without running", "why - last resolution",
        "log - recent ledger", "undo N - reverse actions",
        "aliases - learned phrasings", "unalias P - forget a phrasing",
    ])
