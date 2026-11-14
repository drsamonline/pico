"""pico shortcuts, open, search, weather."""


import pathlib, platform, re, subprocess, webbrowser


E = None  # engine, rebound by Engine._bind_modules()


def _S():
    return E.S


def site_set(m):
    k = m["name"]
    had = k in _S()["sites"]
    old = _S()["sites"].get(k)
    _S()["sites"][k] = m["url"]
    E.set_inverse("dict_set" if had else "dict_del", {"key": "sites", "k": k, "v": old})
    return "Shortcut saved."


def open_any(m):
    t = m["t"].strip()
    if t in _S()["sites"]:
        webbrowser.open(_S()["sites"][t])
        return "Opened " + t
    p = pathlib.Path(t).expanduser()
    if p.exists():
        if platform.system() == "Windows":
            os_startfile(p)
        else:
            subprocess.Popen(["xdg-open" if platform.system() == "Linux" else "open", str(p)])
        return "Opened path."
    if re.match(r"^[\w.-]+\.[a-z]{2,}(/.*)?$", t, re.I):
        webbrowser.open("https://" + t)
        return "Opened site."
    return "Unknown target. Save one: site name=https://..."


def os_startfile(p):
    import os
    os.startfile(str(p))


def search(m):
    webbrowser.open("https://duckduckgo.com/?q=" + m["q"].replace(" ", "+"))
    return "Opened search."


def weather(m):
    import urllib.request
    try:
        url = "https://wttr.in/" + (m["city"] or "").strip().replace(" ", "+") + "?format=3"
        with urllib.request.urlopen(url, timeout=6) as r:
            return r.read().decode().strip()
    except Exception:
        return "Weather unavailable (offline?)."
