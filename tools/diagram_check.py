#!/usr/bin/env python3
"""A diagram is code: check it still parses and still points at things that exist.

An Excalidraw file is JSON with ids and bound arrows. Rename a box by hand and the
arrow keeps a dangling id, which Excalidraw silently drops on open. This is the
cheap half of a test: structure, bindings, and that every text element carries the
font the rest of the scene uses.

    python tools/diagram_check.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIAGRAMS = sorted((ROOT / "docs").glob("*.excalidraw"))


def check(path):
    problems = []
    try:
        scene = json.loads(path.read_text(encoding="utf-8"))
    except Exception as ex:
        return ["%s does not parse: %s" % (path.name, ex)]
    if scene.get("type") != "excalidraw":
        problems.append("%s has no excalidraw type" % path.name)
    els = scene.get("elements") or []
    if not els:
        problems.append("%s has no elements" % path.name)
    ids = {e.get("id") for e in els}
    for e in els:
        if e.get("type") == "text" and e.get("fontFamily") != 5:
            problems.append("%s: text %r does not use fontFamily 5"
                            % (path.name, (e.get("text") or "")[:20]))
        if e.get("type") == "arrow":
            for end in ("startBinding", "endBinding"):
                b = e.get(end) or {}
                if b.get("elementId") not in ids:
                    problems.append("%s: arrow %s points at a missing element"
                                    % (path.name, end))
        if not all(k in e for k in ("x", "y", "width", "height")):
            problems.append("%s: element %r has no geometry"
                            % (path.name, e.get("id")))
    return problems


def main():
    if not DIAGRAMS:
        print("no .excalidraw files to check")
        return 0
    problems = []
    for d in DIAGRAMS:
        problems += check(d)
    if problems:
        print("%d problem(s):" % len(problems))
        for p in problems:
            print("  " + p)
        return 1
    print("%d diagram(s) parse, bind and use one font" % len(DIAGRAMS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
