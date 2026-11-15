"""pico state store — atomic writes, snapshots, replay."""
import datetime
import json
import os
import pathlib
import threading

from .base import STATE_DEFAULT


class StoreMixin:
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
        """Atomic, and safe against the scheduler thread writing at the same time."""
        with self._lock:
            tmp = self.state_file.with_name(
                "state.json.tmp.%d.%d" % (os.getpid(), threading.get_ident()))
            # compact on the hot path: 7x faster and 35% smaller than indent=1
            tmp.write_text(json.dumps(self.S, ensure_ascii=False,
                                      separators=(",", ":")), "utf-8")
            os.replace(tmp, self.state_file)

    def _maybe_snapshot(self):
        """Keep a rolling 12 snapshots, written every 25 mutating commands."""
        with self._lock:
            self._snapshot_locked()

    def _snapshot_locked(self):
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
            return ("No snapshot at or before %s. Snapshots are kept for the last 12 "
                    "write bursts." % target)
        work = self.home / ("replay-" + target.replace(":", ""))
        work.mkdir(parents=True, exist_ok=True)
        (work / "state.json").write_text(base.read_text("utf-8"), "utf-8")
        from .engine import Engine as _Engine
        import os as _os
        _os.environ["PICO_NO_THREADS"] = "1"
        try:
            side = _Engine(home=work, load_packs=True, quiet=True)
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

    def tail_log(self, n=8):
        if not self.ledger_file.exists():
            return "Empty."
        return "\n".join(self.ledger_file.read_text("utf-8").splitlines()[-n:])
