# pico — project overview

**One page. What it is, what it does, what it refuses to do.**

## In one sentence

A personal automation engine that runs on the Python standard library alone: 114 rules, four risk
tiers, universal undo, slot dialogue, replay, a trigger DSL, and an optional language model that
may only ever propose a command.

## The problem it solves

Asking a model to *do* something on your machine means handing it your machine. pico inverts that: the
rule engine owns every action, and a model — if you enable one — can only suggest which rule to run.
Delete the model and nothing stops working.

## What it does

| Area | Capability |
| --- | --- |
| Capture | tasks, notes, shopping, events, a daily brief that totals the month |
| Money | EMI, SIP, FD, simple interest, GST both directions, bill split with the residue stated, discounts, monthly caps |
| Time | clock, countdown, daily reminder, unit and temperature conversion, AST-safe arithmetic |
| Files | sort by type, zip a tree, find by name, fill a template, count, extract, dedupe, redact |
| Life | habit streaks, journal, contacts, WhatsApp and mail deep links |
| Automation | daily jobs, triggers on time/file/absence, chains, CSV loops, a ledger, universal undo, alias learning, slot dialogue, two-key approval, `dry` / `why` / `log` / `timeline` / `replay` |
| Data | CSV into sqlite3, read-only SQL out, `csv filter/sort/join`, `chart` |
| Faces | CLI, REPL, local web console, Telegram bridge — all through one `handle()` |

## What makes it different

1. **Determinism is the default.** The rule path produces identical output for identical input and
   state. The model path is off until you turn it on, and its output is re-validated by the core.
2. **Every write is reversible.** Handlers register inverses, including inside packs, so `undo` works
   on a `tidy` that moved 200 files.
3. **Consent is a tier, not a dialog box.** Sends and deletes hold state for 120 s and preview what
   they will touch.
4. **The demo is real.** The browser build runs the same resolver and the same arithmetic in
   JavaScript, because both halves are deterministic.

## What it refuses

No abstractive summarising without the model. No OCR, speech or QR rendering without an external
tool. No two-way WhatsApp without Meta's Cloud API. No cloud sync, no account, no telemetry, no
network call at runtime except the one you ask for.

## Numbers

| | |
| --- | --- |
| dependencies | 0 |
| rules | 106 |
| packs | 12 |
| python source | 171,894 bytes, 29 files |
| console | 72,112 bytes, one HTML file |
| read latency | 0.71 ms/call |
| write latency | 4.03 ms/call |
| engine heap | 0.1 MB |
| tests | 481 passing |

## Shape of the repository

```
pico.py  pico/  packs/  web/  templates/  tests/  docs/
```

Core owns state, resolution, the risk gate, the ledger and the plugin loader. Packs own capabilities.
Front-ends own transport only.

## Licence and author

PolyForm Noncommercial 1.0.0. Built by [Dr. Sohil Momin](https://drsamonline.github.io/).

---

Required Notice: Copyright 2026 Dr. Sohil Momin (https://github.com/drsamonline/pico)
