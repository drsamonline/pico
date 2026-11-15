#!/usr/bin/env python3
"""Catch APIs the CI matrix's oldest interpreter does not have.

`Path.is_relative_to` shipped in 3.9 and the matrix still runs 3.8. It raised
AttributeError into a bare `except`, so the guard silently did nothing and only the
3.8 job noticed. This looks for the handful of post-3.8 names this project could
plausibly reach for, in call or attribute position, so the mistake fails here rather
than on one matrix leg.

    python tools/py38.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# name -> the release that introduced it
POST_38 = {
    "is_relative_to": "3.9",
    "removeprefix": "3.9",
    "removesuffix": "3.9",
    "math.lcm": "3.9",
    "math.nextafter": "3.9",
    "ast.unparse": "3.9",
    "functools.cache": "3.9",
    "zoneinfo": "3.9",
    "graphlib": "3.9",
    "pairwise": "3.10",
    "anext": "3.10",
    "tomllib": "3.11",
}

SCAN = ["pico", "packs", "tools", "tests", "pico.py"]
SKIP = re.compile(r"__pycache__|\.pyc$|tools[/\\]py38\.py$")


def hits(line, name):
    """A mention is only a problem when it is code, not prose in a docstring."""
    if "`" in line:                       # documented in backticks, not called
        return False
    if re.search(r"(?:\.|^|\s)%s\s*\(" % re.escape(name.split(".")[-1]), line):
        return True
    return bool(re.search(r"import\s+%s\b" % re.escape(name), line))


def main():
    problems = []
    for target in SCAN:
        path = ROOT / target
        files = [path] if path.is_file() else sorted(path.rglob("*.py"))
        for f in files:
            if SKIP.search(str(f)):
                continue
            for lineno, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                for name, since in POST_38.items():
                    if name in line and hits(line, name):
                        problems.append("%s:%d %r is %s+: %s"
                                        % (f.relative_to(ROOT), lineno, name, since,
                                           line.strip()[:64]))
    if problems:
        print("%d line(s) reach past Python 3.8:" % len(problems))
        for p in problems:
            print("  " + p)
        return 1
    print("no post-3.8 API calls in %d paths" % len(SCAN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
