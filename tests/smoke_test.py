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


def main():
    print("pico acceptance tests")
    for fn in (t1_parity, t2_firewall, t3_degradation, t4_consent, t5_undo,
               t6_lattice, t7_distillation, t8_privacy, t9_scheduler,
               t10_maths, t11_state, t12_ledger):
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
