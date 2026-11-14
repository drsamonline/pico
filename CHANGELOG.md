# Changelog

All notable changes. Dates are ISO. Versions follow [semver](https://semver.org/).

## 1.0.0 — 2026-11-14

First public release. The engine was rebuilt around the audit findings below rather than patched
around them.

### Added

- **Resolution ladder** — rule → alias → typo → fuzzy → translator → teach, each tier inspectable.
- **Risk tiers** — `safe`, `write`, `send`, `danger`, with a 120 s consent window and blast-radius
  previews for handlers that define `fn.preview`.
- **Universal undo** — handlers register an inverse; packs can register their own via
  `api["inverse_handler"]`. 50-step stack.
- **Ledger** — one JSON line per executed command, with `cmd`, `src`, `tier`, rule, output, timestamp.
- **Local console** (`web/index.html`) — one file, no external assets, token-gated, responsive from
  390 px to 1440 px, with a client-side demo mode that runs the same resolver and arithmetic.
- **Optional translator** (`packs/llm.py`) — off by default, mode-aware provider routing, daily budget,
  response cache, alias distillation.
- **Privacy gate in the core** — `never_send` is checked before any translator is called, not inside
  the adapter.
- **Core firewall** — translator output is validated by the core: rule match, no shell metacharacters,
  length cap, deny-list.
- 30 acceptance tests covering the ten spec test cases plus state recovery and ledger redaction.
- Landing page, architecture, command reference, roadmap, privacy and security documents.
- GitHub Actions: CI across Python 3.8/3.10/3.12 and three operating systems; release workflow that
  builds one-file binaries and the source zip on every tag.

### Fixed — carried over from the audit of the v4 bundle

| Defect | Now |
| --- | --- |
| Any handler exception killed the process (`split 1000 0` was enough) | handlers are wrapped; the REPL and one-shot CLI are wrapped again |
| `dry` bypassed the resolution ladder and reported "NO MATCH" for commands that would run | `dry` calls `resolve()` and reports the tier that resolved it |
| `privacy never X` wrote a setting nothing read | enforced in the core resolver before any translator runs |
| `llm local` / `llm cloud` were cosmetic; the provider never changed | the mode constrains the provider, and a mismatch refuses with the fix |
| Packs and templates were invisible unless `--install` had run | the bundle directory is searched as well as `~/.pico/` |
| `load_plugins()` only ran under `__main__`, so importers got zero packs | loading is a method; the console and tests both use it |
| The ledger stored `recall pin` output verbatim, and `log` printed it | output of secret-bearing commands is redacted; `remember`/`contact` values are masked too |
| One corrupt `state.json` bricked the tool permanently | quarantined to `state.json.corrupt-<ts>`, engine starts empty |
| The model could trigger ungated `tidy`/`backup` | write-tier commands from a translator are gated like a send |
| `journal 5` was ambiguous and shadowed the add rule | `journal show N` reads, `journal text` writes |
| `remind 18:30` with no text did not match | message is optional |
| `disc 999 150` returned a negative price; `split` silently dropped a cent | range checks; the rounding residue is stated |
| `calc` used `eval` with a character allowlist | AST walker with power and magnitude caps |
| Two engines in one process shared handler state | module-level engine refs are rebound per call |
| `undo` swallowed `undone` because of a prefix check | full-match regex |

### Known limits

- Timers, reminders and daily jobs fire only while pico runs.
- State is plaintext JSON; nothing is encrypted.
- No OCR, speech, QR rendering or two-way WhatsApp without an external tool or Meta's Cloud API.
- `write`-tier commands typed by hand are not gated, only undoable. Deliberate, and open for review.
- The core is 22,462 B against a 20 KB spec budget. The overage is the inverse registry, the
  translator firewall and the privacy gate. Stated rather than hidden; the CI ceiling is 24 KB.
