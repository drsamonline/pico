"""text — local text operations on files. No model, no network."""
import pathlib
import re

CATALOG = ["count PATH - lines, words, chars", "extract TYPE PATH - emails, urls, phones, amounts",
           "sortlines PATH - sorted unique-safe output", "dedupe PATH - drop duplicate lines",
           "redact PATH - mask PII into a new file"]
from pico.base import unquote

E = None

PATTERNS = {
    "emails": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "urls": r"https?://[^\s<>\"')]+",
    "phones": r"(?:\+?\d[\d\s-]{7,}\d)",
    "amounts": r"(?:Rs\.?|INR|₹|\$)\s?[\d,]+(?:\.\d+)?",
    "dates": r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b",
}


def setup(api):
    global E
    E = api["engine"]


def _read(m):
    p = pathlib.Path(unquote(m["path"])).expanduser()
    if not p.exists() or not p.is_file():
        return None, "File not found: " + str(p)
    try:
        return p.read_text("utf-8", errors="replace"), None
    except Exception as ex:
        return None, "Cannot read: %s" % ex


def count(m):
    text, err = _read(m)
    if err:
        return err
    lines = text.splitlines()
    return "lines %d | words %d | chars %d | bytes %d" % (
        len(lines), len(text.split()), len(text), len(text.encode("utf-8")))


def extract(m):
    kind = m["kind"].lower()
    if kind not in PATTERNS:
        return "Types: " + ", ".join(PATTERNS)
    text, err = _read(m)
    if err:
        return err
    found = []
    for hit in re.findall(PATTERNS[kind], text):
        if hit not in found:
            found.append(hit)
    if not found:
        return "No %s found." % kind
    return "\n".join(found[:200]) + ("\n(%d total)" % len(found) if len(found) > 200 else "")


def sortlines(m):
    text, err = _read(m)
    if err:
        return err
    lines = sorted({ln.rstrip() for ln in text.splitlines() if ln.strip()})
    return "\n".join(lines[:200]) or "Empty."


def dedupe(m):
    text, err = _read(m)
    if err:
        return err
    seen, out = set(), []
    for ln in text.splitlines():
        if ln not in seen:
            seen.add(ln)
            out.append(ln)
    out_p = pathlib.Path(m["path"]).expanduser().with_suffix(
        pathlib.Path(m["path"]).suffix + ".deduped.txt")
    out_p.write_text("\n".join(out) + "\n", "utf-8")
    E.set_inverse("file_rm", {"path": str(out_p)})
    return "Kept %d of %d lines -> %s" % (len(out), len(text.splitlines()), out_p)


def redact(m):
    text, err = _read(m)
    if err:
        return err
    n = 0
    for tag, pat in (("EMAIL", PATTERNS["emails"]), ("PHONE", PATTERNS["phones"]),
                     ("URL", PATTERNS["urls"])):
        text, k = re.subn(pat, "<%s>" % tag, text)
        n += k
    out_p = pathlib.Path(m["path"]).expanduser().with_suffix(
        pathlib.Path(m["path"]).suffix + ".redacted.txt")
    out_p.write_text(text, "utf-8")
    E.set_inverse("file_rm", {"path": str(out_p)})
    return "Masked %d item(s) -> %s" % (n, out_p)


RULES = [
    (r"^count (?P<path>.+)$", count),
    (r"^extract (?P<kind>\w+) (?P<path>.+)$", extract),
    (r"^sortlines (?P<path>.+)$", sortlines),
    (r"^dedupe (?!files\b)(?P<path>.+)$", dedupe),
    (r"^redact (?P<path>.+)$", redact),
]
