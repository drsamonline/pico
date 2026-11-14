"""habits — daily streaks, kept in habits.json."""
import datetime
import json

CATALOG = ["habit add X - new habit", "did X - log habit today",
           "habits - streaks", "habit del X - remove habit"]
P = H = E = None


def setup(api):
    global P, H, E
    E = api["engine"]
    P = api["HOME"] / "habits.json"
    H = json.loads(P.read_text("utf-8")) if P.exists() else {}
    api["inverse_handler"]("habit_del", lambda a: (H.pop(a["n"], None), save()))
    api["inverse_handler"]("habit_restore",
                           lambda a: (H.__setitem__(a["n"], a["dates"]), save()))
    api["inverse_handler"]("habit_undid",
                           lambda a: (H.get(a["n"], []).remove(a["d"]), save()))


def save():
    P.write_text(json.dumps(H, indent=2), "utf-8")


def _streak(dates):
    d = datetime.date.today()
    s = 0
    if d.isoformat() not in dates:
        d -= datetime.timedelta(days=1)
    while d.isoformat() in dates:
        s += 1
        d -= datetime.timedelta(days=1)
    return s


def add(m):
    n = m["name"].strip().lower()
    if n in H:
        return "Habit already exists."
    H[n] = []
    save()
    E.set_inverse("habit_del", {"n": n})
    return "Habit added."


def did(m):
    n = m["name"].strip().lower()
    if n not in H:
        return "No such habit. Try: habit add %s" % n
    t = datetime.date.today().isoformat()
    if t in H[n]:
        return "Already logged today."
    H[n].append(t)
    save()
    E.set_inverse("habit_undid", {"n": n, "d": t})
    return "%s: %d-day streak." % (n, _streak(H[n]))


def show(m):
    if not H:
        return "No habits. Try: habit add walk"
    t = datetime.date.today().isoformat()
    return "\n".join("%s %-12s %2dd streak  %3d total" %
                     ("x" if t in v else ".", k, _streak(v), len(v))
                     for k, v in sorted(H.items()))


def drop(m):
    n = m["name"].strip().lower()
    if n in H:
        old = H.pop(n)
        save()
        E.set_inverse("habit_restore", {"n": n, "dates": old})
        return "Removed."
    return "No such habit."


RULES = [
    (r"^habit add (?P<name>.+)$", add),
    (r"^(did|habit done) (?P<name>.+)$", did),
    (r"^habits$", show),
    (r"^habit del (?P<name>.+)$", drop),
]
