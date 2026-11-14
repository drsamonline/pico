"""pico doctor — a self-check that names what is wrong instead of failing later."""
import datetime
import json
import pathlib
import sys

E = None  # engine, rebound by Engine._bind_modules()

OK, WARN, FAIL = "ok  ", "warn", "FAIL"


def _line(state, label, detail=""):
    return "%-4s  %-26s %s" % (state, label, detail)


def fix(m):
    """Repair what `doctor` can repair, and say what it did."""
    done = []
    home = E.home

    for name in ("templates", "rules", "snapshots", "quarantine", "backups"):
        d = home / name
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            done.append("created %s/" % name)

    # stray temp files from an interrupted write
    strays = list(home.glob("state.json.tmp*"))
    for f in strays:
        try:
            f.unlink()
        except Exception:
            pass
    if strays:
        done.append("removed %d stray temp file(s)" % len(strays))

    # an unreadable state file is moved aside, never deleted
    sf = E.state_file
    if sf.exists():
        try:
            json.loads(sf.read_text("utf-8"))
        except Exception:
            bad = sf.with_name(
                "state.json.corrupt-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
            try:
                sf.rename(bad)
                done.append("quarantined unreadable state.json -> %s" % bad.name)
            except Exception as ex:
                done.append("could not move state.json: %s" % ex)

    # snapshots beyond the rolling limit
    snaps = sorted((home / "snapshots").glob("*.json")) if (home / "snapshots").exists() else []
    extra = snaps[:-12]
    for f in extra:
        try:
            f.unlink()
        except Exception:
            pass
    if extra:
        done.append("pruned %d old snapshot(s)" % len(extra))

    # per-pack data files that will not parse
    for name in ("jobs.json", "habits.json", "cards.json", "life.json",
                 "triggers.json", "llm.json", "llm_cache.json"):
        f = home / name
        if not f.exists():
            continue
        try:
            json.loads(f.read_text("utf-8"))
        except Exception:
            bad = f.with_name(f.name + ".corrupt-" +
                              datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
            try:
                f.rename(bad)
                done.append("quarantined unreadable %s" % name)
            except Exception:
                pass

    # a quarantine index that points at files which are gone
    q = home / "quarantine"
    if q.exists():
        idx_f = q / "index.json"
        if idx_f.exists():
            try:
                idx = json.loads(idx_f.read_text("utf-8"))
            except Exception:
                idx = {}
            live = {p.name for p in q.iterdir() if p.is_file() and p.name != "index.json"}
            stale = [k for k in idx if k not in live]
            if stale:
                for k in stale:
                    idx.pop(k, None)
                idx_f.write_text(json.dumps(idx, indent=1), "utf-8")
                done.append("pruned %d stale quarantine index entr%s"
                            % (len(stale), "y" if len(stale) == 1 else "ies"))

    # the console token
    tok = home / "web.token"
    if not tok.exists() or not tok.read_text("utf-8").strip():
        import secrets
        tok.write_text(secrets.token_urlsafe(24), "utf-8")
        try:
            tok.chmod(0o600)
        except Exception:
            pass
        done.append("generated web.token")

    if not done:
        return "Nothing to fix. Run `doctor` for the full report."
    return "\n".join(["fixed:"] + ["  " + d for d in done] +
                     ["", "Run `doctor` again to confirm."])


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

    # ledger
    lf = E.ledger_file
    if lf.exists():
        n = len(lf.read_text("utf-8").splitlines())
        rows.append(_line(OK, "ledger", "%d line(s), %d B" % (n, lf.stat().st_size)))
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
        rows.append(_line(OK, "quarantine", "%d file(s), %d B" % (len(files), size)))
    else:
        rows.append(_line(OK, "quarantine", "empty"))

    # snapshots
    snaps = sorted((home / "snapshots").glob("*.json")) if (home / "snapshots").exists() else []
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

    # python
    rows.append(_line(OK if sys.version_info >= (3, 8) else FAIL, "python",
                      "%d.%d.%d" % sys.version_info[:3]))

    bad = [r for r in rows if r.startswith(FAIL)]
    warn = [r for r in rows if r.startswith(WARN)]
    head = "pico %s — doctor" % __import__("pico.base", fromlist=["x"]).__version__
    tail = "%d check(s): %d ok, %d warn, %d fail" % (
        len(rows), len(rows) - len(warn) - len(bad), len(warn), len(bad))
    return "\n".join([head, ""] + rows + ["", tail])
