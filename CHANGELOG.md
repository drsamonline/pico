# Changelog

All notable changes. Dates are ISO. Versions follow [semver](https://semver.org/).

## 1.3.0 — 2026-11-14

The last of the "next" list, plus a concurrency bug the trigger thread exposed.

### Added

- **Trigger DSL** — `when 22:30 then a ; b`, `when every 30m then …`, `when file GLOB then …` with
  `{file}` substitution, and the negative trigger `when not CMD by 21:00 then …`. Actions are
  validated against the rule set when saved. `triggers` lists, `untrigger N` removes.
- **Chains** — `chain morning: add stretch ; tasks` defines a named sequence; `chain morning` runs it.
- **CSV loops** — `for each row in clients.csv then add call {name}`. 200-row cap, per-row failures
  reported rather than swallowed.
- **`csv pivot`** — `csv pivot city sum amt spend.csv`, with `count`, `avg`, `min`, `max` and a total.
- **Phone-only approval** — `2key phone` sends the code to the bound chat and refuses `approve` at
  the terminal. The Telegram pack marks the approval source.
- **`notify MSG`** — a first-class action, so a trigger can say something without running a command.
- Chains and loops refuse to carry a send or danger action. A saved rule cannot fire a message.

### Fixed

- **Concurrent writers corrupted state.** The scheduler thread and the REPL shared one
  `state.json.tmp` path, so a trigger firing during a command produced
  `FileNotFoundError: state.json.tmp`. `save()` now takes a re-entrant lock and writes to a
  thread-unique temp name. A four-thread stress test writing 480 tasks concurrently reports zero
  errors and zero lost writes (T29).
- `chain` read `m["body"]` on a pattern without that group, so every `chain NAME` raised
  `IndexError: no such group`.
- Trigger actions were validated with `if not E.match_rule(a)`, but `match_rule` returns a tuple and
  `(None, None)` is truthy — so an invalid action was accepted. Now checks `[0] is None`.
- `when` was briefly a `write`-tier command, which meant saving a trigger asked for confirmation.

### Performance

Both latency budgets are met for the first time: reads 0.65 ms (was 1.09), writes 3.58 ms (was 5.12).
The thread-unique temp filename removed the contention that had been costing about 1.5 ms per write.

### Tests

88 checks, up from 68. T26–T30 cover triggers, chains, the CSV loop and pivot, concurrent writers, and
phone-only approval.

## 1.2.0 — 2026-11-14

The rest of the 1.1 "next" list.

### Added

- **Replay** — a rolling 12 snapshots, written every 25 mutating commands, and `replay <ISO ts>`
  which rebuilds state into `~/.pico/replay-<ts>/` without touching live state.
- **Quarantine lifecycle** — `quarantine` lists it, `restore N` puts a file back at the path recorded
  when it was deleted, `quarantine sweep 30d` empties the old end. Restore is danger-tier with a
  preview.
- **Position** — `asset NAME AMT`, `debt NAME AMT RATE`, `net worth`, and `debt snowball [EXTRA]`
  which simulates an avalanche payoff month by month.
- **`subs audit`** — flags charges that repeat across months as candidate subscriptions. It reports;
  it cancels nothing.
- **CSV verbs** — `csv filter COND PATH`, `csv sort COL [desc] PATH`, `csv join KEY A.csv B.csv`.
  No pandas, no sqlite round-trip.
- **`chart 1,4,9`** — horizontal bars scaled to the maximum, in the terminal.
- **Phone approval** — the two-key code now goes through the notifier bus, so a bound Telegram chat
  receives it as well as the terminal.
- `PICO_NO_THREADS` suppresses the scheduler and Telegram threads, so a replay engine cannot start
  background work.

### Changed

- Snapshots are written every 25 mutations, not every 10: writes went 6.09 ms → 5.12 ms.
- The console gained 14 commands and demo handlers for net worth, chart, subs audit and the
  quarantine verbs.

### Fixed

- `replay` parsed snapshot filenames by deleting the `T` and then indexing as if it were still there,
  so the base timestamp came out as `2026-11-14T00:71:8` and every ledger row matched.
- `snowball` and `files` used `m.get()` on a `re.Match`, which has no such method.
- `_q_index` used an `and`/`or` chain that returned `{}` for a valid empty index.

### Tests

68 checks, up from 52. T21–T25 cover the quarantine lifecycle, net worth and avalanche, the
subscription audit, the three CSV verbs with `chart`, and replay.

## 1.1.0 — 2026-11-14

Everything on the 1.0 "next" list that did not need a new dependency.

### Added

- **Slot dialogue** — six partial commands ask one question instead of printing a syntax lesson:
  `emi 500000 8.5` → "how many months?" → runs. Packs register their own with
  `api["add_slots"](pattern, template, prompts)`.
- **Context** — `again`, `it` and `that` repeat the previous command.
- **Recurring tasks** — `recur daily X` reopens itself when the day turns over.
- **Due dates** — `due N YYYY-MM-DD`, and `overdue` to see what slipped.
- **Two-key approval** — `2key on` makes every danger action print a 6-hex code; plain `confirm`
  is refused and `approve <code>` completes it.
- **Quarantine** — `safe delete PATH` moves a file to `~/.pico/quarantine/` and `undo` restores it.
  Nothing is destroyed.
- **Disk questions** — `big files`, `old files Nd`, `dedupe files PATH` (sha256, report only) and
  `dedupe files PATH apply` (quarantines duplicates, reversible).
- **Spaced repetition** — `card add Q|A`, `review`, `grade 0-5`, `cards`. SM-2, no model.
- **Reports** — `report weekly`, `report month`, `decide A|B|C` (seeded, stable for the day).
- **Data** — `importcsv PATH TABLE`, read-only `sql SELECT …`, `tables`. sqlite3, stdlib.
- **`timeline [TS]`** — the ledger as a readable list.
- Four new packs: `files`, `learn`, `report`, `data`.

### Changed

- State is serialised compactly: the read path fell from 1.77 ms to 0.98 ms per call, writes from
  6.29 ms to 4.06 ms.
- The console gained 18 commands, a slot-dialogue engine that mirrors the Python one, an 80 ms
  debounce on suggestions, and iOS standalone meta tags.
- `--hash` runs on the demo page now decode per segment, so `#decide tea%7Ccoffee` works.

### Fixed

- Two-key codes were clobbered by the preview block, so the gate never armed.
- New packs shipped double-escaped regexes (`\\s` instead of `\s`), so four commands silently
  never matched. Caught by the rule-matching test.
- `re.Match` has no `.get()`, which broke the optional-argument paths in `files.py`.
- `tables` used a connection outside its `with` block.

### Tests

52 checks, up from 30. T13–T20 cover slots, context, recurrence, two-key, quarantine, cards,
sqlite and the hashing helpers.

## 1.0.0 — 2026-11-14

First public release. The engine was rebuilt around the audit findings below rather than patched
around them.

### Added

- **Resolution ladder** — rule → alias → typo → fuzzy → translator → teach, each tier inspectable.
- **Risk tiers** — `safe`, `write`, `send`, `danger`, with a 120 s consent window and blast-radius
  previews for handlers that define `fn.preview`.
- **Universal undo** — handlers register an inverse; packs can register their own via
  `api["inverse_handler"]`. 50-step stack.
- **Ledger** — one JSON line per executed command, with `cmd`, `src`, `tier`, rule, output, timestamp.
- **Local console** (`web/index.html`) — one file, no external assets, token-gated, responsive from
  390 px to 1440 px, with a client-side demo mode that runs the same resolver and arithmetic.
- **Optional translator** (`packs/llm.py`) — off by default, mode-aware provider routing, daily budget,
  response cache, alias distillation.
- **Privacy gate in the core** — `never_send` is checked before any translator is called, not inside
  the adapter.
- **Core firewall** — translator output is validated by the core: rule match, no shell metacharacters,
  length cap, deny-list.
- 30 acceptance tests covering the ten spec test cases plus state recovery and ledger redaction.
- Landing page, architecture, command reference, roadmap, privacy and security documents.
- GitHub Actions: CI across Python 3.8/3.10/3.12 and three operating systems; release workflow that
  builds one-file binaries and the source zip on every tag.

### Fixed — carried over from the audit of the v4 bundle

| Defect | Now |
| --- | --- |
| Any handler exception killed the process (`split 1000 0` was enough) | handlers are wrapped; the REPL and one-shot CLI are wrapped again |
| `dry` bypassed the resolution ladder and reported "NO MATCH" for commands that would run | `dry` calls `resolve()` and reports the tier that resolved it |
| `privacy never X` wrote a setting nothing read | enforced in the core resolver before any translator runs |
| `llm local` / `llm cloud` were cosmetic; the provider never changed | the mode constrains the provider, and a mismatch refuses with the fix |
| Packs and templates were invisible unless `--install` had run | the bundle directory is searched as well as `~/.pico/` |
| `load_plugins()` only ran under `__main__`, so importers got zero packs | loading is a method; the console and tests both use it |
| The ledger stored `recall pin` output verbatim, and `log` printed it | output of secret-bearing commands is redacted; `remember`/`contact` values are masked too |
| One corrupt `state.json` bricked the tool permanently | quarantined to `state.json.corrupt-<ts>`, engine starts empty |
| The model could trigger ungated `tidy`/`backup` | write-tier commands from a translator are gated like a send |
| `journal 5` was ambiguous and shadowed the add rule | `journal show N` reads, `journal text` writes |
| `remind 18:30` with no text did not match | message is optional |
| `disc 999 150` returned a negative price; `split` silently dropped a cent | range checks; the rounding residue is stated |
| `calc` used `eval` with a character allowlist | AST walker with power and magnitude caps |
| Two engines in one process shared handler state | module-level engine refs are rebound per call |
| `undo` swallowed `undone` because of a prefix check | full-match regex |

### Known limits

- Timers, reminders and daily jobs fire only while pico runs.
- State is plaintext JSON; nothing is encrypted.
- No OCR, speech, QR rendering or two-way WhatsApp without an external tool or Meta's Cloud API.
- `write`-tier commands typed by hand are not gated, only undoable. Deliberate, and open for review.
- The core is 30,794 B against a 20 KB spec budget. The overage is the inverse registry, the
  translator firewall, the privacy gate, slot dialogue, snapshots, replay and the write lock.
  Stated rather than hidden; the CI ceiling is 32 KB.
