"""pico rules — the core command table.

Handlers live in `cmd_*` modules by domain. This file is the registry: the pattern
table, the help text and the catalogue. `register()` wires them to an engine and
records the modules so `Engine._bind_modules()` can rebind their `E` globals.
"""
from . import (cmd_doctor, cmd_files, cmd_money, cmd_quarantine, cmd_tasks,
               cmd_time, cmd_web)
from .cmd_doctor import doctor, fix
from .cmd_files import backup, fill, find, tidy, tpl_list
from .cmd_quarantine import quarantine, restore, safe_delete, sweep
from .cmd_money import spend_add, spend_sum
from .cmd_tasks import (bought, brief, buy, event_add, note_del, note_get,
                        note_set, overdue, shop_list, task_add, task_del,
                        task_done, task_due, task_recur, task_undone, tasks_list)
from .cmd_time import calc, clock, convert_, remind, timer
from .cmd_web import open_any, search, site_set, weather

CATALOG = []
CORE_MODULES = (cmd_tasks, cmd_money, cmd_time, cmd_files, cmd_quarantine,
                cmd_web, cmd_doctor)
E = None


def _S():
    return E.S


def help_(m):
    return HELP


def aliases(m):
    a = E.aliases
    return "\n".join("%s -> %s" % (k, v) for k, v in a.items()) or "None learned yet."


def unalias(m):
    from .base import normalize
    k = normalize(m["p"])
    if E.aliases.pop(k, None) is not None:
        E.set_inverse("alias_del", {"k": k})
        return "Alias removed."
    return "No such alias."


HELP = """CORE
  tasks | add X | done N | undone N | del N | brief
  recur daily X | due N YYYY-MM-DD | overdue
  safe delete PATH | quarantine | restore N | quarantine sweep 30d
  remember k=v | recall k | forget k
  buy X | shop | bought N | on MM-DD text
  spend AMT [CAT] | expenses | calc EXPR | convert V U to U
  time | timer 10m MSG | remind 18:30 MSG
  tidy [PATH] | backup PATH | find NAME | templates | fill TPL k=v
  site k=URL | open X | search X | weather [CITY]
SAFETY
  dry CMD | why | log | undo [N] | confirm | cancel | aliases | unalias P
  doctor | timeline | replay TS | 2key on|off|phone
PACKS
  emi/sip/fd/si/gst/split/disc | habit add/did/habits | journal [show N]
  contact/wa/mail | daily HH:MM CMD | jobs | unjob N | llm off/local/cloud/auto"""


def register(engine):
    global E
    E = engine
    engine.core_modules = list(CORE_MODULES)
    for _mod in CORE_MODULES:
        _mod.E = engine
    R = [
        (r"^(hi|hello|hey|salam)$", lambda m: "Ready. Type 'help'."),
        (r"^(help|\?|start)$", help_),
        (r"^(tasks|todo|list)$", tasks_list),
        (r"^(add|task)\s+(?P<text>.+)$", task_add),
        (r"^done\s+(?P<n>\d+)$", task_done),
        (r"^undone\s+(?P<n>\d+)$", task_undone),
        (r"^del\s+(?P<n>\d+)$", task_del),
        (r"^recur\s+(?P<every>daily|weekly|monthly)\s+(?P<text>.+)$", task_recur),
        (r"^due\s+(?P<n>\d+)\s+(?P<date>\d{4}-\d{2}-\d{2})$", task_due),
        (r"^overdue$", overdue),
        (r"^safe delete\s+(?P<path>.+)$", safe_delete),
        (r"^quarantine$", quarantine),
        (r"^restore\s+(?P<n>\d+)$", restore),
        (r"^quarantine sweep\s+(?P<n>\d+)d$", sweep),
        (r"^remember\s+(?P<key>\w+)\s*[:=]\s*(?P<val>.+)$", note_set),
        (r"^(recall|what is)\s+(?P<key>\w+)$", note_get),
        (r"^forget\s+(?P<key>\w+)$", note_del),
        (r"^buy\s+(?P<item>.+)$", buy),
        (r"^shop$", shop_list),
        (r"^bought\s+(?P<n>\d+)$", bought),
        (r"^on\s+(?P<date>\d{4}-\d{2}-\d{2}|\d{2}-\d{2})\s+(?P<text>.+)$", event_add),
        (r"^(brief|today|agenda)$", brief),
        (r"^spend\s+(?P<amt>\d+(?:\.\d+)?)\s*(?P<cat>\w+)?$", spend_add),
        (r"^(spend|expenses)$", spend_sum),
        (r"^calc\s+(?P<e>.+)$", calc),
        (r"^convert\s+(?P<v>-?\d+(?:\.\d+)?)\s*(?P<a>[a-zA-Z]+)\s+(?:to|in)\s+(?P<b>[a-zA-Z]+)$", convert_),
        (r"^timer\s+(?P<n>\d+)\s*(?P<u>sec|min|hr|[smh])\b\s*(?P<msg>.*)$", timer),
        (r"^remind\s+(?P<h>\d{1,2}):(?P<mi>\d{2})\s*(?P<msg>.*)$", remind),
        (r"^(time|date|now)$", clock),
        (r"^tidy(?:\s+(?P<path>.+))?$", tidy),
        (r"^backup\s+(?P<path>.+)$", backup),
        (r"^find\s+(?P<q>.+)$", find),
        (r"^templates$", tpl_list),
        (r"^fill\s+(?P<tpl>\w+)\s+(?P<args>.+)$", fill),
        (r"^site\s+(?P<name>\w+)\s*=\s*(?P<url>\S+)$", site_set),
        (r"^open\s+(?P<t>.+)$", open_any),
        (r"^search\s+(?P<q>.+)$", search),
        (r"^weather(?:\s+(?P<city>.+))?$", weather),
        (r"^doctor fix$", fix),
        (r"^doctor$", doctor),
        (r"^aliases$", aliases),
        (r"^unalias\s+(?P<p>.+)$", unalias),
    ]
    engine.add_rules(R)
    CATALOG.extend([
        "tasks - list tasks", "add X - new task", "done N - finish task",
        "undone N - reopen task", "del N - delete task", "brief - daily briefing",
        "remember k=v - store a note", "recall k - read a note",
        "buy X - shopping list", "shop - show list", "bought N - remove item",
        "on MM-DD text - add event", "spend AMT CAT - log expense",
        "expenses - month totals", "calc EXPR - arithmetic",
        "convert V U to U - unit conversion", "time - clock",
        "timer Nm MSG - countdown", "remind HH:MM MSG - reminder",
        "tidy [PATH] - sort files by type", "backup PATH - zip a folder",
        "find NAME - locate files", "templates - list templates",
        "fill TPL k=v - fill a template", "site k=url - save a shortcut",
        "open X - open site/app/path", "search X - web search",
        "weather [city] - forecast", "help - command list",
        "dry CMD - preview without running", "why - last resolution",
        "log - recent ledger", "undo N - reverse actions",
        "doctor - self-check every subsystem",
        "doctor fix - repair what can be repaired",
        "aliases - learned phrasings", "unalias P - forget a phrasing",
        "recur daily X - repeating task", "due N YYYY-MM-DD - set a due date",
        "overdue - tasks past their date", "safe delete PATH - quarantine a file",
        "quarantine - list quarantined files", "restore N - put one back",
        "quarantine sweep ND - delete old quarantined files",
    ])
