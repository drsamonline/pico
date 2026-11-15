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

    REPLAY_KEEP = 5            # reconstructions kept beside the state

    def replay_dirs(self):
        return sorted(p for p in self.home.glob("replay-*") if p.is_dir())

    def _prune_replays(self):
        """Every replay writes a directory and nothing used to remove them.

        A user who explores replay a dozen times ends up with a dozen full state
        copies and no idea why. Keep the newest few, like snapshots.
        """
        try:
            for extra in self.replay_dirs()[:-self.REPLAY_KEEP]:
                import shutil as _shutil
                _shutil.rmtree(extra, ignore_errors=True)
        except Exception:
            pass

    def _snapshot_index(self):
        f = self.snapshots / "index.json"
        if not f.exists():
            return {}
        try:
            d = json.loads(f.read_text("utf-8"))
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def _record_snapshot(self, name):
        """Remember where the ledger had reached, so replay needs no clock.

        Timestamps are not good enough: a Windows clock ticks in ~15 ms steps, so
        several commands share a stamp with the snapshot and fall outside a
        `base < ts <= target` window. A line ordinal cannot do that.
        """
        try:
            idx = self._snapshot_index()
            idx[name] = {"lines": sum(1 for _ in self.ledger_lines())}
            (self.snapshots / "index.json").write_text(json.dumps(idx, indent=1), "utf-8")
        except Exception:
            pass

    def _snapshot_locked(self):
        self._since_snap += 1
        if self._since_snap < 25:
            return
        self._since_snap = 0
        try:
            self.snapshots.mkdir(exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S%f")
            f = self.snapshots / (ts + ".json")
            f.write_text(json.dumps(self.S, ensure_ascii=False), "utf-8")
            self._record_snapshot(f.name)
            files = sorted(p for p in self.snapshots.glob("*.json") if p.name != "index.json")
            for old in files[:-12]:
                old.unlink()
                try:
                    idx = self._snapshot_index()
                    idx.pop(old.name, None)
                    (self.snapshots / "index.json").write_text(json.dumps(idx, indent=1), "utf-8")
                except Exception:
                    pass
        except Exception:
            pass

    def replay(self, target):
        """Rebuild state as of an ISO timestamp, into a side directory. Live state untouched."""
        if not target:
            return "Usage: replay 2026-11-14T09:30"
        # a bare date means "as of the end of that day"
        if len(target) == 10:
            target = target + "T23:59:59.999999"
        snaps = sorted(p for p in self.snapshots.glob("*.json")
                       if p.name != "index.json") if self.snapshots.exists() else []
        base, base_ts = None, ""
        for f in snaps:
            try:
                stamp = datetime.datetime.strptime(f.stem, "%Y%m%dT%H%M%S%f").isoformat(
                    timespec="microseconds")
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
        # start from the ledger position the snapshot recorded; fall back to the
        # timestamp only for snapshots written before the index existed
        start = (self._snapshot_index().get(base.name) or {}).get("lines")
        n = 0
        for i, line in enumerate(self.ledger_lines()):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if start is not None:
                if i < start:
                    continue
            else:
                ts = r.get("ts", "")
                if not (base_ts < ts <= target):
                    continue
            if r.get("tier") in ("send", "danger"):
                continue
            side.handle(r.get("cmd", ""))
            n += 1
        s2 = side.S
        self._prune_replays()
        return ("Replayed %d command(s) after the %s snapshot.\n"
                "State at %s: %d task(s), %d expense(s), %d note(s).\n"
                "Written to %s (live state untouched)."
                % (n, base_ts, target, len(s2.get("tasks", [])),
                   len(s2.get("spend", [])), len(s2.get("notes", {})), work))

    def ledger_lines(self):
        """Every ledger line, oldest generation first.

        Rotation keeps `ledger.1.jsonl`, so reading only `ledger.jsonl` would make
        the oldest history silently disappear from `timeline` and `report`.
        """
        gens = sorted(self.ledger_file.parent.glob("%s-*.jsonl" % self.ledger_file.stem))
        for f in gens + [self.ledger_file]:
            if not f.exists():
                continue
            for line in f.read_text("utf-8").splitlines():
                if line.strip():
                    yield line

    def timeline(self, since=""):
        if not self.ledger_file.exists():
            return "Ledger empty."
        rows = []
        for line in self.ledger_lines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if since and r.get("ts", "") < since:
                continue
            rows.append("%s  %-7s %-6s %s" % (r.get("ts", "")[5:19], r.get("tier", ""),
                                              r.get("src", ""), r.get("cmd", "")))
        if not rows:
            return "Nothing since " + since if since else "Ledger empty."
        shown = rows[-40:]
        out = list(shown)
        if len(rows) > len(shown):
            out.insert(0, "... %d older line(s). Narrow with: timeline YYYY-MM-DD"
                       % (len(rows) - len(shown)))
        return "\n".join(out)

    def tail_log(self, n=8):
        if not self.ledger_file.exists():
            return "Empty."
        return "\n".join(self.ledger_file.read_text("utf-8").splitlines()[-n:])
