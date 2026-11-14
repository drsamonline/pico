"""pico engine — the composition root.

State, the ladder and the ledger live in their own modules as mixins, so the
core file stays a place where things are wired rather than where everything is
written. Every public name that packs and tests import is re-exported here.
"""
import datetime
import json
import os
import pathlib
import re
import secrets
import sys
import threading
import time

from .base import (DENY_LLM, MASK_CMD, PENDING_TTL, RISK_RULES, SECRET_OUT,
                   STATE_DEFAULT, UNITS, convert, importlib_spec, mask_cmd,
                   normalize, safe_eval, __version__)          # noqa: F401
from .ladder import LadderMixin
from .ledger import LedgerMixin
from .store import StoreMixin


class Engine(StoreMixin, LadderMixin, LedgerMixin):
    def __init__(self, home=None, load_packs=True, quiet=False):
        self.home = pathlib.Path(home or os.environ.get("PICO_HOME")
                                 or (pathlib.Path.home() / ".pico")).expanduser()
        self.templates = self.home / "templates"
        self.plugins = self.home / "rules"
        for d in (self.home, self.templates, self.plugins):
            d.mkdir(parents=True, exist_ok=True)
        self.state_file = self.home / "state.json"
        self.ledger_file = self.home / "ledger.jsonl"
        self.quiet = quiet
        self.S = self._load_state()
        self.aliases = self.S.setdefault("aliases", {})
        self.rules = []            # [(pattern, fn)]
        self.notifiers = []
        self.translators = []
        self.catalog = []
        self.pending = {}
        self.last = {}
        self._inverse = None
        self._dirty = False
        self.inverse_handlers = {}
        self.pack_modules = []
        self.privacy = {"never_send": []}
        self.slot_rules = []
        self.history = []
        self.approve_source = None
        self._lock = threading.RLock()
        self.snapshots = self.home / "snapshots"
        self._since_snap = 0
        self._busy = False
        self.api = self._build_api()
        self.register_core()
        if load_packs:
            self.load_packs()
        try:
            self.roll_recurring()
        except Exception:
            pass

    def _warn(self, msg):
        if not self.quiet:
            print(msg, file=sys.stderr)

    def _build_api(self):
        return {
            "HOME": self.home, "S": self.S, "save": self.save,
            "reply": self.handle, "notify": self.notify,
            "notifiers": self.notifiers, "translators": self.translators,
            "catalog": self.catalog, "match_rule": self.match_rule,
            "aliases": self.aliases, "inverse": self.set_inverse,
            "add_rule": self.add_rule, "add_rules": self.add_rules,
            "inverse_handler": self.register_inverse,
            "privacy": self.privacy, "add_slots": self.add_slots,
            "engine": self, "version": __version__,
        }

    def notify(self, msg):
        print("\n[!] " + str(msg), flush=True)
        for fn in list(self.notifiers):
            try:
                fn(str(msg))
            except Exception as ex:
                self._warn("[notify failed] %s" % ex)

    def _bind_modules(self):
        """Point every pack's module-level engine ref at this instance.

        Packs follow the documented contract `handler(m) -> str`, so they read a
        module global. Rebinding here keeps two engines in one process isolated.
        """
        try:
            import pico.rules as R
            R.E = self
        except Exception:
            pass
        for mod in self.pack_modules:
            if hasattr(mod, "E"):
                mod.E = self

    def pack_dirs(self):
        dirs = [self.plugins]
        try:
            here = pathlib.Path(__file__).resolve().parent.parent / "packs"
            if here.is_dir() and here.resolve() != self.plugins.resolve():
                dirs.append(here)
        except Exception:
            pass
        return dirs

    def load_packs(self):
        seen, files = set(), []
        for d in self.pack_dirs():
            for f in sorted(d.glob("*.py")):
                if f.stem.startswith("_") or f.stem in seen:
                    continue
                seen.add(f.stem)
                files.append(f)
        for f in files:
            try:
                spec = importlib_spec("pico_pack_" + f.stem, f)
                mod = spec
                if hasattr(mod, "setup"):
                    mod.setup(self.api)
                self.pack_modules.append(mod)
                self.add_rules(getattr(mod, "RULES", []), front=True)
                for entry in getattr(mod, "CATALOG", []):
                    self.catalog.append(entry)
            except Exception as ex:
                self._warn("[pack %s failed: %s]" % (f.name, ex))
        self.catalog.sort()

    def handle(self, text):
        """Single entry point. Never raises (C9)."""
        try:
            return self._handle(text)
        except Exception as ex:
            return "Internal error: %s: %s" % (type(ex).__name__, ex)

    def _handle(self, text):
        t = (text or "").strip()
        low = t.lower()
        p = self.pending
        if p and p.get("at") and time.time() - p["at"] > PENDING_TTL:
            self.pending = {}
            p = self.pending
        if low == "confirm" and p.get("confirm"):
            held = p["confirm"]
            if held.get("code"):
                return ("Two-key is on for danger actions. Approve with:\n"
                        "approve " + held["code"])
            self.pending = {}
            return self._run(held["cmd"], "confirmed")
        if low == "cancel":
            self.pending = {}
            return "Cancelled."
        if low == "why":
            return json.dumps(self.last, indent=2) if self.last else "Nothing run yet."
        if low == "log":
            return self.tail_log(8)
        undo_m = re.fullmatch(r"undo(?:\s+(\d+))?", low)
        if undo_m:
            return self.undo(int(undo_m.group(1) or 1))
        if low.startswith("dry "):
            c = t[4:].strip()
            r = self.resolve(c)
            cmd = r["cmd"]
            if not cmd:
                opts = r.get("options") or []
                return ("Would run: nothing - no rule matched.\n"
                        + ("Closest: " + ", ".join(opts) if opts else "Type 'help'."))
            rk = self.risk_of(cmd)
            fn, m = self.match_rule(cmd)
            lines = ["Would run: " + cmd, "Resolved by: " + r["src"],
                     "Risk: %s (%s)" % (rk, "confirm required"
                                        if rk in ("send", "danger") else "runs immediately")]
            prev = getattr(fn, "preview", None)
            if prev:
                try:
                    aff = prev(m)
                    lines.append("Affects: %d item(s)" % len(aff))
                    lines.extend("  " + str(a) for a in list(aff)[:8])
                except Exception:
                    pass
            return "\n".join(lines)
        slot = p.get("slot")
        if slot:
            self.pending = {}
            slot["have"][slot["need"][0]] = t.strip()
            slot["need"] = slot["need"][1:]
            if slot["need"]:
                self.pending = {"slot": slot, "at": time.time()}
                return slot["prompts"].get(slot["need"][0], slot["need"][0] + "?")
            cmd = slot["tmpl"].format(**slot["have"])
            if not self.match_rule(cmd)[0]:
                return "That did not produce a valid command: " + cmd
            return self._run(cmd, "slot")
        if low in ("again", "it", "that", "same"):
            if not self.history:
                return "Nothing to repeat yet."
            return self.handle(self.history[-1])
        m2k = re.fullmatch(r"2key\s+(on|off|phone)", low)
        if m2k:
            self.S["two_key"] = m2k.group(1) != "off"
            self.S["two_key_phone"] = m2k.group(1) == "phone"
            self._dirty = True
            self.save()
            if m2k.group(1) == "phone":
                return ("Two-key: phone only. Codes go to the bound chat and "
                        "approve is refused at this desk.")
            return "Two-key: " + ("on" if self.S["two_key"] else "off")

        ap = re.fullmatch(r"approve\s+(\w+)", low)
        if ap:
            held = p.get("confirm")
            if not held:
                return "Nothing waiting for approval."
            if not secrets.compare_digest(ap.group(1), held.get("code", "")):
                return "Wrong code. Still waiting."
            if self.S.get("two_key_phone") and self.approve_source != "phone":
                return ("Two-key is phone-only: approve must come from the bound chat, "
                        "not this terminal.")
            self.pending = {}
            return self._run(held["cmd"], "approved")
        if low.startswith("replay "):
            return self.replay(t[7:].strip())
        if low == "timeline" or low.startswith("timeline "):
            since = t[8:].strip()
            return self.timeline(since)
        if t in ("1", "2", "3") and p.get("choice"):
            i = int(t) - 1
            opts = p["choice"]
            if i < len(opts):
                cmd = opts[i]
                said = p.get("said", "")
                self.pending = {}
                return self._run(cmd, "learned", original=said)
            self.pending = {}
            return "No option " + t + "."
        sm = self._slot_match(t)
        if sm:
            self.pending = {"slot": sm, "at": time.time()}
            return sm["prompts"].get(sm["need"][0], sm["need"][0] + "?")
        r = self.resolve(t)
        if not r["cmd"]:
            opts = r.get("options") or []
            self.pending = {"choice": opts, "said": t, "at": time.time()}
            if opts:
                return ("No rule matched. Did you mean:\n"
                        + "\n".join("  %d. %s" % (i + 1, o) for i, o in enumerate(opts))
                        + "\nReply 1/2/3 - I will run it and remember your wording.")
            return "No rule matched. Type 'help', or 'llm auto' to enable the translator."
        cmd = r["cmd"]
        if r["src"] in ("llm", "cache") and not self.llm_payload_ok(cmd):
            return "Refused: the translator may not issue that command."
        if r["src"] == "blocked":
            return "Blocked: that phrase contains a never-send domain, so it never reaches the model."
        rk = self.risk_of(cmd)
        if rk in ("send", "danger") or (rk == "write" and r["src"] in ("llm", "cache")):
            held = {"cmd": cmd}
            gate = ""
            if rk == "danger" and self.S.get("two_key"):
                held["code"] = secrets.token_hex(3)
                gate = "\nTwo-key: approve " + held["code"]
                try:
                    self.notify("pico approval needed: approve " + held["code"])
                except Exception:
                    pass
            self.pending = {"confirm": held, "at": time.time()}
            fn, m = self.match_rule(cmd)
            preview = ""
            prev = getattr(fn, "preview", None)
            if prev:
                try:
                    preview = "\nAffects: %d item(s)" % len(prev(m))
                except Exception:
                    pass
            tail = "approve <code>" if gate else "confirm"
            return "[%s] About to run: %s%s%s\nType '%s' or 'cancel'." % (
                rk, cmd, preview, gate, tail)
        return self._run(cmd, r["src"], original=t)

    def roll_recurring(self):
        """Reopen a recurring task once the day turns over."""
        today = datetime.date.today().isoformat()
        recur = self.S.setdefault("recur", {})
        changed = False
        for i, task in enumerate(self.S.get("tasks", [])):
            key = str(i)
            if not task.get("recur"):
                continue
            if recur.get(key) != today and task.get("done"):
                task["done"] = False
                recur[key] = today
                changed = True
            elif key not in recur:
                recur[key] = today
        if changed:
            self.save()
        return changed

    def register_core(self):
        import pico.rules as R
        R.register(self)
        self.catalog.extend(R.CATALOG)
        self.catalog.sort()


_engine = None


def get_engine(**kw):
    global _engine
    if _engine is None:
        _engine = Engine(**kw)
    return _engine
