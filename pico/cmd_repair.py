"""pico repair — what `doctor fix` actually does.

Everything here moves or regenerates a file. Nothing is deleted: unreadable JSON is
renamed with a `.corrupt-<ts>` suffix so it can be inspected afterwards.
"""
import datetime
import json
import pathlib
import secrets

E = None  # engine, rebound by Engine._bind_modules()

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
