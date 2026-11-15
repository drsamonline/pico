"""pico doctor — a self-check that names what is wrong instead of failing later."""
import datetime
import json
import pathlib
import sys

E = None  # engine, rebound by Engine._bind_modules()

OK, WARN, FAIL = "ok  ", "warn", "FAIL"


def _line(state, label, detail=""):
    return "%-4s  %-26s %s" % (state, label, detail)


PROBES = {
    "finance": "gst 100 18",
    "habits": "habits",
    "learn": "cards",
    "life": "journal",
    "report": "report month",
    "schedule": "jobs",
    "text": "templates",
    "triggers": "triggers",
    "llm": "llm status",
    "files": "templates",
    "data": "tables",
}


def probe(m):
    """Run one read-only command per pack, through the handler, not through _run.

    Nothing is logged and nothing is saved: `_run` is what writes the ledger, and a
    diagnostic should not leave marks in the audit trail it is checking.
    """
    rows = []
    for mod in E.pack_modules:
        name = getattr(mod, "__name__", "?").replace("pico_pack_", "")
        cmd = PROBES.get(name)
        if not cmd:
            rows.append(_line(OK, name, "no probe (no rules)" if name == "telegram"
                              else "no probe defined"))
            continue
        fn, match = E.match_rule(cmd)
        if fn is None:
            rows.append(_line(FAIL, name, "probe %r matches no rule" % cmd))
            continue
        try:
            out = fn(match)
        except Exception as ex:
            rows.append(_line(FAIL, name, "%s: %s" % (type(ex).__name__, ex)))
            continue
        text = str(out)
        if text.startswith("Command failed") or not text:
            rows.append(_line(FAIL, name, text[:60] or "empty reply"))
        else:
            rows.append(_line(OK, name, "%r -> %r" % (cmd, text.replace("\n", " ")[:40])))

    bad = [r for r in rows if r.startswith(FAIL)]
    head = "pico %s — probe" % __import__("pico.base", fromlist=["x"]).__version__
    tail = "%d pack(s): %d ok, %d fail" % (len(rows), len(rows) - len(bad), len(bad))
    return "\n".join([head, ""] + rows + ["", tail])


# (label, command, fixtures that must exist for it) — each probe gets its own
# directory, so a destructive one cannot starve the next
WRITE_PROBES = [
    ("tidy", "tidy {dir}", {"a.png": "x", "b.pdf": "x", "c.mp3": "x"}),
    ("backup", "backup {dir}", {"a.png": "x", "b.pdf": "x"}),
    ("redact", "redact {dir}/notes.txt",
     {"notes.txt": "mail bob@example.com or 9876543210"}),
    ("dedupe files", "dedupe files {dir}", {"one.txt": "same", "two.txt": "same"}),
    ("dedupe", "dedupe {dir}/lines.txt", {"lines.txt": "a\na\nb\n"}),
    ("safe delete", "safe delete {dir}/throwaway.txt", {"throwaway.txt": "x"}),
    ("restore", "restore 1", {}),
    ("sweep", "quarantine sweep 1d", {}),
    ("fill", "fill probe to {dir} name=Asha body=hi", {}),
]


def probe_write(m):
    """Exercise the write paths inside a scratch directory, then clean up.

    `fill` writes to `{dir}` now that it takes an output directory, so it is covered
    here too — into a scratch directory, never the user's home.
    """
    import shutil as _sh
    import tempfile
    root = pathlib.Path(tempfile.mkdtemp(prefix="pico-probe-", dir=str(E.home)))
    made = []
    rows = []
    try:
        backups_before = {p.name for p in (E.home / "backups").glob("*.zip")} \
            if (E.home / "backups").exists() else set()

        for label, template, fixtures in WRITE_PROBES:
            case = root / label.replace(" ", "-")
            case.mkdir(parents=True, exist_ok=True)
            for name, body in fixtures.items():
                (case / name).write_text(body, "utf-8")
            cmd = template.format(dir=case)
            fn, match = E.match_rule(cmd)
            if fn is None:
                rows.append(_line(FAIL, label, "probe %r matches no rule" % cmd))
                continue
            try:
                out = str(fn(match))
            except Exception as ex:
                rows.append(_line(FAIL, label, "%s: %s" % (type(ex).__name__, ex)))
                continue
            if out.startswith("Command failed"):
                rows.append(_line(FAIL, label, out[:60]))
            else:
                rows.append(_line(OK, label, "%r -> %r" % (cmd, out.replace("\n", " ")[:44])))

        # outputs written beside the fixtures
        for pattern in ("*.redacted.txt", "*.deduped.txt"):
            made.extend(root.rglob(pattern))
        # the backup zip
        backups_after = {p.name for p in (E.home / "backups").glob("*.zip")} \
            if (E.home / "backups").exists() else set()
        for name in backups_after - backups_before:
            made.append(E.home / "backups" / name)
    finally:
        _sh.rmtree(root, ignore_errors=True)
        for f in made:
            try:
                f.unlink()
            except Exception:
                pass
        # anything the quarantine gained during the probe
        q = E.home / "quarantine"
        if q.exists():
            idx_f = q / "index.json"
            idx = {}
            if idx_f.exists():
                try:
                    idx = json.loads(idx_f.read_text("utf-8"))
                except Exception:
                    idx = {}
            live = {p.name for p in q.iterdir() if p.is_file() and p.name != "index.json"}
            for name in list(idx):
                if name not in live:
                    idx.pop(name, None)
            if idx_f.exists():
                idx_f.write_text(json.dumps(idx, indent=1), "utf-8")

    bad = [r for r in rows if r.startswith(FAIL)]
    head = "pico %s — probe write" % __import__("pico.base", fromlist=["x"]).__version__
    tail = "%d write path(s): %d ok, %d fail. Scratch removed." % (
        len(rows), len(rows) - len(bad), len(bad))
    return "\n".join([head, ""] + rows + ["", tail])


def doctor(m):
    rows = []
    home = E.home
    rows.append(_line(OK, "home", str(home)))

    # state file
    sf = E.state_file
    if not sf.exists():
        # nothing has been changed yet: correct, not broken
        rows.append(_line(OK, "state.json", "not written yet"))
    else:
        try:
            json.loads(sf.read_text("utf-8"))
            rows.append(_line(OK, "state.json", "%d B, parses" % sf.stat().st_size))
        except Exception as ex:
            rows.append(_line(FAIL, "state.json", "unreadable: %s" % ex))
    corrupt = list(home.glob("state.json.corrupt-*"))
    if corrupt:
        rows.append(_line(WARN, "quarantined state",
                          "%d old file(s) kept" % len(corrupt)))

    # secrets: presence only, never the value
    for label, name in (("telegram token", "telegram.token"), ("llm key", "llm.key")):
        f = home / name
        if f.exists():
            try:
                n = len(f.read_text("utf-8").strip())
                mode = oct(f.stat().st_mode & 0o777)
            except Exception:
                n, mode = 0, "?"
            rows.append(_line(OK if mode == "0o600" else WARN, label,
                              "set (%d chars), %s" % (n, "owner-only" if mode == "0o600"
                                                      else "mode %s — run: chmod 600 %s"
                                                      % (mode, f))))

    # scheduled jobs that threw
    errs = E.S.get("job_errors") or []
    if errs:
        last = errs[-1]
        rows.append(_line(WARN, "job errors",
                          "%d recorded, newest %s: %s" % (len(errs), last.get("at", ""),
                                                          last.get("error", "")[:48])))

    # reconstructions left by `replay`
    reps = E.replay_dirs() if hasattr(E, "replay_dirs") else []
    if reps:
        size = sum(f.stat().st_size for d in reps for f in d.rglob("*") if f.is_file())
        rows.append(_line(OK, "replays", "%d kept, %d B (newest %s)"
                          % (len(reps), size, reps[-1].name)))

    # ledger, including the rotated generations
    lf = E.ledger_file
    gens = sorted(lf.parent.glob("%s-*.jsonl" % lf.stem))
    if lf.exists() or gens:
        n = len(list(E.ledger_lines()))
        size = (lf.stat().st_size if lf.exists() else 0) + sum(g.stat().st_size for g in gens)
        rows.append(_line(OK, "ledger", "%d line(s) over %d file(s), %d B"
                          % (n, len(gens) + (1 if lf.exists() else 0), size)))
    else:
        rows.append(_line(OK, "ledger", "nothing run yet"))

    # rules and packs
    rows.append(_line(OK if E.rules else FAIL, "rules", "%d loaded" % len(E.rules)))
    packs = [getattr(p, "__name__", "?").replace("pico_pack_", "")
             for p in E.pack_modules]
    rows.append(_line(OK if packs else WARN, "packs", ", ".join(sorted(packs)) or "none"))

    # templates
    import pico.cmd_files as F
    names = F.tpl_list(m).splitlines() if F.tpl_list(m) not in ("", "No templates.") else []
    rows.append(_line(OK if names else WARN, "templates", ", ".join(names) or "none"))

    # quarantine
    q = home / "quarantine"
    if q.exists():
        files = [p for p in q.iterdir() if p.is_file() and p.name != "index.json"]
        size = sum(p.stat().st_size for p in files)
        level = WARN if size > 50 * 1024 * 1024 or len(files) > 100 else OK
        rows.append(_line(level, "quarantine",
                          "%d file(s), %d B — `quarantine sweep 30d` drops the old ones"
                          % (len(files), size)))
    else:
        rows.append(_line(OK, "quarantine", "empty"))

    # snapshots
    snaps = sorted(q for q in (home / "snapshots").glob("*.json")
                   if q.name != "index.json") if (home / "snapshots").exists() else []
    rows.append(_line(OK, "snapshots",
                      "%d kept, newest %s" % (len(snaps), snaps[-1].stem if snaps else "-")))

    # triggers
    tj = home / "triggers.json"
    if tj.exists():
        try:
            jobs = json.loads(tj.read_text("utf-8"))
            backing = sum(1 for j in jobs if j.get("ab"))
            rows.append(_line(OK, "triggers",
                              "%d saved%s" % (len(jobs),
                                              ", %d backing off" % backing if backing else "")))
        except Exception as ex:
            rows.append(_line(FAIL, "triggers.json", "unreadable: %s" % ex))
    else:
        rows.append(_line(OK, "triggers", "none saved"))

    # jobs, habits, cards
    for name, key in (("jobs.json", "jobs"), ("habits.json", "habits"),
                      ("cards.json", "cards"), ("life.json", "life")):
        f = home / name
        if not f.exists():
            rows.append(_line(OK, name, "not created yet"))
            continue
        try:
            d = json.loads(f.read_text("utf-8"))
            if isinstance(d, list):
                n = len(d)
            elif isinstance(d, dict) and "cards" in d:
                n = len(d.get("cards") or [])
            elif isinstance(d, dict) and "journal" in d:
                n = len(d.get("journal") or [])
            else:
                n = len(d)
            rows.append(_line(OK, name, "%d entr%s" % (n, "y" if n == 1 else "ies")))
        except Exception as ex:
            rows.append(_line(FAIL, name, "unreadable: %s" % ex))

    # sqlite
    db = home / "pico.db"
    if db.exists():
        try:
            import sqlite3
            with sqlite3.connect(str(db)) as c:
                n = c.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            rows.append(_line(OK, "pico.db", "%d table(s)" % n))
        except Exception as ex:
            rows.append(_line(FAIL, "pico.db", str(ex)))
    else:
        rows.append(_line(OK, "pico.db", "no CSV imported yet"))

    # security surface
    tok = home / "web.token"
    rows.append(_line(OK if not tok.exists() else OK, "web.token",
                      "set" if tok.exists() else "not generated yet"))
    tg = home / "telegram.token"
    rows.append(_line(OK, "telegram", "configured" if tg.exists() else "not configured"))
    rows.append(_line(OK, "two-key",
                      "phone only" if E.S.get("two_key_phone")
                      else ("on" if E.S.get("two_key") else "off")))

    # background threads, via the heartbeat each one writes
    import time as _t
    beats, idle = [], []
    for mod in E.pack_modules:
        beat = getattr(mod, "LAST", None)
        if beat is None:
            continue
        name = getattr(mod, "__name__", "?").replace("pico_pack_", "")
        if not beat:
            idle.append(name)          # the pack never started its thread
            continue
        beats.append((name, int(_t.time() - beat)))
    if beats:
        worst = max(beats, key=lambda x: x[1])
        state = OK if worst[1] < 120 else WARN
        detail = ", ".join("%s %ds" % (n, a) for n, a in sorted(beats))
        if idle:
            detail += " | idle: " + ", ".join(sorted(idle))
        if worst[1] >= 120:
            detail += " — a thread may have stopped; --serve keeps them alive"
        rows.append(_line(state, "threads", detail))
    else:
        rows.append(_line(OK, "threads",
                          "none running" + (" (idle: %s)" % ", ".join(sorted(idle))
                                            if idle else "")))

    # python
    rows.append(_line(OK if sys.version_info >= (3, 8) else FAIL, "python",
                      "%d.%d.%d" % sys.version_info[:3]))

    bad = [r for r in rows if r.startswith(FAIL)]
    warn = [r for r in rows if r.startswith(WARN)]
    head = "pico %s — doctor" % __import__("pico.base", fromlist=["x"]).__version__
    tail = "%d check(s): %d ok, %d warn, %d fail" % (
        len(rows), len(rows) - len(warn) - len(bad), len(warn), len(bad))
    return "\n".join([head, ""] + rows + ["", tail])
