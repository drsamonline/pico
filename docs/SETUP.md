# What you have to do

Everything else is already done. These are the steps only you can take.

## 1. Install it

| Your machine | Command |
| --- | --- |
| Windows | download `pico-windows-x86_64.exe` from the latest release, put it anywhere, run it |
| macOS (Apple silicon) | download `pico-macos-arm64`, `chmod +x`, run it |
| Linux | download `pico-linux-x86_64`, `chmod +x`, run it |
| Any, from source | `git clone https://github.com/drsamonline/pico && cd pico && python3 pico.py` |

No installer, no admin rights, no dependencies. Python is only needed for the source route — the
binaries carry their own.

## 2. Say hello

```
pico
tasks
add buy milk
brief
```

If those three work, the tool works. Nothing is sent anywhere; there is no account.

## 3. Optional — the Telegram bridge

1. In Telegram, message **@BotFather**, send `/newbot`, answer two questions.
2. It replies with a token shaped like `123456789:AAH...`.
3. In pico:

```
telegram token 123456789:AAH...
pico --serve
```

The token is stored at `~/.pico/telegram.token`, readable only by you, never logged, never in the
binary. `telegram token status` tells you whether one is set without showing it. `telegram token forget`
removes it.

Nothing happens until you set the token, so the bridge costs nothing if you never want it.

## 4. Optional — the model

pico works with the model off. Turn it on only if you want to type sentences the rules do not cover.

```
llm key sk-...          # stored at ~/.pico/llm.key, owner-only, never logged
llm set provider openai # or ollama for a local model
llm set endpoint https://api.openai.com/v1/chat/completions
llm set model gpt-4o-mini
llm cloud
llm status
```

`llm key forget` removes it. `privacy never TAG` blocks a word from ever reaching the model.

## 5. Optional — the phone

Open <https://drsamonline.github.io/pico/app.html> and use **Add to Home Screen**. It is the same
console, one HTML file, and it works offline once loaded.

## 6. Know what you have

```
doctor              # is everything healthy
doctor probe        # does every command answer
help                # the rule list
aliases             # your own words
```

## What is already done for you

| Thing | State |
| --- | --- |
| 114 rules, 12 packs | built and tested |
| 457 acceptance checks | green on 3 OSes and 3 Python versions |
| six gates (tests, parity, contrast, 3.8, budget, docs) | green in CI |
| Windows, macOS, Linux binaries | built on every release |
| landing page and console | published on GitHub Pages |
| licence, privacy, security, architecture, roadmap | written |

## What nobody has done yet

pico has never been used for a week on a real desktop by a real person. That is the one test left, and
it is yours. When something annoys you, that annoyance is the bug report worth more than another
thousand checks.
