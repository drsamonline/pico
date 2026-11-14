# Roadmap

Ordered by what a user feels first, not by what is interesting to build. Every item has an exit test,
because "done" without a test is an opinion.

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
| **CSV as a loop** | `for each row in clients.csv then fill letter name={name}` turns a mail merge into one line | 50-row CSV produces 50 letters, one ledger line each |
| **Trigger DSL** | `when 22:30 unless away then backup ~/Documents ; tidy` — `daily` is the only trigger today | a rule fires on time, file, or clipboard match |
| **Approval from the phone only** | the code reaches the chat, but `approve` also works at the desk | with a token set, the desktop refuses `approve` |

## Next — cheap and useful

| Item | Why | Exit test |
| --- | --- | --- |
| `net worth` / `debt snowball` | one screen that answers "am I okay" | given a debt list, returns a payoff order and total interest |
| `subs audit` | recurring charges found in `spend` | flags same-amount repeats |
| `csv pivot` | `join` and `filter` exist; grouping is the missing verb | `csv pivot cat sum amt spend.csv` |
| `watch FOLDER then CMD` | the last trigger that needs no DSL | a new file in a folder fires a command |

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
