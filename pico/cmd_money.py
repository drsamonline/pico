"""pico the expense log and its formatting."""


import datetime


E = None  # engine, rebound by Engine._bind_modules()


def _S():
    return E.S


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
