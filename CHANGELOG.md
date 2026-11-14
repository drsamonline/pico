# Changelog

All notable changes. Dates are ISO. Versions follow [semver](https://semver.org/).

## 1.8.0 — 2026-11-14

### Changed

- **The quarantine lifecycle has its own module.** `cmd_files.py` (7.3 KB) split into `cmd_files.py`
  (3.9 KB: sort, archive, find, fill) and `cmd_quarantine.py` (3.6 KB: `safe delete`, `quarantine`,
  `restore`, `sweep`, the index that remembers where a file came from). Six `cmd_*` modules now.
- **`csv sort` takes a column type.** `csv sort score:number desc x.csv` forces a numeric read,
  `:text` forces lexicographic, and the default compares numbers numerically and places text after
  them. The default previously raised `TypeError` on a mixed column, because the sort key mixed
  floats and strings.

### Added

- **A dismissible install prompt.** The console listens for `beforeinstallprompt` and offers Install /
  Not now; the dismissal is remembered in `localStorage`. iOS, which never fires that event, gets the
  Share → Add to Home Screen instruction instead. It never appears in standalone mode and never from
  `file://`.

### Fixed

- `csv sort` on a mixed column crashed with `TypeError: '<' not supported between instances of 'str'
  and 'float'`. The auto key is now a tuple, so the two never meet.
- The `csv sort` handler read a `kind` group the pattern never defined, so every typed call raised
  `IndexError: no such group` before the type was even considered.

### Tests

158 checks, up from 143. T46 covers the module split, T47 the three sort modes and the crash case,
T48 the install prompt's triggers and guards.

## 1.7.0 — 2026-11-14

### Changed

- **`pico/rules.py` split into five `cmd_*` modules.** The 20 KB handler file became `cmd_tasks`,
  `cmd_money`, `cmd_time`, `cmd_files` and `cmd_web`; `rules.py` keeps only the pattern table, the
  help text and the catalogue, at 5.8 KB. `rules.register()` records the five modules on
  `engine.core_modules` and binds their `E` globals immediately, and `_bind_modules()` rebinds them
  alongside every pack's — which is what keeps two engines in one process isolated.
- **Backoff moved from the rule to the action.** A rule with three actions no longer stops as a unit:
  the failing action alone backs off for 2, 4, 8, 16, 32 then 60 minutes while the others keep
  running. `triggers` shows how many actions are backing off.
- **`csv pivot … order by key|value [asc|desc]`** — groups were always sorted by aggregate descending.

### Added

- **The console is installable.** `web/manifest.webmanifest`, two PNG icons and `sw.js`, served by
  `pico/ui.py` and shipped in `docs/` so the GitHub Pages build installs too. Add to Home Screen gives
  a standalone window that opens offline. The worker deliberately never caches `/cmd` or
  `/api/state`: the engine must always be live, or the console would answer from a stale cache.

### Fixed

- `pico/rules.py` lost three `fn.preview` assignments in the split, because they are attribute
  targets rather than plain assignments — `dry safe delete` stopped showing what it would touch. T17
  caught it; they are back and T42 asserts them.
- `help_` was dropped from the registry, so every command raised `NameError` on the first call.
- `cmd_files` lost its `re` import, which `fill` needs.
- `csv pivot … order by value asc` ignored the direction: the regex captured only the key, not the
  direction.
- T40 asserted rule-level backoff, which no longer exists; rewritten for per-action semantics.

### Tests

143 checks, up from 125. T42 covers the module split and the surviving previews, T43 per-action
backoff, T44 the four ordering modes, T45 the manifest, icons and worker.

## 1.6.0 — 2026-11-14

### Changed

- **`pico/engine.py` split into four modules.** 31 methods in one 31 KB file became:
  `store.py` (state, atomic writes, snapshots, replay), `ladder.py` (rules, risk tiers, slot
  dialogue, the translator firewall), `ledger.py` (execution, inverses, undo) and `base.py`
  (constants and pure helpers). `Engine` is now `class Engine(StoreMixin, LadderMixin, LedgerMixin)`,
  so every attribute a pack reaches for still resolves on the instance, and `engine.py` re-exports
  `safe_eval`, `convert`, `normalize` and `__version__` for the code that imports them.
- **Budget accounting follows the split.** The unit is now the package (64 KB ceiling, 55,814 B
  actual) rather than one file, plus packs and console.
- A linter pass over the whole tree after the split caught two names that had been in the old
  module's import list but are used by the moved methods: `difflib` in `resolve` and `threading`
  in `save`. Both fixed, plus a circular import in `replay` that is now a local import.

### Added

- **Trigger backoff** — a rule whose action still fails after the retry backs off for 2, 4, 8, 16,
  32 then 60 minutes. `triggers` shows the failure count and the remaining wait; a success clears it.
- **`csv pivot … having EXPR`** — `csv pivot city sum amt spend.csv having sum>100` filters groups
  after aggregation, and says so when nothing survives.

### Tests

125 checks, up from 111. T39 asserts the mixin composition and the re-exports, T40 the backoff curve,
T41 `having`.

## 1.5.1 — 2026-11-14

### Fixed

- **`pico --version` reported 1.2.0** while the console said 1.5.0. The engine constant was never
  bumped from 1.2.0 through three releases. It is now 1.5.1, and T38 fails the suite whenever the
  engine, the console chip, the boot script and the badge disagree.

### Changed

- **Size budgets replaced, not chased.** The 20 KB core figure came from a spec written for a bundle
  with no undo engine, inverse registry, translator firewall, privacy gate, slot dialogue, snapshots,
  replay or write lock. Eight subsystems later the number was wrong, not the code. New ceilings, all
  measured size plus about 30% headroom:

  | Part | Ceiling | Actual |
  | --- | --- | --- |
  | core | 40 KB | 30,794 B |
  | rule set | 28 KB | 20,293 B |
  | front-end | 8 KB | 3,969 B |
  | packs | 96 KB | 63,489 B |
  | console | 96 KB | 59,237 B |

- **The CI check now covers every part.** It previously measured only core and packs, so
  `pico/rules.py` and `pico/ui.py` could have grown unchecked. All five are now enforced on every
  push, and a breach fails the build with the offending part named.

## 1.5.0 — 2026-11-14

### Added

- **OR-ed conditions** — `when 22:30 unless away or weekend then …`. Any one true condition vetoes the
  trigger. A pair containing an unrecognised condition is refused whole.
- **Firing history** — the last 5 firings per rule are kept with timestamp, ok/FAIL and output.
  `triggers` shows the count; `trigger log [N]` prints the detail.
- **Wayland clipboard** — `wl-paste` is tried before `xclip` and `xsel`, so the clipboard trigger
  works on a modern Linux session.
- **`csv pivot` on any number of keys** — `csv pivot a,b,c sum amt x.csv`.

### Fixed

- **`unless weekend` fired on weekends.** `_cond_ok` mixed two meanings: it returned the *condition*
  for `weekend` and the *negation* for `away`. Splitting it into `_cond_true` (does the condition
  hold?) and `_cond_ok` (may the trigger fire?) made every condition consistent. The old T31
  assertion had encoded the bug as expected behaviour and was inverted to match.
- `triggers` crashed with `AttributeError: 'list' object has no attribute 'get'` once a rule carried
  more than one condition.

### Tests

108 checks, up from 101. T35–T37 cover OR-ed conditions, firing history, and three-key pivot.

## 1.4.0 — 2026-11-14

The trigger DSL finished.

### Added

- **`unless` conditions** — `when 22:30 unless away then …`. `COND` is `away`, `weekend`, `weekday`,
  `file GLOB` (skip if a matching file exists) or `exists PATH`. A bad condition is refused with the
  list of what is accepted.
- **`away on` / `away off`** — a state flag that pauses every trigger gated with `unless away`.
- **Clipboard trigger** — `when clip matches REGEX then CMD`, with `{clip}` substitution. Reads via
  `pbpaste`, `xclip`, `xsel` or `powershell Get-Clipboard`, in that order, and stays inert with no
  error when none is present.
- **`watch FOLDER then CMD`** — shorthand for a file trigger on `FOLDER/*`.
- **Retry** — a failing action is retried once; `triggers` shows the last error against that rule.
- **Multi-key `csv pivot`** — `csv pivot city,plan sum amt spend.csv`, grouped on up to two columns.

### Fixed

- `csv pivot` rejected a comma in the key list, so the two-key form fell through to "no rule matched".
- The T31 and T34 assertions were wrong, not the code: the first expected zero firings while a second
  trigger was legitimately due, the second expected a total that the data does not contain. Both
  corrected rather than the behaviour bent to fit them.

### Tests

101 checks, up from 88. T31–T34 cover `unless`, `watch` and the clipboard trigger, the retry path,
and multi-key pivot.

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
- Budgets are the project's own, not the spec's: core 40 KB, rule set 28 KB, front-end 8 KB,
  packs 96 KB, console 96 KB. See the Budgets section of the README.
