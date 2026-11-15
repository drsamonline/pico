"""triggers — when / every / file / not-by, plus chains and CSV loops.

A trigger is a saved rule: one condition, one or more commands. Actions run through
the same risk gate as typed input, and a chain or loop refuses to carry a send or
danger action, because a saved rule should not be able to fire a message.
"""
import datetime
import fnmatch
import json
import os
import pathlib
import re
import threading
import time

CATALOG = ["when HH:MM then CMD - time trigger",
           "when every 30m then CMD - repeating trigger",
           "when file GLOB then CMD - new file trigger",
           "when not CMD by HH:MM then CMD - negative trigger",
           "chain NAME: a ; b - name a sequence",
           "for each row in PATH then CMD - CSV loop",
           "triggers - list", "untrigger N - remove",
           "when clip matches RE then CMD - clipboard trigger",
           "trigger log [N] - the last firings",
           "watch FOLDER then CMD - new files in a folder", "away on|off - pause away-gated triggers"]

P = T = E = REPLY = None
REFUSE = ("send", "danger")


def setup(api):
    global P, T, E, REPLY
    E = api["engine"]
    REPLY = api["reply"]
    P = api["HOME"] / "triggers.json"
    T = json.loads(P.read_text("utf-8")) if P.exists() else []
    if not os.environ.get("PICO_NO_THREADS"):
        threading.Thread(target=loop, daemon=True).start()


def save():
    P.write_text(json.dumps(T, indent=1), "utf-8")


# ------------------------------------------------------------------ running
def run_actions(actions, ctx=None, retry=True, job=None, now=None):
    """Run a saved sequence. Refuses anything that sends or deletes.

    With a `job`, a failing action backs off on its own: the other actions in the
    same rule keep running.
    """
    now = now or datetime.datetime.now()
    ab = job.setdefault("ab", {}) if job is not None else {}
    out = []
    for cmd in actions:
        cmd = cmd.strip()
        if not cmd:
            continue
        if ctx:
            for k, v in ctx.items():
                cmd = cmd.replace("{" + k + "}", str(v))
        if E.risk_of(cmd) in REFUSE:
            out.append("[skipped: %s is %s-tier, a saved rule may not run it]"
                       % (cmd, E.risk_of(cmd)))
            continue
        state = ab.get(cmd) or {}
        if state.get("until", 0) > now.timestamp():
            mins = int((state["until"] - now.timestamp()) / 60) + 1
            out.append("[skipped: backing off %dm after %d failure(s)]"
                       % (mins, state.get("fails", 0)))
            continue
        res = E.handle(cmd)
        if retry and isinstance(res, str) and res.startswith("Command failed"):
            time.sleep(0.2)
            res2 = E.handle(cmd)
            res = res2 if not res2.startswith("Command failed") else \
                res + " (retried once, still failing)"
        if job is not None:
            if isinstance(res, str) and res.startswith("Command failed"):
                n = state.get("fails", 0) + 1
                ab[cmd] = {"fails": n,
                           "until": (now + datetime.timedelta(
                               minutes=min(60, 2 ** n))).timestamp()}
            else:
                ab.pop(cmd, None)
        out.append(res)
    if job is not None and not ab:
        job.pop("ab", None)
    return out


def away(m):
    E.S["away"] = m["v"].lower() in ("on", "1", "true", "yes")
    E._dirty = True
    E.save()
    return "Away: " + ("on — triggers with `unless away` are paused" if E.S["away"] else "off")


def notify(m):
    E.notify(m["msg"])
    return "Notified."


# ------------------------------------------------------------------ ticking
def _cond_ok(cond):
    """True means the trigger may fire. A list of conditions is OR-ed: any true one vetoes."""
    if not cond:
        return True
    if isinstance(cond, list):
        return not any(_cond_true(c) for c in cond)
    return not _cond_true(cond)


def _cond_true(cond):
    kind, arg = cond["kind"], cond.get("arg")
    if kind == "away":
        return bool(E.S.get("away"))
    if kind == "weekend":
        return datetime.date.today().weekday() >= 5
    if kind == "weekday":
        return datetime.date.today().weekday() < 5
    if kind == "file":
        return bool(_glob(arg))
    if kind == "exists":
        return pathlib.Path(arg).expanduser().exists()
    return False


def _glob(pat):
    """Glob a pattern that may be absolute, ~-relative or home-relative.

    `Path.home().glob("/tmp/x/*.csv")` returns nothing: glob does not accept an
    absolute pattern. Absolute patterns must be globbed from their own anchor.
    """
    pat = os.path.expanduser(str(pat))
    p = pathlib.Path(pat)
    if p.is_absolute():
        return list(pathlib.Path(p.anchor).glob(str(p)[len(p.anchor):]))
    return list(pathlib.Path.home().glob(pat))


def _clip():
    """Best-effort clipboard read. Returns '' when no tool is available."""
    import subprocess
    for cmd in (["pbpaste"],
                ["wl-paste", "--no-newline"],
                ["xclip", "-selection", "clipboard", "-o"],
                ["xsel", "--clipboard", "--output"],
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard"]):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if r.returncode == 0:
                return r.stdout
        except Exception:
            continue
    return ""


def _due(job, now):
    kind = job["kind"]
    if not _cond_ok(job.get("unless")):
        return False
    day = now.strftime("%Y-%m-%d")
    if kind == "time":
        if job.get("at") == now.strftime("%H:%M") and job.get("last") != day:
            return True
    elif kind == "every":
        if now.timestamp() - job.get("last_ts", 0) >= job["every"]:
            return True
    elif kind == "negate":
        hm = now.strftime("%H:%M")
        if hm >= job["by"] and job.get("last") != day:
            ran = any(str(r.get("cmd", "")).startswith(job["cmd"])
                      for r in _ledger_today())
            return not ran
    elif kind == "clip":
        text = _clip()
        if not text:
            return False
        m = re.search(job["pattern"], text)
        if m and m.group(0) != job.get("last_clip"):
            job["last_clip"] = m.group(0)
            job["_clip"] = m.group(0)
            return True
        return False
    elif kind == "file":
        now_seen = set()
        for pat in job["glob"]:
            for p in _glob(pat):
                now_seen.add(str(p))
        fresh = now_seen - set(job.get("seen", []))
        job["seen"] = sorted(now_seen)[-500:]
        if fresh:
            job["_fresh"] = sorted(fresh)
            return True
    return False


def _ledger_today():
    f = E.ledger_file
    if not f.exists():
        return []
    day = datetime.date.today().isoformat()
    rows = []
    for line in f.read_text("utf-8").splitlines()[-500:]:
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("ts", "").startswith(day):
            rows.append(r)
    return rows


def tick(now=None):
    """Fire every trigger that is due. Returns [(index, actions, results)]."""
    now = now or datetime.datetime.now()
    fired = []
    changed = False
    for i, job in enumerate(T):
        try:
            if not _due(job, now):
                continue
        except Exception:
            continue
        changed = True
        if job["kind"] == "time" or job["kind"] == "negate":
            job["last"] = now.strftime("%Y-%m-%d")
        elif job["kind"] == "every":
            job["last_ts"] = now.timestamp()
        ctx = {}
        if job.get("_clip"):
            ctx = {"clip": job["_clip"], "file": job["_clip"]}
            job.pop("_clip", None)
        if job.get("_fresh"):
            ctx = {"file": job["_fresh"][0], "files": " ".join(job["_fresh"])}
            job.pop("_fresh", None)
        results = run_actions(job["actions"], ctx, job=job, now=now)
        fired.append((i, job["actions"], results))
        ok = not any(str(r).startswith("Command failed") for r in results)
        hist = job.setdefault("history", [])
        hist.append({"ts": now.strftime("%Y-%m-%dT%H:%M"),
                     "out": " | ".join(str(r)[:60] for r in results)[:200], "ok": ok})
        del hist[:-5]
        if ok:
            job.pop("last_error", None)
        else:
            job["last_error"] = hist[-1]["out"]
    if changed:
        save()
    return fired


def loop():
    last = None
    while True:
        now = datetime.datetime.now()
        hm = now.strftime("%H:%M")
        if hm != last:
            last = hm
            for i, actions, results in tick(now):
                E.notify("[trigger %d] %s\n%s" % (i + 1, "; ".join(actions),
                                                 "\n".join(results)))
        time.sleep(15)


# ------------------------------------------------------------------ parsing
def _parse_unless(text):
    if not text:
        return None
    parts = re.split(r"\s+or\s+", text, flags=re.I)
    if len(parts) > 1:
        out = [_parse_unless(p) for p in parts]
        if any(o == "bad" for o in out):
            return "bad"
        return out
    t = text.strip().lower()
    if t in ("away", "weekend", "weekday"):
        return {"kind": t}
    m = re.fullmatch(r"file\s+(.+)", t)
    if m:
        return {"kind": "file", "arg": m.group(1).strip()}
    m = re.fullmatch(r"exists\s+(.+)", t)
    if m:
        return {"kind": "exists", "arg": m.group(1).strip()}
    return "bad"


def _parse_spec(spec):
    spec = spec.strip()
    m = re.fullmatch(r"clip\s+matches\s+(.+)", spec, re.I)
    if m:
        return {"kind": "clip", "pattern": m.group(1).strip()}
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", spec)
    if m:
        return {"kind": "time", "at": "%02d:%02d" % (int(m.group(1)), int(m.group(2)))}
    m = re.fullmatch(r"every\s+(\d+)\s*([smh])", spec, re.I)
    if m:
        unit = {"s": 1, "m": 60, "h": 3600}[m.group(2).lower()]
        return {"kind": "every", "every": int(m.group(1)) * unit}
    m = re.fullmatch(r"file\s+(.+)", spec, re.I)
    if m:
        return {"kind": "file", "glob": [g.strip() for g in m.group(1).split(",")],
                "seen": []}
    m = re.fullmatch(r"not\s+(.+?)\s+by\s+(\d{1,2}):(\d{2})", spec, re.I)
    if m:
        return {"kind": "negate", "cmd": m.group(1).strip(),
                "by": "%02d:%02d" % (int(m.group(2)), int(m.group(3)))}
    return None


def when(m):
    spec = m["spec"].strip()
    unless = None
    parts = re.split(r"\s+unless\s+", spec, maxsplit=1, flags=re.I)
    if len(parts) == 2:
        spec, unless_text = parts[0], parts[1]
        unless = _parse_unless(unless_text)
        if unless == "bad":
            return ("Unrecognised unless. Try: away | weekend | weekday | "
                    "file ~/x.lock | exists ~/busy")
    job = _parse_spec(spec)
    if job is not None and unless:
        job["unless"] = unless
    if job is None:
        return ("Unrecognised condition. Try: 22:30 | every 30m | file ~/Downloads/*.csv | "
                "not did meds by 21:00")
    job["actions"] = [a.strip() for a in m["actions"].split(";") if a.strip()]
    for a in job["actions"]:
        if E.match_rule(a)[0] is None and not a.lower().startswith("notify "):
            return "Action does not match any rule: " + a
    T.append(job)
    save()
    return "Trigger %d saved: %s -> %s" % (len(T), m["spec"].strip(),
                                          " ; ".join(job["actions"]))


def _cond_label(cond):
    if isinstance(cond, list):
        return " or ".join(_cond_label(c) for c in cond)
    return cond.get("arg") or cond["kind"]


def show(m):
    if not T:
        return "No triggers. Try: when 22:30 then backup ~/Documents ; tidy"
    out = []
    for i, job in enumerate(T):
        kind = job["kind"]
        label = {"time": "at " + job.get("at", ""),
                 "every": "every %ds" % job.get("every", 0),
                 "file": "file " + ",".join(job.get("glob", [])),
                 "clip": "clip matches " + job.get("pattern", ""),
                 "negate": "not %s by %s" % (job.get("cmd", ""), job.get("by", ""))}[kind]
        u = job.get("unless")
        if u:
            label += " unless " + _cond_label(u)
        err = job.get("last_error")
        n = len(job.get("history") or [])
        ab = job.get("ab") or {}
        live = [k for k, v in ab.items() if v.get("until", 0) > time.time()]
        if live:
            label += "  [%d action(s) backing off]" % len(live)
        out.append("%d. %-32s -> %s%s%s" % (
            i + 1, label, " ; ".join(job["actions"]),
            ("\n   %d firing(s) recorded" % n) if n else "",
            ("\n   last error: " + err) if err else ""))
    return "\n".join(out)


def log(m):
    i = int(m["n"]) - 1 if m["n"] else 0
    if not T:
        return "No triggers."
    if m["n"] and not (0 <= i < len(T)):
        return "No such trigger."
    picks = [T[i]] if m["n"] else T
    out = []
    for job in picks:
        hist = job.get("history") or []
        head = " ; ".join(job["actions"])[:60]
        if not hist:
            out.append(head + "\n   never fired")
            continue
        out.append(head)
        for h in reversed(hist):
            out.append("   %s  %s  %s" % (h["ts"], "ok  " if h["ok"] else "FAIL",
                                          h["out"][:80]))
    return "\n".join(out)


def drop(m):
    i = int(m["n"]) - 1
    if 0 <= i < len(T):
        T.pop(i)
        save()
        return "Removed."
    return "No such trigger."


# ------------------------------------------------------------------ chains and loops
def chain(m):
    name = m["name"].strip().lower()
    body = m.groupdict().get("body")
    if body:
        steps = [s.strip() for s in body.split(";") if s.strip()]
        C = E.S.setdefault("chains", {})
        C[name] = steps
        E._dirty = True
        return "Chain %s: %s" % (name, " ; ".join(steps))
    C = E.S.get("chains", {})
    if name not in C:
        return "No chain named %s. Define one: chain %s: a ; b" % (name, name)
    results = run_actions(C[name])
    return "\n".join(results)


def loop_csv(m):
    p = pathlib.Path(m["path"]).expanduser()
    if not p.exists():
        return "File not found: " + str(p)
    import csv as _csv
    with p.open(newline="", encoding="utf-8", errors="replace") as f:
        rows = list(_csv.DictReader(f))
    if not rows:
        return "No data rows."
    if len(rows) > 200:
        return "Refusing %d rows. Split the file; a saved loop caps at 200." % len(rows)
    if E.risk_of(m["cmd"]) in REFUSE:
        return "Refused: a loop may not run %s-tier commands." % E.risk_of(m["cmd"])
    ok, failed = 0, []
    for i, row in enumerate(rows, 1):
        try:
            run_actions([m["cmd"]], {k: (v or "") for k, v in row.items()})
            ok += 1
        except Exception as ex:
            failed.append("row %d: %s" % (i, ex))
    msg = "%d of %d row(s) done: %s" % (ok, len(rows), m["cmd"])
    if failed:
        msg += "\nfailed: " + "; ".join(failed[:5])
    return msg


def watch(m):
    folder = m["folder"].strip().rstrip("/")
    job = {"kind": "file", "glob": [folder + "/*"], "seen": [], "actions": []}
    for a in m["actions"].split(";"):
        a = a.strip()
        if not a:
            continue
        if E.match_rule(a)[0] is None and not a.lower().startswith("notify "):
            return "Action does not match any rule: " + a
        job["actions"].append(a)
    T.append(job)
    save()
    return "Watching %s -> %s" % (folder, " ; ".join(job["actions"]))


RULES = [
    (r"^watch (?P<folder>\S+) then (?P<actions>.+)$", watch),
    (r"^when (?P<spec>.+?) then (?P<actions>.+)$", when),
    (r"^triggers$", show),
    (r"^untrigger (?P<n>\d+)$", drop),
    (r"^trigger log(?: (?P<n>\d+))?$", log),
    (r"^chain (?P<name>[^\s:]+)\s*:\s*(?P<body>.+)$", chain),
    (r"^chain (?P<name>[^\s:]+)$", chain),
    (r"^for each row in (?P<path>\S+) then (?P<cmd>.+)$", loop_csv),
    (r"^notify (?P<msg>.+)$", notify),
    (r"^away (?P<v>on|off)$", away),
]
