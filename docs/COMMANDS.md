# Command reference

66 rules. `[optional]` means the argument may be omitted. Every command is case-insensitive and
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

`journal 5` records the text "5". To read entries use `journal show 5`.

## Automation

| Command | Tier | Notes |
| --- | --- | --- |
| `daily HH:MM CMD` | safe | reversible; fires while pico runs |
| `jobs` | safe | list |
| `unjob N` | **danger** | reversible |

## Web

| Command | Tier | Notes |
| --- | --- | --- |
| `site k=url` · `open X` | safe | shortcut, path, or domain |
| `search X` | safe | opens DuckDuckGo |
| `weather [city]` | safe | the only command that needs the network; degrades to a message offline |

## Safety

| Command | What it does |
| --- | --- |
| `dry CMD` | resolves CMD through the full ladder, prints the resolved command, which tier resolved it, the risk tier, and the affected set. Executes nothing |
| `why` | the last resolution as JSON: cmd, src, tier, rule, output, timestamp |
| `log` | last 8 ledger lines |
| `undo [N]` | reverses the last N actions that have an inverse; names the ones that do not |
| `confirm` · `cancel` | resolve or discard a pending send/danger action (120 s TTL) |
| `aliases` · `unalias P` | inspect or remove learned phrasings |

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
