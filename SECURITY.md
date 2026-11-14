# Security

## Threat model

pico runs as you, on your machine, with your permissions. It is not a sandbox and does not pretend to
be one. The realistic threats it does address:

| Threat | Mitigation |
| --- | --- |
| A model proposes a destructive command | the core matches every proposed string against `RULES` before anything runs; no match means no action |
| A model is talked into a shell payload | `; & \| \` $ > <` are rejected in the core, not only in the adapter |
| A prompt injection tries to change pico's own settings | `llm`, `privacy`, `panic`, `permissions`, `2key`, `vault`, `sync`, `unalias`, `undo`, `restore` are denied to any translator-sourced command |
| A stranger finds your Telegram bot | set `~/.pico/telegram.bindcode`; the first message must match it before the chat binds |
| Anything on your LAN drives your machine | the console binds `127.0.0.1` and requires a 32-byte token; `--lan` is opt-in and warns |
| A malicious web page POSTs to the console | the token is required on every `/cmd`, compared with `secrets.compare_digest`, and no CORS headers are sent |
| A crafted expression executes code | `calc` uses an AST walker, not `eval`. No names, no calls, no attributes, caps on power and result size |
| Two instances corrupt state | atomic write (`tmp` + `os.replace`); a corrupt `state.json` is quarantined, not fatal |
| A pack is malicious | packs are plain Python you can read. They run with your privileges — review one before you drop it in `~/.pico/rules/` |

## What is not defended

- **A compromised account.** Anything that can read `~/.pico/` can read your notes.
- **A malicious pack.** The plugin contract is code execution by design. Only install packs you have
  read.
- **Filesystem permissions.** pico does not chmod your data beyond `web.token` (mode 600).
- **Traffic analysis.** The translator talks to whatever endpoint you configured. It does not pin
  certificates beyond Python's default verification.

## Secrets

`web.token`, `telegram.token` and any API key file are read from disk and never written to the ledger,
never echoed, and never included in `why` or `log`. The token is injected into the served HTML, so
anyone who can read that page can drive the console — that is the same trust boundary as reading the
token file.

## Reporting

Open a private security advisory at
[github.com/drsamonline/pico/security/advisories/new](https://github.com/drsamonline/pico/security/advisories/new),
or email [sohilmomin2000@gmail.com](mailto:sohilmomin2000@gmail.com). Please do not open a public issue
for an exploitable defect. Expect an answer within a week; this is a single-maintainer project and the
answer will be honest about timing.

## Supported versions

The latest release. Fixes land on `main` and ship as a patch release.

---

Required Notice: Copyright 2026 Dr. Sohil Momin (https://github.com/drsamonline/pico)
