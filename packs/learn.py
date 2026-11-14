"""learn — spaced repetition (SM-2) over your own notes. No model, no network."""
import datetime
import json

CATALOG = ["card add Q|A - new flashcard", "review - next due card",
           "grade 0-5 - score the card", "cards - deck stats"]
P = D = E = None


def setup(api):
    global P, D, E
    E = api["engine"]
    P = api["HOME"] / "cards.json"
    D = json.loads(P.read_text("utf-8")) if P.exists() else {"cards": [], "session": None}


def save():
    P.write_text(json.dumps(D, indent=1), "utf-8")


def _today():
    return datetime.date.today().isoformat()


def add(m):
    q, a = [x.strip() for x in m["qa"].split("|", 1)] if "|" in m["qa"] else (m["qa"].strip(), "")
    D["cards"].append({"q": q, "a": a, "ef": 2.5, "n": 0, "interval": 0, "due": _today()})
    save()
    return "Card added. %d in the deck." % len(D["cards"])


def review(m):
    today = _today()
    due = [c for c in D["cards"] if c.get("due", today) <= today]
    if not due:
        return "Nothing due. %d card(s) scheduled later." % len(D["cards"])
    card = due[0]
    D["session"] = card["q"]
    save()
    return "Q: %s\n\n(answer in your head, then: grade 0-5)" % card["q"]


def grade(m):
    g = int(m["n"])
    if not 0 <= g <= 5:
        return "Grade is 0-5. 0 = blank, 3 = hard, 5 = easy."
    key = D.get("session")
    if not key:
        return "Nothing in review. Run: review"
    card = next((c for c in D["cards"] if c["q"] == key), None)
    if card is None:
        return "That card is gone."
    if g < 3:
        card["interval"] = 1
        card["n"] = 0
    else:
        card["n"] = card.get("n", 0) + 1
        if card["n"] == 1:
            card["interval"] = 1
        elif card["n"] == 2:
            card["interval"] = 6
        else:
            card["interval"] = max(1, round(card.get("interval", 1) * card.get("ef", 2.5)))
        card["ef"] = max(1.3, card.get("ef", 2.5) + (0.1 - (5 - g) * 0.08))
    card["due"] = (datetime.date.today() +
                   datetime.timedelta(days=card["interval"])).isoformat()
    D["session"] = None
    save()
    answer = ("\nA: " + card["a"]) if card["a"] else ""
    return "Next in %d day(s).%s" % (card["interval"], answer)


def show(m):
    cards = D["cards"]
    if not cards:
        return "No cards. Try: card add What is the EMI formula?|P*r*(1+r)^n/((1+r)^n-1)"
    today = _today()
    due = sum(1 for c in cards if c.get("due", today) <= today)
    return "%d card(s), %d due today, %d scheduled later" % (
        len(cards), due, len(cards) - due)


RULES = [
    (r"^card add (?P<qa>.+)$", add),
    (r"^review$", review),
    (r"^grade (?P<n>[0-5])$", grade),
    (r"^cards$", show),
]
