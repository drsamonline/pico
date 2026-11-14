"""pico engine — deterministic core.

State, resolution ladder, risk gate, ledger with inverses, plugin loader.
No third-party imports. Python 3.8+.
"""
import ast, difflib, json, operator, os, pathlib, re, secrets, sys, threading, time
import datetime

__version__ = "1.2.0"

STATE_DEFAULT = {
    "tasks": [], "notes": {}, "spend": [], "events": [], "sites": {},
    "shop": [], "aliases": {}, "undo": [], "llm_use": {},
    "two_key": False, "recur": {},
}

RISK_RULES = [
    (r"^(wa|mail|sms|tg|bulk|send)\b", "send"),
    (r"^(panic|shutdown|kill|restore|safe delete|unjob|habit del|vault|wipe)\b", "danger"),
    (r"^(tidy|rename|backup|fill|batch|autofile|zip|unzip|export)\b", "write"),
]

DENY_LLM = re.compile(
    r"^(llm|privacy|panic|permissions|2key|vault|sync|unalias|undo|restore)\b", re.I)

# commands whose output is stored personal data; never written to the ledger
SECRET_OUT = re.compile(r"^(recall|what is|journal|contacts|aliases|card|review)\b", re.I)
MASK_CMD = re.compile(r"^((?:remember|contact|site)\s+\w+\s*[:=]\s*)(\S+)", re.I)


def mask_cmd(cmd):
    m = MASK_CMD.match(cmd)
    return (m.group(1) + "<redacted>") if m else cmd

PENDING_TTL = 120  # seconds


def normalize(t):
    """Lowercase, collapse whitespace, strip edge punctuation. Never touches stored data."""
    t = (t or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t.strip(" .,;:!?\"'")


# ---------------------------------------------------------------- safe arithmetic
_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.Pow: operator.pow}
_UN = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def safe_eval(expr, _depth=0):
    """Arithmetic only. No names, no calls, no attributes. Raises ValueError otherwise."""
    if len(expr) > 120 or _depth > 8:
        raise ValueError("expression too large")
    tree = ast.parse(expr, mode="eval")

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant):
            if isinstance(n.value, bool) or not isinstance(n.value, (int, float)):
                raise ValueError("numbers only")
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and (abs(b) > 64 or abs(a) > 1e6):
                raise ValueError("power too large")
            v = _BIN[type(n.op)](a, b)
            if isinstance(v, (int, float)) and abs(v) > 1e18:
                raise ValueError("result too large")
            return v
        if isinstance(n, ast.UnaryOp) and type(n.op) in _UN:
            return _UN[type(n.op)](ev(n.operand))
        raise ValueError("only + - * / // % ** on numbers")

    return ev(tree)


UNITS = {
    "mm": ("len", .001), "cm": ("len", .01), "m": ("len", 1), "km": ("len", 1000),
    "in": ("len", .0254), "ft": ("len", .3048), "yd": ("len", .9144), "mi": ("len", 1609.344),
    "mg": ("mass", .001), "g": ("mass", 1), "kg": ("mass", 1000), "lb": ("mass", 453.592),
    "oz": ("mass", 28.3495), "tonne": ("mass", 1e6),
    "ml": ("vol", .001), "l": ("vol", 1), "gal": ("vol", 3.78541), "cup": ("vol", .24),
    "s": ("time", 1), "min": ("time", 60), "h": ("time", 3600), "day": ("time", 86400),
    "kb": ("data", 1024), "mb": ("data", 1024 ** 2), "gb": ("data", 1024 ** 3),
    "tb": ("data", 1024 ** 4),
}


def convert(v, a, b):
    a, b = a.lower(), b.lower()
    temps = {"c": lambda x: x, "f": lambda x: (x - 32) * 5 / 9, "k": lambda x: x - 273.15}
    if a in temps and b in temps:
        c = temps[a](v)
        return {"c": c, "f": c * 9 / 5 + 32, "k": c + 273.15}[b]
    if a in UNITS and b in UNITS and UNITS[a][0] == UNITS[b][0]:
        return v * UNITS[a][1] / UNITS[b][1]
    raise ValueError("incompatible units")


# ---------------------------------------------------------------- engine
class Engine:
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

    # -- state
    def _load_state(self):
        if not self.state_file.exists():
            s = json.loads(json.dumps(STATE_DEFAULT))
            return s
        try:
            s = json.loads(self.state_file.read_text("utf-8"))
            if not isinstance(s, dict):
                raise ValueError("not an object")
        except Exception as ex:
            bad = self.state_file.with_name(
                "state.json.corrupt-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
            try:
                self.state_file.rename(bad)
            except Exception:
                bad = self.state_file
            self._warn("[!] state.json unreadable (%s). Moved to %s, starting fresh."
                       % (type(ex).__name__, bad))
            s = json.loads(json.dumps(STATE_DEFAULT))
        for k, v in STATE_DEFAULT.items():
            s.setdefault(k, json.loads(json.dumps(v)))
        return s

    def save(self):
        tmp = self.state_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.S, indent=1, ensure_ascii=False,
                                  separators=(",", ": ")), "utf-8")
        os.replace(tmp, self.state_file)

    def _warn(self, msg):
        if not self.quiet:
            print(msg, file=sys.stderr)

    # -- api handed to packs
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

    def set_inverse(self, op, args=None):
        self._inverse = {"op": op, "args": args or {}}
        self._dirty = True

    def register_inverse(self, name, fn):
        self.inverse_handlers[name] = fn

    def add_slots(self, pattern, template, prompts):
        """Register a partial command: match, then ask for the missing slots."""
        self.slot_rules.append((re.compile(pattern, re.I), template, prompts))

    def _slot_match(self, text):
        for pat, tmpl, prompts in self.slot_rules:
            m = pat.match(text)
            if not m:
                continue
            have = {k: v for k, v in m.groupdict().items() if v is not None}
            need = [k for k in re.findall(r"{(\w+)}", tmpl) if k not in have]
            if need:
                return {"tmpl": tmpl, "have": have, "need": need, "prompts": prompts}
        return None

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

    # -- rules
    def add_rule(self, pattern, fn):
        self.rules.append((re.compile(pattern, re.I), fn))

    def add_rules(self, pairs, front=False):
        compiled = [(re.compile(p, re.I), f) for p, f in pairs]
        if front:
            self.rules[:0] = compiled
        else:
            self.rules.extend(compiled)

    def match_rule(self, cmd):
        for pat, fn in self.rules:
            m = pat.match((cmd or "").strip())
            if m:
                return fn, m
        return None, None

    def risk_of(self, cmd):
        for p, t in RISK_RULES:
            if re.match(p, cmd, re.I):
                return t
        return "safe"

    # -- plugin loader
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

    # -- resolution ladder
    def resolve(self, text):
        t = (text or "").strip()
        if not t:
            return {"cmd": None, "src": "empty", "options": []}
        fn, m = self.match_rule(t)
        if fn:
            return {"cmd": t, "src": "rule"}
        a = self.aliases.get(normalize(t))
        if a and self.match_rule(a)[0]:
            return {"cmd": a, "src": "alias"}
        verbs = sorted({c.split(" - ")[0].split()[0] for c in self.catalog} |
                       {"tasks", "add", "done", "brief", "time", "help", "habits",
                        "journal", "jobs", "llm", "undo", "log", "why"})
        parts = t.split(" ", 1)
        near = difflib.get_close_matches(parts[0].lower(), verbs, 1, 0.80)
        if near:
            cand = near[0] + (" " + parts[1] if len(parts) > 1 else "")
            if self.match_rule(cand)[0]:
                return {"cmd": cand, "src": "typo"}
        ex = [c.split(" - ")[0] for c in self.catalog]
        near = difflib.get_close_matches(normalize(t), [normalize(e) for e in ex], 3, 0.72)
        cands = [e for e in ex if normalize(e) in near]
        for c in cands:
            if self.match_rule(c)[0] and not re.search(r"[A-Z]{2,}|\bX\b|\bN\b", c):
                return {"cmd": c, "src": "fuzzy"}
        low = t.lower()
        if any(tag and tag.lower() in low for tag in self.privacy.get("never_send") or []):
            return {"cmd": None, "src": "blocked", "options": []}
        for tr in list(self.translators):
            try:
                r = tr(t)
                if r and self.llm_payload_ok(r.get("cmd") or ""):
                    return r
            except Exception:
                pass
        return {"cmd": None, "src": "teach", "options": cands[:3]}

    def llm_payload_ok(self, cmd):
        """The core, not the adapter, decides what a model may propose (C4)."""
        if not cmd or len(cmd) > 200:
            return False
        if re.search(r"[;&|`$><]", cmd):
            return False
        if DENY_LLM.match(cmd):
            return False
        return self.match_rule(cmd)[0] is not None

    # -- execution
    def _run(self, cmd, src, original=None):
        fn, m = self.match_rule(cmd)
        if fn is None:
            return "No rule matched: " + cmd
        self._bind_modules()
        self._inverse = None
        self._dirty = False
        try:
            out = fn(m)
        except Exception as ex:
            return "Command failed: %s: %s" % (type(ex).__name__, ex)
        if src in ("llm", "cache", "learned") and original:
            self.aliases[normalize(original)] = cmd
            self._dirty = True
        tier = self.risk_of(cmd)
        self.last = {"cmd": cmd, "src": src, "tier": tier,
                     "rule": "%s.%s" % (getattr(fn, "__module__", "?").split(".")[-1],
                                        getattr(fn, "__name__", "?")),
                     "out": str(out)[:200],
                     "ts": datetime.datetime.now().isoformat(timespec="seconds")}
        if self._inverse:
            self.S.setdefault("undo", []).append(dict(self._inverse, cmd=cmd, ts=self.last["ts"]))
            del self.S["undo"][:-50]
        logged = dict(self.last)
        logged["cmd"] = mask_cmd(cmd)
        if SECRET_OUT.match(cmd):
            logged["out"] = "<redacted: stored personal data>"
        try:
            with self.ledger_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(logged, ensure_ascii=False) + "\n")
        except Exception:
            pass
        if self._dirty:
            self.save()
            self._maybe_snapshot()
        self.history.append(cmd)
        del self.history[:-20]
        return out

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
        m2k = re.fullmatch(r"2key\s+(on|off)", low)
        if m2k:
            self.S["two_key"] = m2k.group(1) == "on"
            self._dirty = True
            self.save()
            return "Two-key: " + ("on — danger actions need the code printed here" if
                                  self.S["two_key"] else "off")
        ap = re.fullmatch(r"approve\s+(\w+)", low)
        if ap:
            held = p.get("confirm")
            if not held:
                return "Nothing waiting for approval."
            if not secrets.compare_digest(ap.group(1), held.get("code", "")):
                return "Wrong code. Still waiting."
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

    reply = handle

    # -- ledger / undo
    def _maybe_snapshot(self):
        """Keep a rolling 12 snapshots, written every 25 mutating commands."""
        self._since_snap += 1
        if self._since_snap < 25:
            return
        self._since_snap = 0
        try:
            self.snapshots.mkdir(exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
            f = self.snapshots / (ts + ".json")
            f.write_text(json.dumps(self.S, ensure_ascii=False), "utf-8")
            files = sorted(self.snapshots.glob("*.json"))
            for old in files[:-12]:
                old.unlink()
        except Exception:
            pass

    def replay(self, target):
        """Rebuild state as of an ISO timestamp, into a side directory. Live state untouched."""
        if not target:
            return "Usage: replay 2026-11-14T09:30"
        snaps = sorted(self.snapshots.glob("*.json")) if self.snapshots.exists() else []
        base, base_ts = None, ""
        for f in snaps:
            try:
                stamp = datetime.datetime.strptime(f.stem, "%Y%m%dT%H%M%S").isoformat(
                    timespec="seconds")
            except Exception:
                continue
            if stamp <= target:
                base, base_ts = f, stamp
        if base is None:
            return ("No snapshot at or before %s. Snapshots are kept for the last 20 "
                    "write bursts." % target)
        work = self.home / ("replay-" + target.replace(":", ""))
        work.mkdir(parents=True, exist_ok=True)
        (work / "state.json").write_text(base.read_text("utf-8"), "utf-8")
        import os as _os
        _os.environ["PICO_NO_THREADS"] = "1"
        try:
            side = Engine(home=work, load_packs=True, quiet=True)
        finally:
            _os.environ.pop("PICO_NO_THREADS", None)
        n = 0
        for line in self.ledger_file.read_text("utf-8").splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            ts = r.get("ts", "")
            if not (base_ts < ts <= target):
                continue
            if r.get("tier") in ("send", "danger"):
                continue
            side.handle(r.get("cmd", ""))
            n += 1
        s2 = side.S
        return ("Replayed %d command(s) after the %s snapshot.\n"
                "State at %s: %d task(s), %d expense(s), %d note(s).\n"
                "Written to %s (live state untouched)."
                % (n, base_ts, target, len(s2.get("tasks", [])),
                   len(s2.get("spend", [])), len(s2.get("notes", {})), work))

    def timeline(self, since=""):
        if not self.ledger_file.exists():
            return "Ledger empty."
        rows = []
        for line in self.ledger_file.read_text("utf-8").splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if since and r.get("ts", "") < since:
                continue
            rows.append("%s  %-7s %-6s %s" % (r.get("ts", "")[5:19], r.get("tier", ""),
                                              r.get("src", ""), r.get("cmd", "")))
        return "\n".join(rows[-40:]) or "Nothing since " + since

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

    def tail_log(self, n=8):
        if not self.ledger_file.exists():
            return "Empty."
        return "\n".join(self.ledger_file.read_text("utf-8").splitlines()[-n:])

    def undo(self, n=1):
        stack = self.S.get("undo") or []
        if not stack:
            return "Nothing to undo."
        done, failed = [], []
        for _ in range(max(1, min(n, len(stack)))):
            op = stack.pop()
            try:
                self._apply_inverse(op)
                done.append(op.get("cmd", "?"))
            except Exception as ex:
                failed.append("%s (%s)" % (op.get("cmd", "?"), ex))
        self.save()
        msg = "Undone: " + (", ".join(reversed(done)) if done else "nothing")
        if failed:
            msg += "\nNot invertible: " + ", ".join(failed)
        return msg

    def _apply_inverse(self, op):
        kind, a = op.get("op"), op.get("args") or {}
        S = self.S
        if kind in self.inverse_handlers:
            return self.inverse_handlers[kind](a)
        if kind == "list_rm":
            S[a["key"]].pop(a["i"])
        elif kind == "list_ins":
            S[a["key"]].insert(min(a["i"], len(S[a["key"]])), a["item"])
        elif kind == "task_done":
            S["tasks"][a["i"]]["done"] = True
        elif kind == "task_undone":
            S["tasks"][a["i"]]["done"] = False
        elif kind == "task_due":
            S["tasks"][a["i"]]["due"] = a["date"]
        elif kind == "note_set":
            S["notes"][a["k"]] = a["v"]
        elif kind == "note_del":
            S["notes"].pop(a["k"], None)
        elif kind == "dict_set":
            S[a["key"]][a["k"]] = a["v"]
        elif kind == "dict_del":
            S[a["key"]].pop(a["k"], None)
        elif kind == "move_back":
            for src, dst in a["map"]:
                p = pathlib.Path(dst)
                if p.exists():
                    pathlib.Path(src).parent.mkdir(parents=True, exist_ok=True)
                    p.rename(src)
        elif kind == "file_rm":
            p = pathlib.Path(a["path"])
            if p.exists():
                p.unlink()
        elif kind == "alias_del":
            self.aliases.pop(a["k"], None)
        else:
            raise ValueError("no inverse for " + str(kind))

    # -- core rules
    def register_core(self):
        import pico.rules as R
        R.register(self)
        self.catalog.extend(R.CATALOG)
        self.catalog.sort()


def importlib_spec(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_engine = None


def get_engine(**kw):
    global _engine
    if _engine is None:
        _engine = Engine(**kw)
    return _engine
