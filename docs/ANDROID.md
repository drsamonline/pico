# Android

There is no `.apk`, and this file explains why, then gives the two routes that work today.

## Why no APK

pico is a Python program with a local web console. An APK would need one of:

| Approach | Cost |
| --- | --- |
| Chaquopy / Briefcase / Buildozer | a Gradle toolchain, a ~40 MB wrapper, and a Python runtime per architecture |
| Termux bootstrap | a package manager inside a sandbox, which Termux already is |
| A WebView shell around the console | 40 MB to display a page the browser already renders |

None of them makes a command *work* that does not work now. The console is one HTML file with a
manifest, icons and a service worker, so it already installs to the home screen and opens standalone.
That is the same outcome an APK would give, at 60 KB instead of 40 MB.

## Route 1 — install the console (recommended)

The phone talks to pico running on a computer on the same network.

**On the computer:**

```bash
python3 pico.py --ui --lan
```

That prints a URL like `http://192.168.1.20:8765/` and a warning: LAN mode means anyone on that
network can drive pico, so use it on a network you trust, or over Tailscale instead.

**On the phone:**

1. Open that URL in Chrome or Safari.
2. Menu → **Add to Home Screen** (iOS: Share → Add to Home Screen).
3. Open it from the home screen. It runs standalone, without browser chrome.

The service worker caches the shell, so the console opens offline — but the engine lives on the
computer, so commands need the network. When the computer is unreachable the status chip turns red and
says so; it recovers by itself when pico comes back.

## Route 2 — run pico on the phone

Termux is a real terminal, so pico runs there directly.

```bash
pkg update && pkg install python
git clone https://github.com/drsamonline/pico
cd pico
sh install.sh
python3 ~/pico.py --ui
```

Then open `http://127.0.0.1:8765/` in the phone's browser.

Keep it alive across screen locks:

```bash
termux-wake-lock
python3 ~/pico.py --serve &
```

Android will still kill it eventually; `--serve` is not a system service. For anything you rely on,
run pico on a computer and use Route 1.

What works on Termux: everything except the commands that need desktop software — `tidy`, `backup`,
`find`, `quarantine`, `dedupe files` work on the phone's own storage, but Android scopes that storage,
so `~/Downloads` is usually empty unless you grant Termux access with `termux-setup-storage`.

## Route 3 — Telegram instead of a console

If the point of the phone is to run a command away from the desk, the Telegram bridge is lighter than
either route:

```bash
echo "<your bot token>" > ~/.pico/telegram.token
python3 pico.py --serve
```

Message the bot once to bind the chat, then send commands as if you were at the terminal. Set
`~/.pico/telegram.bindcode` first if the bot could be found by someone else before you message it.

## What does not exist

- No Play Store listing, and none planned: the licence is noncommercial and the app is one file.
- No background service. Timers and daily jobs fire only while pico runs.
- No widget, no share-sheet target, no notification channel beyond the Telegram bridge.

---

Required Notice: Copyright 2026 Dr. Sohil Momin (https://github.com/drsamonline/pico)
