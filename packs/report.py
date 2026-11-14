"""report — the week in numbers, and a decision that shows its work."""
import datetime
import hashlib
import json
import random

CATALOG = ["report weekly - the last seven days", "report month - this month",
           "decide A|B|C - pick one, reproducibly",
           "chart 1,4,9 - bar chart of numbers"]
E = None


def setup(api):
    global E
    E = api["engine"]


def _ledger(days):
    f = E.home / "ledger.jsonl"
    if not f.exists():
        return []
    cut = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()[:19]
    rows = []
    for line in f.read_text("utf-8").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("ts", "") >= cut:
            rows.append(r)
    return rows


def weekly(m):
    rows = _ledger(7)
    s = E.S
    done = sum(1 for t in s.get("tasks", []) if t.get("done"))
    open_ = sum(1 for t in s.get("tasks", []) if not t.get("done"))
    mon = datetime.date.today().strftime("%Y-%m")
    spend = {}
    for r in s.get("spend", []):
        if str(r["d"]).startswith(mon):
            spend[r["cat"]] = spend.get(r["cat"], 0) + r["amt"]
    by_tier = {}
    for r in rows:
        by_tier[r.get("tier", "?")] = by_tier.get(r.get("tier", "?"), 0) + 1
    by_src = {}
    for r in rows:
        by_src[r.get("src", "?")] = by_src.get(r.get("src", "?"), 0) + 1
    lines = ["pico — last 7 days",
             "commands   %d" % len(rows),
             "by tier    " + ", ".join("%s %d" % (k, v) for k, v in sorted(by_tier.items())),
             "by source  " + ", ".join("%s %d" % (k, v) for k, v in sorted(by_src.items())),
             "tasks      %d done, %d open" % (done, open_)]
    if spend:
        lines.append("spend      " + ", ".join(
            "%s %s" % (k, "{:,.0f}".format(v)) for k, v in sorted(spend.items())))
        lines.append("total      " + "{:,.0f}".format(sum(spend.values())))
    if rows:
        lines.append("")
        lines.append("busiest day " + _busiest(rows))
    return "\n".join(lines)


def _busiest(rows):
    days = {}
    for r in rows:
        d = r.get("ts", "")[:10]
        days[d] = days.get(d, 0) + 1
    if not days:
        return "-"
    d = max(days, key=days.get)
    return "%s (%d commands)" % (d, days[d])


def month(m):
    rows = _ledger(31)
    s = E.S
    spend = {}
    for r in s.get("spend", []):
        if str(r["d"]).startswith(datetime.date.today().strftime("%Y-%m")):
            spend[r["cat"]] = spend.get(r["cat"], 0) + r["amt"]
    lines = ["pico — this month", "commands %d" % len(rows)]
    for k, v in sorted(spend.items()):
        lines.append("  %-10s %s" % (k, "{:,.0f}".format(v)))
    if spend:
        lines.append("  %-10s %s" % ("total", "{:,.0f}".format(sum(spend.values()))))
    return "\n".join(lines)


def chart(m):
    raw = [x.strip() for x in m["values"].split(",") if x.strip()]
    vals = []
    for x in raw:
        try:
            vals.append(float(x))
        except Exception:
            return "chart takes numbers: chart 3,7,12,9"
    if not vals:
        return "Nothing to chart."
    top = max(abs(v) for v in vals) or 1
    width = 40
    out = []
    for v in vals:
        n = int(round(abs(v) / top * width))
        bar = ("#" * n) if v >= 0 else ("-" * n)
        out.append("%9s %s" % ("{:,.0f}".format(v), bar))
    out.append("max %s over %d value(s)" % ("{:,.0f}".format(max(vals)), len(vals)))
    return "\n".join(out)


def decide(m):
    opts = [o.strip() for o in m["options"].split("|") if o.strip()]
    if len(opts) < 2:
        return "Give at least two options: decide tea|coffee"
    seed = hashlib.sha256("|".join(opts).encode() +
                          datetime.date.today().isoformat().encode()).hexdigest()
    pick = opts[int(seed[:8], 16) % len(opts)]
    return "%s\n\n(from %d options, seed %s — same answer all day)" % (
        pick, len(opts), seed[:8])


RULES = [
    (r"^report weekly$", weekly),
    (r"^report month$", month),
    (r"^decide (?P<options>.+\|.+)$", decide),
    (r"^chart (?P<values>[\d.,\- ]+)$", chart),
]
