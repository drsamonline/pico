# Roadmap

Ordered by what a user feels first, not by what is interesting to build. Every item has an exit test,
because "done" without a test is an opinion.

## 1.33 — shipped

`alias P -> CMD` binds any phrase in any script to a command, so the command names a user types are
theirs. This closes the last item on the "worth the complexity" list except the journal. 381 checks.

## 1.32 — shipped

Aliases move to their own file past fifty; a job that fails three times switches itself off.

## 1.31 — shipped

Four small items in one release: `fill` takes an output directory and is now covered by `doctor probe
write`; a scheduled job that throws is recorded, notified and shown by `doctor`; the console palette
gained fourteen measured pairs including control borders, and `--line2` was raised from 1.72:1 to
3.45:1 because it draws the boundary of every button and input. 354 checks.

## 1.30 — shipped

The console palette is measured by `tools/contrast.py` in CI, following an a11y fix committed straight
to the console.

## 1.29 — shipped

Backups keep a rolling window of 20 and no longer overwrite each other; `doctor` warns when the
quarantine grows.

## 1.28 — shipped

`replay` keeps five reconstructions instead of leaking one per call.

## 1.27 — shipped

A Devanagari answer no longer crashes the CLI on a cp1252 console.

## 1.26 — shipped

`replay` reconstructs exactly: the window counts ledger lines, not clock ticks.

## 1.25 — shipped

The size budget became a recorded baseline with a 10% tolerance; ledger retention is by age as well as
count.

## 1.24 — shipped

`tools/doc_consistency.py` checks every number the docs quote. It found fifteen stale ones on its first
run.

## 1.23 — shipped

The ledger keeps five dated generations instead of overwriting one.

## 1.22 — shipped

`timeline` and `report` read the rotated ledger, so history stops halving.

## 1.21 — shipped

The parity gate takes hostile input; the demo's Unicode, date and arithmetic bugs fixed.

## 1.20 — shipped

The parity gate covers every handler the demo implements.

## 1.19 — shipped

`tools/demo_parity.py`: the demo is checked against the engine, and six ways it lied were fixed.

## 1.18 — shipped

A performance pass: compact `state.json` (7× faster to write), a capped task listing, and the scale
numbers in the README. 300 acceptance tests.

## 1.17 — shipped

A third hardening pass, aimed at the parts no test had touched: file triggers, name arguments in
Indic scripts, the confirmation gate on a no-op, and the SM-2 schedule. 290 acceptance tests.

## 1.16 — shipped

A second hardening pass, aimed at the web surface and the long-running state: the SQL pragma
allowlist, date validation, the fuzzy tier refusing to run a catalogue template, an expired
confirmation that says so, ledger rotation at 5,000 lines, and cache-busting query strings on every
route. 272 acceptance tests.

## 1.15 — shipped

A hardening release, driven by an adversarial probe rather than a feature list: Indic scripts in keys,
BOM and duplicate headers in CSV, clock and timer bounds, single-pass template substitution, quoted
paths. 246 acceptance tests.

## 1.14 — shipped

`doctor probe write` exercises the eight write paths in a scratch directory; `dedupe files`, `big
files` and `old files` now honour the path they are given, and `dedupe files` is no longer swallowed
by the text pack's `dedupe`. 226 acceptance tests.

## 1.13 — shipped

`doctor probe` runs one read-only command per pack through the handler, so a pack that loads but
cannot answer is caught; nothing is logged. The package ceiling moved 72 KB → 80 KB, recorded in the
README. 216 acceptance tests.

## 1.12 — shipped

`doctor` reports the scheduler and Telegram heartbeats, so a thread that stopped is visible; `doctor
fix` moves to its own module. 210 acceptance tests.

## 1.11 — shipped

`doctor fix` repairs the eight things `doctor` can only report; `csv join` takes the same
`:number`/`:text` key hint as `sort`, `filter` and `pivot`; and `docs/ANDROID.md` states plainly why
there is no APK and what works instead. 200 acceptance tests.

## 1.10 — shipped

`doctor`, a self-check that names what is wrong across fourteen subsystems; `csv pivot` key typing;
and an offline chip that turns red when the engine stops answering and recovers by itself. 184
acceptance tests. The package ceiling moved 64 KB → 72 KB, recorded in the README.

## 1.9 — shipped

The dispatcher gets its own module, `csv filter` takes the same `:number`/`:text` hint as `sort`, and
the console offers a Reload bar when a newer service worker is waiting. 171 acceptance tests.

## 1.8 — shipped

The quarantine lifecycle gets its own module; `csv sort` takes an explicit column type; the console
gained a dismissible install prompt. 158 acceptance tests.

## 1.7 — shipped

`pico/rules.py` split into five `cmd_*` modules behind a 5.8 KB registry; backoff moved from the rule
to the action; `csv pivot … order by key|value [asc|desc]`; and the console is now an installable PWA
with a manifest, icons and a service worker that never caches the engine. 143 acceptance tests.

## 1.6 — shipped

106 rules. `pico/engine.py` split into store, ladder, ledger and base mixins; trigger backoff;
`csv pivot … having EXPR`. 125 acceptance tests.

## 1.5 — shipped

106 rules. OR-ed `unless` conditions, per-rule firing history with `trigger log`, Wayland clipboard
support, and `csv pivot` on any number of keys. 108 acceptance tests.

## 1.4 — shipped

105 rules. `unless` conditions, `watch`, the clipboard trigger, `away`, a retry on a failing action,
and multi-key `csv pivot`. 101 acceptance tests.

## 1.3 — shipped

103 rules. The trigger DSL (`when` on time, interval, file and absence), chains, CSV loops, `csv pivot`,
phone-only approval, and a write lock that took the write path under the 5 ms budget. 88 acceptance
tests.

## 1.2 — shipped

95 rules. Replay from snapshots, the full quarantine lifecycle, net worth and debt avalanche,
subscription audit, `csv filter/sort/join`, `chart`. Approval codes now also go to the bound phone.
68 acceptance tests.

## 1.1 — shipped

83 rules, four risk tiers, universal undo, slot dialogue, two-key approval, quarantine, recurring
tasks, SM-2 cards, sqlite over CSV, weekly report, local console, Telegram bridge, optional
translator, 52 acceptance tests. Measured in the [README](../README.md#measured).

## 1.0 — shipped

66 rules, four risk tiers, universal undo, local console, Telegram bridge, optional translator.

## Next — worth the complexity

| Item | Why | Exit test |
| --- | --- | --- |
| **Writes rewrite the whole state file** | 9.5 ms at 5,000 tasks, 0.45 ms empty. The 5 ms figure was this project's own spec, not a measured complaint, and an append-only journal puts the write path — the one that holds the user's tasks — at risk | a journal that survives a kill -9 mid-write, with a test that proves it |


## Deliberately not built

| Tempting | Why not |
| --- | --- |
| Abstractive summarising | That is the model's job. With the model off, an extractive summary must be labelled extractive — and a worse summary than a `grep` is not worth the code |
| OCR, speech, QR rendering | Pure stdlib cannot. Shipping a dependency contradicts the whole premise |
| Two-way WhatsApp | Needs Meta's Cloud API and a public webhook. Telegram already works and needs nothing |
| A plugin marketplace | Every pack is a file you can read in one sitting. A registry would be a supply-chain risk in a tool that promises no network |
| Cloud sync | The point is that there is no server. Export/import a JSON file and use whatever you already trust |
| A native mobile app | The console is one HTML file. An APK would be 40 MB of wrapper around a page your browser already renders. Add to Home Screen already gives standalone chrome |

## Open questions

- **Should `write` be gated for typed commands?** It is gated for model-proposed ones. A typed `tidy`
  runs immediately and is undoable. That is a judgement call, not a settled one.
- **How long should a reconstruction live?** `replay` keeps five. Nobody has asked for a sixth.

Settled since: a failing job is recorded, notified, shown by `doctor`, and switches itself off after
three consecutive failures (1.32.0); aliases move to their own file past fifty (1.32.0).

## Gates that hold the line

| Gate | What it protects |
| --- | --- |
| `tests/smoke_test.py` | 354 acceptance checks |
| `tools/demo_parity.py` | the console answers what the engine answers, 193 commands |
| `tools/doc_consistency.py` | every number quoted in the docs |
| `tools/budget.py` | growth against a recorded baseline, 10% tolerance |
| `tools/contrast.py` | the console palette against WCAG AA, 14 pairs |
