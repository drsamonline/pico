"""finance — loan, investment, tax and split arithmetic. Deterministic, no advice."""
CATALOG = ["emi P R N - loan EMI", "sip A R Y - SIP maturity", "fd P R Y - FD maturity",
           "si P R Y - simple interest", "gst A R - add/remove GST",
           "split A N - divide a bill", "disc A R - discount",
           "budget CAT AMT - set monthly cap", "budget - caps vs spend"]
E = None


def setup(api):
    global E
    E = api["engine"]
    # partial commands ask one question instead of printing a syntax lesson
    api["add_slots"](r"^emi\s+(?P<p>[\d.]+)\s+(?P<r>[\d.]+)$", "emi {p} {r} {n}",
                     {"n": "Loan EMI: how many months?"})
    api["add_slots"](r"^sip\s+(?P<a>[\d.]+)\s+(?P<r>[\d.]+)$", "sip {a} {r} {y}",
                     {"y": "SIP: how many years?"})
    api["add_slots"](r"^fd\s+(?P<p>[\d.]+)\s+(?P<r>[\d.]+)$", "fd {p} {r} {y}",
                     {"y": "FD: how many years?"})
    api["add_slots"](r"^gst\s+(?P<a>[\d.]+)$", "gst {a} {r}",
                     {"r": "GST rate? (5, 12, 18 or 28)"})
    api["add_slots"](r"^split\s+(?P<a>[\d.]+)$", "split {a} {n}",
                     {"n": "Split between how many people?"})
    api["add_slots"](r"^disc\s+(?P<a>[\d.]+)$", "disc {a} {r}",
                     {"r": "Discount percent?"})
    api["inverse_handler"]("budget_restore",
                           lambda a: (E.S.setdefault("budget", {}).__setitem__(a["cat"], a["v"])
                                      if a["v"] is not None
                                      else E.S.setdefault("budget", {}).pop(a["cat"], None)))


def emi(m):
    p, r, n = float(m["p"]), float(m["r"]) / 1200, int(m["n"])
    if n <= 0:
        return "EMI needs at least 1 month."
    if p <= 0:
        return "Loan amount must be positive."
    e = p / n if r == 0 else p * r * (1 + r) ** n / ((1 + r) ** n - 1)
    tot = e * n
    return "EMI {:,}/mo | total {:,} | interest {:,}".format(round(e), round(tot), round(tot - p))


def sip(m):
    a, r, y = float(m["a"]), float(m["r"]) / 1200, int(m["y"])
    n = y * 12
    if n <= 0:
        return "SIP needs at least 1 month."
    fv = a * ((1 + r) ** n - 1) / r * (1 + r) if r else a * n
    return "Maturity {:,} | invested {:,} | gain {:,}".format(
        round(fv), round(a * n), round(fv - a * n))


def fd(m):
    p, r, y = float(m["p"]), float(m["r"]) / 100, float(m["y"])
    if y <= 0:
        return "FD needs a positive term."
    fv = p * (1 + r / 4) ** (4 * y)
    return "Maturity {:,} | interest {:,} (quarterly compounding)".format(
        round(fv), round(fv - p))


def si(m):
    p, r, y = float(m["p"]), float(m["r"]), float(m["y"])
    i = p * r * y / 100
    return "Interest {:,} | total {:,}".format(round(i), round(p + i))


def gst(m):
    a, r = float(m["a"]), float(m["r"])
    if r < 0:
        return "Rate cannot be negative."
    return "+GST {:,.2f} | -GST {:,.2f} | tax part {:,.2f}".format(
        a * (1 + r / 100), a / (1 + r / 100), a - a / (1 + r / 100))


def split(m):
    a, n = float(m["a"]), int(m["n"])
    if n <= 0:
        return "Split by at least 1 person."
    each = round(a / n, 2)
    if abs(each * n - a) >= 0.005:
        return "{:,.2f} each ({} people) - {:,.2f} left to assign".format(each, n, a - each * n)
    return "{:,.2f} each ({} people)".format(each, n)


def disc(m):
    a, r = float(m["a"]), float(m["r"])
    if not 0 <= r <= 100:
        return "Discount must be between 0 and 100 percent."
    return "Final {:,.2f} | saved {:,.2f}".format(a * (1 - r / 100), a * r / 100)


def budget_set(m):
    b = E.S.setdefault("budget", {})
    cat = m["cat"].lower()
    old = b.get(cat)
    b[cat] = float(m["amt"])
    E.set_inverse("budget_restore", {"cat": cat, "v": old})
    return "Cap set: %s %s/month" % (cat, "{:,.0f}".format(float(m["amt"])))


def budget_show(m):
    import datetime
    b = E.S.get("budget") or {}
    if not b:
        return "No caps. Set one: budget food 8000"
    mon = datetime.date.today().strftime("%Y-%m")
    spent = {}
    for r in E.S.get("spend", []):
        if str(r["d"]).startswith(mon):
            spent[r["cat"]] = spent.get(r["cat"], 0) + r["amt"]
    lines = []
    for cat, cap in sorted(b.items()):
        s = spent.get(cat, 0)
        pct = (s / cap * 100) if cap else 0
        bar = "#" * min(20, int(pct / 5))
        lines.append("%-10s %8.0f / %-8.0f %5.0f%% %s" % (cat, s, cap, pct, bar))
    return "\n".join(lines)


RULES = [
    (r"^emi (?P<p>[\d.]+) (?P<r>[\d.]+) (?P<n>\d+)$", emi),
    (r"^sip (?P<a>[\d.]+) (?P<r>[\d.]+) (?P<y>\d+)$", sip),
    (r"^fd (?P<p>[\d.]+) (?P<r>[\d.]+) (?P<y>[\d.]+)$", fd),
    (r"^si (?P<p>[\d.]+) (?P<r>[\d.]+) (?P<y>[\d.]+)$", si),
    (r"^gst (?P<a>[\d.]+) (?P<r>[\d.]+)$", gst),
    (r"^split (?P<a>[\d.]+) (?P<n>\d+)$", split),
    (r"^disc (?P<a>[\d.]+) (?P<r>[\d.]+)$", disc),
    (r"^budget (?P<cat>\w+) (?P<amt>[\d.]+)$", budget_set),
    (r"^budget$", budget_show),
]
