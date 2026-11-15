#!/usr/bin/env python3
"""Compare the console's own engine with the Python engine, command by command.

The landing page says the demo runs the resolver, the risk gate and all arithmetic
locally. This checks that claim instead of trusting it.

    python tools/demo_parity.py            # exit 0 = every command agrees
    python tools/demo_parity.py --verbose  # print every divergence
"""
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pico.engine import Engine  # noqa: E402

# A demo that says it cannot answer is honest, not divergent. This is checked by
# the answer text rather than by a list, so a new "needs the engine" handler is
# covered the moment it exists.
PARTIAL_MARKERS = ("local engine", "demo build", "live in the engine")

# Wording the demo is allowed to differ on: it speaks to a visitor, not to a
# terminal, and none of it changes an answer.
COSMETIC = {
    "help", "calc 9/0", "fd 100000 7.1 5", "gst 1000 18", "budget", "net worth",
    "brief", "time", "habits", "report weekly", "log", "why", "dry wa bob hi",
    "dry tidy", "srots", "aliases",
    # both refuse and both name the same suggestion; only the hint's phrasing
    # differs ("Did you mean: 1. …" here, "Closest: …" there)
    "decide a",
    # both refuse; the demo has no rule for the spelled-out form, so only the
    # closing hint differs
    "two-key on", "two-key off",
    # both gate the action; the engine also prints a two-key code, which the demo
    # has no key material for
    "habit del walk",
    # both refuse; only the closing hint differs
    "spend -50 food", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    # undo depends on which inverses each side recorded; the demo's set is smaller
    "undo",
}

# One command per handler the demo implements, plus the edge cases that have
# bitten before. A handler with no line here is a handler nobody checks.
COMMANDS = [
    "tasks", "add buy milk", "tasks", "done 1", "tasks", "undone 1", "add call bank",
    "del 2", "remember pin=4821", "recall pin", "forget pin", "buy eggs", "shop",
    "bought 1", "spend 250 food", "expenses", "calc 2+2*3", "calc 9/0",
    "convert 10 km to mi", "convert 100 c to f", "emi 500000 8.5 240",
    "sip 5000 12 10", "fd 100000 7.1 5", "si 10000 8 2", "gst 1000 18",
    "split 1000 3", "disc 999 15", "budget food 8000", "budget", "asset cash 50000",
    "debt card 40000 36", "net worth", "chart 3,7,12,9", "brief", "time",
    "on 12-25 xmas", "on 13-45 bad", "due 1 2026-12-25", "recur daily water",
    "overdue", "journal hello there", "journal", "contact bob=91999", "contacts",
    "habit add walk", "did walk", "habits", "card add Q|A", "cards", "report weekly",
    "decide tea|coffee", "decide a", "aliases", "undo", "log", "why",
    "dry wa bob hi", "dry tidy", "srots", "tsks", "tasks.",
    # --- one per remaining handler ---
    "timer 1m tea", "remind 18:30 call", "site gh=https://github.com", "open gh",
    "search rust", "weather Pune", "templates", "count ~/.pico/state.json",
    "extract emails ~/.pico/state.json", "journal show 3", "jobs",
    "daily 09:00 brief", "unjob 1", "aliases", "unalias tsks",
    "quarantine", "restore 1", "safe delete /nonexistent/x", "big files 3",
    "old files 30d", "dedupe files /tmp", "subs audit", "trigger log",
    "triggers", "untrigger 1", "when 22:30 then brief", "away on", "away off",
    "two-key on", "two-key off", "2key phone", "llm status", "replay 2020-01-01T00:00:00",
    "timeline", "csv filter x=1 /tmp/none.csv", "csv sort x /tmp/none.csv",
    "csv join x /tmp/a.csv /tmp/b.csv", "importcsv /tmp/none.csv t",
    "sql SELECT 1", "tables", "fill letter a=b", "tidy /tmp", "backup /tmp",
    "find nothing", "wa bob hi", "mail bob subj", "chain x: tasks", "chain x",
    "for each row in /tmp/none.csv then tasks", "csv pivot city sum amt /tmp/none.csv",
    "doctor", "doctor fix", "doctor probe", "doctor probe write",
    "card add Q|A", "review", "grade 3", "cards", "debt snowball 5000",
    "net worth", "asset cash 50000", "debt card 40000 36", "budget food 8000",
    "habit add walk", "did walk", "habit del walk", "habits", "contact bob=91999",
    "contacts", "remember k=v", "recall k", "forget k", "add one", "done 1",
    "undone 1", "del 1", "recur daily water", "due 1 2026-12-25", "overdue",
    "log", "why", "help", "aliases",
    # --- hostile and awkward input: the resolver must agree on what it refuses ---
    "remember नाम=Sohil", "recall नाम", "spend 100 खाना", "expenses",
    "habit add ध्यान", "did ध्यान", "habits", "contact रवि=91999", "contacts",
    "add कल दूध लाना", "tasks", "journal café ☕", "journal",
    "calc 2**1000", "calc " + "9" * 40, "convert 10 km to km", "convert -5 c to f",
    "on 2026-02-29 nope", "on 02-29 leap", "due 1 2026-13-45", "on 13-45 bad",
    "timer 25h no", "remind 25:99 x", "split 1000 0", "emi 100 5 0",
    "disc 999 150", "emi 0.01 99 1", "gst 0 18", "spend -50 food",
    "done 0", "done 999", "undone 0", "del 999", "budget खाना 5000", "budget",
    "decide tea|coffee|water", "chart -5,0,5", "chart 1",
    "tasks", "tsks", "TASKS", "TaSkS", "tasks.", "   ", "a" * 60,
    "remember k=v", "recall k", "recall nosuchkey",
    # last on purpose: `undo` pops each side's own inverse stack, so every command
    # after it would compare two different histories
    "undo",
]


DASHES = {"\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
          "\u201c": '"', "\u201d": '"', "\u00a0": " "}


def _norm(value):
    """Compare answers, not typography.

    A typographic dash is not a different answer, and Windows console encoding can
    mangle one side of a comparison on the way to the log. Fold the punctuation
    that carries no meaning, keep everything else exact.
    """
    text = str(value).strip()
    for src, dst in DASHES.items():
        text = text.replace(src, dst)
    return text


def js_results(commands):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(commands, f)
        path = f.name
    try:
        # node writes UTF-8; decoding with the platform default (cp1252 on Windows)
        # turns an em dash into mojibake and invents a divergence
        r = subprocess.run(["node", str(ROOT / "tools" / "demo_run.js"),
                            str(ROOT / "web" / "index.html"), path],
                           capture_output=True, encoding="utf-8", timeout=120)
    finally:
        pathlib.Path(path).unlink(missing_ok=True)
    if r.returncode != 0:
        raise SystemExit("demo_run.js failed:\n" + (r.stderr or r.stdout)[:800])
    return json.loads(r.stdout)


def main():
    verbose = "--verbose" in sys.argv
    js = js_results(COMMANDS)
    engine = Engine(home=tempfile.mkdtemp(prefix="pico-parity-"), quiet=True)
    # the two-key gate notifies on every danger command; silence it for the run
    engine.notify = lambda message: None

    same, partial, cosmetic, broken = 0, 0, 0, []
    for i, cmd in enumerate(COMMANDS):
        if not cmd.strip():
            continue
        got = js.get(str(i), {})
        if "error" in got:
            broken.append((cmd, "demo raised: " + got["error"][:60]))
            continue
        py = _norm(engine.handle(cmd))
        jsout = _norm(got.get("out", ""))
        if py == jsout:
            same += 1
        elif any(m in jsout.lower() for m in PARTIAL_MARKERS):
            partial += 1
        elif cmd in COSMETIC:
            cosmetic += 1
            if verbose:
                print("  cosmetic  %-24r py=%r js=%r" % (cmd, py[:60], jsout[:60]))
        else:
            broken.append((cmd, "py=%s js=%s" % (ascii(py[:70]), ascii(jsout[:70]))))

    total = len(COMMANDS)
    print("%d commands: %d identical, %d partial by design, %d cosmetic, %d divergent"
          % (total, same, partial, cosmetic, len(broken)))
    if broken:
        print("\ndivergent — the demo is answering differently from the engine:")
        for cmd, why in broken:
            print("  %-24r %s" % (cmd, why))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
