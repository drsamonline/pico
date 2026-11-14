# Command reference

106 rules, plus 6 slot rules that ask one question instead of failing. `[optional]` means the argument may be omitted. Every command is case-insensitive and
`<angle brackets>` are the risk tier.

## Capture

| Command | Tier | Notes |
| --- | --- | --- |
| `tasks` · `todo` · `list` | safe | `[x] N. text` for each task |
| `add X` · `task X` | safe | appends an open task |
| `done N` · `undone N` | safe | 1-based index; both reversible |
| `del N` | safe | reversible — the task is restored by `undo` |
| `remember k=v` · `remember k: v` | safe | plain note; masked in the ledger |
| `recall k` · `what is k` | safe | output redacted in the ledger |
| `forget k` | safe | reversible |
| `buy X` · `shop` · `bought N` | safe | shopping list |
| `on YYYY-MM-DD text` · `on MM-DD text` | safe | appears in `brief` on that date |
| `recur daily\|weekly\|monthly X` | safe | reopens itself when the day turns over |
| `due N YYYY-MM-DD` | safe | sets a due date on task N; reversible |
| `overdue` | safe | tasks past their date |
| `brief` · `today` · `agenda` | safe | date, open tasks, today's events, month spend |

## Money

| Command | Tier | Notes |
| --- | --- | --- |
| `spend AMT [CAT]` | safe | category defaults to `misc` |
| `expenses` | safe | this month, by category, with total |
| `budget CAT AMT` | safe | monthly cap; reversible |
| `budget` | safe | spend vs cap, with a bar |
| `emi P R N` | safe | principal, annual rate %, months |
| `sip A R Y` | safe | monthly amount, annual return %, years |
| `fd P R Y` | safe | quarterly compounding |
| `si P R Y` | safe | simple interest |
| `gst A R` | safe | amount, rate — returns +GST, −GST and the tax part |
| `split A N` | safe | states the rounding residue instead of hiding it |
| `disc A R` | safe | rejects a rate outside 0–100 |
| `asset NAME AMT` | safe | records an asset |
| `debt NAME AMT RATE` | safe | records a debt with its annual rate |
| `net worth` | safe | assets, debts, and the difference |
| `debt snowball [EXTRA]` | safe | avalanche order (dearest first) and the month each clears |
| `subs audit` | safe | charges repeating across months, flagged as candidate subscriptions |

All finance commands reject zero or negative terms with a message rather than a traceback. None of
them is advice; they are arithmetic.

## Time

| Command | Tier | Notes |
| --- | --- | --- |
| `time` · `date` · `now` | safe | local clock |
| `timer 10m MSG` | safe | `s`, `m`, `h`, or `sec`/`min`/`hr` |
| `remind 18:30 MSG` | safe | message optional; fires today or tomorrow |
| `calc EXPR` | safe | `+ - * / // % **` on numbers only, AST-checked |
| `convert V U to U` | safe | length, mass, volume, time, data, °C/°F/K |

`calc` is not `eval`. `pico/engine.py:safe_eval` walks the AST and admits only numeric constants and
the seven arithmetic operators, with size caps on powers and results.

## Files

| Command | Tier | Notes |
| --- | --- | --- |
| `tidy [PATH]` | write | defaults to `~/Downloads`; 7 categories; reversible |
| `backup PATH` | write | zip into `~/.pico/backups/`; reversible |
| `find NAME` | safe | Downloads, Documents, Desktop; first 10 hits |
| `templates` | safe | names from `~/.pico/templates/` and the bundle |
| `fill TPL k=v …` | write | replaces `{{k}}`; writes `TPL_<date>.txt`; reversible |
| `count PATH` | safe | lines, words, chars, bytes |
| `extract emails\|urls\|phones\|amounts\|dates PATH` | safe | deduplicated |
| `sortlines PATH` | safe | sorted unique lines, printed |
| `dedupe PATH` | write | writes `NAME.deduped.txt`; reversible |
| `redact PATH` | write | masks email, phone, URL; writes `NAME.redacted.txt`; reversible |
| `safe delete PATH` | **danger** | moves to `~/.pico/quarantine/`; `undo` restores it |
| `quarantine` | safe | what is in quarantine, with sizes |
| `restore N` | **danger** | puts item N back at its recorded original path |
| `quarantine sweep Nd` | **danger** | deletes quarantined files older than N days. Not undoable |
| `big files [N]` | safe | largest N files under Downloads, Documents, Desktop, Pictures |
| `old files Nd` | safe | untouched for N days |
| `dedupe files PATH` | safe | sha256 groups; reports only |
| `dedupe files PATH apply` | write | quarantines the duplicates; reversible |

## Life

| Command | Tier | Notes |
| --- | --- | --- |
| `habit add X` · `did X` · `habits` · `habit del X` | safe / **danger** for `del` | streak counts today or yesterday as current |
| `journal` | safe | last 5 entries |
| `journal show N` | safe | last N |
| `journal text` | safe | appends a timestamped entry; reversible |
| `contact k=v` · `contacts` | safe | reversible |
| `wa NAME MSG` | **send** | opens a `wa.me` deep link; you press send |
| `mail NAME SUBJ` | **send** | opens a `mailto:` draft |
| `card add Q\|A` · `review` · `grade 0-5` · `cards` | safe | SM-2 spaced repetition over your own notes |

`journal 5` records the text "5". To read entries use `journal show 5`.

## Automation

| Command | Tier | Notes |
| --- | --- | --- |
| `daily HH:MM CMD` | safe | reversible; fires while pico runs |
| `jobs` | safe | list |
| `unjob N` | **danger** | reversible |
| `report weekly` · `report month` | safe | commands run, by tier and source; tasks; spend |
| `decide A\|B\|C` | safe | one pick, seeded from the options and the date, so it is stable all day |

## Web

| Command | Tier | Notes |
| --- | --- | --- |
| `site k=url` · `open X` | safe | shortcut, path, or domain |
| `search X` | safe | opens DuckDuckGo |
| `weather [city]` | safe | the only command that needs the network; degrades to a message offline |

## Data

| Command | Tier | Notes |
| --- | --- | --- |
| `importcsv PATH TABLE` | safe | loads a CSV into `~/.pico/pico.db` (sqlite3), reversible |
| `sql SELECT …` | safe | read-only: SELECT, WITH and PRAGMA only. 50-row cap |
| `tables` | safe | what is loaded, and how many rows |
| `csv filter COL[:number\|:text]OP VAL PATH` | safe | `age>30`, `name=Asha`, `>= <= !=`. `:number` drops non-numeric rows, `:text` compares lexicographically |
| `csv sort COL[:number\|:text] [asc\|desc] PATH` | safe | auto compares numbers numerically and text after them; `:number` and `:text` force one reading |
| `csv join KEY[:number\|:text] A.csv B.csv` | safe | inner join, 50-row cap. `:number` treats `01` and `1` as the same key |
| `csv pivot COL[:number\|:text][,…] sum\|count\|avg\|min\|max FIELD PATH [having EXPR] [order by key\|value [asc\|desc]]` | safe | group by any number of columns, aggregate another, with a total. `having sum>100` filters groups; `order by` sets the sort; the key type decides how `order by key` compares |
| `chart 1,4,9` | safe | horizontal bars scaled to the maximum |

## Triggers

A saved rule: one condition, one or more commands. Actions are validated against the rule set when
saved, run through the same risk gate, and **a chain or loop refuses to carry a send or danger
action** — a saved rule should not be able to fire a message on its own.

| Command | Tier | Notes |
| --- | --- | --- |
| `when HH:MM then CMD ; CMD` | safe | fires once per day at that minute |
| `when every 30m then CMD` | safe | `s`, `m`, `h` |
| `when file GLOB then CMD` | safe | new files only; `{file}` and `{files}` are substituted |
| `when not CMD by HH:MM then CMD` | safe | negative trigger: fires if CMD has not run by that time today |
| `when clip matches REGEX then CMD` | safe | clipboard poller; `{clip}` is the match. Inert if no clipboard tool exists |
| `when SPEC unless COND then CMD` | safe | `COND` is `away`, `weekend`, `weekday`, `file GLOB`, `exists PATH`. Join two with `or`: any one true vetoes |
| `watch FOLDER then CMD` | safe | shorthand for a file trigger on `FOLDER/*` |
| `away on` · `away off` | safe | pauses every trigger gated with `unless away` |
| `chain NAME: a ; b ; c` | safe | defines a named sequence in `state.json` |
| `chain NAME` | write | runs it |
| `for each row in PATH.csv then CMD` | write | `{column}` substituted per row; 200-row cap |
| `triggers` · `untrigger N` | safe | list (with firing count) and remove |
| `trigger log [N]` | safe | the last 5 firings per rule: timestamp, ok/FAIL, output |
| `notify MSG` | safe | pushes through the notifier bus (console bell, Telegram) |

Triggers fire only while pico runs (`--serve` or the REPL), checked every 15 seconds. A failing action
is retried once; if it still fails **that action alone** backs off for 2, 4, 8, 16, 32 then 60
minutes, and the rest of the rule keeps running. `triggers` shows how many actions are backing off.

## Diagnostics

| Command | Tier | Notes |
| --- | --- | --- |
| `doctor` | safe | checks home, state, ledger, rules, packs, templates, quarantine, snapshots, triggers, the per-pack data files, sqlite, tokens, two-key, the background-thread heartbeats and the Python version. Prints `ok` / `warn` / `FAIL` per line and a count |
| `doctor probe` | safe | runs one read-only command per pack **through the handler, not through `_run`**, so nothing is logged and nothing is saved. Catches a pack that loads but cannot answer |
| `doctor fix` | safe | repairs what can be repaired: creates missing directories, removes stray temp files, quarantines unreadable JSON (never deletes it), prunes old snapshots, prunes a stale quarantine index, regenerates an empty `web.token`. Lists each action |

A fresh home reports all `ok`: nothing written yet is correct, not broken.

## Safety

| Command | What it does |
| --- | --- |
| `dry CMD` | resolves CMD through the full ladder, prints the resolved command, which tier resolved it, the risk tier, and the affected set. Executes nothing |
| `why` | the last resolution as JSON: cmd, src, tier, rule, output, timestamp |
| `log` | last 8 ledger lines |
| `undo [N]` | reverses the last N actions that have an inverse; names the ones that do not |
| `confirm` · `cancel` | resolve or discard a pending send/danger action (120 s TTL) |
| `aliases` · `unalias P` | inspect or remove learned phrasings |
| `2key on` · `2key off` | danger actions then print a 6-hex code; `approve <code>` completes them |
| `2key phone` | the code goes to the bound chat and `approve` is **refused at the terminal** |
| `timeline [TS]` | the ledger as a readable list, optionally since an ISO timestamp |
| `replay TS` | rebuilds state as of an ISO timestamp into `~/.pico/replay-<ts>/`. Snapshots are written every 25 mutations, 12 kept. Live state is never touched |
| `again` · `it` · `that` | repeat the previous command |

## Slot dialogue

Six partial commands ask one question rather than printing a syntax lesson:

| You type | It asks |
| --- | --- |
| `emi 500000 8.5` | how many months? |
| `sip 5000 12` | how many years? |
| `fd 100000 7.1` | how many years? |
| `gst 1000` | GST rate? |
| `split 1000` | how many people? |
| `disc 999` | discount percent? |

`cancel` clears the question. Packs register their own with `api["add_slots"](pattern, template, prompts)`.

## Model (optional)

| Command | Notes |
| --- | --- |
| `llm off` | default. Rules only, nothing leaves the device |
| `llm local` | requires `provider` ∈ `ollama`, `llamacpp`, `cli`; refuses otherwise and tells you how to fix it |
| `llm cloud` | requires `provider = openai`; same |
| `llm auto` | rules first, model only on a miss |
| `llm status` | mode, provider, model, calls today, cache size, alias count, redaction, blocklist |
| `llm set K V` | any key from the config: `provider`, `endpoint`, `model`, `timeout`, `max_calls_day`, `redact`, … |
| `llm test SENTENCE` | translates without running |
| `llm forget` | clears the translation cache |
| `privacy never TAG` | blocks any sentence containing TAG from ever reaching the model |

Deleting `packs/llm.py` removes this block entirely and changes nothing else.
