# Changelog

All notable changes. Dates are ISO. Versions follow [semver](https://semver.org/).

## 1.40.0 — 2026-11-15

### Added — secrets are entered at the prompt, never built in

There was no token or key anywhere in the repo or the binaries, but there was also no way to *enter*
one: you had to know that `~/.pico/telegram.token` had to exist, and the model wanted a path in a config
key. Two commands close that.

| Command | Effect |
| --- | --- |
| `telegram token <TOKEN>` | writes `~/.pico/telegram.token`, mode `0600`, atomically |
| `llm key <KEY>` | writes `~/.pico/llm.key`, mode `0600`, and sets it as `api_key_file` |
| `… status` | says whether one is set and how long it is — never the value |
| `… forget` | removes it |

Both refuse an obvious non-secret (`telegram token nope` wants `digits:letters`; `llm key short` is under
16 characters), never echo the value, and never reach the ledger — it records
`telegram token <redacted>` and `llm key <redacted>`. `doctor` reports presence and file mode, and warns
with the exact `chmod` when the mode has drifted.

`docs/SETUP.md` is new: install per platform, then the three optional paths (Telegram, model, phone),
then what is already done and what nobody has done yet. `SECURITY.md` gained the reasoning for a file
rather than an environment variable.

### Fixed

- `write_secret` in `base.py` used `pathlib` without importing it, and the telegram pack had no engine
  handle; both found the moment the command was first run.

### Tests

457 checks, up from 439. T105 the whole secret lifecycle — refused inputs, `0600`, no echo, no value in
the ledger, `doctor` showing presence only, removal. T106 scans the source for anything shaped like a
bot token or an API key, and asserts the spec bundles no secret file.

## 1.39.0 — 2026-11-15

### Fixed

- **`redact` labelled a credit-card number `<PHONE>` and ate the word after it.** The phone pattern
  `\+?\d[\d\s-]{7,}\d` matched any long digit run, so `card 4111111111111111` became `<PHONE>` — the
  right digits masked under the wrong label, which matters when the file is later read by someone
  deciding what is sensitive. A card rule now runs first: `(?:\d[ -]?){12,18}\d`, which ends on a digit,
  so `4111 1111 1111 1111 and` keeps its ` and` instead of swallowing it.
- **A date was masked as a phone number.** `2026-11-15` matched the phone rule. `PATTERNS["dates"]`
  existed and was never used; redact now applies DATE before PHONE, and both `2026-11-15` and
  `15/11/2026` mask as `<DATE>`.

### Verified, not changed

`importcsv` sanitises table names (`"select"` → `_select_`, `t"x` → `t_x`), the ledger masks
`remember pin=…` to `remember pin=<redacted>` and the reply to `<redacted: stored personal data>`, and
`privacy never TAG` blocks a tag from reaching the model — which is what `docs/COMMANDS.md` promises,
and all it promises.

### Tests

439 checks, up from 428. T104 each pattern: email, card in both spacings, both date forms, phone, URL,
an amount left alone, the word after a card surviving, and the source file untouched.

## 1.38.0 — 2026-11-15

### Fixed — two ways the recovery path lied

- **Two deletes of the same filename in the same second kept one copy, not two.** The quarantined name
  was `<second>_<name>`, so deleting `a.txt` twice inside a second made the second copy overwrite the
  first — the user's first file was gone, and the index had one entry where there should have been two.
  Names now carry microseconds and a counter, and both copies survive. Proved by reverting the fix:
  the old naming kept `SECOND` and lost `FIRST`.

  This is the fourth time a one-second stamp has been used as an identifier, and the first time it
  destroyed data. The other three: ledger generations (1.23.0), snapshots (1.26.1), backups (1.29.0).

- **`undo` said "Undone" after the quarantined copy had been swept.** The `move_back` inverse checked
  `if p.exists()` and did nothing when it did not, so the ledger reported success while restoring
  nothing. On a recovery path that is the worst possible message. It now raises, and `undo` reports
  `Not invertible: … is gone from the quarantine — it was swept, so this cannot be undone`.

### Tests

428 checks, up from 418. T102 two same-name quarantines keeping both contents, T103 the swept-copy undo
refusing honestly while a live copy still undoes.

## 1.37.0 — 2026-11-15

### Fixed

- **Every command that calls `handle()` internally recorded a duplicate inverse.** `_run` set
  `self._inverse = None` before calling the handler, but a handler like `chain` calls `handle()` again —
  and the inner call left *its* inverse in place. The outer frame then read that stale value and
  appended it a second time under its own name. Running a three-step chain put four entries on the undo
  stack:

  ```
  {"op":"list_rm","args":{"i":0},"cmd":"add a"}
  {"op":"list_rm","args":{"i":1},"cmd":"add b"}
  {"op":"list_rm","args":{"i":2},"cmd":"add c"}
  {"op":"list_rm","args":{"i":2},"cmd":"chain three"}   <- the duplicate
  ```

  `undo 3` then undid the duplicate first, failed with `pop index out of range`, and left a task behind.
  The inverse now remembers which frame set it and only that frame records it. Same fix covers trigger
  actions, `for each`, and both `doctor probe` commands, which all re-enter `handle()`.

- **`chain` did not say that one `undo` reverses one step.** It does now:
  `(3 step(s). `undo 3` reverses all of them.)` — appended only when the chain has more than one step.

### Note on the fix that did not survive

The first attempt tagged each inverse with the chain's name so `undo` could report "step 2 of 3". It
mis-assigned entries through the nested calls — the same stale-frame problem, one layer up — and made
`undo` worse. It was reverted; the tag was solving a symptom of the bug above.

### Tests

418 checks, up from 411. T101 the exact stack contents after a chain, `undo 3` reversing all three,
a plain command still recording one inverse, and a one-step chain staying quiet.

## 1.36.0 — 2026-11-15

Another probe round, another three defects. The first one was the worst failure mode this project has
produced.

### Fixed

- **`chain a: chain a` then `chain a` hung the process forever.** Not slow, not an error — no output, no
  prompt, a dead REPL until Ctrl-C. A saved sequence re-enters `handle()`, and nothing limited how deep.
  Two budgets now stop it: nesting depth (8) and total actions per top-level command (500). Both refuse
  with a sentence that says which budget ran out. Mutual recursion (`b: chain c`, `c: chain b`) is
  covered by the same depth count, a legitimate nested chain still runs, and a `danger`-tier action
  inside a chain is still skipped by the existing gate.
- **`importcsv` crashed on a ragged CSV** with `ProgrammingError: Incorrect number of bindings`, after
  dropping the target table — so the table was gone and the data never arrived. A row *wider* than the
  header is now refused with the row number, because importing it would silently drop columns; a row
  *narrower* is padded with empty strings, because refusing that would be pedantry.
- **`journal show -1` wrote a journal entry** instead of showing one. The `show N` rule required digits,
  so `-1` fell through to the "journal this text" rule and a request to *read* became a write. The rule
  takes a signed number now and refuses anything not positive, and `journal show 0` says the same.

### Tests

411 checks, up from 399. T99 the chain budgets in four directions, T100 the CSV arity and the journal
bounds.

## 1.35.1 — 2026-11-15

### Fixed

- **The `safe delete` home guard did nothing on Python 3.8.** It used `Path.is_relative_to`,
  which shipped in 3.9. On 3.8 the call raised `AttributeError` straight into a bare `except`, so
  `safe delete /tmp` — a directory containing pico's home — still prompted and would have moved the
  quarantine into itself. The guard now uses `parents`, which works everywhere, and the bare `except`
  that hid it is gone. Only the 3.8 leg of the matrix caught this; every other leg was green.

### Added

- **`tools/py38.py`** — looks for post-3.8 names in call or attribute position across `pico/`, `packs/`,
  `tools/`, `tests/` and the launcher, and fails the build. CI runs it. Proved by putting
  `is_relative_to` back: the gate names the file, the line and the release.

  A matrix leg is the slowest possible way to learn this. The gate is a second.

### Tests

399 checks, up from 397. T98 runs the gate.

## 1.35.0 — 2026-11-15

### The write path, decided on measurements

Asked for the curve instead of an opinion, so here it is — median of 10–25 runs, one machine:

| Tasks | state.json | read | write |
| --- | --- | --- | --- |
| 1,000 | 36 KB | 0.49 ms | 2.07 ms |
| 5,000 | 168 KB | 1.10 ms | 6.48 ms |
| 20,000 | 674 KB | 0.73 ms | 19.10 ms |
| 50,000 | 1,700 KB | 0.37 ms | 44.89 ms |

Reads are flat because the listing is capped; writes are linear in state size. Twenty thousand tasks is
five a day for eleven years, and 19 ms there is inside a keystroke. **The append-only journal is not
being built**: it puts the file holding the user's tasks at risk to fix a latency no user has felt, and
the original 5 ms figure was this project's own spec. The curve is in the README so the decision can be
reopened with numbers. The roadmap now has no open items and nothing "worth the complexity".

### Fixed — two defects from the next probe round

- **`remember key` silently stored `k: v`.** The fuzzy tier takes a catalogue entry, strips its
  description and runs what is left — and `remember k=v` is a template whose placeholders are single
  lowercase letters. `PLACEHOLDER` caught `X`, `N` and all-caps words but not `k` or `v`, so a typo
  wrote a note that looked like it had worked. It now matches single lowercase letters as well, and the
  guard is applied to the command part of the entry rather than the whole line, so `doctor probe write`
  stays correctable. The same hole existed in the console's guard; the parity gate keeps them in step.
- **`safe delete ~/.pico` crashed after the user confirmed.** Moving a directory into a subdirectory of
  itself is an error `shutil` raises late. `safe delete` now refuses a target that is pico's own home or
  contains it, and the preview returns empty so the refusal is shown *before* the confirmation prompt
  rather than after it.

### Tests

397 checks, up from 382. T96 the template guard in both directions — a template must not run, a real
command must, a typo must still be corrected. T97 the home refusal, that nothing is moved, and that a
real file still asks, confirms and undoes.

## 1.34.0 — 2026-11-15

### Decided

Two questions the roadmap had carried since 1.18, answered rather than deferred.

- **A typed `write` is not gated.** The gate exists to stop a command the user did not ask for; a typed
  `tidy` *is* the ask. A confirmation in front of the user's own sentence buys no safety, and the
  pressure it creates is to type `confirm` reflexively — the exact habit that makes the `danger` gate
  worthless when it matters. A typed write gets an inverse instead, so `undo` reverses it, and the
  quarantine, so a deletion is recoverable afterwards. Recorded in `docs/ARCHITECTURE.md`.
- **A reconstruction lives for five runs or seven days, whichever keeps more.** `replay` used a bare
  count of five; the ledger already uses count-or-age, and two different retention rules in one home is
  a thing to explain rather than a thing to have.

### Docs

- **The roadmap has no open questions left.** Every one it carried is answered, and the table says
  where each answer lives. The "worth the complexity" list holds one item — the journal.

### Tests

382 checks. T87 now covers both halves of the retention rule: nothing inside the floor or the window is
lost, and an aged one past the floor goes on the next replay.

## 1.33.0 — 2026-11-15

### Added

- **`alias P -> CMD` binds any phrase, in any script, to a command.** Aliases existed but only the
  translator could create one; there was no way to say "when I type this, run that". Now:

  ```
  alias खर्च -> spend
  खर्च 100 खाना        # Logged.
  alias kaam -> tasks
  kaam                  # Nothing pending.
  ```

  An alias bound to a verb takes arguments, so `खर्च 100 खाना` becomes `spend 100 खाना`. An alias
  cannot shadow an existing command, and a target that matches no rule is refused rather than stored as
  a dead end. `aliases` lists them, `unalias` removes one, and both are undoable.

  This closes the roadmap item "Devanagari in command names". The answer is not a built-in language
  pack — India has twenty-two scheduled languages and picking one as the default would contradict the
  project's own stance. The user binds the words they use.

### Fixed

- **T86 was flaky, one run in three.** It built a real `TextIOWrapper` over a `BytesIO` and asked it to
  reconfigure, which intermittently raised `MemoryError` inside the codec lookup. It now passes a
  recording stub to `utf8_console` and proves the real path through the CLI under `PYTHONIOENCODING=cp1252`.
  Four consecutive clean runs after.

### Tests

381 checks, up from 367. T95 covers binding, arguments, refusal to shadow, refusal of a dead target,
rebinding, unalias, undo, and persistence across a restart.

## 1.32.1 — 2026-11-15

### Fixed

- **The doc gate ran the test suite a second time, and on Windows the two runs disagreed.**
  `tests/smoke_test.py` reported 367 passing; the gate's own re-run reported 365, so it failed the
  build with "README.md says 367 tests, suite reports 365" — a documentation error that was really a
  measurement error. The suite now writes its count to `tests/.count` and the gate reads that, or takes
  `--count N`. The suite runs once.

  Fourth flaky gate in five releases, and the same shape every time: a check that measures something
  instead of reading what was already measured. The clock, the line endings, the console encoding, and
  now a second run.

## 1.32.0 — 2026-11-15

Two of the three open questions on the roadmap, answered in code.

### Changed

- **Aliases leave `state.json` once there are fifty.** They are the one part of the state that can grow
  without bound — a user who aliases everything ends up with a state file that is mostly aliases. Past
  `ALIAS_SPLIT` they are written to `aliases.json` and cleared from the state; below it they stay put,
  because a second file for five entries is worse than the five entries. The loader merges both, so a
  half-migrated home still loads, a corrupt `aliases.json` degrades to empty rather than crashing, and
  going back to an older build loses nothing.
- **A job that fails three times switches itself off.** A reminder that errors every morning is noise,
  and silence about it is worse. The count is per job, a successful run resets it, `jobs` shows
  `<off: failed 3 times>`, and re-adding the same time and command re-arms it in place instead of
  creating a duplicate.

### Tests

367 checks, up from 354. T93 the alias threshold in both directions plus a corrupt file, T94 the
switch-off, the listing, that an off job does not fire, and that re-adding re-arms it.

T93 and T94 rebind the schedule pack with `mod.setup(e.api)` first. The pack binds its globals once per
process, so a later engine's test was reading the first engine's jobs — T91 had been passing on that
luck rather than on the code.

## 1.31.0 — 2026-11-15

Four small items, one release.

### Changed

- **`fill` takes an output directory.** `fill letter to ~/out name=Asha body=hi` writes there; without
  `to` it still writes to the home. A directory that does not exist is refused, not created.
- **`fill` is now covered by `doctor probe write`.** It was the one write path no probe touched, because
  it could only write into the user's home. With a target directory it runs into the probe's scratch
  directory like everything else, and the probe still leaves the home clean.
- **A scheduled job that throws is recorded, not printed into the void.** The loop used to
  `print("[job error]", ex)`, which in `--serve` goes to a console nobody is watching. Failures are now
  appended to `job_errors` (capped at 20), notified through the same channel as the job, and shown by
  `doctor` as `job errors  3 recorded, newest 09:00: ValueError: …`.
- **The contrast gate covers non-text pairs.** Three more at 3:1: a border on the page, an accent
  outline on a panel, and tertiary ink on a panel.

### Fixed

- **`--line2` failed WCAG AA and drew the boundary of every control.** At `#2b3d4d` on `#0b0f14` it
  measured 1.72:1, and it is the only visible edge on a button, the input, the suggestion popup and the
  install bar — their fills are 1.17:1 against the page. It is now `#4e6b85`, 3.45:1 on the page and
  3.15:1 on a panel. The palette gate found this the moment it was given a non-text pair to check.

### Docs

- **The roadmap was rewritten.** It still claimed the ledger kept one generation (five since 1.23.0), a
  96 KB ceiling (a baseline since 1.25.0), and listed `net worth`, `debt snowball` and `subs audit` as
  future work when all three had shipped. The shipped list stopped at 1.18; it now runs to 1.31. The
  gate table is in it too.

### Tests

354 checks, up from 340. T90 the `fill` target directory and its refusal, T91 the job-error record and
its cap, T92 that the write probe covers `fill` and still leaves the home clean.

## 1.30.0 — 2026-11-15

### Added

- **`tools/contrast.py`** — reads the console's custom properties out of `web/index.html`, computes the
  WCAG contrast ratio for the eleven pairs that carry text, and fails below the target. CI runs it.

  This follows a contrast fix committed directly to the console (`3297cc4`), which corrected
  `button.mini` and the code block. That fix is kept and is measured now; the gate exists so the next
  palette nudge cannot undo it silently.

  It found one thing the hand fix did not: `--acc2` on the page background is 4.15:1. That turned out
  not to be a failure — `--acc2` is only ever a border and a filled button, so the pair that matters is
  the white label on it, at 4.63:1. The check was corrected to measure the colour where it is used,
  which is the difference between a gate and a rule.

### Tests

340 checks, up from 335. T89 runs the gate and checks the ratio function itself against the two
anchors that are true by definition: black on white is 21:1, a colour against itself is 1:1, and the
order of a pair does not change the answer.

## 1.29.0 — 2026-11-15

### Fixed

- **Backups overwrote each other and grew without limit.** The name carried a date only, so a second
  backup on the same day replaced the first — 25 backups produced one file. Across days nothing was ever
  removed. Names now carry microseconds and a rolling window of 20 is kept; the message says how many
  were dropped. Pruning is safe here because every file was produced by `backup` from a source the user
  still has.
- **`doctor` now warns when the quarantine grows.** Deleted files are held until someone sweeps them,
  and nothing sweeps automatically. The line reports the count and size, turns into a warning past 50 MB
  or 100 files, and names the command that fixes it.

### The same bug, three times

Microsecond-resolution names have now been needed in three places, each found separately:

| Release | Where | Symptom |
| --- | --- | --- |
| 1.23.0 | ledger generations | five rotations in one second became one file |
| 1.26.1 | snapshots | replay could not tell two snapshots apart |
| 1.29.0 | backups | 25 backups became one file |

A one-second stamp is not an identifier. It is worth stating once rather than rediscovering.

### Tests

335 checks, up from 331. T88 runs 25 backups and asserts the window, unique names, that the newest is a
real zip, and that the count is reported.

## 1.28.0 — 2026-11-15

### Fixed

- **Every `replay` left a directory behind and nothing removed them.** A reconstruction writes a full
  state copy into `replay-<stamp>/`, so a user who explores replay a dozen times ends up with a dozen
  state copies and no idea why. Nine replays produced nine directories. The newest five are now kept,
  like snapshots, and the rest are removed after each replay.
- **`doctor` did not mention them.** It now reports how many reconstructions are kept and how much they
  cost: `replays  5 kept, 24125 B (newest replay-2026-11-15T125304.826709)`.

### Tests

331 checks, up from 327. T87 runs nine replays and asserts the keep limit holds, that the newest
reconstruction is intact, and that `doctor` reports them.

## 1.27.0 — 2026-11-15

### Fixed

- **A Devanagari answer crashed the CLI on a Windows console.** `pico expenses` printing a category
  like `खाना` raised `UnicodeEncodeError` against cp1252 before a character reached the user — in a tool
  whose whole point is that a name can be in any script. `utf8_console()` reconfigures stdout and stderr
  to UTF-8 with `errors="replace"` at startup, so an unrepresentable character becomes `?` instead of a
  traceback.

### Portability audit

Two Windows-only failures in a row (1.19.0 and 1.26.0) made the rest worth checking systematically
rather than waiting for CI. What the sweep found:

| Area | Verdict |
| --- | --- |
| `csv` reads | all three already pass `newline=""` |
| `Path.rename` | only used for new names, and wrapped in `try` |
| `fcntl` / `msvcrt` / `signal` / `fork` / `chmod` | none used |
| subprocess decoding | already `encoding="utf-8"` since 1.19.0 |
| stdout encoding | **broken** — fixed here |

### Tests

327 checks, up from 323. T86 writes through a cp1252 stream and runs the real CLI under
`PYTHONIOENCODING=cp1252`.

T86's first version patched `sys.stdout` for the whole process and failed one run in three with a
`MemoryError` in the codec lookup. `utf8_console()` now takes the streams to configure, so the test
passes its own writer and the process's stdout is left alone. Five consecutive clean runs after.

### Tool

- **The parity gate folds timestamps before comparing.** It failed on macOS because `journal` stamped
  the same entry `12:44` for the engine and `12:45` for the demo — the two run seconds apart, and the
  minute turned over between them. A timestamp is not an answer. Dates and times are now `<stamp>` on
  both sides; everything else is still compared exactly.

  This is the third flaky-gate fix in four releases, and the pattern is the same each time: a check
  that compares something nondeterministic — a clock, a console encoding, a wall-clock duration —
  reports the environment instead of the code.

## 1.26.1 — 2026-11-15

### Fixed

- **Replay still under-reconstructed on Windows.** 1.26.0 gave the timestamps microseconds, which fixed
  Linux and not Windows: the Windows clock ticks in ~15 ms steps, so several commands still shared a
  stamp with the snapshot and fell outside the window. A probe on CI reconstructed 34 tasks where live
  had 36.

  The window no longer uses the clock at all. Each snapshot records how many ledger lines existed when
  it was taken, in `snapshots/index.json`, and replay applies every line after that ordinal. A line
  count cannot collide the way a timestamp can.

- **`replay 2026-11-15` picked no snapshot.** A bare date compared as a string is shorter than any
  timestamp, so nothing matched. It now means "as of the end of that day".
- `doctor` counted `snapshots/index.json` as a snapshot; the listing skips it.

### Tests

323 checks. T85 now also asserts that each snapshot records its ledger position and that a bare date is
accepted.

## 1.26.0 — 2026-11-15

### Fixed

- **`replay` silently dropped every command that shared a second with the snapshot.** Ledger entries and
  snapshot names both carried one-second timestamps, so a replay window was `base < ts <= target` at
  second resolution — anything written in the snapshot's own second fell outside it. A probe that ran
  25 commands, forced a snapshot, then 11 more, replayed 6 of them and reconstructed 31 tasks where the
  live state had 36. Both now carry microseconds, and the same probe reconstructs all 36 exactly.

  This is the recovery path, so a silent under-reconstruction is worse than a failure: it produces a
  plausible state that is not the real one.

### Tests

321 checks, up from 315. T85 builds a state, forces a snapshot, adds more, then asserts the
reconstruction matches live exactly — task count, every task, and the expense log — and that the live
state is untouched.

## 1.25.0 — 2026-11-15

### Changed

- **The size budget is a recorded baseline, not a hard cap.** `budget.json` holds the current size of
  each part; `tools/budget.py` fails the build when anything grows past it by more than 10%. A feature
  that needs room runs `python tools/budget.py --update` in the same commit, so the decision is in the
  diff instead of in a ceiling someone has to remember to raise. The three hand-raised caps (64 → 72 →
  80 → 96 KB across 1.10.0, 1.13.0 and 1.17.1) were the symptom; this removes the cause.
- **Ledger retention is by age as well as count.** Five generations are always kept, and anything
  younger than 30 days is kept too — so a quiet week no longer erases history, and a chatty day still
  cannot fill the disk.

### Fixed

- The CI workflow had two size-budget steps after the 1.24.0 edit: the new tool call and the old inline
  heredoc. The duplicate is gone and the workflow parses.

### Tests

315 checks, up from 307. T83 covers the retention policy in both directions — a young generation
survives past the file count, an aged one is dropped. T84 asserts the baseline records all three parts,
that the tree is inside it, and that the tool reports a ceiling per part.

## 1.24.1 — 2026-11-15

### Fixed

- **`.gitattributes` forces LF for text files.** The doc-consistency gate compares byte counts against
  the docs, and those were measured on Linux. Windows runners default to `core.autocrlf=true`, so every
  text file arrived with CRLF and ten numbers disagreed — the docs were right and the checkout was
  different. LF everywhere makes the tree byte-identical on every platform, which also means the console
  demo hashes the same.

## 1.24.0 — 2026-11-15

### Added

- **`tools/doc_consistency.py`** — measures the tree and checks every number the docs quote against it:
  version, package/packs/console bytes, python source size, file counts, rule count, catalogue size and
  test count. CI runs it on every push.

  It found **15 stale numbers on its first run**, including a README badge that had claimed 137 tests
  since 1.8.0, three places still saying 106 rules, two meta descriptions saying 66, and a console size
  from three releases ago. Every one of those was a number I had been correcting by hand each release
  and missing.

### Changed

- The README's "read next" table now lists both tools.

## 1.23.0 — 2026-11-15

### Changed

- **The ledger rotates to dated generations.** Rotation used to rename to `ledger.1.jsonl`, so the next
  rotation overwrote it and everything older than two generations was gone. It now renames to
  `ledger-<YYYYMMDDTHHMMSSffffff>.jsonl` and keeps the newest five. Microseconds in the name mean two
  rotations in the same second cannot collide, and the names still sort chronologically.
- **`engine.ledger_lines()` spans every generation**, oldest first, so `timeline`, `report` and `doctor`
  all see the retained history rather than only the live file.

### Fixed

- **`timeline` truncated at 40 lines silently.** It now says how many it withheld and how to narrow the
  window (`timeline 2026-11-01`).
- `doctor` reported the live ledger file's size only; it now counts every generation.
- Generation names collided when two rotations landed in the same second, because the stamp had
  one-second resolution. Found immediately by the probe: 75 commands produced one generation, not five.

### Tests

307 checks. T72 was rewritten and T80 folded into T82, because both asserted the single-generation
scheme that this release replaces — the tests were right for the old behaviour and wrong for the new one.

## 1.22.0 — 2026-11-15

### Fixed

- **`timeline` and `report` read only the live ledger file**, so once rotation moved the older lines to
  `ledger.1.jsonl` the history silently halved. Both now go through one reader, `engine.ledger_lines()`,
  which spans the generations oldest-first.
- **The busiest-day line said "1 commands".** Pluralised.

### Tests

305 checks, up from 298. T80 asserts that rotation produces a generation and that the reader, the
timeline and the report all see it. T81 covers both plural forms.

T81's first version expected "2 commands" after two adds; the report counts itself, so the answer is
three. The test was wrong, not the code.

## 1.21.0 — 2026-11-15

### Changed

- **The parity gate takes hostile input.** 145 commands became 193: Devanagari keys and categories,
  impossible dates, a 40-digit integer, `2**1000`, `split 1000 0`, negative chart values, 60-character
  nonsense, case variants. 115 identical, 51 partial by design, 26 wording, 0 divergent.

### Fixed

The Unicode bug, for the third time — this time in the demo:

- **`remember नाम=Sohil`, `recall नाम`, `spend 100 खाना`, `contact रवि=91999`, `budget खाना 5000`** and
  seven more patterns used `\w+` in the console, which stops at a combining vowel sign. The engine was
  widened in 1.15.0 and 1.17.0; the demo never was. Eleven patterns now take any non-space run.
- **`due 1 2026-13-45` was accepted** by the demo — `on` got validation in 1.19.0, `due` did not.
- **`calc` printed `1e+40` for a 40-digit integer.** JavaScript has no exact integer past 2^53, so the
  demo now refuses with "Numbers past 15 digits need the local engine — it keeps them exact" instead of
  showing a wrong number. Its `2**1000` guard also said `big`; it says what the engine says.
- **`chart -5,0,5`** drew negatives with `#` where the engine draws `-`.

### Tool

- `undo` moved to the end of the parity list. It pops each side's own inverse stack, so every command
  after it compares two different histories — the run was reporting five `tasks` divergences caused by
  one `undo`.
- Blank commands are skipped: `run()` returns early for them, so the harness read `undefined`.

## 1.20.0 — 2026-11-15

### Changed

- **The parity gate now covers the whole demo.** 61 commands became 145: one per handler the console
  implements, plus every edge case that has bitten before. 73 identical, 48 partial by design, 24 that
  differ only in wording, 0 divergent.
- **"Needs the local engine" is detected from the answer, not from a list.** A handler that refuses
  honestly is counted as partial the moment it exists, so a new one cannot slip past the gate.

### Fixed

Three more ways the demo answered differently from the engine:

- **`timeline` showed the undo stack** and called it a ledger. The demo has no ledger; it now says so.
- **`restore 999` and `safe delete /nonexistent`** prompted for confirmation of a no-op, three releases
  after the engine stopped doing that. The empty-preview rule is ported; `safe delete` in the demo now
  says plainly that deleting a real file needs the engine, because the page cannot stat the filesystem.
- **The confirmation line** said `Type 'confirm' to approve.` where the engine offers `'confirm' or
  'cancel'`. A visitor reading the demo learned a command that does not exist.

### Verified

The four remaining wording differences are recorded in the tool with a reason each: `two-key on|off`
(both refuse, different closing hint), `habit del` (the engine also prints a two-key code the demo has
no key material for), `undo` (each side's inverse set differs), and `decide a` (both refuse, both name
the same suggestion).

## 1.19.0 — 2026-11-15

### Added

- **`tools/demo_parity.py`** — runs the console's own engine headlessly through node, compares it with
  the Python engine command by command, and fails the build when they disagree. CI runs it on every
  push. The landing page claims the demo runs the resolver, the risk gate and all arithmetic locally;
  this checks that claim instead of trusting it.

### Fixed

Six ways the demo answered differently from the engine, found by the new check:

- **Numbers were grouped in lakhs** (`10,41,388`) while the engine groups in thousands (`1,041,388`).
  The demo's `toLocaleString` used `en-IN`; it now matches `{:,.0f}`.
- **`decide` picked a different option on the same day** — the demo used a hand-rolled rolling hash
  where the engine uses `sha256("a|b|" + date)`. The demo now carries a real SHA-256, so both say
  "same answer all day" and mean it.
- **`decide a` ran a catalogue template** (`decide a|b|c`) in the demo while the engine refused it.
  The placeholder guard now covers single letters, and the demo's catalogue entry is `decide A|B|C`
  like the engine's.
- **`on 13-45 bad` was accepted** by the demo; the date validation added to the engine in 1.17.0 had
  never been ported.
- **`undo` and `log` recorded `cmd: "?"`** because the demo's inverse helper never saw the command.
- **`tasks` showed no `<due>` or `<recur>` marks**, and the demo's suggestions printed the
  normalised text (`decide a|b|c`) instead of the catalogue string.

### Tests

The parity check is 61 commands: 44 identical, 2 that the demo refuses on purpose, 15 that differ only
in wording, 0 divergent. It is a separate gate from the 298-check suite because it needs node.

The gate earned its keep before it ever passed. On `windows-latest` it reported a divergence for
`decide tea|coffee` where both sides had picked `coffee` with the same seed. The cause was
`subprocess.run(text=True)`, which decodes the child's stdout with the platform default — cp1252 on
Windows — so node's UTF-8 em dash arrived as mojibake and invented a difference. The call now passes
`encoding="utf-8"`. A first attempt blamed the console and folded dashes instead; that masked the
symptom without finding the cause, and the second CI run said so.

## 1.18.1 — 2026-11-15

### Fixed

- **T79 asserted wall-clock time**, and failed on macOS CI at 16.31 ms where the same code measured
  2.3 ms locally. A timing bound in a test suite measures the runner, not the code. The two latency
  assertions are now printed rather than asserted; the structural checks — the 40-line cap, the
  withheld count, compact JSON, that it parses — still fail the build when they break.
- The README now says which machine the latency numbers came from, and that the suite reports timings
  instead of asserting them.

298 checks. Two fewer than 1.18.0 because two assertions became measurements.

## 1.18.0 — 2026-11-15

A performance pass, aimed at what happens after a year of use.

### Changed

- **`state.json` is compact JSON.** `indent=1` cost 28 ms of serialisation at 5,000 tasks and made the
  file 229 KB; compact is 3.9 ms and 149 KB. End to end a write at 5,000 tasks went from **30.8 ms to
  9.5 ms**, and the file shrank by 35%. It is still valid JSON and still yours —
  `python3 -m json.tool ~/.pico/state.json` prints it indented.
- **`tasks` caps its listing at 40 lines** and says how many it withheld. Printing 5,000 lines cost
  6.5 ms and was useless to read; the read path at 5,000 tasks is now 1.45 ms. `done N` still
  addresses any index, including the hidden ones.

### Fixed

- The capped listing dropped `t["text"]` in its first version, so every task printed as `[ ] 1. `
  with no text. T27 and T63 caught it immediately; the tests were right and the code was wrong.

### Measured

| Tasks | read before | read after | write before | write after | state before | state after |
| --- | --- | --- | --- | --- | --- | --- |
| 100 | 0.52 ms | 1.22 ms | 1.70 ms | 1.81 ms | 7 KB | 5 KB |
| 1,000 | 2.50 ms | 0.35 ms | 7.85 ms | 3.62 ms | 49 KB | 32 KB |
| 5,000 | 6.48 ms | 1.45 ms | 30.77 ms | 9.46 ms | 229 KB | 150 KB |

Both budgets hold to roughly 2,000 tasks. Beyond that the write exceeds 5 ms because the whole file is
rewritten; an append-only journal is the fix and is on the roadmap.

### Tests

300 checks, up from 294. T79 covers the cap, both latencies at 1,200 tasks, and that the state file is
compact and still parses.

## 1.17.1 — 2026-11-15

### Changed

- **The package ceiling moved 80 KB → 96 KB**, so the package, the packs and the console share one
  ceiling instead of the package sitting 3.5 KB below its own. Headroom is now 17.6 KB. Recorded in
  the README with the reason, alongside the two earlier moves, and the CI comment lists all three.

No behaviour changed. 294 checks still pass.

## 1.17.0 — 2026-11-14

A third hardening pass, aimed at the parts no test had touched.

### Fixed

- **`when file /absolute/path/*.csv` never fired.** The trigger globbed from `Path.home()`, and
  `Path.home().glob("/abs/pattern")` returns nothing because glob does not accept an absolute pattern.
  A shared `_glob()` now anchors absolute patterns at their own root, so absolute, `~`-relative and
  home-relative patterns all work. Both the trigger and the `unless file` condition were affected.
- **Indic scripts still broke name and category arguments.** The previous pass widened the *key*
  patterns; `spend 100 खाना`, `budget खाना 5000`, `asset सोना 50000`, `debt कार्ड 40000 36` and
  `importcsv x.csv तालिका` all still failed, because `\w+` stops at a combining vowel sign. They now
  take any non-space run.
- **A danger command with nothing to affect asked for confirmation.** `restore 999` and
  `safe delete /nope` produced "Affects: 0 item(s). Type confirm" — a prompt to confirm a no-op.
  When a handler's preview is empty the command now runs straight through and the handler's own
  refusal is shown instead.
- The `replay` message still said snapshots were kept for "the last 20 write bursts" after the count
  was reduced to 12.

### Verified, not changed

SM-2 is correct: repeated grade 5 gives intervals 1, 6, 16, 45, 127, 351 … with ease rising 2.5 →
3.16, and a grade below 3 resets the interval and the repetition count. `brief` renders 300 events in
1.1 ms. The `for each` cap refuses 300 rows with a message that says why.

### Tests

294 checks, up from 272. T74 the Indic names and categories, T75 the file trigger including
once-per-file, T76 the no-op gate, T77 the SM-2 schedule, T78 the glob helper.

A first attempt at the file-trigger fix anchored absolute patterns with `Path.glob`, which works on
Linux and fails on Windows — `Path.glob` splits the pattern on `\\` only, so a pattern written with a
`/` separator matches nothing. CI caught it on windows-latest. The helper now uses the stdlib `glob`
module, which accepts both.

## 1.16.0 — 2026-11-14

A second hardening pass, this one aimed at the web surface and at long-running state. Again every fix
came from a probe, not a feature list.

### Fixed

- **`sql PRAGMA table_info(t1)` was refused while the error message promised it worked.** `pragma` was
  in the write-blocking regex, so *every* pragma was refused, including the describing ones. There is
  now an allowlist — `table_info`, `table_xinfo`, `index_list`, `index_info`, `foreign_key_list`,
  `database_list`, `compile_options` — and `PRAGMA writable_schema` is refused with a message that
  names the safe set.
- **`on 13-45 bad` was accepted.** Neither `on` nor `due` validated the date. Both now check the
  month and day, allow `02-29` as a recurring date, and reject `2026-02-29` because 2026 is not a leap
  year.
- **`decide a` silently picked from `A|B|C`.** The fuzzy tier matched the catalogue *template*
  `decide A|B|C`, whose placeholders are single uppercase letters, and ran it. The placeholder guard
  now catches `\b[A-Z]\b` as well as `X`, `N` and multi-letter words.
- **An expired confirmation answered "No rule matched".** After 120 seconds the pending request is
  dropped, and a later `confirm` fell through to the resolver. It now says the confirmation expired
  and that nothing ran.
- **The ledger grew without bound.** 2,000 commands produced 256 KB and nothing ever removed it. It
  now rotates at 5,000 lines to `ledger.1.jsonl`, keeping one generation.
- **A cache-busting query string turned a known route into a 404.** `/sw.js?cache=1` failed because
  routes matched the raw path. The query string is stripped before routing, and `/app.html` serves the
  console as well as `/`.

### Verified, not changed

The web surface held up under a deliberate probe: `GET /../../etc/passwd` and its percent-encoded
form are 404, `PUT /cmd` is 501, a 70 KB body is 413, malformed JSON is 400, and 60 concurrent POSTs
from four threads produced 60 tasks with no errors.

### Tests

272 checks, up from 246. T68 the pragma allowlist, T69 the dates, T70 the fuzzy template, T71 the
expired confirmation, T72 ledger rotation, T73 the web routes including traversal.

## 1.15.0 — 2026-11-14

A hardening release. Every fix below came from an adversarial probe — quoted commas, CRLF, a BOM, a
Devanagari key, `remind 25:99`, `timer 999999h`, a quoted path — not from a feature list.

### Fixed

- **Devanagari, and every Indic script, broke key arguments.** `\w` matches a base letter but stops at
  a combining vowel sign, so `remember नाम=Sohil` matched only `न` and the whole rule failed. Keys in
  `remember`, `recall`, `forget`, `site`, `contact` and `chain` now accept any run of non-space,
  non-separator characters. Values were already fine.
- **A UTF-8 BOM in a CSV header broke every column lookup.** Excel writes one by default; `\ufeffid`
  is not `id`. Files are now opened with `utf-8-sig`, and a stray BOM is stripped from the first cell
  as well.
- **Duplicate CSV headers were fatal.** `importcsv` raised `OperationalError: duplicate column name`.
  Repeated names are now suffixed `_2`, `_3` in both `importcsv` and the read verbs.
- **`remind 25:99` raised `ValueError`.** Now refused with "That is not a clock time".
- **`timer 999999h` armed a 114-year thread.** Anything over 24 hours is refused, with `remind`
  suggested instead.
- **`fill` substituted twice.** A value containing `{{body}}` was re-expanded by the next key, so
  `name={{body}}` produced the body text. Substitution is now a single pass: a value is data.
- **Quoted paths were not understood.** `count "/a/b c.txt"` looked for a file called `"/a/b c.txt"`.
  Path arguments in `count`, `extract`, `sortlines`, `dedupe`, `redact`, `tidy`, `backup`, `find`,
  `big files`, `old files`, `dedupe files`, `safe delete` and `importcsv` now strip one layer of
  matching quotes.

### Changed

- `pico/cmd_files.py` and three packs import `unquote` from `pico.base`. Packs load as top-level
  modules, so the import has to be absolute — a relative one fails silently under `quiet=True`.

### Tests

246 checks, up from 226. T63 the Indic keys, T64 the three CSV edge cases, T65 the bounds, T66 the
single-pass fill, T67 the quoted paths.

## 1.14.0 — 2026-11-14

### Added

- **`doctor probe write`** — exercises the eight write paths (`tidy`, `backup`, `redact`,
  `dedupe files`, `dedupe`, `safe delete`, `restore`, `quarantine sweep`) inside a scratch directory,
  then removes it, the backup zip and the quarantine entry. `fill` is excluded on purpose: it writes a
  dated file into your home, and a diagnostic must not be able to overwrite real output.
- **`big files [N] [PATH]`** and **`old files ND [PATH]`** take an optional folder.

### Fixed

- **`dedupe files PATH` ignored PATH.** It accepted a directory and then walked Downloads, Documents
  and Desktop instead. Found while writing the write probe: the probe's two identical fixtures
  reported "no duplicates".
- **`dedupe files` was shadowed by the text pack's `dedupe`.** Packs load alphabetically and are
  prepended, so `text` sat above `files` and `^dedupe (?P<path>.+)$` matched `dedupe files /tmp/x`
  with `path="files /tmp/x"`. The text rule now refuses a first token of `files`.
- The write probe reused one directory for every step, so `tidy` moved the fixtures the later steps
  needed. Each probe now gets its own directory and its own fixtures.

### Tests

226 checks, up from 216. T61 covers the write probe and its cleanup, T62 the path arguments and the
shadowing fix.

## 1.13.0 — 2026-11-14

### Added

- **`doctor probe`** — runs one read-only command per pack *through the handler, not through `_run`*.
  A diagnostic should not leave marks in the audit trail it is checking, so nothing is logged and
  nothing is saved. Catches the case `doctor` cannot: a pack that loads, registers its rules, and
  still cannot answer. Twelve packs, one line each.

### Changed

- **The package ceiling moved 72 KB → 80 KB.** It reached 70.7 KB with 3 KB left, which the next
  feature would not have fitted into. Recorded in the README with the reason, alongside the 1.10.0
  move, and the CI comment now lists both.

### Tests

216 checks, up from 210. T60 asserts the probe runs, every pack with rules answers, a pack without
rules is reported as such, and the probes themselves never reach the ledger.

## 1.12.0 — 2026-11-14

### Added

- **`doctor` reads thread heartbeats.** `schedule` and `telegram` publish a module-level `LAST`
  timestamp from inside their loops; `doctor` compares it with now and reports each pack's age. Under
  120 s is `ok`, older is `warn` with the reason, and a pack that never started a thread is named
  *idle* rather than stale — a missing Telegram token is not a fault.

### Changed

- **`doctor fix` has its own module.** `cmd_doctor.py` had grown to 8.5 KB doing two jobs; `doctor`
  and `fix` now live in `cmd_doctor.py` and `cmd_repair.py`. Eight `cmd_*` modules.

### Fixed

- The first heartbeat pass reported `telegram 1794680609s`, because the pack leaves `LAST` at zero
  when there is no token. Zero now means "never started", not "stopped 56 years ago".
- `cmd_repair.py` carried a duplicate `import secrets` inside the function as well as at the top.

### Tests

210 checks, up from 200. T58 covers the heartbeat line, the idle case and the stale case, T59 the
module split.

## 1.11.0 — 2026-11-14

### Added

- **`doctor fix`** — repairs the eight things `doctor` can only report: creates missing directories,
  removes stray `state.json.tmp*` files, quarantines unreadable JSON (moved aside, never deleted),
  prunes snapshots beyond the rolling 12, prunes a quarantine index pointing at files that are gone,
  and regenerates an empty `web.token`. Each action is listed; a second run says there is nothing left.
- **`csv join KEY:number`** — treats `01` and `1` as the same key, matching the hint that `sort`,
  `filter` and `pivot` already take. Every `csv` verb now accepts a type.
- **`docs/ANDROID.md`** — states plainly why there is no APK, what an APK would cost, and the three
  routes that work: install the console to the home screen, run pico under Termux, or use the
  Telegram bridge.

### Fixed

- T55 expected `doctor fix` to be a no-op on a fresh home, but a fresh home genuinely lacks
  `snapshots/`, `quarantine/` and `backups/`, so the first run creates them. The test now asserts
  that, and that the second run has nothing to do.
- The same test built colliding snapshot filenames (`% (i % 10)`), so it never exercised pruning.

### Tests

200 checks, up from 184. T55 covers every repair `doctor fix` performs, T56 the join key types,
T57 the Android document's claims.

## 1.10.0 — 2026-11-14

### Added

- **`doctor`** — a self-check across fourteen subsystems: home, `state.json`, the ledger, the rule
  table, loaded packs, templates, quarantine, snapshots, triggers, the per-pack data files
  (`jobs.json`, `habits.json`, `cards.json`, `life.json`), sqlite, the tokens, two-key state and the
  Python version. One line each, `ok` / `warn` / `FAIL`, then a count. A fresh home reports all `ok`:
  nothing written yet is correct, not broken.
- **`csv pivot` key typing** — `csv pivot zip:number sum amt x.csv` makes `order by key` compare
  numerically; `:text` forces a lexicographic read.
- **An offline chip.** A failed `/cmd` turns the status chip red, explains that the engine is not
  answering, says how to start it, and polls `/api/state` every 5 s until it comes back — then
  recovers without a reload.

### Changed

- **The package ceiling moved 64 KB → 72 KB.** `doctor` added 5.6 KB and left 1.6 KB of headroom,
  which is not enough to work in. The change is recorded in the README rather than made quietly, and
  the CI comment now states the review policy: a ceiling is reviewed when a feature needs more.

### Fixed

- `doctor` reported a missing `state.json` as `FAIL` on a brand-new install. Nothing has been written
  yet, so it is `ok`; T52 caught it.

### Tests

184 checks, up from 171. T52 covers `doctor` including the corrupt-state case, T53 the three pivot key
types, T54 the offline chip's states and recovery.

## 1.9.0 — 2026-11-14

### Changed

- **`handle()` moved to `pico/dispatch.py`.** `engine.py` fell from 12,695 B to 6,004 B; the largest
  file in the package is now 7,071 B. `Engine` is `StoreMixin, LadderMixin, LedgerMixin,
  DispatchMixin`.
- **`csv filter` takes the same column type as `csv sort`** — `csv filter score:number>9 x.csv`.
  `:number` drops rows that do not parse, `:text` compares lexicographically, and the default keeps
  the old guess.

### Added

- **A Reload bar when a newer build is waiting.** The service worker reports an update through
  `updatefound` + `statechange`, and the console offers Reload / Later. Reload posts `skip` to the
  waiting worker and only reloads on `controllerchange`, so the swap is not interrupted. The cache
  name is versioned, so a new build actually replaces the old shell.
- The README's measured section lost a stale row and paragraph left over from before the budgets
  were restated.

### Tests

171 checks, up from 158. T49 the dispatcher split, T50 the three filter modes, T51 the update bar.

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
