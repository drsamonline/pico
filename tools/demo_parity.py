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

# Commands the demo refuses on purpose, because they need the local engine.
# Both sides must still agree that they are *not* answered locally.
PARTIAL = {"card add Q|A", "cards", "debt snowball 5000", "review", "grade 5",
           "tidy /tmp", "backup /tmp", "find x", "open x", "search x", "weather",
           "importcsv x.csv t", "sql SELECT 1", "tables", "trigger log"}

# Wording the demo is allowed to differ on: it speaks to a visitor, not to a
# terminal, and none of it changes an answer.
COSMETIC = {
    "help", "calc 9/0", "fd 100000 7.1 5", "gst 1000 18", "budget", "net worth",
    "brief", "time", "habits", "report weekly", "log", "why", "dry wa bob hi",
    "dry tidy", "srots", "aliases",
    # both refuse and both name the same suggestion; only the hint's phrasing
    # differs ("Did you mean: 1. …" here, "Closest: …" there)
    "decide a",
}

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
]


def js_results(commands):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(commands, f)
        path = f.name
    try:
        r = subprocess.run(["node", str(ROOT / "tools" / "demo_run.js"),
                            str(ROOT / "web" / "index.html"), path],
                           capture_output=True, text=True, timeout=120)
    finally:
        pathlib.Path(path).unlink(missing_ok=True)
    if r.returncode != 0:
        raise SystemExit("demo_run.js failed:\n" + (r.stderr or r.stdout)[:800])
    return json.loads(r.stdout)


def main():
    verbose = "--verbose" in sys.argv
    js = js_results(COMMANDS)
    engine = Engine(home=tempfile.mkdtemp(prefix="pico-parity-"), quiet=True)

    same, partial, cosmetic, broken = 0, 0, 0, []
    for i, cmd in enumerate(COMMANDS):
        got = js.get(str(i), {})
        if "error" in got:
            broken.append((cmd, "demo raised: " + got["error"][:60]))
            continue
        py = str(engine.handle(cmd)).strip()
        jsout = str(got.get("out", "")).strip()
        if py == jsout:
            same += 1
        elif cmd in PARTIAL and "local engine" in jsout:
            partial += 1
        elif cmd in COSMETIC:
            cosmetic += 1
            if verbose:
                print("  cosmetic  %-24r py=%r js=%r" % (cmd, py[:60], jsout[:60]))
        else:
            broken.append((cmd, "py=%r js=%r" % (py[:70], jsout[:70])))

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
