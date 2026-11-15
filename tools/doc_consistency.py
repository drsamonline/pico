#!/usr/bin/env python3
"""Check that the numbers quoted in the docs match the tree.

Every release so far has needed a hand pass to fix a stale size, count or version
somewhere in README, the landing page or the overview. This does that pass instead.

    python tools/doc_consistency.py          # exit 0 = every quoted number is true
    python tools/doc_consistency.py -v       # print every number found and checked
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DOCS = ["README.md", "PROJECT_OVERVIEW.md", "docs/index.html"]


def measure():
    parts = sorted((ROOT / "pico").glob("*.py")) + [ROOT / "pico.py"]
    packs = sorted((ROOT / "packs").rglob("*.py"))
    tests = sorted((ROOT / "tests").rglob("*.py"))
    all_py = [p for p in ROOT.rglob("*.py") if "tests" not in p.parts and "tools" not in p.parts]
    console = (ROOT / "web" / "index.html").stat().st_size

    from pico.engine import Engine
    import tempfile
    engine = Engine(home=tempfile.mkdtemp(prefix="pico-doc-"), quiet=True)
    return {
        "version": __import__("pico.base", fromlist=["x"]).__version__,
        "package": sum(p.stat().st_size for p in parts),
        "package_files": len(parts),
        "packs": sum(p.stat().st_size for p in packs),
        "console": console,
        "python_total": sum(p.stat().st_size for p in all_py),
        "python_files": len(all_py),
        "rules": len(engine.rules),
        "catalog": len(engine.catalog),
    }


def test_count():
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "smoke_test.py")],
                       capture_output=True, encoding="utf-8", timeout=300)
    m = re.search(r"(\d+) passed", r.stdout)
    return int(m.group(1)) if m else -1


def check(docs, facts, verbose):
    problems = []
    for name in docs:
        path = ROOT / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")

        # the version appears as v1.2.3, 1.2.3, or alt="version 1.2.3"
        for found in set(re.findall(r"\bv(\d+\.\d+\.\d+)\b", text)) | \
                     set(re.findall(r'version (\d+\.\d+\.\d+)', text)):
            if found != facts["version"]:
                problems.append("%s: says version %s, tree is %s"
                                % (name, found, facts["version"]))

        # byte counts, with or without thousands separators
        for pattern, key, label in [
            (r"package / packs / console \| ([\d,]+) / ([\d,]+) / ([\d,]+) B", None, None),
            (r"\| console \| ([\d,]+) bytes", "console", "console"),
            (r"<tr><td>console</td><td>([\d,]+) bytes", "console", "console"),
            (r"\| python source \| ([\d,]+) bytes", "python_total", "python source"),
            (r"<tr><td>python source</td><td>([\d,]+) bytes", "python_total", "python source"),
            (r"\| package \(`pico/` \+ launcher, (\d+) files\)", "package_files",
             "package file count"),
            (r"\| package \(`pico/` \+ launcher, (\d+) files\) \| 96 KB \| ([\d,]+) B",
             "package", "package size"),
        ]:
            for m in re.finditer(pattern, text):
                if key is None:
                    for got, k in zip(m.groups(), ("package", "packs", "console")):
                        got = int(got.replace(",", ""))
                        if got != facts[k]:
                            problems.append("%s: says %s %d B, tree is %d B"
                                            % (name, k, got, facts[k]))
                        elif verbose:
                            print("  ok   %-22s %s %d B" % (name, k, got))
                else:
                    got = int(m.group(m.lastindex).replace(",", "")) \
                        if m.lastindex > 1 else int(m.group(1).replace(",", ""))
                    if got != facts[key]:
                        problems.append("%s: says %s %d, tree is %d"
                                        % (name, label, got, facts[key]))
                    elif verbose:
                        print("  ok   %-22s %s %d" % (name, label, got))

        # test counts
        for m in re.finditer(r"(?:tests: |acceptance tests \| |<tr><td>acceptance tests</td><td>)"
                             r"(\d+)", text):
            got = int(m.group(1))
            if facts["tests"] >= 0 and got != facts["tests"]:
                problems.append("%s: says %d tests, suite reports %d"
                                % (name, got, facts["tests"]))
            elif verbose:
                print("  ok   %-22s tests %d" % (name, got))

        # rule counts
        for m in re.finditer(r"(\d+) rules", text):
            got = int(m.group(1))
            if got != facts["rules"]:
                problems.append("%s: says %d rules, engine has %d"
                                % (name, got, facts["rules"]))
            elif verbose:
                print("  ok   %-22s rules %d" % (name, got))
    return problems


def main():
    verbose = "-v" in sys.argv
    facts = measure()
    facts["tests"] = test_count()
    if verbose:
        print(json.dumps(facts, indent=1))

    problems = check(DOCS, facts, verbose)
    if problems:
        print("\n%d quoted number(s) disagree with the tree:" % len(problems))
        for p in problems:
            print("  " + p)
        return 1
    print("%d docs agree with the tree: version %s, %d rules, %d tests, "
          "package %d B, packs %d B, console %d B"
          % (len(DOCS), facts["version"], facts["rules"], facts["tests"],
             facts["package"], facts["packs"], facts["console"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
