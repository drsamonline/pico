#!/usr/bin/env python3
"""Every file the code writes must be named in PRIVACY.md.

A privacy policy that lists yesterday's files is a false statement. This walks the
source for the paths the program actually creates under its home and checks each
one appears in the policy, so the document and the code move together.

    python tools/privacy_files.py          # exit 0 = the policy is complete
    python tools/privacy_files.py -v       # print every file found
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICY = ROOT / "PRIVACY.md"

# every state-file literal in the code, however it is joined to the home
PATTERNS = [re.compile(r'"([a-zA-Z0-9_]+\.(?:json|jsonl|token|key))"')]
# names that are not pico's own state
IGNORE = {"package.json", "manifest.json", "tsconfig.json"}
# directories the program creates under its home
DIRS = ["snapshots", "quarantine", "backups", "rules", "templates"]


def written():
    found = set()
    for f in list((ROOT / "pico").rglob("*.py")) + list((ROOT / "packs").rglob("*.py")):
        text = f.read_text(encoding="utf-8")
        for pat in PATTERNS:
            found.update(pat.findall(text))
    return found


def main():
    verbose = "-v" in sys.argv
    policy = POLICY.read_text(encoding="utf-8")
    files = sorted(written())

    missing = [f for f in files if "`%s`" % f not in policy and f not in policy]
    missing += [d for d in DIRS if ("`%s/`" % d) not in policy and (d + "/") not in policy]

    if verbose:
        for f in files:
            print("  %-24s %s" % (f, "in the policy" if f in policy else "MISSING"))
    if missing:
        print("%d file(s) or folder(s) the code writes are not in PRIVACY.md:" % len(missing))
        for m in missing:
            print("  " + m)
        return 1
    print("PRIVACY.md names all %d files and %d folders the code writes"
          % (len(files), len(DIRS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
