#!/usr/bin/env python3
"""A flexible size budget: growth is allowed, silent growth is not.

An absolute cap has to be raised by hand every time a feature needs room, which
turns a guard into a chore. This keeps a recorded baseline per part and fails only
when something grows past it by more than the tolerance — so a feature that needs
space must raise the baseline in the same commit, and the diff shows it.

    python tools/budget.py            # check against budget.json
    python tools/budget.py --update   # record the current sizes as the baseline
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE = ROOT / "budget.json"
TOLERANCE = 0.10          # 10% over the recorded baseline is a failure


def measure():
    parts = sorted((ROOT / "pico").glob("*.py")) + [ROOT / "pico.py"]
    return {
        "package": sum(p.stat().st_size for p in parts),
        "packs": sum(p.stat().st_size for p in (ROOT / "packs").rglob("*.py")),
        "console": (ROOT / "web" / "index.html").stat().st_size,
    }


def main():
    sizes = measure()
    if "--update" in sys.argv or not BASELINE.exists():
        BASELINE.write_text(json.dumps(sizes, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
        print("baseline recorded:", ", ".join("%s %d B" % kv for kv in sorted(sizes.items())))
        return 0

    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    over = []
    for part in sorted(sizes):
        now, was = sizes[part], base.get(part, 0)
        room = int(was * (1 + TOLERANCE))
        state = "ok" if now <= room else "over"
        if now > room:
            over.append(part)
        print("  %-8s %7d B  baseline %7d  ceiling %7d (%+d%%)  %s"
              % (part, now, was, room, round((now - was) * 100.0 / max(was, 1)), state))
    if over:
        print("\n%d part(s) grew past the baseline by more than %d%%: %s"
              % (len(over), int(TOLERANCE * 100), ", ".join(over)))
        print("If the growth is wanted, record it in the same commit:")
        print("  python tools/budget.py --update")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
