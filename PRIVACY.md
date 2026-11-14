# Privacy

pico is a local program. It has no server, no account and no telemetry. This file states exactly what
is stored, what can leave the machine, and what stops it.

## What is stored, and where

Everything lives under `~/.pico/` (override with `PICO_HOME`).

| File | Contents | Encrypted |
| --- | --- | --- |
| `state.json` | tasks, notes (including anything you `remember`), expenses, events, shopping, site shortcuts, aliases, undo stack | no |
| `ledger.jsonl` | one line per executed command, append-only | no |
| `jobs.json` | daily jobs | no |
| `habits.json` | habit names and ISO dates | no |
| `life.json` | contacts and journal entries | no |
| `llm.json` | translator config, including the blocklist | no |
| `llm_cache.json` | sentence → command translations | no |
| `web.token` | the console's shared secret, mode 600 | n/a |
| `telegram.token` | bot token, if you provide one | no |
| `backups/` | zips you asked for | no |

Nothing is encrypted. Use full-disk encryption if that matters — it is a better answer than a
hand-rolled cipher in a stdlib program.

## What the ledger does and does not record

The ledger records the **command** and a 200-character preview of its **output**, with two exceptions:

- `remember`, `contact` and `site` store their value as `<redacted>` in the command field.
- `recall`, `journal`, `contacts` and `aliases` store `<redacted: stored personal data>` as the output.

`why` shows the unredacted last action in your terminal, because you just typed it. The file on disk
does not get it.

## What can leave the machine

Only four things, and three of them are opt-in per command.

| Path | When | What goes out |
| --- | --- | --- |
| `weather` | you run it | the city name, to `wttr.in` |
| `search`, `open`, `wa`, `mail` | you run them | a URL opened in **your** browser. pico makes no request |
| Telegram bridge | you created `telegram.token` | command text and replies, to Telegram |
| The translator | `mode` is not `off` and the sentence is not blocked | the sentence, redacted |

Nothing else. There is no update check, no analytics, no crash reporting.

## The translator's guarantees

Five things have to be true before a sentence is sent:

1. `mode` is `local`, `cloud` or `auto` — never the default `off`.
2. The sentence contains none of the `never_send` tags. The default list is
   `health`, `finance`, `contacts`, `vault`, `journal`, `pin`, and `privacy never TAG` adds more.
   **This check runs in the core resolver**, before any translator is called — not inside the adapter
   where a different translator could bypass it.
3. The configured provider matches the mode: `local` accepts `ollama`/`llamacpp`/`cli`, `cloud`
   accepts `openai`. A mismatch refuses and tells you how to fix it rather than silently sending to the
   wrong place.
4. The daily call budget has room (default 60).
5. Redaction is applied: emails, phone numbers and 10+ digit IDs become `<EMAIL1>`, `<NUM1>`, `<ID1>`,
   and are restored locally after the reply.

The reply must then pass the core firewall: it has to match an existing rule, contain no
`; & | \` $ > <`, stay under 200 characters, and avoid the deny-list (`llm`, `privacy`, `panic`,
`permissions`, `2key`, `vault`, `sync`, `unalias`, `undo`, `restore`).

## Deleting the model entirely

```bash
rm ~/.pico/rules/llm.py
```

That is the whole procedure. Every command in [COMMANDS.md](docs/COMMANDS.md) except the `llm` and
`privacy` blocks keeps working, and test T1 verifies that output is byte-identical with and without a
translator present.

## Third parties

- **Telegram** — messages are stored on their servers. Treat the bridge as a remote control, not a
  vault.
- **wttr.in** — receives the city string you type.
- **CallMeBot** — not included. If you add a notifier that posts to a third party, read its terms
  yourself; pico cannot make someone else's retention policy better.

## Your rights over the data

It is a folder. `cat`, `grep`, `rm`, `rsync` and `git` all work on it. There is no export endpoint
because the files are already the export.

---

Required Notice: Copyright 2026 Dr. Sohil Momin (https://github.com/drsamonline/pico)
