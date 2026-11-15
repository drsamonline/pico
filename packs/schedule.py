"""schedule — persistent daily jobs. They fire while pico runs (--serve or REPL)."""
import datetime
import json
import os
import threading
import time

CATALOG = ["daily HH:MM CMD - repeat a command", "jobs - list jobs", "unjob N - remove job"]
P = J = REPLY = NOTIFY = E = None
LAST = 0.0   # heartbeat, read by `doctor`


def setup(api):
    global P, J, REPLY, NOTIFY, E
    E = api["engine"]
    P = api["HOME"] / "jobs.json"
    J = json.loads(P.read_text("utf-8")) if P.exists() else []
    REPLY, NOTIFY = api["reply"], api["notify"]
    api["inverse_handler"]("job_rm", lambda a: (J.pop(a["i"]), save()))
    api["inverse_handler"]("job_add", lambda a: (J.insert(min(a["i"], len(J)), a["item"]), save()))
    global LAST
    LAST = time.time()
    if not os.environ.get("PICO_NO_THREADS"):
        threading.Thread(target=loop, daemon=True).start()


def save():
    P.write_text(json.dumps(J, indent=2), "utf-8")


FAILURE_CAP = 20
FAILURE_LIMIT = 3          # consecutive failures before a job switches itself off


def record_failure(job, ex, at=""):
    errs = E.S.setdefault("job_errors", [])
    errs.append({"at": at or datetime.datetime.now().strftime("%Y-%m-%dT%H:%M"),
                 "cmd": job.get("cmd", ""), "error": "%s: %s" % (type(ex).__name__, ex)})
    del errs[:-FAILURE_CAP]

    # three failures in a row and the job stops trying: a reminder that errors every
    # day is noise, and silence about it is worse
    job["fails"] = int(job.get("fails", 0)) + 1
    off = job["fails"] >= FAILURE_LIMIT
    if off:
        job["off"] = True
    save()
    try:
        if off:
            NOTIFY("[job switched off] %s\nIt failed %d times: %s: %s\n"
                   "Fix it, then re-add it with: daily %s CMD"
                   % (job.get("cmd", ""), job["fails"], type(ex).__name__, ex,
                      job.get("at", "HH:MM")))
        else:
            NOTIFY("[job failed %d/%d] %s\n%s: %s"
                   % (job["fails"], FAILURE_LIMIT, job.get("cmd", ""),
                      type(ex).__name__, ex))
    except Exception:
        pass
    return errs[-1]


def tick(now=None):
    """Return the jobs due at this minute, marking each as run for the day."""
    now = now or datetime.datetime.now()
    hm, day = now.strftime("%H:%M"), now.strftime("%Y-%m-%d")
    fired = [j for j in J if j.get("at") == hm and j.get("last") != day
             and not j.get("off")]
    if fired:
        for job in fired:
            job["last"] = day
        save()
    return fired


def loop():
    global LAST
    last = None
    while True:
        LAST = time.time()
        now = datetime.datetime.now()
        hm = now.strftime("%H:%M")
        if hm != last:
            last = hm
            for job in tick(now):
                try:
                    NOTIFY("[%s] %s\n%s" % (hm, job["cmd"], REPLY(job["cmd"])))
                    if job.get("fails"):
                        job["fails"] = 0
                        save()
                except Exception as ex:
                    # a reminder that fails silently is the worst outcome: the user
                    # believes it ran. Record it, notify it, and let `doctor` show it.
                    record_failure(job, ex, hm)
        time.sleep(15)


def add(m):
    h, mi = m["at"].split(":")
    at = "%02d:%02d" % (int(h), int(mi))
    body = m["cmd"].strip()
    for existing in J:
        if existing["at"] == at and existing["cmd"] == body:
            existing.pop("off", None)
            existing["fails"] = 0
            save()
            return "Re-armed %s -> %s" % (at, body)
    J.append({"at": at, "cmd": body})
    save()
    E.set_inverse("job_rm", {"i": len(J) - 1})
    return "Daily %s -> %s" % (at, m["cmd"].strip())


def show(m):
    if not J:
        return "No jobs."
    lines = []
    for i, j in enumerate(J):
        note = "  <off: failed %d times>" % int(j.get("fails", 0)) if j.get("off") else ""
        lines.append("%d. %s  %s%s" % (i + 1, j["at"], j["cmd"], note))
    return "\n".join(lines)


def drop(m):
    i = int(m["n"]) - 1
    if 0 <= i < len(J):
        item = J.pop(i)
        save()
        E.set_inverse("job_add", {"i": i, "item": item})
        return "Removed."
    return "No such job."


RULES = [
    (r"^daily (?P<at>\d{1,2}:\d{2}) (?P<cmd>.+)$", add),
    (r"^jobs$", show),
    (r"^unjob (?P<n>\d+)$", drop),
]
