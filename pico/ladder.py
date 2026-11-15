"""pico resolution ladder — rules, risk tiers, slot dialogue."""
import difflib
import re

from .base import DENY_LLM, PLACEHOLDER, RISK_RULES, normalize


class LadderMixin:
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
        # an alias bound to a verb takes arguments: `karch 100 food` -> `spend 100 food`
        head, _, rest = t.partition(" ")
        if rest:
            verb = self.aliases.get(normalize(head))
            if verb:
                cand = verb + " " + rest
                if self.match_rule(cand)[0]:
                    return {"cmd": cand, "src": "alias"}
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
            # a catalogue entry is a template: `decide A|B|C` must not run itself
            if self.match_rule(c)[0] and not PLACEHOLDER.search(c):
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

    def llm_payload_ok(self, cmd):
        """The core, not the adapter, decides what a model may propose (C4)."""
        if not cmd or len(cmd) > 200:
            return False
        if re.search(r"[;&|`$><]", cmd):
            return False
        if DENY_LLM.match(cmd):
            return False
        return self.match_rule(cmd)[0] is not None
