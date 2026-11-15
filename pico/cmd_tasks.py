"""pico tasks, notes, shopping, events, the daily brief."""


import datetime


E = None  # engine, rebound by Engine._bind_modules()


def _S():
    return E.S


def _mark(t):
    bits = []
    if t.get("recur"):
        bits.append("recur " + t["recur"])
    due = t.get("due")
    if due:
        bits.append(("overdue " if due < datetime.date.today().isoformat() else "due ") + due)
    return ("  <" + ", ".join(bits) + ">") if bits else ""


def tasks_list(m):
    items = _S()["tasks"]
    if not items:
        return "Nothing pending."
    shown = items[:40]
    lines = ["[%s] %d. %s%s" % ("x" if t["done"] else " ", i + 1, t["text"], _mark(t))
             for i, t in enumerate(shown)]
    if len(items) > len(shown):
        lines.append("... and %d more. `done N` still addresses any index."
                     % (len(items) - len(shown)))
    return "\n".join(lines)


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


def task_recur(m):
    every = m["every"].lower()
    i = len(_S()["tasks"])
    _S()["tasks"].append({"text": m["text"].strip(), "done": False, "recur": every})
    _S().setdefault("recur", {})[str(i)] = datetime.date.today().isoformat()
    E.set_inverse("list_rm", {"key": "tasks", "i": i})
    return "Recurring %s: %s" % (every, m["text"].strip())


def task_due(m):
    if not _valid_date(m["date"]) or len(m["date"].split("-")) != 3:
        return "That is not a date. Use due N 2026-12-25"
    i = int(m["n"]) - 1
    ts = _S()["tasks"]
    if not (0 <= i < len(ts)):
        return "No such task."
    old_due = ts[i].get("due")
    ts[i]["due"] = m["date"]
    E.set_inverse("task_due", {"i": i, "date": old_due})
    return "Due %s: %s" % (m["date"], ts[i]["text"])


def overdue(m):
    today = datetime.date.today().isoformat()
    rows = [(i, t) for i, t in enumerate(_S()["tasks"])
            if not t["done"] and t.get("due") and t["due"] < today]
    if not rows:
        return "Nothing overdue."
    return "\n".join("%d. %s  (due %s)" % (i + 1, t["text"], t["due"]) for i, t in rows)


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


def _valid_date(text):
    """MM-DD or YYYY-MM-DD, with 02-29 allowed as a recurring date."""
    parts = text.split("-")
    if len(parts) == 3:
        try:
            y, mo, d = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            return False
        if not (1 <= mo <= 12):
            return False
        if mo == 2 and d == 29:
            return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
        return 1 <= d <= [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1]
    if len(parts) == 2:
        try:
            mo, d = int(parts[0]), int(parts[1])
        except ValueError:
            return False
        if not (1 <= mo <= 12):
            return False
        return 1 <= d <= [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1]
    return False


def event_add(m):
    if not _valid_date(m["date"]):
        return "That is not a date. Use on 12-25 text or on 2026-12-25 text"
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
