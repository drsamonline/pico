"""pico dispatch — the single entry point.

`handle()` is the only way into the engine. Everything else — the CLI, the REPL,
the console, the Telegram bridge — calls it and nothing below it.
"""
import datetime
import json
import re
import secrets
import time

from .base import DENY_LLM, PENDING_TTL


class DispatchMixin:
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
