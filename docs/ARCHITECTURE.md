# Architecture

Three layers, one entry point.

```
                       ~/.pico/  (state, ledger, packs/, templates/)
                                    │
      ┌──────────────┬──────────────┼───────────────┬──────────────┐
   CLI / REPL     Web console    Telegram        Scheduler      (future)
      └──────────────┴──────────────┴───────────────┴──────────────┘
                                    │
                            Engine.handle(text)
                                    │
              resolve → risk gate → confirm → handler → inverse → ledger
```

`Engine.handle()` is the only way in. The CLI, the console and the Telegram bridge all call it and
nothing else. Front-ends hold no business logic.

## The pieces

| File | Owns |
| --- | --- |
| `pico/engine.py` | composition root: `__init__`, `handle()`, the plugin loader, the notifier bus |
| `pico/store.py` | state load/save, the write lock, snapshots, replay, timeline |
| `pico/ladder.py` | rule registration, `match_rule`, risk tiers, `resolve`, slot dialogue, the translator firewall |
| `pico/ledger.py` | `_run`, the inverse registry, `undo` |
| `pico/base.py` | constants and pure helpers — `safe_eval`, `convert`, `normalize` |
| `pico/rules.py` | the pattern table, help text and catalogue |
| `pico/cmd_*.py` | the core handlers by domain — `tasks`, `money`, `time`, `files`, `web` |
| `pico/ui.py` | `http.server`, token check, `POST /cmd`, `GET /api/state`, HTML injection |

`Engine` is `class Engine(StoreMixin, LadderMixin, LedgerMixin)`, so every attribute a pack reaches
for still resolves on the instance. `rules.register()` records the five `cmd_*` modules on
`engine.core_modules`, and `_bind_modules()` rebinds their `E` globals alongside every pack's — which
is what keeps two engines in one process isolated. `pico/engine.py` re-exports `safe_eval`, `convert`, `normalize`
and `__version__`, which is what packs and tests import. T39 fails the suite if a mixin loses its
methods or the re-exports disappear.
| `packs/*.py` | capabilities. Each may define `setup(api)` and `RULES`; deleting one removes only its commands |
| `web/index.html` | the console. One file, no external assets, works served or as `file://` |

## The resolution ladder

`Engine.resolve()` walks six tiers and returns `{cmd, src, options}`.

1. **rule** — first match in `self.rules`, which is plugins-first, then core. Regex, case-insensitive.
2. **alias** — `aliases[normalize(text)]`, and the result must still match a rule.
3. **typo** — `difflib.get_close_matches(first_token, verbs, 1, 0.80)`; the rest of the sentence is kept.
4. **fuzzy** — close matches at 0.72 against the catalogue, skipping entries with unfilled slots
   (`X`, `N`, `PATH`, …) so a fuzzy hit cannot run a half-formed command.
5. **translator** — only if a translator is registered, the sentence is not in `never_send`, the mode
   admits the configured provider, and the budget has room. The returned command is re-validated by
   the core (`llm_payload_ok`) before it is accepted.
6. **teach** — up to three candidates. The user's `1`/`2`/`3` runs the choice *and* stores the phrasing
   as an alias, so the next time it resolves at tier 2 with the model off.

Normalisation lowercases, collapses whitespace and strips edge punctuation. It never touches stored
user data — only the lookup key.

## The risk gate

`RISK_RULES` maps a command prefix to a tier. `handle()` reads the tier of the *resolved* command,
not the typed text, which is why `dry wa bob hi` reports `send` even though the word "dry" is safe.

| Tier | Gate |
| --- | --- |
| `safe` | runs |
| `write` | runs; handlers register an inverse. Gated if the source was `llm` or `cache` |
| `send` | pending consent, 120 s TTL |
| `danger` | pending consent plus a blast-radius preview from `fn.preview(m)` when a handler defines it |

Consent lives in `self.pending`, expires by timestamp, and is cleared by `cancel` or by any new
command. `confirm` re-resolves nothing — it runs the exact string that was held.

## Ledger and inverses

Every executed command appends one JSON line:

```json
{"cmd":"spend 250 food","src":"rule","tier":"safe","rule":"rules.spend_add",
 "out":"Logged.","ts":"2026-11-14T09:34:35"}
```

`cmd` is masked for `remember`/`contact`/`site` (the value becomes `<redacted>`), and `out` is masked
for `recall`/`journal`/`contacts`/`aliases`. The in-memory `last` keeps the real value so `why` still
shows you what happened.

Handlers call `api["inverse"](op, args)`. Core ops (`list_rm`, `list_ins`, `note_set`, `dict_set`,
`move_back`, `file_rm`, `alias_del`, …) live in `Engine._apply_inverse`. Packs register their own with
`api["inverse_handler"](name, fn)` — that is how `daily`, `habit`, `journal`, `contact` and `budget`
stay reversible without the engine knowing anything about their files.

The stack holds 50 entries. `undo N` pops N and reports anything that was not invertible.

## Why state is only saved when dirty

An early build rewrote `state.json` on every command, including reads: 3.42 ms per call. Tracking a
dirty flag — set by `set_inverse`, alias learning and pack `save()` calls — took reads to 1.77 ms and
left writes at 6.29 ms. Writes pay for durability; reads should not.

## Plugin contract

```python
def setup(api): ...                      # optional, called once
RULES = [(r"^pattern (?P<name>\w+)$", handler), ...]
CATALOG = ["pattern NAME - one line"]    # optional, feeds fuzzy and the model prompt
```

`api` keys: `HOME`, `S`, `save`, `reply`, `notify`, `notifiers`, `translators`, `catalog`,
`match_rule`, `aliases`, `inverse`, `inverse_handler`, `privacy`, `add_rule`, `add_rules`, `engine`,
`version`.

A pack that raises on import prints `[pack X failed: …]` and is skipped. A handler that raises returns
`Command failed: <type>: <message>` instead of killing the session.

### The module-global engine, and why it is rebound

Packs follow `handler(m) -> str`, so they read a module-level `E`. That makes two engines in one
process share state. `Engine._bind_modules()` rebinds `pico.rules.E` and every loaded pack's `E` to the
current engine before each handler call. It costs nothing and it is what makes the test suite able to
run two isolated engines in one interpreter.

## The console

`web/index.html` is the whole UI: no framework, no build step, no external asset. It detects its
backend at load:

- **server mode** — `/*__PICO_TOKEN__*/null` was replaced by `ui.py` with the real token, so it
  `POST`s to `/cmd` and reads `/api/state`.
- **demo mode** — the placeholder is still `null`, so it runs the same resolver and the same
  arithmetic in JavaScript, with state in `localStorage`. File, timer and network commands answer
  honestly that they need the local engine.

That is why the GitHub Pages demo is a real demo rather than a screenshot: the interesting half of
pico — resolution, the risk gate, the maths — is deterministic and therefore portable.

## Layout and portability

Python 3.8+, standard library only. Windows, Linux, macOS and Termux. The console is one HTML file, so
"install on a phone" means adding a bookmark to a page the desktop is already serving.
