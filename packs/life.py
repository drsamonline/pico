"""life — journal, contacts, WhatsApp and mail links. Nothing is sent by pico."""
import datetime
import json
import urllib.parse
import webbrowser

CATALOG = ["journal [show N] - write or read", "contact k=v - save a contact",
           "contacts - list", "wa NAME MSG - open WhatsApp", "mail NAME SUBJ - open mail"]
P = C = J = E = None


def setup(api):
    global P, C, J, E
    E = api["engine"]
    P = api["HOME"] / "life.json"
    d = json.loads(P.read_text("utf-8")) if P.exists() else {}
    C, J = d.get("contacts", {}), d.get("journal", [])
    api["inverse_handler"]("journal_pop", lambda a: (J.pop(a["i"]), save()))
    api["inverse_handler"]("contact_del", lambda a: (C.pop(a["n"], None), save()))
    api["inverse_handler"]("contact_set",
                           lambda a: (C.__setitem__(a["n"], a["v"]), save()))


def save():
    P.write_text(json.dumps({"contacts": C, "journal": J}, indent=2, ensure_ascii=False), "utf-8")


def jadd(m):
    J.append({"d": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "t": m["t"].strip()})
    save()
    E.set_inverse("journal_pop", {"i": len(J) - 1})
    return "Journaled."


def jshow(m):
    n = int(m["n"]) if m["n"] else 5
    return "\n".join("%s  %s" % (e["d"], e["t"]) for e in J[-n:]) or "Empty."


def cadd(m):
    k = m["name"].lower()
    had = k in C
    old = C.get(k)
    C[k] = m["num"]
    save()
    E.set_inverse("contact_set" if had else "contact_del", {"n": k, "v": old})
    return "Contact saved."


def cshow(m):
    return "\n".join("%s: %s" % (k, v) for k, v in sorted(C.items())) or "No contacts."


def wa(m):
    num = C.get(m["name"].lower(), m["name"]).replace("+", "").replace(" ", "").replace("-", "")
    url = "https://wa.me/" + num
    if m["msg"]:
        url += "?text=" + urllib.parse.quote(m["msg"])
    webbrowser.open(url)
    return "Opened WhatsApp — press send."


def mail(m):
    addr = C.get(m["name"].lower(), m["name"])
    sub = urllib.parse.quote(m["sub"] or "")
    webbrowser.open("mailto:%s?subject=%s" % (addr, sub))
    return "Opened mail draft."


RULES = [
    (r"^journal(?: show(?: (?P<n>\d+))?)?$", jshow),
    (r"^journal (?P<t>.+)$", jadd),
    (r"^contact (?P<name>\w+)=(?P<num>\S+)$", cadd),
    (r"^contacts$", cshow),
    (r"^wa (?P<name>[\w+]+)(?: (?P<msg>.+))?$", wa),
    (r"^mail (?P<name>\S+)(?: (?P<sub>.+))?$", mail),
]
