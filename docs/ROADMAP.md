# Roadmap

Ordered by what a user feels first, not by what is interesting to build. Every item has an exit test,
because "done" without a test is an opinion.

## 1.1 — shipped

83 rules, four risk tiers, universal undo, slot dialogue, two-key approval, quarantine, recurring
tasks, SM-2 cards, sqlite over CSV, weekly report, local console, Telegram bridge, optional
translator, 52 acceptance tests. Measured in the [README](../README.md#measured).

## 1.0 — shipped

66 rules, four risk tiers, universal undo, local console, Telegram bridge, optional translator.

## Next — worth the complexity

| Item | Why | Exit test |
| --- | --- | --- |
| **Replay** | `timeline` reads the log; rebuilding state needs snapshots | `replay <ts>` reproduces state from the nearest snapshot plus the log |
| **CSV as a loop** | `for each row in clients.csv then fill letter name={name}` turns a mail merge into one line | 50-row CSV produces 50 letters, one ledger line each |
| **Quarantine sweep** | `safe delete` keeps files forever today | `quarantine sweep 30d` empties anything older than the window |
| **Phone approval for two-key** | the code prints on the desktop; it should also go to the bound chat | with a token set, `approve` works from the phone only |
| **Blast radius on every danger handler** | `tidy` and `safe delete` preview; `restore` does not | `dry restore` names the file count |

## Next — cheap and useful

| Item | Why | Exit test |
| --- | --- | --- |
| `net worth` / `debt snowball` | one screen that answers "am I okay" | given a debt list, returns a payoff order and total interest |
| `subs audit` | recurring charges found in `spend` | flags same-amount repeats |
| `csv filter/sort/join` | the sqlite pack covers query; the shell verbs are still missing | `csv filter age>30 people.csv` prints the rows |
| `ascii chart` | `report` prints numbers; a sparkline reads faster | `chart 1,4,9,16` draws bars in the terminal |

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
