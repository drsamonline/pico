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
           "triggers - list", "untrigger N - remove"]

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
def run_actions(actions, ctx=None):
    """Run a saved sequence. Refuses anything that sends or deletes."""
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
        out.append(E.handle(cmd))
    return out


def notify(m):
    E.notify(m["msg"])
    return "Notified."


# ------------------------------------------------------------------ ticking
def _due(job, now):
    kind = job["kind"]
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
    elif kind == "file":
        now_seen = set()
        for pat in job["glob"]:
            for p in pathlib.Path.home().glob(pat):
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
        if job.get("_fresh"):
            ctx = {"file": job["_fresh"][0], "files": " ".join(job["_fresh"])}
            job.pop("_fresh", None)
        fired.append((i, job["actions"], run_actions(job["actions"], ctx)))
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
def _parse_spec(spec):
    spec = spec.strip()
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
    job = _parse_spec(m["spec"])
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


def show(m):
    if not T:
        return "No triggers. Try: when 22:30 then backup ~/Documents ; tidy"
    out = []
    for i, job in enumerate(T):
        kind = job["kind"]
        label = {"time": "at " + job.get("at", ""),
                 "every": "every %ds" % job.get("every", 0),
                 "file": "file " + ",".join(job.get("glob", [])),
                 "negate": "not %s by %s" % (job.get("cmd", ""), job.get("by", ""))}[kind]
        out.append("%d. %-32s -> %s" % (i + 1, label, " ; ".join(job["actions"])))
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


RULES = [
    (r"^when (?P<spec>.+?) then (?P<actions>.+)$", when),
    (r"^triggers$", show),
    (r"^untrigger (?P<n>\d+)$", drop),
    (r"^chain (?P<name>\w+)\s*:\s*(?P<body>.+)$", chain),
    (r"^chain (?P<name>\w+)$", chain),
    (r"^for each row in (?P<path>\S+) then (?P<cmd>.+)$", loop_csv),
    (r"^notify (?P<msg>.+)$", notify),
]
