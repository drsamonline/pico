#!/usr/bin/env python3
"""Check the console's palette against WCAG AA, using the values in the file.

A contrast fix is easy to undo by accident: someone nudges a colour, the page still
looks fine to them, and a low-vision reader loses the text. This reads the actual
custom properties out of `web/index.html` and checks the pairs that carry text.

    python tools/contrast.py           # exit 0 = every pair meets its target
    python tools/contrast.py -v        # print every pair measured
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONSOLE = ROOT / "web" / "index.html"

# pair: (foreground variable, background variable, minimum ratio, what it is)
# 4.5:1 is AA for body text; 3.0:1 is AA for large text and non-text UI.
PAIRS = [
    ("--tx",   "--bg",    4.5, "body ink on the page"),
    ("--tx",   "--panel", 4.5, "body ink on a panel"),
    ("--tx2",  "--bg",    4.5, "secondary ink on the page"),
    ("--tx2",  "--panel", 4.5, "secondary ink on a panel"),
    ("--tx3",  "--bg",    3.0, "tertiary ink (large only)"),
    ("--safe", "--bg",    4.5, "safe tier"),
    ("--write", "--bg",   4.5, "write tier"),
    ("--send", "--bg",    4.5, "send tier"),
    ("--danger", "--bg",  4.5, "danger tier"),
    ("--acc",  "--bg",    4.5, "accent"),
    # --acc2 is never text on the page: it is a border and a filled button, so the
    # pair that matters is the white label on it
    ("#ffffff", "--acc2", 4.5, "white label on the accent fill"),
    # non-text: a focus ring or a meaningful border is UI, and AA asks 3:1
    ("--line2", "--bg",   3.0, "border on the page"),
    ("--acc",   "--panel", 3.0, "accent outline on a panel"),
    ("--tx3",   "--panel", 3.0, "tertiary ink on a panel (large only)"),
]


def variables():
    html = CONSOLE.read_text(encoding="utf-8")
    root = re.search(r":root\{(.*?)\}", html, re.S)
    if not root:
        raise SystemExit("no :root block in the console")
    found = dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})", root.group(1)))
    # the a11y override block, if present, wins
    for name, value in re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})",
                                  html[root.end():]):
        found.setdefault(name, value)
    return found


def luminance(colour):
    h = colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    parts = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]

    def channel(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in parts)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def main():
    verbose = "-v" in sys.argv
    v = variables()
    # a literal colour in a pair is fine; only variables have to exist
    missing = [x for pair in PAIRS for x in (pair[0], pair[1])
               if x.startswith("--") and x not in v]
    if missing:
        print("missing custom properties: %s" % ", ".join(sorted(set(missing))))
        return 1

    def colour(token):
        return v[token] if token.startswith("--") else token

    failures = []
    for fg, bg, target, label in PAIRS:
        r = ratio(colour(fg), colour(bg))
        ok = r >= target
        if not ok:
            failures.append((label, fg, bg, r, target))
        if verbose or not ok:
            print("  %-5s %-32s %s on %s  %.2f:1 (needs %.1f)"
                  % ("ok" if ok else "FAIL", label, colour(fg), colour(bg), r, target))
    if failures:
        print("\n%d pair(s) below WCAG AA:" % len(failures))
        for label, fg, bg, r, target in failures:
            print("  %s: %s on %s is %.2f:1, needs %.1f"
                  % (label, colour(fg), colour(bg), r, target))
        return 1
    print("%d palette pairs meet WCAG AA" % len(PAIRS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
