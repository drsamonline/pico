"""pico ledger — execution, inverses, undo."""
import datetime
import json
import pathlib
import re
import secrets

from .base import MASK_CMD, SECRET_OUT, mask_cmd, normalize


class LedgerMixin:
    def set_inverse(self, op, args=None):
        self._inverse = {"op": op, "args": args or {}}
        self._dirty = True

    def register_inverse(self, name, fn):
        self.inverse_handlers[name] = fn

    LEDGER_CAP = 5000          # lines before the file is rotated
    LEDGER_KEEP = 1            # generations kept beside it

    def _append_ledger(self, line):
        """Append one line, rotating at the cap so the file cannot grow forever.

        `ledger.1.jsonl` is the previous generation; older ones are dropped. The
        audit trail stays bounded without a background job.
        """
        f = self.ledger_file
        try:
            with f.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:
            return
        self._ledger_lines = getattr(self, "_ledger_lines", 0) + 1
        if self._ledger_lines < self.LEDGER_CAP:
            return
        self._ledger_lines = 0
        try:
            target = f.with_name("%s.1.jsonl" % f.stem)
            if target.exists():
                target.unlink()
            f.rename(target)
            for extra in sorted(f.parent.glob("%s.*.jsonl" % f.stem)):
                try:
                    if int(extra.name.split(".")[-2]) > self.LEDGER_KEEP:
                        extra.unlink()
                except (ValueError, IndexError):
                    pass
        except Exception:
            pass

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
        self._append_ledger(json.dumps(logged, ensure_ascii=False))
        if self._dirty:
            self.save()
            self._maybe_snapshot()
        self.history.append(cmd)
        del self.history[:-20]
        return out

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
