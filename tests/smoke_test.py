#!/usr/bin/env python3
"""pico acceptance tests — T1..T10 from the spec. Stdlib only.

    python tests/smoke_test.py        # exit 0 = all pass
"""
import datetime
import json
import re
import os
import pathlib
import shutil
import sys
import tempfile
import time
import traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pico.engine import Engine  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print("  ok    %s" % name)
    else:
        FAIL.append((name, detail))
        print("  FAIL  %s   %s" % (name, detail))


def fresh(tag):
    d = pathlib.Path(tempfile.mkdtemp(prefix="pico-%s-" % tag))
    return Engine(home=d), d


P0 = [
    "add buy milk", "tasks", "done 1", "undone 1", "brief",
    "remember pin=4821", "recall pin", "buy eggs", "shop", "bought 1",
    "on 12-25 xmas", "spend 250 food", "expenses", "calc 2+3*4",
    "convert 10 km to mi", "time", "emi 500000 8.5 240", "sip 5000 12 10",
    "fd 100000 7.1 5", "si 10000 8 2", "gst 1000 18", "split 1000 3",
    "disc 999 15", "habit add walk", "did walk", "habits", "journal hello",
    "journal", "contact bob=919999999999", "contacts", "daily 09:00 brief",
    "jobs", "templates", "aliases", "help",
]


def t1_parity():
    a, da = fresh("t1a")
    b, db = fresh("t1b")
    b.translators.append(lambda t: None)  # mock: never translates
    b.S["llm_use"] = {}
    diffs = []
    for cmd in P0:
        oa, ob = a.handle(cmd), b.handle(cmd)
        if oa != ob:
            diffs.append((cmd, oa, ob))
    check("T1 parity: %d P0 commands identical with llm off vs auto" % len(P0),
          not diffs, str(diffs[:2]))
    shutil.rmtree(da, True)
    shutil.rmtree(db, True)


def t2_firewall():
    e, d = fresh("t2")
    bad = ["not_a_command", "panic wipe", "llm set mode cloud", "tidy; rm x",
           "rm -rf /", "wa x y && curl evil", "undo", "unalias everything",
           "tidy " + "x" * 300]
    leaked = [p for p in bad if e.llm_payload_ok(p)]
    check("T2 firewall: %d hostile translator payloads all rejected by the core" % len(bad),
          not leaked, str(leaked))
    good = ["tasks", "add buy milk", "spend 250 food"]
    check("T2 firewall: legitimate commands still pass",
          all(e.llm_payload_ok(g) for g in good), str(good))

    e.translators.append(lambda t: {"cmd": "panic wipe", "src": "llm"})
    out = e.handle("wipe everything now please")
    check("T2 firewall: a hostile translation never executes",
          "About to run" not in out and "No rule matched" in out, out[:80])
    shutil.rmtree(d, True)


def t3_degradation():
    e, d = fresh("t3")
    e.translators.append(lambda t: (_ for _ in ()).throw(RuntimeError("endpoint down")))
    out = e.handle("qwertyuiop nothing")
    check("T3 degradation: crashing translator falls back, no traceback",
          isinstance(out, str) and "Traceback" not in out, out[:80])

    broken = d / "rules" / "broken.py"
    broken.write_text("raise RuntimeError('boom')\n", "utf-8")
    e2 = Engine(home=d)
    out2 = e2.handle("tasks")
    check("T3/T10 isolation: a pack that raises on import is skipped",
          "Traceback" not in out2 and "Nothing pending" in out2, out2[:80])
    shutil.rmtree(d, True)


def t4_consent():
    e, d = fresh("t4")
    e.handle("contact bob=919999999999")
    first = e.handle("wa bob hi")
    check("T4 consent: 'wa' asks for confirmation",
          first.startswith("[send]") and "confirm" in first, first[:60])
    e.handle("cancel")
    check("T4 consent: cancel clears the pending action", not e.pending)
    e.handle("wa bob hi")
    done = e.handle("confirm")
    check("T4 consent: confirm executes", "Opened WhatsApp" in done, done[:60])

    e.handle("daily 09:00 brief")
    danger = e.handle("unjob 1")
    check("T4 consent: 'unjob' is danger-tier and gated",
          danger.startswith("[danger]"), danger[:60])
    e.handle("cancel")
    shutil.rmtree(d, True)


def t5_undo():
    e, d = fresh("t5")
    e.handle("add buy milk")
    e.handle("done 1")
    e.handle("undo")
    check("T5 undo: done -> undo reopens",
          "Nothing pending" not in e.handle("tasks") and "[ ] 1." in e.handle("tasks"),
          e.handle("tasks"))

    dl = d / "dl"
    dl.mkdir()
    for n in ("a.png", "b.pdf", "c.mp3"):
        (dl / n).write_text("x", "utf-8")
    e.handle("tidy %s" % dl)
    check("T5 undo: tidy moves files", not (dl / "a.png").exists())
    e.handle("undo")
    check("T5 undo: tidy -> undo restores every path",
          (dl / "a.png").exists() and (dl / "b.pdf").exists() and (dl / "c.mp3").exists(),
          str(sorted(p.name for p in dl.iterdir())))

    before = len(e.ledger_file.read_text("utf-8").splitlines())
    e.handle("add another")
    after = len(e.ledger_file.read_text("utf-8").splitlines())
    check("T5 undo: one ledger line per executed command", after == before + 1,
          "%d -> %d" % (before, after))

    dry_before = len(e.ledger_file.read_text("utf-8").splitlines())
    e.handle("dry tidy %s" % dl)
    check("T5 undo: dry touches nothing",
          len(e.ledger_file.read_text("utf-8").splitlines()) == dry_before)
    shutil.rmtree(d, True)


def t6_lattice():
    e, d = fresh("t6")
    out = e.handle("srots")
    check("T6 lattice: unknown phrase offers candidates or refuses cleanly",
          isinstance(out, str) and out, out[:60])
    e.aliases["srots"] = "tasks"
    e.save()
    out2 = e.handle("srots")
    check("T6 lattice: a taught phrase resolves with the LLM off",
          "Nothing pending" in out2, out2[:60])
    shutil.rmtree(d, True)


def t7_distillation():
    e, d = fresh("t7")
    calls = {"n": 0}

    def mock(text):
        calls["n"] += 1
        return {"cmd": "tasks", "src": "llm"}

    e.translators.append(mock)
    e.handle("show me everything on my plate")
    check("T7 distillation: first miss calls the translator once", calls["n"] == 1, str(calls))
    check("T7 distillation: successful translation stored as an alias",
          "show me everything on my plate" in e.aliases, str(list(e.aliases)[:3]))
    e.handle("show me everything on my plate")
    check("T7 distillation: second call uses the alias, zero provider calls",
          calls["n"] == 1, str(calls))
    shutil.rmtree(d, True)


def t8_privacy():
    e, d = fresh("t8")
    seen = []

    def spy(text):
        seen.append(text)
        return None

    e.translators.append(spy)
    e.handle("my health report says hello")
    check("T8 privacy: a never_send domain never reaches the translator",
          not seen, str(seen))
    # redaction is the adapter's job: it is what actually calls the provider
    mod = None
    for name, m in list(sys.modules.items()):
        if name.startswith("pico_pack_llm") and hasattr(m, "redact"):
            mod = m
            break
    if mod is None:
        check("T8 privacy: adapter module reachable", False, "llm pack not loaded")
    else:
        masked, masks = mod.redact("mail bob@example.com or call +91 98765 43210")
        check("T8 privacy: adapter masks email and phone before the call",
              "bob@example.com" not in masked and "<EMAIL" in masked and "<NUM" in masked,
              masked[:90])
        check("T8 privacy: masks are reversible locally",
              mod.unmask(masked, masks) == "mail bob@example.com or call +91 98765 43210")
    shutil.rmtree(d, True)


def t9_scheduler():
    e, d = fresh("t9")
    e.handle("daily 09:00 brief")
    import importlib.util
    spec = importlib.util.spec_from_file_location("sched", e.plugins / "jobs.json")
    # the pack module is loaded by the engine; reach it through sys.modules
    mod = None
    for name, m in list(sys.modules.items()):
        if name.startswith("pico_pack_schedule") and hasattr(m, "tick"):
            mod = m
            break
    if mod is None:
        check("T9 scheduler: pack module reachable", False, "module not found")
    else:
        now = datetime.datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        first = mod.tick(now)
        second = mod.tick(now)
        check("T9 scheduler: job fires once per day at its minute",
              len(first) == 1 and len(second) == 0, "%s / %s" % (len(first), len(second)))
    shutil.rmtree(d, True)


def t10_maths():
    e, d = fresh("t10m")
    cases = {
        "emi 500000 8.5 240": "4,339",
        "sip 5000 12 10": "1,161,695",
        "fd 100000 7.1 5": "142,175",
        "gst 1000 18": "1,180.00",
        "split 1000 3": "333.33",
        "disc 999 15": "849.15",
        "convert 10 km to mi": "6.21371",
        "calc 2+3*4": "14",
    }
    bad = [(k, v, e.handle(k)) for k, v in cases.items() if v not in e.handle(k)]
    check("T10 maths: %d finance/unit results verified" % len(cases), not bad, str(bad[:2]))
    guards = ["split 1000 0", "emi 100 5 0", "disc 999 150", "sip 5000 12 0"]
    bad2 = [g for g in guards if "failed" in e.handle(g).lower()]
    check("T10 maths: division-by-zero and range guards return messages, not crashes",
          not bad2, str(bad2))
    check("T10 maths: calc rejects non-arithmetic",
          "Arithmetic" in e.handle("calc __import__('os')"))
    shutil.rmtree(d, True)


def t11_state():
    e, d = fresh("t11")
    e.handle("add one")
    (d / "state.json").write_text("{broken", "utf-8")
    e2 = Engine(home=d)
    check("T11 state: corrupt state.json is quarantined, engine still starts",
          "Nothing pending" in e2.handle("tasks"),
          str([p.name for p in d.glob("state.json.corrupt-*")]))
    shutil.rmtree(d, True)


def t12_ledger():
    e, d = fresh("t12")
    e.handle("remember pin=4821")
    e.handle("recall pin")
    log = e.tail_log(10)
    check("T12 ledger: secret output is redacted in the ledger",
          "4821" not in log and "redacted" in log, log[-120:])
    check("T12 ledger: the live reply still shows the value",
          e.handle("recall pin") == "4821")
    shutil.rmtree(d, True)


def t13_slots():
    e, d = fresh("t13")
    ask = e.handle("emi 500000 8.5")
    check("T13 slots: a partial command asks one question",
          "how many months" in ask.lower(), ask[:60])
    out = e.handle("240")
    check("T13 slots: the answer completes and runs the command",
          "4,339" in out, out[:60])
    check("T13 slots: cancel clears the question",
          e.handle("split 1000").lower().startswith("split") and
          e.handle("cancel") == "Cancelled." and "Nothing" in e.handle("tasks"),
          "cancel path")
    shutil.rmtree(d, True)


def t14_context():
    e, d = fresh("t14")
    e.handle("add buy milk")
    out = e.handle("again")
    check("T14 context: 'again' repeats the last command",
          out == "Added." and len(e.S["tasks"]) == 2, out[:40])
    shutil.rmtree(d, True)


def t15_recur():
    e, d = fresh("t15")
    e.handle("recur daily water plants")
    e.handle("done 1")
    check("T15 recur: a recurring task can be completed", e.S["tasks"][0]["done"])
    e.S["recur"]["0"] = "2000-01-01"
    e.save()
    e2 = Engine(home=d)
    check("T15 recur: it reopens on a new day",
          e2.S["tasks"][0]["done"] is False, str(e2.S["tasks"][0]))
    e2.handle("due 1 2026-01-01")
    check("T15 recur: overdue lists it",
          "water plants" in e2.handle("overdue"), e2.handle("overdue")[:60])
    shutil.rmtree(d, True)


def t16_two_key():
    e, d = fresh("t16")
    e.handle("daily 09:00 brief")
    e.handle("2key on")
    gate = e.handle("unjob 1")
    check("T16 two-key: danger prints an approval code",
          "approve" in gate.lower(), gate[:70])
    check("T16 two-key: plain 'confirm' is refused",
          "Two-key is on" in e.handle("confirm"))
    import re as _re
    code = _re.search(r"approve (\w+)", e.handle("unjob 1") or "")
    out = e.handle("approve " + code.group(1)) if code else ""
    check("T16 two-key: the code completes the action", out == "Removed.", out[:40])
    shutil.rmtree(d, True)


def t17_safe_delete():
    e, d = fresh("t17")
    f = d / "junk.txt"
    f.write_text("x", "utf-8")
    first = e.handle("safe delete %s" % f)
    check("T17 quarantine: safe delete is danger-gated",
          first.startswith("[danger]") and "Affects: 1" in first, first[:70])
    e.handle("confirm")
    check("T17 quarantine: the file left its original path", not f.exists())
    check("T17 quarantine: it landed in quarantine",
          any((d / "quarantine").iterdir()))
    e.handle("undo")
    check("T17 quarantine: undo restores it", f.exists())
    shutil.rmtree(d, True)


def t18_learn():
    e, d = fresh("t18")
    e.handle("card add What is 2+2?|4")
    q = e.handle("review")
    check("T18 cards: review shows the question", q.startswith("Q: What is 2+2?"), q[:50])
    out = e.handle("grade 5")
    check("T18 cards: a grade schedules the next review",
          "Next in 1 day" in out and "A: 4" in out, out[:60])
    check("T18 cards: nothing due afterwards", "Nothing due" in e.handle("review"))
    shutil.rmtree(d, True)


def t19_data():
    e, d = fresh("t19")
    csv_path = d / "people.csv"
    csv_path.write_text("name,age\nAsha,34\nRavi,41\n", "utf-8")
    out = e.handle("importcsv %s people" % csv_path)
    check("T19 data: CSV imports", "2 row(s)" in out, out[:60])
    rows = e.handle("sql SELECT name FROM people ORDER BY name")
    check("T19 data: SQL reads it back", "Asha" in rows and "Ravi" in rows, rows[:60])
    check("T19 data: writes are refused",
          "Read-only" in e.handle("sql DROP TABLE people"))
    shutil.rmtree(d, True)


def t20_files():
    e, d = fresh("t20")
    a = d / "a.txt"
    b = d / "b.txt"
    a.write_text("same bytes", "utf-8")
    b.write_text("same bytes", "utf-8")
    import packs.files as PF
    by_size = {}
    for p in (a, b):
        by_size.setdefault(p.stat().st_size, []).append(p)
    h1, h2 = PF._sha(a), PF._sha(b)
    check("T20 files: identical files hash identically", h1 == h2 and len(h1) == 64, h1[:12])
    check("T20 files: size helper formats", PF._h(1536) == "1.5KB", PF._h(1536))
    shutil.rmtree(d, True)


def t21_quarantine():
    e, d = fresh("t21")
    f = d / "notes.txt"
    f.write_text("hello", "utf-8")
    e.handle("safe delete %s" % f)
    e.handle("confirm")
    listing = e.handle("quarantine")
    check("T21 quarantine: the file is listed", "notes.txt" in listing, listing[:60])
    e.handle("restore 1")
    out = e.handle("confirm")
    check("T21 quarantine: restore puts it back at the original path",
          f.exists() and "Restored" in out, out[:60])
    check("T21 quarantine: the listing empties", "empty" in e.handle("quarantine"))
    shutil.rmtree(d, True)


def t22_net_worth():
    e, d = fresh("t22")
    e.handle("asset cash 50000")
    e.handle("asset gold 120000")
    e.handle("debt card 40000 36")
    out = e.handle("net worth")
    check("T22 net worth: assets minus debts",
          "170,000" in out and "40,000" in out and "130,000" in out, out.replace("\n", " | ")[:90])
    order = e.handle("debt snowball 5000")
    check("T22 net worth: avalanche puts the dearest debt first",
          order.startswith("avalanche order: card"), order[:60])
    check("T22 net worth: the payoff terminates", "month(s)" in order)
    shutil.rmtree(d, True)


def t23_subs():
    e, d = fresh("t23")
    e.S["spend"] = [{"d": "2026-10-05", "amt": 199.0, "cat": "netflix"},
                    {"d": "2026-11-05", "amt": 199.0, "cat": "netflix"},
                    {"d": "2026-11-06", "amt": 40.0, "cat": "misc"}]
    e.save()
    out = e.handle("subs audit")
    check("T23 subs: a charge repeating across months is flagged",
          "netflix" in out and "2 months" in out, out[:70])
    check("T23 subs: one-off spend is not flagged", "misc" not in out, out[:70])
    shutil.rmtree(d, True)


def t24_csv():
    e, d = fresh("t24")
    a = d / "a.csv"
    b = d / "b.csv"
    a.write_text("id,name,age\n1,Asha,34\n2,Ravi,41\n3,Meera,29\n", "utf-8")
    b.write_text("id,city\n1,Pune\n2,Surat\n3,Bhopal\n", "utf-8")
    out = e.handle("csv filter age>30 %s" % a)
    check("T24 csv: filter keeps the matching rows",
          "Asha" in out and "Ravi" in out and "Meera" not in out, out.replace("\n", " ")[:80])
    out = e.handle("csv sort age desc %s" % a)
    check("T24 csv: sort orders numerically",
          out.splitlines()[1].startswith("2"), out.splitlines()[1][:40])
    out = e.handle("csv join id %s %s" % (a, b))
    check("T24 csv: join adds the right-hand columns",
          "Pune" in out and "city" in out and "3 joined" in out, out[-60:])
    chart = e.handle("chart 3,7,12")
    check("T24 csv: chart scales bars to the max",
          chart.splitlines()[2].count("#") == 40, chart.splitlines()[2][:50])
    shutil.rmtree(d, True)


def t25_replay():
    e, d = fresh("t25")
    e.handle("add one")
    for i in range(30):          # snapshots are written every 25 mutating commands
        e.handle("add t%d" % i)
    snaps = sorted((d / "snapshots").glob("*.json"))
    check("T25 replay: snapshots are written on write bursts", len(snaps) >= 1, str(len(snaps)))
    if not snaps:
        shutil.rmtree(d, True)
        return
    stamp = datetime.datetime.strptime(snaps[0].stem, "%Y%m%dT%H%M%S").isoformat(timespec="seconds")
    before = len(e.S["tasks"])
    out = e.handle("replay " + stamp)
    check("T25 replay: it reports a reconstruction", "Replayed" in out, out[:70])
    check("T25 replay: live state is untouched", len(e.S["tasks"]) == before)
    side = d / ("replay-" + stamp.replace(":", ""))
    check("T25 replay: the reconstruction is written to a side directory",
          (side / "state.json").exists(), str(side))
    shutil.rmtree(d, True)


def t26_triggers():
    e, d = fresh("t26")
    out = e.handle("when 22:30 then brief ; tasks")
    check("T26 triggers: a time trigger saves", out.startswith("Trigger 1 saved"), out[:60])
    check("T26 triggers: a bad condition is explained",
          "Unrecognised" in e.handle("when bogus then tasks"))
    check("T26 triggers: an action that matches no rule is rejected",
          "does not match any rule" in e.handle("when 22:30 then qwertyuiop zzz"))
    e.handle("when every 30m then brief")
    e.handle("when not did meds by 21:00 then notify Meds not logged")
    listing = e.handle("triggers")
    check("T26 triggers: all three are listed",
          "22:30" in listing and "1800s" in listing and "not did meds" in listing,
          listing.replace("\n", " | ")[:90])
    import sys as _sys
    mod = next((m for n, m in _sys.modules.items()
                if n.startswith("pico_pack_triggers") and hasattr(m, "tick")), None)
    if mod is None:
        check("T26 triggers: pack reachable", False, "not loaded")
    else:
        now = datetime.datetime.now().replace(hour=22, minute=30, second=0, microsecond=0)
        first = mod.tick(now)
        second = mod.tick(now)
        check("T26 triggers: a time trigger fires once",
              any("brief" in " ".join(a) for _, a, _ in first) and not second,
              "%d / %d" % (len(first), len(second)))
    shutil.rmtree(d, True)


def t27_chain():
    e, d = fresh("t27")
    e.handle("chain morning: add stretch ; tasks")
    out = e.handle("chain morning")
    check("T27 chain: a named sequence runs every step",
          "Added." in out and "stretch" in out, out.replace("\n", " ")[:70])
    check("T27 chain: an unknown name says how to define one",
          "Define one" in e.handle("chain nope"))
    e.handle("chain bad: wa bob hi")
    check("T27 chain: a send-tier step is refused inside a chain",
          "skipped" in e.handle("chain bad"), e.handle("chain bad")[:80])
    shutil.rmtree(d, True)


def t28_loop_pivot():
    e, d = fresh("t28")
    csv_path = d / "rows.csv"
    csv_path.write_text("name,city,amt\nAsha,Pune,100\nRavi,Pune,250\nMeera,Surat,90\n", "utf-8")
    out = e.handle("for each row in %s then add call {name}" % csv_path)
    check("T28 loop: every row runs the command", "3 of 3" in out, out[:50])
    check("T28 loop: placeholders were substituted",
          [t["text"] for t in e.S["tasks"]] == ["call Asha", "call Ravi", "call Meera"],
          str([t["text"] for t in e.S["tasks"]]))
    piv = e.handle("csv pivot city sum amt %s" % csv_path)
    check("T28 loop: pivot groups and totals",
          "350" in piv and "90" in piv and "440" in piv, piv.replace("\n", " | ")[:80])
    check("T28 loop: a send-tier body is refused",
          "Refused" in e.handle("for each row in %s then wa bob hi" % csv_path))
    shutil.rmtree(d, True)


def t29_concurrency():
    e, d = fresh("t29")
    import threading as _th
    errs = []

    def hammer(n):
        try:
            for i in range(60):
                e.handle("add t%d_%d" % (n, i))
        except Exception as ex:
            errs.append(ex)

    ts = [_th.Thread(target=hammer, args=(k,)) for k in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    check("T29 concurrency: parallel writers do not collide", not errs, str(errs[:1]))
    check("T29 concurrency: no state is lost", len(e.S["tasks"]) == 180,
          str(len(e.S["tasks"])))
    reloaded = Engine(home=d, quiet=True)
    check("T29 concurrency: the file on disk is valid", len(reloaded.S["tasks"]) == 180)
    check("T29 concurrency: no temp files left behind",
          not list(d.glob("state.json.tmp*")))
    shutil.rmtree(d, True)


def t30_phone_approval():
    e, d = fresh("t30")
    e.handle("daily 09:00 brief")
    out = e.handle("2key phone")
    check("T30 phone: two-key phone mode is announced", "phone only" in out, out[:60])
    gate = e.handle("unjob 1")
    import re as _re
    code = _re.search(r"approve (\w+)", gate or "")
    check("T30 phone: a code is issued", bool(code), gate[:60])
    if code:
        check("T30 phone: the desk is refused",
              "phone-only" in e.handle("approve " + code.group(1)))
        e.approve_source = "phone"
        out = e.handle("approve " + code.group(1))
        e.approve_source = None
        check("T30 phone: the phone completes it", out == "Removed.", out[:40])
    shutil.rmtree(d, True)


def _trig_mod():
    import sys as _sys
    return next((m for n, m in _sys.modules.items()
                 if n.startswith("pico_pack_triggers") and hasattr(m, "tick")), None)


def t31_unless():
    e, d = fresh("t31")
    e.handle("when 22:30 unless away then add fired")
    e.handle("when 22:30 unless weekend then add weekendjob")
    e.handle("when 22:30 unless bogus then tasks")
    check("T31 unless: an unknown condition is refused",
          "Unrecognised unless" in e.handle("when 22:30 unless bogus then tasks"))
    mod = _trig_mod()
    if mod is None:
        check("T31 unless: pack reachable", False, "not loaded")
        shutil.rmtree(d, True)
        return
    now = datetime.datetime.now().replace(hour=22, minute=30, second=0, microsecond=0)
    e.handle("away on")
    mod.tick(now)
    check("T31 unless: `unless away` blocks its trigger",
          "fired" not in [x["text"] for x in e.S["tasks"]],
          str([x["text"] for x in e.S["tasks"]]))
    e.handle("away off")
    fired = mod.tick(now)
    texts = [t["text"] for t in e.S["tasks"]]
    check("T31 unless: it fires once away is off", "fired" in texts, str(texts))
    is_weekend = datetime.date.today().weekday() >= 5
    check("T31 unless: `unless weekend` vetoes on a weekend, and only then",
          ("weekendjob" in texts) == (not is_weekend),
          "%s, weekend=%s" % (texts, is_weekend))
    shutil.rmtree(d, True)


def t32_watch_clip():
    e, d = fresh("t32")
    out = e.handle("watch %s then count {file}" % d)
    check("T32 watch: a folder watch is saved", out.startswith("Watching"), out[:60])
    check("T32 watch: an invalid action is refused",
          "does not match any rule" in e.handle("watch %s then zzz" % d))
    out = e.handle("when clip matches ^ORD[0-9]+ then notify Order {clip}")
    check("T32 watch: a clipboard trigger is saved", out.startswith("Trigger"), out[:60])
    listing = e.handle("triggers")
    check("T32 watch: both appear in the list",
          "file" in listing and "clip matches" in listing, listing.replace("\n", " | ")[:90])
    mod = _trig_mod()
    if mod:
        check("T32 watch: clipboard read degrades to empty, never raises",
              isinstance(mod._clip(), str))
    shutil.rmtree(d, True)


def t33_retry():
    e, d = fresh("t33")
    mod = _trig_mod()
    if mod is None:
        check("T33 retry: pack reachable", False, "not loaded")
        shutil.rmtree(d, True)
        return
    calls = {"n": 0}

    def flaky(cmd):
        calls["n"] += 1
        return "Command failed: staged" if calls["n"] == 1 else "ok"

    real = mod.E.handle
    mod.E.handle = flaky
    try:
        out = mod.run_actions(["tasks"])
    finally:
        mod.E.handle = real
    check("T33 retry: a failing action is retried once", calls["n"] == 2, str(calls))
    check("T33 retry: the retry result is what is reported", out == ["ok"], str(out))
    check("T33 retry: send and danger actions are still refused",
          "skipped" in mod.run_actions(["wa bob hi"])[0])
    shutil.rmtree(d, True)


def t34_multikey_pivot():
    e, d = fresh("t34")
    csv_path = d / "rows.csv"
    csv_path.write_text("city,plan,amt\nPune,pro,100\nPune,basic,50\nSurat,pro,90\n", "utf-8")
    out = e.handle("csv pivot city,plan sum amt %s" % csv_path)
    check("T34 pivot: two keys group together",
          "Pune / pro" in out and "Pune / basic" in out and "240" in out,
          out.replace("\n", " | ")[:120])
    shutil.rmtree(d, True)


def t35_or_conditions():
    e, d = fresh("t35")
    out = e.handle("when 22:30 unless away or weekend then add fired")
    check("T35 or: a two-condition unless is accepted", out.startswith("Trigger"), out[:60])
    check("T35 or: one bad condition rejects the pair",
          "Unrecognised unless" in e.handle("when 22:30 unless bogus or away then tasks"))
    listing = e.handle("triggers")
    check("T35 or: the listing renders both conditions",
          "away or weekend" in listing, listing.replace("\n", " | ")[:80])
    mod = _trig_mod()
    if mod:
        now = datetime.datetime.now().replace(hour=22, minute=30, second=0, microsecond=0)
        e.handle("away on")
        mod.tick(now)
        e.handle("away off")
        mod.tick(now)
        texts = [x["text"] for x in e.S["tasks"]]
        weekend = datetime.date.today().weekday() >= 5
        check("T35 or: any true condition vetoes",
              ("fired" in texts) is (not weekend), str(texts))
    shutil.rmtree(d, True)


def t36_history():
    e, d = fresh("t36")
    e.handle("when every 1m then add ticked")
    mod = _trig_mod()
    if mod is None:
        check("T36 history: pack reachable", False, "not loaded")
        shutil.rmtree(d, True)
        return
    now = datetime.datetime.now()
    mod.tick(now)
    mod.tick(now + datetime.timedelta(minutes=2))
    log = e.handle("trigger log")
    check("T36 history: firings are recorded", "ok" in log and log.count("ok") >= 2, log[:90])
    check("T36 history: the listing shows the count", "firing(s) recorded" in e.handle("triggers"))
    shutil.rmtree(d, True)


def t37_three_key_pivot():
    e, d = fresh("t37")
    p = d / "p.csv"
    p.write_text("a,b,c,amt\nx,y,z,10\nx,y,z,5\nx,q,z,7\n", "utf-8")
    out = e.handle("csv pivot a,b,c sum amt %s" % p)
    check("T37 pivot: three keys group and total",
          "x / y / z" in out and "15" in out and "22" in out,
          out.replace("\n", " | ")[:100])
    shutil.rmtree(d, True)


def t38_version_consistency():
    """The engine, the console and the README must agree on the version."""
    from pico.engine import __version__ as engine_version
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    chip = re.search(r'id="ver">v([\d.]+)<', html)
    boot = re.search(r'\$\("#ver"\)\.textContent="v([\d.]+)"', html)
    badge = re.search(r'aria-label="version: ([\d.]+)"',
                      (ROOT / "docs/assets/badge-version.svg").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    found = {
        "console chip": chip.group(1) if chip else None,
        "console boot": boot.group(1) if boot else None,
        "badge": badge.group(1) if badge else None,
        "readme badge alt": ("version " + engine_version) in readme,
    }
    check("T38 version: the console chip matches the engine",
          found["console chip"] == engine_version, str(found))
    check("T38 version: the boot script matches the engine",
          found["console boot"] == engine_version, str(found))
    check("T38 version: the badge matches the engine",
          found["badge"] == engine_version, str(found))


def t39_module_split():
    import pico.base as B
    import pico.ladder as L
    import pico.ledger as G
    import pico.store as S
    from pico.engine import Engine
    check("T39 split: Engine composes store, ladder and ledger",
          all(issubclass(Engine, m) for m in (S.StoreMixin, L.LadderMixin, G.LedgerMixin)),
          str(Engine.__mro__[:4]))
    for mod, cls, names in (
            (S, "StoreMixin", ["save", "_load_state", "replay", "timeline"]),
            (L, "LadderMixin", ["resolve", "match_rule", "risk_of", "_slot_match"]),
            (G, "LedgerMixin", ["_run", "undo", "set_inverse", "_apply_inverse"])):
        have = getattr(mod, cls, None)
        check("T39 split: %s owns its methods" % cls,
              have is not None and all(hasattr(have, n) for n in names), cls)
    check("T39 split: base holds the shared helpers",
          all(hasattr(B, n) for n in ("safe_eval", "convert", "normalize", "STATE_DEFAULT")))
    check("T39 split: engine re-exports what packs import",
          all(hasattr(__import__("pico.engine", fromlist=["x"]), n)
              for n in ("Engine", "safe_eval", "convert", "normalize", "__version__")))
    e, d = fresh("t39")
    check("T39 split: an engine still works end to end",
          "4,339" in e.handle("emi 500000 8.5 240"))
    shutil.rmtree(d, True)


def t40_backoff():
    e, d = fresh("t40")
    e.handle("when every 1m then tasks")
    mod = _trig_mod()
    if mod is None:
        check("T40 backoff: pack reachable", False, "not loaded")
        shutil.rmtree(d, True)
        return
    real = mod.E.handle
    mod.E.handle = lambda cmd: "Command failed: staged"
    now = datetime.datetime.now()
    try:
        mod.tick(now)
        soon = mod.tick(now + datetime.timedelta(seconds=90))
        later = mod.tick(now + datetime.timedelta(minutes=20))
    finally:
        mod.E.handle = real
    listing = e.handle("triggers")
    check("T40 backoff: the rule shows that an action is backing off",
          "backing off" in listing, listing.replace("\n", " | ")[:90])
    soon_out = " ".join(str(x) for _, _, r in soon for x in r)
    check("T40 backoff: the next firing skips the failing action",
          "skipped" in soon_out, soon_out[:80])
    later_out = " ".join(str(x) for _, _, r in later for x in r)
    check("T40 backoff: it retries once the window passes",
          "skipped" not in later_out, later_out[:80])
    shutil.rmtree(d, True)


def t41_pivot_having():
    e, d = fresh("t41")
    p = d / "p.csv"
    p.write_text("city,amt\nPune,350\nSurat,90\nNagpur,10\n", "utf-8")
    out = e.handle("csv pivot city sum amt %s having sum>100" % p)
    check("T41 having: only groups above the threshold survive",
          "Pune" in out and "Surat" not in out and "Nagpur" not in out,
          out.replace("\n", " | ")[:90])
    check("T41 having: the total reflects the survivors", "350" in out)
    check("T41 having: an impossible threshold says so",
          "No group satisfies" in e.handle("csv pivot city sum amt %s having sum>99999" % p))
    check("T41 having: a malformed clause is explained",
          "looks like" in e.handle("csv pivot city sum amt %s having sumxx" % p))
    shutil.rmtree(d, True)


def t42_core_modules():
    import pico.rules as R
    from pico.engine import Engine
    e, d = fresh("t42")
    check("T42 core: register records the command modules",
          len(e.core_modules) == 8, str(len(e.core_modules)))
    check("T42 core: every module can see the engine",
          all(getattr(m, "E", None) is e for m in e.core_modules))
    e2, d2 = fresh("t42b")
    check("T42 core: a second engine rebinds them",
          all(getattr(m, "E", None) is e2 for m in e2.core_modules)
          and e.handle("tasks") == "Nothing pending.")
    check("T42 core: the blast-radius previews survived the split",
          all(hasattr(fn, "preview") for fn in
              (R.tidy, R.safe_delete, R.restore)))
    shutil.rmtree(d, True)
    shutil.rmtree(d2, True)


def t43_action_backoff():
    e, d = fresh("t43")
    e.handle("when every 1m then add good ; tasks")
    mod = _trig_mod()
    if mod is None:
        check("T43 action backoff: pack reachable", False, "not loaded")
        shutil.rmtree(d, True)
        return
    real = mod.E.handle
    mod.E.handle = lambda cmd: ("Command failed: staged"
                                if cmd.startswith("add") else real(cmd))
    now = datetime.datetime.now()
    try:
        mod.tick(now)
        soon = mod.tick(now + datetime.timedelta(seconds=90))
    finally:
        mod.E.handle = real
    out = " ".join(str(x) for _, _, r in soon for x in r)
    check("T43 action backoff: the failing action is skipped",
          "backing off" in out, out[:90])
    check("T43 action backoff: the healthy action still runs",
          "Nothing pending" in out or "task" in out.lower(), out[:90])
    shutil.rmtree(d, True)


def t44_pivot_order():
    e, d = fresh("t44")
    p = d / "p.csv"
    p.write_text("city,amt\nPune,350\nSurat,90\nNagpur,10\n", "utf-8")
    def first(cmd):
        rows = e.handle(cmd).splitlines()
        return rows[1].split()[0] if len(rows) > 1 else ""
    base = "csv pivot city sum amt %s" % p
    check("T44 order: default is value descending", first(base) == "Pune")
    check("T44 order: key ascending", first(base + " order by key") == "Nagpur")
    check("T44 order: key descending", first(base + " order by key desc") == "Surat")
    check("T44 order: value ascending", first(base + " order by value asc") == "Nagpur")
    shutil.rmtree(d, True)


def t45_installable():
    web = ROOT / "web"
    man = web / "manifest.webmanifest"
    check("T45 install: the manifest exists", man.exists())
    import json as _json
    m = _json.loads(man.read_text(encoding="utf-8"))
    check("T45 install: the manifest is valid and points at the console",
          m.get("start_url") == "./app.html" and m.get("display") == "standalone", str(m)[:80])
    check("T45 install: both icon sizes are declared",
          {i["sizes"] for i in m["icons"]} == {"192x192", "512x512"})
    for name in ("icon-192.png", "icon-512.png"):
        check("T45 install: %s exists" % name, (web / name).exists())
    sw = (web / "sw.js").read_text(encoding="utf-8")
    check("T45 install: the worker never caches the engine",
          '"/cmd"' in sw or "endsWith(\"/cmd\")" in sw, sw[:60])
    html = (web / "index.html").read_text(encoding="utf-8")
    check("T45 install: the console links the manifest",
          'rel="manifest"' in html and "serviceWorker" in html)
    check("T45 install: the demo copy is in sync",
          (ROOT / "docs" / "app.html").read_bytes() == (web / "index.html").read_bytes())


def t46_quarantine_module():
    import pico.cmd_files as F
    import pico.cmd_quarantine as Q
    from pico.engine import Engine
    e, d = fresh("t46")
    check("T46 modules: the quarantine lifecycle has its own module",
          hasattr(Q, "safe_delete") and hasattr(Q, "restore") and hasattr(Q, "sweep"))
    check("T46 modules: cmd_files no longer carries it",
          not hasattr(F, "safe_delete") and not hasattr(F, "restore"))
    check("T46 modules: both are registered with the engine",
          F in e.core_modules and Q in e.core_modules)
    check("T46 modules: both can see the engine",
          F.E is e and Q.E is e)
    check("T46 modules: previews survived",
          hasattr(F.tidy, "preview") and hasattr(Q.safe_delete, "preview"))
    shutil.rmtree(d, True)


def t47_sort_types():
    e, d = fresh("t47")
    p = d / "m.csv"
    p.write_text("name,score\nAsha,9\nRavi,10\nMeera,2\nZoya,n/a\n", "utf-8")

    def col(cmd, i=1):
        return [ln.split(" | ")[i] for ln in e.handle(cmd).splitlines()[1:5]]

    base = "csv sort %s %s"
    check("T47 sort: auto keeps numbers numeric and text last",
          col(base % ("score", p)) == ["2", "9", "10", "n/a"], str(col(base % ("score", p))))
    check("T47 sort: :number sorts numerically",
          col(base % ("score:number desc", p)) == ["10", "9", "2", "n/a"],
          str(col(base % ("score:number desc", p))))
    check("T47 sort: :text sorts lexicographically",
          col(base % ("score:text", p)) == ["10", "2", "9", "n/a"],
          str(col(base % ("score:text", p))))
    check("T47 sort: an unknown type is explained",
          "number or :text" in e.handle(base % ("score:date", p)))
    shutil.rmtree(d, True)


def t48_install_prompt():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    check("T48 prompt: the bar exists in the markup", 'id="install"' in html)
    check("T48 prompt: it reacts to beforeinstallprompt",
          "beforeinstallprompt" in html and "deferredInstall" in html)
    check("T48 prompt: dismissal is remembered",
          'pico.installDismissed' in html)
    check("T48 prompt: it hides once installed",
          "display-mode: standalone" in html and "appinstalled" in html)
    check("T48 prompt: iOS gets an instruction instead",
          "Add to Home Screen" in html)
    check("T48 prompt: it never shows from file://",
          "location.protocol.startsWith" in html)
    shutil.rmtree(fresh("t48")[1], True)


def t49_dispatch_module():
    import pico.dispatch as D
    from pico.engine import Engine
    check("T49 dispatch: handle lives in its own module",
          hasattr(D, "DispatchMixin") and hasattr(D.DispatchMixin, "handle")
          and hasattr(D.DispatchMixin, "_handle"))
    check("T49 dispatch: the engine composes it", issubclass(Engine, D.DispatchMixin))
    check("T49 dispatch: engine.py no longer defines handle",
          "def handle" not in (ROOT / "pico" / "engine.py").read_text(encoding="utf-8"))
    e, d = fresh("t49")
    check("T49 dispatch: a command still round-trips",
          "4,339" in e.handle("emi 500000 8.5 240"))
    shutil.rmtree(d, True)


def t50_filter_types():
    e, d = fresh("t50")
    p = d / "m.csv"
    p.write_text("name,score\nAsha,9\nRavi,10\nMeera,2\nZoya,n/a\n", "utf-8")
    base = "csv filter score%s>9 %s"

    def names(suffix):
        out = e.handle(base % (suffix, p))
        return [ln.split(" | ")[0] for ln in out.splitlines()[1:-1]]

    check("T50 filter: auto compares numbers numerically and text as text",
          names("") == ["Ravi", "Zoya"], str(names("")))
    check("T50 filter: :number drops the non-numeric row", names(":number") == ["Ravi"],
          str(names(":number")))
    check("T50 filter: :text compares lexicographically", names(":text") == ["Zoya"],
          str(names(":text")))
    check("T50 filter: an unknown type is explained",
          "number or :text" in e.handle(base % (":date", p)))
    shutil.rmtree(d, True)


def t51_update_prompt():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    sw = (ROOT / "web" / "sw.js").read_text(encoding="utf-8")
    check("T51 update: the bar exists", 'id="update"' in html)
    check("T51 update: it fires only for an update, not a first install",
          "navigator.serviceWorker.controller" in html and "updatefound" in html)
    check("T51 update: reload waits for the new worker",
          "controllerchange" in html and "skipWaiting" in sw)
    check("T51 update: the cache name is versioned", "pico-" in sw and "CACHE" in sw)
    check("T51 update: the demo copy is in sync",
          (ROOT / "docs" / "sw.js").read_bytes() == (ROOT / "web" / "sw.js").read_bytes())


def t52_doctor():
    e, d = fresh("t52")
    out = e.handle("doctor")
    check("T52 doctor: it runs and reports", out.startswith("pico ") and "check(s)" in out, out[:50])
    check("T52 doctor: a fresh home is all ok", "0 fail" in out, out.splitlines()[-1])
    check("T52 doctor: it names the rules count", "rules" in out)
    check("T52 doctor: it lists the loaded packs",
          "finance" in out and "triggers" in out)
    e.handle("add one")
    e.handle("habit add walk")
    out2 = e.handle("doctor")
    check("T52 doctor: it sees the files that now exist",
          "jobs.json" in out2 or "habits.json" in out2, out2[:60])
    (d / "state.json").write_text("{broken", "utf-8")
    e2 = Engine(home=d, quiet=True)
    check("T52 doctor: a corrupt state is caught, not fatal",
          "0 fail" in e2.handle("doctor") or "quarantined" in e2.handle("doctor"),
          e2.handle("doctor").splitlines()[-1])
    shutil.rmtree(d, True)


def t53_pivot_types():
    e, d = fresh("t53")
    p = d / "n.csv"
    p.write_text("zip,amt\n9,100\n10,200\n2,50\n", "utf-8")
    base = "csv pivot %s sum amt %s order by key"

    def first(key):
        rows = e.handle(base % (key, p)).splitlines()
        return [ln.split()[0] for ln in rows[1:4]]

    check("T53 pivot types: default sorts keys as text",
          first("zip") == ["10", "2", "9"], str(first("zip")))
    check("T53 pivot types: :number sorts numerically",
          first("zip:number") == ["2", "9", "10"], str(first("zip:number")))
    check("T53 pivot types: an unknown key type is explained",
          "number or :text" in e.handle("csv pivot zip:date sum amt %s" % p))
    shutil.rmtree(d, True)


def t54_offline_chip():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    check("T54 offline: the chip has an offline state",
          'data-state="offline"' in html)
    check("T54 offline: a failed request marks it",
          "markOffline" in html and "Connection lost" not in html)
    check("T54 offline: it polls until the engine returns",
          "setInterval" in html and "markOnline" in html)
    check("T54 offline: the message says how to start the engine",
          "pico.py --ui" in html)
    shutil.rmtree(fresh("t54")[1], True)


def t55_doctor_fix():
    e, d = fresh("t55")
    first = e.handle("doctor fix")
    check("T55 fix: the first run only creates the missing directories",
          "created" in first and "quarantined" not in first, first.replace("\n", " | ")[:90])
    check("T55 fix: a second run has nothing left to do",
          "Nothing to fix" in e.handle("doctor fix"))

    (d / "state.json.tmp.1.2").write_text("x", "utf-8")
    (d / "habits.json").write_text("{broken", "utf-8")
    for i in range(16):
        (d / "snapshots" / ("202601%02dT000000.json" % i)).write_text("{}", "utf-8")
    (d / "web.token").write_text("", "utf-8")
    q = d / "quarantine"
    q.mkdir(exist_ok=True)
    (q / "index.json").write_text(json.dumps({"gone.txt": "/tmp/x", "here.txt": "/tmp/y"}), "utf-8")
    (q / "here.txt").write_text("y", "utf-8")

    out = e.handle("doctor fix")
    check("T55 fix: a stray temp file is removed",
          not list(d.glob("state.json.tmp*")) and "stray" in out)
    check("T55 fix: an unreadable pack file is quarantined, not deleted",
          list(d.glob("habits.json.corrupt-*")) and "habits.json" in out)
    check("T55 fix: snapshots are pruned to the rolling limit",
          len(list((d / "snapshots").glob("*.json"))) == 12)
    check("T55 fix: an empty token is regenerated",
          bool((d / "web.token").read_text("utf-8").strip()))
    idx = json.loads((q / "index.json").read_text("utf-8"))
    check("T55 fix: a stale quarantine index entry is pruned",
          "gone.txt" not in idx and "here.txt" in idx, str(idx))
    check("T55 fix: doctor is clean afterwards",
          "0 fail" in e.handle("doctor"), e.handle("doctor").splitlines()[-1])
    shutil.rmtree(d, True)


def t56_join_types():
    e, d = fresh("t56")
    a, b = d / "a.csv", d / "b.csv"
    a.write_text("id,name\n1,Asha\n01,Ravi\n2,Meera\n", "utf-8")
    b.write_text("id,city\n1,Pune\n2,Surat\n", "utf-8")
    base = "csv join id%s %s %s"

    def rows(kind):
        out = e.handle(base % (kind, a, b))
        return out.splitlines()[-1]

    check("T56 join: :number treats 01 as 1", "3 joined" in rows(":number"), rows(":number"))
    check("T56 join: :text keeps 01 distinct", "2 joined" in rows(":text"), rows(":text"))
    check("T56 join: an unknown key type is explained",
          "number or :text" in e.handle(base % (":date", a, b)))
    shutil.rmtree(d, True)


def t57_android_doc():
    doc = (ROOT / "docs" / "ANDROID.md").read_text(encoding="utf-8")
    check("T57 android: the doc exists and names the two routes",
          "Route 1" in doc and "Route 2" in doc)
    check("T57 android: it explains why there is no APK", "Why no APK" in doc)
    check("T57 android: it states the LAN risk", "--lan" in doc and "trust" in doc)
    check("T57 android: the install command it quotes exists",
          (ROOT / "install.sh").exists() and "sh install.sh" in doc)
    check("T57 android: the README links to it",
          "docs/ANDROID.md" in (ROOT / "README.md").read_text(encoding="utf-8"))


def t58_thread_health():
    e, d = fresh("t58")
    out = e.handle("doctor")
    line = next((ln for ln in out.splitlines() if ln.startswith(("ok    threads",
                                                                "warn  threads"))), "")
    check("T58 threads: doctor reports a heartbeat line", bool(line), out[:60])
    check("T58 threads: the scheduler is running", "schedule" in line, line[:90])
    check("T58 threads: a pack that never started is called idle, not stale",
          "idle: telegram" in line, line[:90])
    check("T58 threads: a fresh heartbeat is not a warning", line.startswith("ok"), line[:40])

    # a stale heartbeat must warn
    import time as _t
    sched = next((m for m in e.pack_modules
                  if getattr(m, "__name__", "").endswith("schedule")), None)
    if sched is not None:
        real = sched.LAST
        sched.LAST = _t.time() - 400
        try:
            stale = e.handle("doctor")
        finally:
            sched.LAST = real
        check("T58 threads: a stopped thread is a warning",
              "warn  threads" in stale, stale[:60])
    shutil.rmtree(d, True)


def t59_repair_module():
    import pico.cmd_doctor as D
    import pico.cmd_repair as R
    from pico.engine import Engine
    e, d = fresh("t59")
    check("T59 repair: fix has its own module",
          hasattr(R, "fix") and not hasattr(D, "fix"))
    check("T59 repair: both are registered with the engine",
          D in e.core_modules and R in e.core_modules)
    check("T59 repair: both can see the engine", D.E is e and R.E is e)
    check("T59 repair: doctor still reports", "check(s)" in e.handle("doctor"))
    check("T59 repair: fix still repairs", "fixed" in e.handle("doctor fix")
          or "Nothing to fix" in e.handle("doctor fix"))
    shutil.rmtree(d, True)


def t60_doctor_probe():
    e, d = fresh("t60")
    out = e.handle("doctor probe")
    check("T60 probe: it runs", out.startswith("pico ") and "pack(s)" in out, out[:50])
    check("T60 probe: every pack with rules answers", "0 fail" in out,
          out.splitlines()[-1])
    check("T60 probe: it names a command per pack",
          "'gst 100 18'" in out and "'jobs'" in out, out[:60])
    check("T60 probe: telegram is reported as having no rules",
          "no probe (no rules)" in out)
    n_before = len(e.ledger_file.read_text("utf-8").splitlines()) \
        if e.ledger_file.exists() else 0
    e.handle("doctor probe")
    n_after = len(e.ledger_file.read_text("utf-8").splitlines())
    check("T60 probe: the probes themselves are not logged",
          n_after == n_before + 1, "%d -> %d" % (n_before, n_after))
    check("T60 probe: it does not change state",
          e.S.get("tasks") == [] and e.S.get("spend") == [])
    shutil.rmtree(d, True)


def t61_probe_write():
    e, d = fresh("t61")
    out = e.handle("doctor probe write")
    check("T61 probe write: it runs", "probe write" in out and "write path(s)" in out, out[:60])
    check("T61 probe write: every write path answers", "0 fail" in out, out.splitlines()[-1])
    check("T61 probe write: it names the paths it exercised",
          "tidy" in out and "safe delete" in out and "restore" in out)
    check("T61 probe write: the scratch directory is gone",
          not list(d.glob("pico-probe-*")))
    check("T61 probe write: no backup zip is left behind",
          not list((d / "backups").glob("*.zip")) if (d / "backups").exists() else True)
    check("T61 probe write: nothing is left in quarantine",
          not [p for p in (d / "quarantine").iterdir()
               if p.is_file() and p.name != "index.json"]
          if (d / "quarantine").exists() else True)
    shutil.rmtree(d, True)


def t62_path_arguments():
    e, d = fresh("t62")
    case = d / "case"
    case.mkdir()
    (case / "one.txt").write_text("same", "utf-8")
    (case / "two.txt").write_text("same", "utf-8")
    (case / "three.txt").write_text("different", "utf-8")

    out = e.handle("dedupe files %s" % case)
    check("T62 paths: dedupe files honours the given path",
          "two.txt" in out and "one.txt" in out, out.replace("\n", " | ")[:90])
    out = e.handle("big files 2 %s" % case)
    listed = [ln for ln in out.splitlines() if ln.strip().endswith(".txt")]
    check("T62 paths: big files honours the given path",
          len(listed) == 2 and all("case" in ln for ln in listed),
          out.replace("\n", " | ")[:90])
    out = e.handle("old files 1d %s" % case)
    check("T62 paths: old files honours the given path", "case" in out or "Nothing" in out,
          out[:70])
    check("T62 paths: `dedupe files` is not swallowed by the text pack",
          "group(s)" in e.handle("dedupe files %s" % case))
    shutil.rmtree(d, True)


def t63_indic_keys():
    e, d = fresh("t63")
    check("T63 unicode: a Devanagari note key is accepted",
          e.handle("remember नाम=Sohil") == "Remembered नाम.", e.handle("remember नाम=Sohil"))
    check("T63 unicode: it reads back", e.handle("recall नाम") == "Sohil")
    check("T63 unicode: a Devanagari contact is accepted",
          "रवि" in e.handle("contact रवि=919999999999") + e.handle("contacts"))
    check("T63 unicode: a Devanagari site shortcut is accepted",
          "saved" in e.handle("site घर=https://example.com"))
    check("T63 unicode: a Devanagari chain name is accepted",
          e.handle("chain सुबह: tasks").startswith("Chain सुबह"))
    check("T63 unicode: the text of a task survives intact",
          "कल दूध" in (e.handle("add कल दूध लाना") + e.handle("tasks")))
    shutil.rmtree(d, True)


def t64_csv_edge_cases():
    e, d = fresh("t64")
    bom = d / "bom.csv"
    bom.write_bytes(b"\xef\xbb\xbfid,city\n1,Pune\n2,Surat\n")
    out = e.handle("csv pivot city count id %s" % bom)
    check("T64 csv: a BOM in the header is stripped",
          "No column" not in out and "city" in out, out.replace("\n", " | ")[:80])

    crlf = d / "crlf.csv"
    crlf.write_bytes(b"a,b\r\n1,2\r\n3,4\r\n")
    out = e.handle("csv pivot a sum b %s" % crlf)
    check("T64 csv: CRLF line endings parse", "4" in out and "2" in out, out[:60])

    dup = d / "dup.csv"
    dup.write_text("id,id\n1,2\n", "utf-8")
    out = e.handle("importcsv %s dup" % dup)
    check("T64 csv: duplicate headers are renamed, not fatal",
          "id_2" in out and "Command failed" not in out, out[:70])
    shutil.rmtree(d, True)


def t65_bounds():
    e, d = fresh("t65")
    check("T65 bounds: an impossible clock time is refused",
          "not a clock time" in e.handle("remind 25:99 x"))
    check("T65 bounds: a valid clock time still works",
          "Reminder at 18:30" in e.handle("remind 18:30 ok"))
    check("T65 bounds: an absurd timer is refused",
          "longer than 24 hours" in e.handle("timer 999999h x"))
    check("T65 bounds: a normal timer still arms", "Timer: 2h" in e.handle("timer 2h ok"))
    check("T65 bounds: a huge exponent is refused", "Arithmetic" in e.handle("calc 2**1000"))
    shutil.rmtree(d, True)


def t66_fill_single_pass():
    e, d = fresh("t66")
    e.handle("fill letter name={{body}} subject=S body=Hello sender=Me")
    out = d / ("letter_%s.txt" % datetime.date.today())
    text = out.read_text("utf-8") if out.exists() else ""
    check("T66 fill: a value containing a placeholder is data, not a template",
          "To: {{body}}" in text and "Dear {{body}}" in text, text[:80])
    check("T66 fill: the real body was still substituted", "Hello" in text)
    shutil.rmtree(d, True)


def t67_quoted_paths():
    e, d = fresh("t67")
    spaced = d / "with space"
    spaced.mkdir()
    (spaced / "f.txt").write_text("hello world", "utf-8")
    check("T67 quotes: count accepts a quoted path",
          "words 2" in e.handle('count "%s"' % (spaced / "f.txt")),
          e.handle('count "%s"' % (spaced / "f.txt"))[:60])
    check("T67 quotes: tidy accepts a quoted path",
          "Sorted" in e.handle('tidy "%s"' % spaced))
    check("T67 quotes: backup accepts a quoted path",
          "Backup" in e.handle('backup "%s"' % spaced))
    # tidy above moved the fixture into a category folder; make a fresh one
    (spaced / "g.txt").write_text("hello again", "utf-8")
    check("T67 quotes: single quotes work too",
          "words 2" in e.handle("count '%s'" % (spaced / "g.txt")),
          e.handle("count '%s'" % (spaced / "g.txt"))[:60])
    shutil.rmtree(d, True)


def t68_sql_pragma():
    e, d = fresh("t68")
    p = d / "x.csv"
    p.write_text("id,v\n1,2\n", "utf-8")
    e.handle("importcsv %s t1" % p)
    out = e.handle("sql PRAGMA table_info(t1)")
    check("T68 pragma: table_info works, as the message promises",
          "name" in out and "cid" in out, out[:70])
    check("T68 pragma: a schema-changing pragma is refused",
          "can change the database" in e.handle("sql PRAGMA writable_schema=ON"))
    check("T68 pragma: index_list is allowed",
          "Read-only" not in e.handle("sql PRAGMA index_list(t1)"))
    check("T68 pragma: a write statement is still refused",
          "Read-only" in e.handle("sql DELETE FROM t1"))
    shutil.rmtree(d, True)


def t69_dates():
    e, d = fresh("t69")
    check("T69 dates: a bad MM-DD is refused",
          "not a date" in e.handle("on 13-45 bad"))
    check("T69 dates: 02-29 is a legitimate recurring date",
          e.handle("on 02-29 leap") == "Saved.")
    check("T69 dates: a non-leap 29 February is refused",
          "not a date" in e.handle("on 2026-02-29 nope"))
    check("T69 dates: a leap 29 February is accepted",
          e.handle("on 2028-02-29 leap") == "Saved.")
    check("T69 dates: a bad due date is refused",
          "not a date" in e.handle("due 1 2026-13-45"))
    shutil.rmtree(d, True)


def t70_fuzzy_template():
    e, d = fresh("t70")
    e.handle("add one")
    out = e.handle("decide a")
    check("T70 fuzzy: a catalogue template is offered, not run",
          "Did you mean" in out and "decide A|B|C" in out, out.replace("\n", " | ")[:80])
    check("T70 fuzzy: a real decide still runs",
          "options" in e.handle("decide tea|coffee|water"))
    shutil.rmtree(d, True)


def t71_expired_confirm():
    e, d = fresh("t71")
    e.handle("wa bob hi")
    check("T71 expiry: the request is pending", "confirm" in e.pending)
    e.pending["at"] -= 200
    out = e.handle("confirm")
    check("T71 expiry: an expired confirmation says so, not 'no rule matched'",
          "expired" in out and "Nothing was run" in out, out[:70])
    check("T71 expiry: the pending request is cleared", "confirm" not in e.pending)
    e.handle("wa bob hi")
    e.pending["at"] -= 200
    check("T71 expiry: cancel after expiry is also clear",
          "expired" in e.handle("cancel"))
    shutil.rmtree(d, True)


def t72_ledger_rotation():
    e, d = fresh("t72")
    e.LEDGER_CAP = 120
    for i in range(260):
        e.handle("add item %d" % i)
    live = e.ledger_file
    gens = sorted(d.glob("ledger-*.jsonl"))
    check("T72 ledger: the file rotates at the cap", bool(gens),
          str(sorted(p.name for p in d.glob("ledger*"))))
    check("T72 ledger: the live file is under the cap",
          len(live.read_text("utf-8").splitlines()) < 120,
          str(len(live.read_text("utf-8").splitlines())))
    check("T72 ledger: no more generations than the keep limit",
          len(gens) <= e.LEDGER_KEEP, str(len(gens)))
    check("T72 ledger: log still reads the live file", "item" in e.handle("log"))
    shutil.rmtree(d, True)


def t73_web_routes():
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer

    import pico.ui as UI
    from pico.engine import Engine
    e = Engine(home=tempfile.mkdtemp(prefix="pico-t73-"), quiet=True)
    tok = UI.token_for(e)
    html = UI.PAGE.read_text().replace("/*__PICO_TOKEN__*/null", json.dumps(tok))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), UI.make_handler(e, tok, html))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.3)

    def get(path):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path),
                                        timeout=4) as r:
                return r.status
        except urllib.error.HTTPError as ex:
            return ex.code

    try:
        check("T73 web: the page answers", get("/") == 200)
        check("T73 web: /index.html answers", get("/index.html") == 200)
        check("T73 web: /app.html answers", get("/app.html") == 200)
        check("T73 web: a cache-busting query string is ignored",
              get("/sw.js?cache=1") == 200)
        check("T73 web: the manifest with a query string answers",
              get("/manifest.webmanifest?v=2") == 200)
        check("T73 web: traversal is refused", get("/../../etc/passwd") == 404)
        check("T73 web: an unknown route is 404", get("/nope") == 404)
    finally:
        srv.shutdown()
        shutil.rmtree(e.home, True)


def t74_indic_names():
    e, d = fresh("t74")
    check("T74 names: a Devanagari spend category is accepted",
          e.handle("spend 100 खाना") == "Logged.", e.handle("spend 100 खाना"))
    check("T74 names: it is reported back", "खाना" in e.handle("expenses"))
    check("T74 names: a Devanagari budget category works",
          "खाना" in e.handle("budget खाना 5000"))
    check("T74 names: a Devanagari asset works", "सोना" in e.handle("asset सोना 50000"))
    check("T74 names: a Devanagari debt works", "कार्ड" in e.handle("debt कार्ड 40000 36"))
    check("T74 names: a Devanagari habit works",
          "streak" in e.handle("habit add ध्यान") + e.handle("did ध्यान"))
    nw = e.handle("net worth")
    check("T74 names: net worth subtracts the debt from the asset",
          "10,000" in nw, nw.replace("\n", " | ")[:90])
    shutil.rmtree(d, True)


def t75_file_trigger():
    e, d = fresh("t75")
    watch = d / "watch"
    watch.mkdir()
    out = e.handle("when file %s/*.csv then count {file}" % watch)
    check("T75 file trigger: an absolute glob is accepted",
          out.startswith("Trigger 1 saved"), out[:60])
    mod = _trig_mod()
    if mod is None:
        check("T75 file trigger: pack reachable", False, "not loaded")
        shutil.rmtree(d, True)
        return
    now = datetime.datetime.now()
    (watch / "a.csv").write_text("x,y\n1,2\n", "utf-8")
    first = mod.tick(now)
    check("T75 file trigger: a new file fires it", len(first) == 1, str(len(first)))
    again = mod.tick(now + datetime.timedelta(seconds=30))
    check("T75 file trigger: the same file does not fire twice", len(again) == 0,
          str(len(again)))
    (watch / "b.csv").write_text("x,y\n3,4\n", "utf-8")
    second = mod.tick(now + datetime.timedelta(seconds=60))
    check("T75 file trigger: a second new file fires it", len(second) == 1,
          str(len(second)))
    shutil.rmtree(d, True)


def t78_glob_helper():
    mod = _trig_mod()
    if mod is None or not hasattr(mod, "_glob"):
        check("T78 glob: the pack exposes _glob", False, "not loaded")
        return
    import os
    d = pathlib.Path(tempfile.mkdtemp(prefix="pico-t78-"))
    try:
        (d / "a.csv").write_text("x", "utf-8")
        (d / "b.csv").write_text("x", "utf-8")
        (d / "c.txt").write_text("x", "utf-8")
        found = {p.name for p in mod._glob(str(d / "*.csv"))}
        check("T78 glob: an absolute pattern matches", found == {"a.csv", "b.csv"},
              str(sorted(found)))
        check("T78 glob: a forward slash in the pattern works on every OS",
              len(mod._glob(os.path.join(str(d), "*.csv"))) == 2)
        home_rel = mod._glob("~/*")
        check("T78 glob: a ~ pattern resolves against home, not cwd",
              all(str(pathlib.Path.home()) in str(p) for p in home_rel) or not home_rel,
              str(len(home_rel)))
        check("T78 glob: a pattern that matches nothing returns an empty list",
              mod._glob(str(d / "*.zzz")) == [])
    finally:
        shutil.rmtree(d, True)


def t76_noop_gate():
    e, d = fresh("t76")
    check("T76 no-op: restoring a nonexistent item explains instead of prompting",
          e.handle("restore 999") == "No such item. Run: quarantine",
          e.handle("restore 999")[:60])
    check("T76 no-op: safe delete of a missing path explains",
          "not found" in e.handle("safe delete /nonexistent/x"))
    real = d / "f.txt"
    real.write_text("x", "utf-8")
    out = e.handle("safe delete %s" % real)
    check("T76 no-op: a real danger action still asks for confirmation",
          out.startswith("[danger]") and "Affects: 1" in out, out[:60])
    check("T76 no-op: the replay message names the real snapshot count",
          "12 write bursts" in e.handle("replay notadate"))
    shutil.rmtree(d, True)


def t77_sm2():
    e, d = fresh("t77")
    e.handle("card add Q|A")
    mod = next((m for n, m in sys.modules.items()
                if n.startswith("pico_pack_learn")), None)
    intervals = []
    for g in (5, 5, 5):
        if mod is not None:
            for c in mod.D["cards"]:
                c["due"] = "2000-01-01"
            mod.save()
        e.handle("review")
        e.handle("grade %d" % g)
        raw = json.loads((d / "cards.json").read_text("utf-8"))
        intervals.append(raw["cards"][0]["interval"])
    check("T77 sm2: the interval grows 1, 6, 16 on repeated grade 5",
          intervals == [1, 6, 16], str(intervals))
    raw = json.loads((d / "cards.json").read_text("utf-8"))
    check("T77 sm2: ease rises above the 2.5 default", raw["cards"][0]["ef"] > 2.5,
          str(raw["cards"][0]["ef"]))
    if mod is not None:
        for c in mod.D["cards"]:
            c["due"] = "2000-01-01"
        mod.save()
    e.handle("review")
    e.handle("grade 1")
    raw = json.loads((d / "cards.json").read_text("utf-8"))
    check("T77 sm2: a lapse resets the interval and the repetition count",
          raw["cards"][0]["interval"] == 1 and raw["cards"][0]["n"] == 0,
          str({k: raw["cards"][0][k] for k in ("interval", "n")}))
    shutil.rmtree(d, True)


def t79_scale():
    e, d = fresh("t79")
    for i in range(1200):
        e.S["tasks"].append({"text": "task %d" % i, "done": False})
    e.save()
    start = time.perf_counter()
    out = e.handle("tasks")
    read_ms = (time.perf_counter() - start) * 1000
    check("T79 scale: a long list is capped, not printed in full",
          len(out.splitlines()) <= 41, str(len(out.splitlines())))
    check("T79 scale: the cap says how many were withheld",
          "and 1160 more" in out, out.splitlines()[-1][:60])
    start = time.perf_counter()
    e.handle("add one more")
    write_ms = (time.perf_counter() - start) * 1000
    # reported, not asserted: a wall-clock bound here fails on a loaded CI runner
    # and measures the machine, not the code
    print("        (read %.2f ms, write %.2f ms at 1,200 tasks)" % (read_ms, write_ms))

    raw = e.state_file.read_text("utf-8")
    check("T79 scale: the state file is compact JSON, not indented",
          "\n" not in raw.strip()[:200], raw[:40])
    check("T79 scale: compact JSON still parses", bool(json.loads(raw)))
    shutil.rmtree(d, True)


def t82_ledger_generations_dated():
    e, d = fresh("t82")
    e.LEDGER_CAP = 10
    for i in range(75):
        e.handle("add x%d" % i)
    gens = sorted(d.glob("ledger-*.jsonl"))
    check("T82 dated generations: five are kept", len(gens) == e.LEDGER_KEEP,
          str(len(gens)))
    check("T82 dated generations: names sort chronologically",
          [g.name for g in gens] == sorted(g.name for g in gens))
    lines = list(e.ledger_lines())
    check("T82 dated generations: the reader spans every generation",
          len(lines) == 55, str(len(lines)))
    check("T82 dated generations: the oldest line is from the oldest kept generation",
          "add x20" in lines[0], lines[0][:50])
    tl = e.handle("timeline")
    check("T82 dated generations: timeline says how many it withheld",
          "older line(s)" in tl.splitlines()[0], tl.splitlines()[0][:60])
    check("T82 dated generations: timeline narrows with a date",
          e.handle("timeline 2099-01-01") == "Nothing since 2099-01-01")
    check("T82 dated generations: an empty ledger says so",
          Engine(home=tempfile.mkdtemp(), quiet=True).handle("timeline") == "Ledger empty.")
    shutil.rmtree(d, True)


def t81_report_plural():
    e, d = fresh("t81")
    e.handle("add a")
    out = e.handle("report weekly")
    check("T81 plural: one command reads '1 command'", "(1 command)" in out,
          [l for l in out.splitlines() if "command" in l])
    e.handle("add b")
    out = e.handle("report weekly")   # this command counts itself
    check("T81 plural: more than one reads '3 commands'", "(3 commands)" in out,
          [l for l in out.splitlines() if "command" in l])
    shutil.rmtree(d, True)


def main():
    print("pico acceptance tests")
    for fn in (t1_parity, t2_firewall, t3_degradation, t4_consent, t5_undo,
               t6_lattice, t7_distillation, t8_privacy, t9_scheduler,
               t10_maths, t11_state, t12_ledger, t13_slots, t14_context,
               t15_recur, t16_two_key, t17_safe_delete, t18_learn, t19_data,
               t20_files, t21_quarantine, t22_net_worth, t23_subs, t24_csv,
               t25_replay, t26_triggers, t27_chain, t28_loop_pivot,
               t29_concurrency, t30_phone_approval, t31_unless, t32_watch_clip,
               t33_retry, t34_multikey_pivot, t35_or_conditions, t36_history,
               t37_three_key_pivot, t38_version_consistency, t39_module_split,
               t40_backoff, t41_pivot_having, t42_core_modules,
               t43_action_backoff, t44_pivot_order, t45_installable,
               t46_quarantine_module, t47_sort_types, t48_install_prompt,
               t49_dispatch_module, t50_filter_types, t51_update_prompt,
               t52_doctor, t53_pivot_types, t54_offline_chip, t55_doctor_fix,
               t56_join_types, t57_android_doc, t58_thread_health,
               t59_repair_module, t60_doctor_probe, t61_probe_write,
               t62_path_arguments, t63_indic_keys, t64_csv_edge_cases,
               t65_bounds, t66_fill_single_pass, t67_quoted_paths,
               t68_sql_pragma, t69_dates, t70_fuzzy_template, t71_expired_confirm,
               t72_ledger_rotation, t73_web_routes, t74_indic_names,
               t75_file_trigger, t76_noop_gate, t77_sm2, t78_glob_helper,
               t79_scale, t81_report_plural,
               t82_ledger_generations_dated):
        print("\n%s" % fn.__name__.upper())
        try:
            fn()
        except Exception:
            FAIL.append((fn.__name__, traceback.format_exc()[-300:]))
            print("  FAIL  %s raised" % fn.__name__)
            traceback.print_exc()
    print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
    if FAIL:
        for n, det in FAIL:
            print("  - %s: %s" % (n, det))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
