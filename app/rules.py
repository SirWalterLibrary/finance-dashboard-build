"""Merchant-key rule helpers (pure functions, no I/O)."""
import re

from app.csvparse import norm_desc

_AUTH_RE = re.compile(r"^.*?AUTHORIZED ON \d\d/\d\d ")


def merchant_key(desc: str) -> str:
    """Suggest a rule keyword from a bank description."""
    d = norm_desc(desc)
    d = _AUTH_RE.sub("", d, count=1)
    if d.startswith("APLPAY "):
        d = d[len("APLPAY "):]
    tokens = [t for t in d.split() if not any(c.isdigit() for c in t)]
    n = 3 if d.startswith(("ZELLE TO", "ZELLE FROM")) else 2
    return " ".join(tokens[:n])


def match_rule(rules, norm_description, amount_cents):
    """Pick the best matching rule for a normalized description and amount.

    A rule matches when its keyword is in the description and the amount
    bounds (inclusive, on abs amount) hold. Winner: longest keyword, then
    a rule with any bound, then highest id. Returns the rule dict or None.
    """
    a = abs(amount_cents)
    best = None
    for r in rules:
        if r["keyword"] not in norm_description:
            continue
        if r.get("min_cents") is not None and a < r["min_cents"]:
            continue
        if r.get("max_cents") is not None and a > r["max_cents"]:
            continue
        rank = (len(r["keyword"]), 0 if r.get("min_cents") is None and r.get("max_cents") is None else 1, r["id"])
        if best is None or rank > best[0]:
            best = (rank, r)
    return None if best is None else best[1]
