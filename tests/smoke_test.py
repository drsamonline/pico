#!/usr/bin/env python3
"""pico acceptance tests — T1..T10 from the spec. Stdlib only.

    python tests/smoke_test.py        # exit 0 = all pass
"""
import datetime
import json
import os
import pathlib
import shutil
import sys
import tempfile
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


def main():
    print("pico acceptance tests")
    for fn in (t1_parity, t2_firewall, t3_degradation, t4_consent, t5_undo,
               t6_lattice, t7_distillation, t8_privacy, t9_scheduler,
               t10_maths, t11_state, t12_ledger, t13_slots, t14_context,
               t15_recur, t16_two_key, t17_safe_delete, t18_learn, t19_data,
               t20_files, t21_quarantine, t22_net_worth, t23_subs, t24_csv,
               t25_replay, t26_triggers, t27_chain, t28_loop_pivot,
               t29_concurrency, t30_phone_approval):
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
