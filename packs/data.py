"""data — CSV in, SQL out. sqlite3 from the standard library, read-only by default."""
import csv
import pathlib
import re
import sqlite3

CATALOG = ["importcsv PATH TABLE - load a CSV into the local db",
           "sql SELECT … - query it", "tables - what is loaded",
           "csv filter COND PATH - rows matching", "csv sort COL [desc] PATH - ordered rows",
           "csv join KEY A.csv B.csv - inner join",
           "csv pivot COL sum AMT PATH - group and aggregate"]
E = DB = None
WRITE = re.compile(r"^\s*(insert|update|delete|drop|alter|create|replace|attach|pragma)\b", re.I)


def setup(api):
    global E, DB
    E = api["engine"]
    DB = api["HOME"] / "pico.db"
    api["inverse_handler"]("sql_drop", _drop)


def _conn():
    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row
    return c


def importcsv(m):
    p = pathlib.Path(m["path"]).expanduser()
    if not p.exists():
        return "File not found: " + str(p)
    table = re.sub(r"\W", "_", m["table"])
    try:
        with p.open(newline="", encoding="utf-8", errors="replace") as f:
            rdr = csv.reader(f)
            rows = list(rdr)
    except Exception as ex:
        return "Cannot read: %s" % ex
    if len(rows) < 2:
        return "Needs a header row and at least one data row."
    header = [re.sub(r"\W", "_", h.strip().lower()) or ("c%d" % i)
              for i, h in enumerate(rows[0])]
    with _conn() as c:
        c.execute('DROP TABLE IF EXISTS "%s"' % table)
        c.execute('CREATE TABLE "%s" (%s)' % (
            table, ", ".join('"%s" TEXT' % h for h in header)))
        c.executemany('INSERT INTO "%s" VALUES (%s)' % (
            table, ", ".join("?" * len(header))), rows[1:])
    E.set_inverse("sql_drop", {"table": table})
    return "Loaded %d row(s) into %s (%s)" % (len(rows) - 1, table, ", ".join(header))


def sql(m):
    q = m["q"].strip()
    if WRITE.match(q):
        return "Read-only: SELECT, WITH and PRAGMA table_info only."
    if not re.match(r"^\s*(select|with|pragma)\b", q, re.I):
        return "Read-only: SELECT, WITH and PRAGMA table_info only."
    if not DB.exists():
        return "No data yet. Try: importcsv ~/clients.csv clients"
    try:
        with _conn() as c:
            cur = c.execute(q)
            rows = cur.fetchmany(50)
            cols = [d[0] for d in cur.description] if cur.description else []
    except Exception as ex:
        return "SQL error: %s" % ex
    if not rows:
        return "No rows."
    out = [" | ".join(cols)]
    out.append("-+-".join("-" * len(c) for c in cols))
    for r in rows:
        out.append(" | ".join("" if v is None else str(v) for v in tuple(r)))
    if len(rows) == 50:
        out.append("(first 50 rows)")
    return "\n".join(out)


def _load(path):
    p = pathlib.Path(path).expanduser()
    if not p.exists():
        return None, None, "File not found: " + str(p)
    with p.open(newline="", encoding="utf-8", errors="replace") as f:
        rows = list(csv.reader(f))
    if not rows:
        return None, None, "Empty file."
    header = [h.strip() for h in rows[0]]
    body = [dict(zip(header, r + [""] * (len(header) - len(r)))) for r in rows[1:]]
    return header, body, None


def _num(v):
    try:
        return float(v)
    except Exception:
        return None


def csv_filter(m):
    header, rows, err = _load(m["path"])
    if err:
        return err
    cond = m["cond"].strip()
    parts = re.split(r"(>=|<=|!=|>|<|=)", cond, maxsplit=1)
    if len(parts) != 3:
        return "Condition looks like: age>30  or  name=Asha"
    col, op, want = parts[0].strip(), parts[1], parts[2].strip()
    if col not in header:
        return "No column '%s'. Columns: %s" % (col, ", ".join(header))
    hits = []
    for r in rows:
        have = r.get(col, "")
        a, b = _num(have), _num(want)
        if a is None or b is None:
            a, b = have.lower(), want.lower()
        ok = {"=": a == b, "!=": a != b, ">": a > b, "<": a < b,
              ">=": a >= b, "<=": a <= b}[op]
        if ok:
            hits.append(r)
    if not hits:
        return "No rows match %s." % cond
    out = [" | ".join(header)]
    for r in hits[:50]:
        out.append(" | ".join(r.get(h, "") for h in header))
    out.append("%d of %d row(s)" % (len(hits), len(rows)))
    return "\n".join(out)


def csv_sort(m):
    header, rows, err = _load(m["path"])
    if err:
        return err
    col = m["col"].strip()
    if col not in header:
        return "No column '%s'. Columns: %s" % (col, ", ".join(header))
    rev = bool(m["dir"]) and m["dir"].lower().startswith("desc")
    rows.sort(key=lambda r: (_num(r.get(col, "")) if _num(r.get(col, "")) is not None
                             else r.get(col, "").lower()), reverse=rev)
    out = [" | ".join(header)]
    for r in rows[:50]:
        out.append(" | ".join(r.get(h, "") for h in header))
    if len(rows) > 50:
        out.append("(first 50 of %d)" % len(rows))
    return "\n".join(out)


def csv_join(m):
    key = m["key"].strip()
    ha, ra, err = _load(m["p1"])
    if err:
        return err
    hb, rb, err = _load(m["p2"])
    if err:
        return err
    if key not in ha or key not in hb:
        return "Column '%s' must be in both files. Left: %s | Right: %s" % (
            key, ", ".join(ha), ", ".join(hb))
    right = {}
    for r in rb:
        right.setdefault(r.get(key, ""), []).append(r)
    extra = [h for h in hb if h not in ha]
    out = [" | ".join(ha + extra)]
    n = 0
    for r in ra:
        for match in right.get(r.get(key, ""), []):
            out.append(" | ".join([r.get(h, "") for h in ha] + [match.get(h, "") for h in extra]))
            n += 1
            if n >= 50:
                break
        if n >= 50:
            break
    if n == 0:
        return "No matching '%s' values." % key
    out.append("%d joined row(s)%s" % (n, ", first 50" if n >= 50 else ""))
    return "\n".join(out)


def csv_pivot(m):
    header, rows, err = _load(m["path"])
    if err:
        return err
    keys = [k.strip() for k in m["key"].split(",") if k.strip()]
    op, col = m["op"].lower(), m["col"].strip()
    for c in keys + [col]:
        if c not in header:
            return "No column '%s'. Columns: %s" % (c, ", ".join(header))
    groups = {}
    for r in rows:
        k = " / ".join(r.get(x, "") for x in keys)
        v = _num(r.get(col, ""))
        if v is None:
            v = 0.0
        groups.setdefault(k, []).append(v)
    if op not in ("sum", "count", "avg", "min", "max"):
        return "op is sum, count, avg, min or max."
    out = ["%-24s %10s" % (",".join(keys), op + "(" + col + ")")]
    total = 0.0
    for k in sorted(groups, key=lambda x: -sum(groups[x])):
        vals = groups[k]
        v = {"sum": sum(vals), "count": float(len(vals)), "avg": sum(vals) / len(vals),
             "min": min(vals), "max": max(vals)}[op]
        total += v if op in ("sum", "count") else 0.0
        out.append("%-24s %10s" % (k, "{:,.2f}".format(v).rstrip("0").rstrip(".")))
    if op in ("sum", "count"):
        out.append("%-24s %10s" % ("total", "{:,.2f}".format(total).rstrip("0").rstrip(".")))
    out.append("%d group(s) over %d row(s)" % (len(groups), len(rows)))
    return "\n".join(out)


def tables(m):
    if not DB.exists():
        return "No data yet."
    with _conn() as c:
        rows = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    if not rows:
        return "No tables."
    out = []
    with _conn() as c:
        for r in rows:
            name = r[0]
            cnt = c.execute('SELECT COUNT(*) FROM "%s"' % name).fetchone()[0]
            out.append("%-20s %d row(s)" % (name, cnt))
    return "\n".join(out)


def _drop(args):
    if DB.exists():
        with _conn() as c:
            c.execute('DROP TABLE IF EXISTS "%s"' % args["table"])


RULES = [
    (r"^importcsv\s+(?P<path>\S+)\s+(?P<table>\w+)$", importcsv),
    (r"^sql\s+(?P<q>.+)$", sql),
    (r"^tables$", tables),
    (r"^csv filter (?P<cond>.+?) (?P<path>\S+\.csv)$", csv_filter),
    (r"^csv sort (?P<col>\w+)(?: (?P<dir>asc|desc))? (?P<path>\S+\.csv)$", csv_sort),
    (r"^csv join (?P<key>\w+) (?P<p1>\S+\.csv) (?P<p2>\S+\.csv)$", csv_join),
    (r"^csv pivot (?P<key>[\w,]+) (?P<op>sum|count|avg|min|max) (?P<col>\w+) (?P<path>\S+\.csv)$",
     csv_pivot),
]
