"""telegram — phone bridge. Inactive until ~/.pico/telegram.token exists.

Security: the first chat to message the bot binds permanently. Set
~/.pico/telegram.bindcode to require that code as the first message instead,
which stops a stranger who finds the bot from claiming it.
"""
import json
import os
import threading
import time
import urllib.parse
import urllib.request

CATALOG = []
TOKEN = CHAT = REPLY = P = BIND = ENG = None
E = None
LAST = 0.0   # heartbeat, read by `doctor`


def setup(api):
    global TOKEN, CHAT, REPLY, P, BIND, ENG, E
    E = api["engine"]
    tf = api["HOME"] / "telegram.token"
    if not tf.exists():
        return
    TOKEN = tf.read_text("utf-8").strip()
    if not TOKEN:
        return
    P = api["HOME"] / "telegram.chat"
    CHAT = P.read_text("utf-8").strip() if P.exists() else None
    bf = api["HOME"] / "telegram.bindcode"
    BIND = bf.read_text("utf-8").strip() if bf.exists() else None
    REPLY = api["reply"]
    ENG = api["engine"]
    global LAST
    LAST = time.time()
    api["notifiers"].append(send)
    if not os.environ.get("PICO_NO_THREADS"):
        threading.Thread(target=poll, daemon=True).start()


def call(method, **params):
    url = "https://api.telegram.org/bot%s/%s" % (TOKEN, method)
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(url, data=data, timeout=70) as r:
        return json.loads(r.read().decode())


def send(msg):
    if CHAT:
        try:
            call("sendMessage", chat_id=CHAT, text=str(msg)[:4000])
        except Exception:
            pass


def poll():
    global CHAT, LAST
    offset = 0
    while True:
        LAST = time.time()
        try:
            upd = call("getUpdates", timeout=60, offset=offset).get("result", [])
            for u in upd:
                offset = u["update_id"] + 1
                msg = u.get("message") or {}
                text = (msg.get("text") or "").strip()
                cid = str((msg.get("chat") or {}).get("id", ""))
                if not text or not cid:
                    continue
                if CHAT is None:
                    if BIND and text != BIND:
                        continue
                    CHAT = cid
                    P.write_text(CHAT, "utf-8")
                    send("pico bound to this chat. Send 'help'.")
                    continue
                if cid != CHAT:
                    continue
                try:
                    ENG.approve_source = "phone"
                    send(REPLY(text[1:] if text.startswith("/") else text))
                finally:
                    ENG.approve_source = None
        except Exception:
            time.sleep(5)


def token_cmd(m):
    import pathlib
    from pico.base import write_secret, read_secret
    action = (m.groupdict().get("act") or "").strip().lower()
    tf = E.home / "telegram.token"
    if action in ("forget", "clear", "remove"):
        if tf.exists():
            tf.unlink()
            return "Token removed. The bridge is off until you set a new one."
        return "No token stored."
    if action in ("status", "show"):
        have = read_secret(tf)
        return ("Token set (%d characters), stored at %s\nThe value is never shown. "
                "Remove it with: telegram token forget" % (len(have), tf)) if have \
            else "No token. Set one with: telegram token <BOT_TOKEN>"
    value = (m.groupdict().get("value") or "").strip()
    if not value:
        return ("Set one with: telegram token <BOT_TOKEN>  (get it from @BotFather)\n"
                "Stored at ~/.pico/telegram.token, readable only by you, never logged.")
    if ":" not in value:
        return ("That does not look like a bot token — BotFather gives you "
                "<digits>:<letters>. Nothing was written.")
    path = write_secret(tf, value)
    return ("Token stored at %s (owner-only). Start the bridge with: pico --serve"
            % path)


RULES = [
    (r"^telegram token(?:\s+(?P<act>status|show|forget|clear|remove))?$", token_cmd),
    (r"^telegram token\s+(?P<value>\S+)$", token_cmd),
]
