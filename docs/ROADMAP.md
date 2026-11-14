# Roadmap

Ordered by what a user feels first, not by what is interesting to build. Every item has an exit test,
because "done" without a test is an opinion.

## 1.0 — shipped

66 rules, four risk tiers, universal undo, local console, Telegram bridge, optional translator,
30 acceptance tests. Measured in the [README](../README.md#measured).

## Next — worth the complexity

| Item | Why | Exit test |
| --- | --- | --- |
| **Slot dialogue** | `emi` with two of three numbers currently just fails. Asking one question beats a syntax lesson | `emi 500000 8.5` → asks for months, then runs, in one turn |
| **Context stack** | `done 2`, then `undo`, then `again` should work without retyping | `it`, `that`, `again` resolve to the previous command |
| **Recurring tasks** | `recur daily water the plants` is the most requested shape of task in every planner | `recur daily X` creates a task that reappears each day, logged once |
| **Two-key for danger** | Right now a danger action is one word away. A phone approval closes that | with two-key on, `unjob 1` cannot complete from the desktop alone |
| **Blast radius everywhere** | `tidy` previews; `safe delete` and `restore` do not | `dry safe delete` names the file count before anything moves |
| **`safe delete`** | A quarantine folder with a 30-day sweep is undo for humans | deleted file lands in `~/.pico/quarantine/`, `undo` restores it |
| **Replay** | The ledger is already append-only; replay is a reader | `replay <ts>` rebuilds state from the nearest snapshot plus the log |
| **CSV as a loop** | `for each row in clients.csv then fill letter name={name}` turns a mail merge into one line | 50-row CSV produces 50 letters, one ledger line each |

## Next — cheap and useful

| Item | Why | Exit test |
| --- | --- | --- |
| `dedupe files` | sha256 grouping, no external tool | two identical files collapse to one plus a report |
| `big files` / `old files Nd` | the two questions everyone asks of a disk | lists top 20 by size, and files older than N days |
| `overdue` / `stale` | tasks with a due date that has passed | `on` gains an optional due field |
| `net worth` / `debt snowball` | one screen that answers "am I okay" | given a debt list, returns a payoff order and total interest |
| `subs audit` | recurring charges found in `spend` | flags same-amount repeats |
| `report weekly` | the ledger already knows; this is a view | one page: tasks closed, spend by category, habits kept |
| `card add Q\|A` + `review` | SM-2 spaced repetition, ~60 lines, no model | after 3 reviews the interval grows 1→6→15 days |
| `decide A\|B\|C` | a coin flip that shows its work | returns a choice and the seed |

## Deliberately not built

| Tempting | Why not |
| --- | --- |
| Abstractive summarising | That is the model's job. With the model off, an extractive summary must be labelled extractive — and a worse summary than a `grep` is not worth the code |
| OCR, speech, QR rendering | Pure stdlib cannot. Shipping a dependency contradicts C1 |
| Two-way WhatsApp | Needs Meta's Cloud API and a public webhook. Telegram already works and needs nothing |
| A plugin marketplace | Every pack is a file you can read in one sitting. A registry would be a supply-chain risk in a tool that promises no network |
| Cloud sync | The point is that there is no server. Export/import a JSON file and use whatever you already trust |
| A native mobile app | The console is one HTML file. An APK would be 40 MB of wrapper around a page your browser already renders |

## Open questions

- **Where does the alias store live?** Currently in `state.json`. If aliases grow past a few hundred,
  they deserve their own file so `state.json` stays readable.
- **Should `write` be gated for typed commands?** It is gated for model-proposed ones. Typed `tidy`
  runs immediately and is undoable. That is a judgement call, not a settled one.
- **How loud should the scheduler be?** Today a job that throws is logged and forgotten. Silent failure
  is the wrong default for a reminder, but noisy failure is worse.
