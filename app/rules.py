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
