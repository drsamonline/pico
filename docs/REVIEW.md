# Code review — 1.40.1

A release-scale review of the tree at 1.40.1, using the checklist: correctness and data loss first,
then security, then performance, then design. Every finding below was reproduced before it was written
down. Findings that were fixed in 1.41.0 are marked so.

## Findings

| # | Severity | Finding | Evidence | State |
| --- | --- | --- | --- | --- |
| 1 | **High** | `open` validated what you typed but not what a saved shortcut held, so `site bad=javascript:alert(1)` then `open bad` handed the OS a script URL | the probe recorded `javascript:alert(1)` and `file:///etc/passwd` reaching `webbrowser.open` | fixed 1.41.0, T109 |
| 2 | **Medium** | `PRIVACY.md` listed the state files as they were several releases ago: `aliases.json`, `cards.json`, `llm.key` and `triggers.json` were missing, and the snapshot index was unmentioned | `tools/privacy_files.py` found four missing entries on its first run | fixed 1.41.0, T107 |
| 3 | **Medium** | There was no `TERMS.md`, though the project ships binaries under PolyForm Noncommercial and has a grievance surface under the DPDP Act | the legal audit scanner lists `TERMS.md` as required for this profile | fixed 1.41.0, T108 |
| 4 | Low | `except Exception: pass` appears 50 times in `pico/`; several of those are guards whose failure is silent by design (a corrupt alias file degrades to empty) | counted, then read each site | accepted, with the reasoning that a personal tool must not die on a damaged file |

## What was checked and found sound

| Area | Result |
| --- | --- |
| `eval` / `exec` / `pickle` / `shell=True` | none |
| subprocess calls | list arguments, no shell, timeouts on the network-bound ones |
| SQL | read-only by construction; table names sanitised; parameters bound |
| Path traversal in the console server | refused; tested |
| Secrets | never in the build, never in the ledger, never echoed; `0600` where the OS allows it |
| Unbounded loops | `chain` has depth and step budgets; `for each` caps at 200 rows |
| Unbounded growth | ledger generations, snapshots, replays, backups and quarantine all have retention |
| Unbounded reads | none found; every file read is bounded by the feature that owns it |
| Error handling | the CLI never raises: `handle()` returns a sentence |

## Verdict

**Ship.** Two findings were fixed in this release; the third was documentation that had drifted from the
code and now has a gate so it cannot drift silently again. The one accepted finding is a deliberate
trade-off, recorded rather than hidden.

## What a review of this size cannot tell you

Whether it is pleasant to use for a week. That needs a person at a keyboard, and it is the only test
still outstanding.
