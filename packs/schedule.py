"""schedule — persistent daily jobs. They fire while pico runs (--serve or REPL)."""
import datetime
import json
import os
import threading
import time

CATALOG = ["daily HH:MM CMD - repeat a command", "jobs - list jobs", "unjob N - remove job"]
P = J = REPLY = NOTIFY = E = None


def setup(api):
    global P, J, REPLY, NOTIFY, E
    E = api["engine"]
    P = api["HOME"] / "jobs.json"
    J = json.loads(P.read_text("utf-8")) if P.exists() else []
    REPLY, NOTIFY = api["reply"], api["notify"]
    api["inverse_handler"]("job_rm", lambda a: (J.pop(a["i"]), save()))
    api["inverse_handler"]("job_add", lambda a: (J.insert(min(a["i"], len(J)), a["item"]), save()))
    if not os.environ.get("PICO_NO_THREADS"):
        threading.Thread(target=loop, daemon=True).start()


def save():
    P.write_text(json.dumps(J, indent=2), "utf-8")


def tick(now=None):
    """Return the jobs due at this minute, marking each as run for the day."""
    now = now or datetime.datetime.now()
    hm, day = now.strftime("%H:%M"), now.strftime("%Y-%m-%d")
    fired = [j for j in J if j.get("at") == hm and j.get("last") != day]
    if fired:
        for job in fired:
            job["last"] = day
        save()
    return fired


def loop():
    last = None
    while True:
        now = datetime.datetime.now()
        hm = now.strftime("%H:%M")
        if hm != last:
            last = hm
            for job in tick(now):
                try:
                    NOTIFY("[%s] %s\n%s" % (hm, job["cmd"], REPLY(job["cmd"])))
                except Exception as ex:
                    print("[job error]", ex)
        time.sleep(15)


def add(m):
    h, mi = m["at"].split(":")
    at = "%02d:%02d" % (int(h), int(mi))
    J.append({"at": at, "cmd": m["cmd"].strip()})
    save()
    E.set_inverse("job_rm", {"i": len(J) - 1})
    return "Daily %s -> %s" % (at, m["cmd"].strip())


def show(m):
    return "\n".join("%d. %s  %s" % (i + 1, j["at"], j["cmd"]) for i, j in enumerate(J)) \
        or "No jobs."


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
