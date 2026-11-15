#!/usr/bin/env python3
"""pico — one brain, many faces.

    python pico.py                 REPL
    python pico.py tasks           one-shot command
    python pico.py --serve         keep scheduler + bridges alive
    python pico.py --ui            local web UI on 127.0.0.1:8765
    python pico.py --version
"""
import argparse
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from pico.base import utf8_console  # noqa: E402
from pico.engine import Engine, __version__  # noqa: E402


def build(args):
    return Engine(home=args.home, quiet=False)


def main(argv=None):
    utf8_console()
    ap = argparse.ArgumentParser(prog="pico", add_help=False)
    ap.add_argument("command", nargs="*")
    ap.add_argument("--home", default=None)
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--ui", action="store_true")
    ap.add_argument("--lan", action="store_true")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--version", "-V", action="store_true")
    ap.add_argument("--help", "-h", action="store_true")
    args = ap.parse_args(argv)

    if args.version:
        print("pico " + __version__)
        return 0
    if args.help:
        print(__doc__)
        return 0

    eng = build(args)

    if args.ui:
        from pico import ui
        return ui.serve(eng, port=args.port, lan=args.lan)

    if args.serve:
        print("pico serving — scheduler and bridges active. Ctrl+C to stop.")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\nstopped.")
        return 0

    if args.command:
        print(eng.handle(" ".join(args.command)))
        return 0

    print("pico %s — deterministic, LLM optional. 'help' to start, 'quit' to leave."
          % __version__)
    while True:
        try:
            q = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if q.strip() in ("quit", "exit"):
            break
        if not q.strip():
            continue
        try:
            print(eng.handle(q))
        except Exception as ex:  # never die on one command (C9)
            print("[error] %s: %s" % (type(ex).__name__, ex))
    return 0


if __name__ == "__main__":
    sys.exit(main())
