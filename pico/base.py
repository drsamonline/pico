"""pico base — constants and pure helpers shared by every module."""
import ast, operator, re, sys

__version__ = "1.36.0"


STATE_DEFAULT = {
    "tasks": [], "notes": {}, "spend": [], "events": [], "sites": {},
    "shop": [], "aliases": {}, "undo": [], "llm_use": {},
    "two_key": False, "recur": {},
}


RISK_RULES = [
    (r"^(wa|mail|sms|tg|bulk|send)\b", "send"),
    (r"^(panic|shutdown|kill|restore|safe delete|unjob|habit del|vault|wipe)\b", "danger"),
    (r"^(tidy|rename|backup|fill|batch|autofile|zip|unzip|export|for each|chain)\b", "write"),
]


DENY_LLM = re.compile(
    r"^(llm|privacy|panic|permissions|2key|vault|sync|unalias|undo|restore)\b", re.I)


SECRET_OUT = re.compile(r"^(recall|what is|journal|contacts|aliases|card|review)\b", re.I)


MASK_CMD = re.compile(r"^((?:remember|contact|site)\s+\w+\s*[:=]\s*)(\S+)", re.I)


def utf8_console(streams=None):
    """Make stdout and stderr survive any script.

    A Windows console defaults to cp1252, and `expenses` on a Devanagari category
    raises UnicodeEncodeError before a single character reaches the user. UTF-8
    where the stream allows it, replacement characters where it does not — never a
    traceback for a name the user typed.

    `streams` exists so a test can hand in its own writer instead of patching the
    process's stdout, which is a global every other test also uses.
    """
    for stream in (streams if streams is not None else (sys.stdout, sys.stderr)):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            try:
                stream.errors = "replace"
            except Exception:
                pass


def mask_cmd(cmd):
    m = MASK_CMD.match(cmd)
    return (m.group(1) + "<redacted>") if m else cmd


PENDING_TTL = 120  # seconds

# a catalogue entry containing one of these is a template, not a command
PLACEHOLDER = re.compile(r"[A-Z]{2,}|\bX\b|\bN\b|\b[A-Z]\b|\b[a-z]\b")


def unquote(p):
    """`count "/a/b c.txt"` should not look for a file called `"/a/b c.txt"`."""
    p = (p or "").strip()
    if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'":
        return p[1:-1]
    return p


def normalize(t):
    """Lowercase, collapse whitespace, strip edge punctuation. Never touches stored data."""
    t = (t or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t.strip(" .,;:!?\"'")


_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.Pow: operator.pow}


_UN = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def safe_eval(expr, _depth=0):
    """Arithmetic only. No names, no calls, no attributes. Raises ValueError otherwise."""
    if len(expr) > 120 or _depth > 8:
        raise ValueError("expression too large")
    tree = ast.parse(expr, mode="eval")

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant):
            if isinstance(n.value, bool) or not isinstance(n.value, (int, float)):
                raise ValueError("numbers only")
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and (abs(b) > 64 or abs(a) > 1e6):
                raise ValueError("power too large")
            v = _BIN[type(n.op)](a, b)
            if isinstance(v, (int, float)) and abs(v) > 1e18:
                raise ValueError("result too large")
            return v
        if isinstance(n, ast.UnaryOp) and type(n.op) in _UN:
            return _UN[type(n.op)](ev(n.operand))
        raise ValueError("only + - * / // % ** on numbers")

    return ev(tree)


UNITS = {
    "mm": ("len", .001), "cm": ("len", .01), "m": ("len", 1), "km": ("len", 1000),
    "in": ("len", .0254), "ft": ("len", .3048), "yd": ("len", .9144), "mi": ("len", 1609.344),
    "mg": ("mass", .001), "g": ("mass", 1), "kg": ("mass", 1000), "lb": ("mass", 453.592),
    "oz": ("mass", 28.3495), "tonne": ("mass", 1e6),
    "ml": ("vol", .001), "l": ("vol", 1), "gal": ("vol", 3.78541), "cup": ("vol", .24),
    "s": ("time", 1), "min": ("time", 60), "h": ("time", 3600), "day": ("time", 86400),
    "kb": ("data", 1024), "mb": ("data", 1024 ** 2), "gb": ("data", 1024 ** 3),
    "tb": ("data", 1024 ** 4),
}


def convert(v, a, b):
    a, b = a.lower(), b.lower()
    temps = {"c": lambda x: x, "f": lambda x: (x - 32) * 5 / 9, "k": lambda x: x - 273.15}
    if a in temps and b in temps:
        c = temps[a](v)
        return {"c": c, "f": c * 9 / 5 + 32, "k": c + 273.15}[b]
    if a in UNITS and b in UNITS and UNITS[a][0] == UNITS[b][0]:
        return v * UNITS[a][1] / UNITS[b][1]
    raise ValueError("incompatible units")


def importlib_spec(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

