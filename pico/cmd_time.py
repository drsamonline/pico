"""pico clock, countdown, reminder, arithmetic, unit conversion."""


import datetime, threading


E = None  # engine, rebound by Engine._bind_modules()


def _S():
    return E.S


def _later(secs, msg):
    t = threading.Timer(secs, lambda: E.notify(msg))
    t.daemon = True
    t.start()


def timer(m):
    unit = m["u"][0].lower()
    secs = int(m["n"]) * {"s": 1, "m": 60, "h": 3600}[unit]
    if secs > 86400:
        return "A timer longer than 24 hours is not useful. Use remind for a time of day."
    msg = (m["msg"] or "Timer done").strip()
    _later(secs, msg)
    return "Timer: %s%s - %s" % (m["n"], m["u"], msg)


def remind(m):
    h, mi = int(m["h"]), int(m["mi"])
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return "That is not a clock time. Use remind 18:30 MSG"
    now = datetime.datetime.now()
    t = now.replace(hour=h, minute=mi, second=0, microsecond=0)
    if t <= now:
        t += datetime.timedelta(days=1)
    msg = (m["msg"] or "Reminder").strip()
    _later((t - now).total_seconds(), msg)
    return "Reminder at %s - %s" % (t.strftime("%H:%M"), msg)


def clock(m):
    return datetime.datetime.now().strftime("%a %d %b %Y, %I:%M %p")


def calc(m):
    from .engine import safe_eval
    try:
        v = safe_eval(m["e"])
    except Exception:
        return "Arithmetic only: numbers and + - * / // % ** ."
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v)


def convert_(m):
    from .engine import convert
    try:
        out = convert(float(m["v"]), m["a"], m["b"])
    except Exception:
        return "Unknown or incompatible units."
    return "%s %s = %s %s" % (m["v"], m["a"], "{:,.6g}".format(out), m["b"])
