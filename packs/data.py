"""data — CSV in, SQL out. sqlite3 from the standard library, read-only by default."""
import csv
import pathlib
import re
import sqlite3

CATALOG = ["importcsv PATH TABLE - load a CSV into the local db",
           "sql SELECT … - query it", "tables - what is loaded"]
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
]
