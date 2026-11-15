# Roadmap

Ordered by what a user feels first, not by what is interesting to build. Every item has an exit test,
because "done" without a test is an opinion.

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
| **`fill` is the one path no probe touches** | it writes a dated file into the home, so a diagnostic must not run it | a `fill` that takes an output directory |
| **Devanagari in command *arguments* is fine, in command *names* it is not** | the rules are English; only the data is multilingual | transliterated command aliases, opt-in |
| **The ledger keeps one generation** | `ledger.1.jsonl` is overwritten on each rotation, so the oldest history is dropped | a dated generation name, kept for N days |
| **Package headroom is finite** | the package sits at 76.3 KB of an 80 KB ceiling | one small fix fits; the next subsystem needs a trim or a recorded ceiling change |

## Next — cheap and useful

| Item | Why | Exit test |
| --- | --- | --- |
| `net worth` / `debt snowball` | one screen that answers "am I okay" | given a debt list, returns a payoff order and total interest |
| `subs audit` | recurring charges found in `spend` | flags same-amount repeats |
| Every `csv` verb now takes a type hint | nothing left to add here | — |

## Deliberately not built

| Tempting | Why not |
| --- | --- |
| Abstractive summarising | That is the model's job. With the model off, an extractive summary must be labelled extractive — and a worse summary than a `grep` is not worth the code |
| OCR, speech, QR rendering | Pure stdlib cannot. Shipping a dependency contradicts C1 |
| Two-way WhatsApp | Needs Meta's Cloud API and a public webhook. Telegram already works and needs nothing |
| A plugin marketplace | Every pack is a file you can read in one sitting. A registry would be a supply-chain risk in a tool that promises no network |
| Cloud sync | The point is that there is no server. Export/import a JSON file and use whatever you already trust |
| A native mobile app | The console is one HTML file. An APK would be 40 MB of wrapper around a page your browser already renders. Add to Home Screen already gives standalone chrome |

## Open questions

- **Where does the alias store live?** Currently in `state.json`. If aliases grow past a few hundred,
  they deserve their own file so `state.json` stays readable.
- **Should `write` be gated for typed commands?** It is gated for model-proposed ones. Typed `tidy`
  runs immediately and is undoable. That is a judgement call, not a settled one.
- **How loud should the scheduler be?** Today a job that throws is logged and forgotten. Silent failure
  is the wrong default for a reminder, but noisy failure is worse.
