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
from .dispatch import DispatchMixin
from .ladder import LadderMixin
from .ledger import LedgerMixin
from .store import StoreMixin


class Engine(StoreMixin, LadderMixin, LedgerMixin, DispatchMixin):
    ALIAS_SPLIT = 50           # above this, aliases leave state.json

    def _alias_file(self):
        return self.home / "aliases.json"

    def _load_aliases(self):
        """Aliases live in state.json until there are enough of them to crowd it.

        The file is additive: whatever is on disk wins over whatever the state
        carried, so a downgrade keeps working and a half-migrated home still loads.
        """
        merged = dict(self.S.get("aliases") or {})
        f = self._alias_file()
        if f.exists():
            try:
                disk = json.loads(f.read_text("utf-8"))
                if isinstance(disk, dict):
                    merged.update(disk)
            except Exception:
                pass
        # share the object with the state, so a small set keeps persisting in it
        self.S["aliases"] = merged
        return merged

    def save_aliases(self):
        """Write aliases out of state.json once they pass the threshold."""
        if len(self.aliases) < self.ALIAS_SPLIT:
            return
        try:
            self._alias_file().write_text(
                json.dumps(self.aliases, ensure_ascii=False, indent=1, sort_keys=True),
                "utf-8")
            self.S["aliases"] = {}
        except Exception:
            pass

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
        self.aliases = self._load_aliases()
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
        self._ledger_lines = 0
        self.core_modules = ()
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
            for mod in getattr(self, "core_modules", ()):
                if hasattr(mod, "E"):
                    mod.E = self
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
