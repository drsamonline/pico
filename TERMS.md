# Terms of use

Version 1.0 · effective 16 November 2026 · owner: Dr Sohil Momin · what changed: first version.

These terms cover the pico program you download and the pico console page. They do not cover anything
else. Read them with [`PRIVACY.md`](PRIVACY.md), which states what the program stores and what can leave
your machine.

## What you are getting

pico is a personal automation program for one person's own computer. It is licensed, not sold, under the
[PolyForm Noncommercial License 1.0.0](LICENSE). That licence governs your right to use, copy, modify and
share the source. Where these terms and the licence disagree about the software, the licence wins.

You get the program as it is. There is no subscription, no account, no server operated by the author, and
nothing to cancel.

## What the program does, and what it does not

| It does | It does not |
| --- | --- |
| run on your machine, storing your data under `~/.pico/` | hold your data on any server |
| answer commands from a fixed rule set | guarantee that any sentence is understood |
| optionally talk to a model provider **you** configure, with **your** key | provide, proxy or pay for model access |
| optionally bridge to Telegram through **your** bot | operate a bot, channel or account on your behalf |
| mask obvious personal data with `redact` | guarantee that every piece of personal data is found |

## Your responsibilities

1. **Your keys, your accounts.** A Telegram token or a provider API key is yours. You are responsible for
   what it is used for, for its cost, and for removing it (`telegram token forget`, `llm key forget`).
2. **Your data, your backup.** The program keeps files on your disk and deletes nothing you did not ask
   it to delete. Back them up. `backup PATH` exists for this.
3. **Your judgement.** The arithmetic, the dates and the reminders are yours to check. `emi`, `sip`,
   `fd`, `gst` and the rest are calculators, not advice.
4. **Your compliance.** If you use pico at work or on other people's data, the obligations are yours,
   including under the Digital Personal Data Protection Act, 2023.

## No warranty

The program is provided **as is**, without warranty of any kind, express or implied, including
merCHANTABILITY, fitness for a particular purpose and non-infringement. The author does not warrant that
it will be uninterrupted, error-free, or that it will not lose data. Keep backups.

## Limitation of liability

To the maximum extent permitted by law, the author is not liable for any indirect, incidental, special,
consequential or punitive damages, or for any loss of data, profits or goodwill, arising from your use of
the program. Where liability cannot be excluded, it is limited to the amount you paid for the program,
which for a free download is zero.

Nothing here limits rights you have under the Consumer Protection Act, 2019 that cannot be limited by
agreement.

## Personal data

The program is built so that your data stays on your machine; see [`PRIVACY.md`](PRIVACY.md) for the file
list, the four paths that can leave the machine, and how to erase each. Where the program sends a sentence
to a model provider you configured, the provider's terms and privacy policy apply to that sentence, not
these terms. Where it sends a message through your Telegram bot, Telegram's terms apply.

For anything about your data in this project:

- **Grievance contact:** Dr Sohil Momin, sohilmomin2000@gmail.com
- **Response window:** 30 days from receipt
- **Escalation:** if you are not satisfied, you may complain to the Data Protection Board of India under
  s.13 of the Digital Personal Data Protection Act, 2023

## Changes

A new version of this file is published with the release that changes the facts in it, and the header
above records what changed. Continuing to use a release means the terms published with that release apply.

## Governing law

These terms are governed by the laws of India. The courts at the author's place of residence in India have
exclusive jurisdiction, subject to any right you have to bring a consumer complaint where you live.

## Not legal advice

This file was drafted to describe the software accurately. It is not legal advice to you, and the author is
not your lawyer. If your use carries real risk, have your own counsel read it.
