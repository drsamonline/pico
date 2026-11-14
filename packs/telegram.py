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


def setup(api):
    global TOKEN, CHAT, REPLY, P, BIND, ENG
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
    global CHAT
    offset = 0
    while True:
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


RULES = []
