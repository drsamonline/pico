"""llm — OPTIONAL translator. Delete this file for a 100% air-gapped build.

The model returns a command string. That string must match an existing rule,
passes the same risk gate as typed input, and is logged. It never executes.
"""
import datetime
import hashlib
import json
import pathlib
import re
import subprocess
import urllib.request

CATALOG = ["llm off|local|cloud|auto - translator mode", "llm status - usage",
           "llm set K V - configure", "llm test SENTENCE - dry translate",
           "llm forget - clear cache", "privacy never TAG - block a domain"]

CFG = C = API = None
CACHE = {}
LOCAL_PROVIDERS = ("ollama", "llamacpp", "cli")

DEF = {"mode": "off", "provider": "ollama",
       "endpoint": "http://127.0.0.1:11434/api/chat",
       "model": "qwen2.5:3b-instruct", "api_key_file": "", "timeout": 25,
       "max_calls_day": 60, "redact": True,
       "never_send": ["health", "finance", "contacts", "vault", "journal", "pin"]}

EXAMPLES = [
    "tasks - list pending tasks", "add X - add a task", "done N - complete task N",
    "tidy - sort Downloads into folders", "backup PATH - zip a folder",
    "spend AMT CAT - log an expense", "expenses - month totals",
    "timer Nm MSG - countdown", "remind HH:MM MSG - reminder",
    "fill TPL k=v - fill a template", "brief - today briefing",
    "buy X - shopping list", "habits - streaks", "did X - log habit",
    "emi P R N - loan EMI", "sip A R Y - SIP maturity", "weather CITY - forecast",
    "find NAME - locate files", "open NAME - open site/app/path", "search X - web search",
]
SYSTEM = ("You translate a user's sentence into ONE command from this catalog. "
          "Reply with the command only, no prose, no quotes. "
          "If nothing fits, reply exactly UNKNOWN.\n\nCATALOG:\n" + "\n".join(EXAMPLES))


def setup(api):
    global CFG, C, API
    API = api
    CFG = api["HOME"] / "llm.json"
    C = json.loads(json.dumps(DEF))
    if CFG.exists():
        try:
            C.update(json.loads(CFG.read_text("utf-8")))
        except Exception:
            pass
    else:
        CFG.write_text(json.dumps(C, indent=2), "utf-8")
    cf = api["HOME"] / "llm_cache.json"
    if cf.exists():
        try:
            CACHE.update(json.loads(cf.read_text("utf-8")))
        except Exception:
            pass
    api["privacy"]["never_send"] = C["never_send"]
    api["translators"].append(translate)


def cfg_save():
    CFG.write_text(json.dumps(C, indent=2), "utf-8")


def cache_save():
    (API["HOME"] / "llm_cache.json").write_text(json.dumps(CACHE, indent=2), "utf-8")


def redact(t):
    masks = {}
    for tag, pat in (("EMAIL", r"[\w.+-]+@[\w-]+\.[\w.]+"),
                     ("NUM", r"\+?\d[\d\s-]{7,}\d"),
                     ("ID", r"\b\d{10,}\b")):
        for m in list(re.finditer(pat, t)):
            s = m.group(0)
            if s in masks.values():
                continue
            k = "<%s%d>" % (tag, len(masks) + 1)
            masks[k] = s
            t = t.replace(s, k)
    return t, masks


def unmask(t, masks):
    for k, v in masks.items():
        t = t.replace(k, v)
    return t


def blocked(text):
    low = text.lower()
    return any(tag and tag.lower() in low for tag in (C.get("never_send") or []))


def _post(url, payload, headers=None, timeout=25):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def ask(prompt):
    p, t = C["provider"], C["timeout"]
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    if p == "ollama":
        return _post(C["endpoint"], {"model": C["model"], "messages": msgs, "stream": False,
                                     "options": {"temperature": 0}}, timeout=t)["message"]["content"]
    if p in ("openai", "llamacpp"):
        h = {}
        if C["api_key_file"]:
            key = pathlib.Path(C["api_key_file"]).expanduser().read_text("utf-8").strip()
            h["Authorization"] = "Bearer " + key
        r = _post(C["endpoint"], {"model": C["model"], "messages": msgs,
                                  "temperature": 0, "max_tokens": 60}, headers=h, timeout=t)
        return r["choices"][0]["message"]["content"]
    if p == "cli":
        out = subprocess.run([C["endpoint"], "-p", SYSTEM + "\nUser: " + prompt + "\nCommand:",
                              "-n", "48", "--temp", "0"],
                             capture_output=True, text=True, timeout=t)
        return out.stdout
    raise RuntimeError("unknown provider")


def budget_ok():
    d = datetime.date.today().isoformat()
    u = API["S"].setdefault("llm_use", {})
    if u.get("date") != d:
        u.clear()
        u["date"] = d
        u["n"] = 0
    return u.get("n", 0) < C["max_calls_day"]


def budget_tick():
    u = API["S"]["llm_use"]
    u["n"] = u.get("n", 0) + 1
    API["save"]()


def translate(text):
    if C["mode"] == "off":
        return None
    if blocked(text):
        return None
    if C["mode"] == "local" and C["provider"] not in LOCAL_PROVIDERS:
        return None
    if C["mode"] == "cloud" and C["provider"] != "openai":
        return None
    if not budget_ok():
        return None
    key = hashlib.sha256((text.strip().lower() + "|" + C["model"]).encode()).hexdigest()[:16]
    if key in CACHE:
        cmd = CACHE[key]
        return {"cmd": cmd, "src": "cache"} if cmd else None
    safe, masks = redact(text) if C["redact"] else (text, {})
    try:
        raw = ask(safe).strip().splitlines()[0].strip().strip("`\"' ")
    except Exception:
        return None
    budget_tick()
    cmd = unmask(raw, masks)
    if cmd.upper().startswith("UNKNOWN") or len(cmd) > 200:
        CACHE[key] = None
        cache_save()
        return None
    if re.search(r"[;&|`$><]", cmd):
        return None
    if not API["match_rule"](cmd)[0]:
        return None
    CACHE[key] = cmd
    cache_save()
    return {"cmd": cmd, "src": "llm"}


def mode(m):
    C["mode"] = m["v"].lower()
    cfg_save()
    if C["mode"] == "off":
        return "LLM mode: off (rules only, nothing leaves this device)"
    if C["mode"] == "local" and C["provider"] not in LOCAL_PROVIDERS:
        return ("LLM mode: local, but provider is '%s' - nothing will translate.\n"
                "Fix: llm set provider ollama" % C["provider"])
    if C["mode"] == "cloud" and C["provider"] != "openai":
        return ("LLM mode: cloud, but provider is '%s' - nothing will translate.\n"
                "Fix: llm set provider openai, then llm set endpoint <api url>" % C["provider"])
    return "LLM mode: %s via provider=%s" % (C["mode"], C["provider"])


def status(m):
    u = API["S"].get("llm_use", {})
    return ("mode=%s provider=%s model=%s\n"
            "calls today=%s/%s  cached=%s  learned aliases=%s\n"
            "redact=%s  never_send=%s\n"
            "All deterministic commands work with LLM off."
            % (C["mode"], C["provider"], C["model"], u.get("n", 0), C["max_calls_day"],
               len(CACHE), len(API["aliases"]), C["redact"],
               ",".join(C["never_send"]) or "none"))


def set_(m):
    k, v = m["k"], m["v"]
    if k not in DEF:
        return "Unknown key: " + ", ".join(DEF)
    if isinstance(DEF[k], bool):
        C[k] = v.lower() in ("1", "true", "on", "yes")
    elif isinstance(DEF[k], list):
        C[k] = C[k] + [v.lower()]
    else:
        C[k] = type(DEF[k])(v)
    cfg_save()
    return "%s = %s" % (k, C[k])


def test(m):
    r = translate(m["t"])
    return ("-> %s  (via %s)" % (r["cmd"], r["src"])) if r else \
        "No translation (off, blocked domain, budget, or no valid rule)."


def forget(m):
    CACHE.clear()
    cache_save()
    return "LLM cache cleared."


def privacy(m):
    t = m["tag"].strip().lower()
    if t in C["never_send"]:
        return "'%s' is already blocked." % t
    C["never_send"].append(t)
    API["privacy"]["never_send"] = C["never_send"]
    cfg_save()
    return "'%s' blocked: any sentence containing that word is not sent to the model." % t


RULES = [
    (r"^llm (?P<v>off|local|cloud|auto)$", mode),
    (r"^llm status$", status),
    (r"^llm set (?P<k>\w+) (?P<v>.+)$", set_),
    (r"^llm test (?P<t>.+)$", test),
    (r"^llm forget$", forget),
    (r"^privacy never (?P<tag>\w+)$", privacy),
]
