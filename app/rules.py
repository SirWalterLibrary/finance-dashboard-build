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


def ensure_rule(conn, keyword, category_id):
    """Return the id of an unbounded rule for keyword + category_id.

    Reuses an existing rule with the same normalized keyword, the same
    category and NULL min_cents/max_cents; otherwise inserts
    (keyword, category_id) and returns the new id. Raises ValueError for a
    blank keyword. Does not commit; the caller wraps it in `with conn:`.
    """
    kw = norm_desc(keyword)
    if not kw:
        raise ValueError("keyword is blank")
    row = conn.execute(
        "SELECT id FROM rules WHERE keyword = ? AND category_id = ? "
        "AND min_cents IS NULL AND max_cents IS NULL",
        (kw, category_id),
    ).fetchone()
    if row is not None:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO rules (keyword, category_id) VALUES (?, ?)",
        (kw, category_id),
    )
    return cur.lastrowid


def load_rules(conn):
    """Return all rules, each keyword normalized via norm_desc."""
    rows = conn.execute(
        "SELECT id, keyword, category_id, min_cents, max_cents FROM rules"
    ).fetchall()
    return [
        {
            "id": r["id"],
            "keyword": norm_desc(r["keyword"]),
            "category_id": r["category_id"],
            "min_cents": r["min_cents"],
            "max_cents": r["max_cents"],
        }
        for r in rows
    ]


def apply_rules(conn, tx_ids=None):
    """Categorize uncategorized ('none') transactions by keyword rules.

    When tx_ids is given, only those rows are considered; an empty list
    means nothing to do. Rows already 'manual', 'rule' or 'llm' are never
    touched. Returns the number of rows changed.
    """
    if tx_ids is not None and not tx_ids:
        return 0
    rules = load_rules(conn)
    sql = "SELECT id, description, amount_cents FROM transactions WHERE category_source = 'none'"
    params = ()
    if tx_ids is not None:
        sql += " AND id IN (" + ",".join("?" * len(tx_ids)) + ")"
        params = tuple(tx_ids)
    txs = conn.execute(sql, params).fetchall()
    changed = 0
    with conn:
        for t in txs:
            rule = match_rule(rules, norm_desc(t["description"]), t["amount_cents"])
            if rule is None:
                continue
            conn.execute(
                "UPDATE transactions SET category_id = ?, category_source = 'rule' "
                "WHERE id = ? AND category_source = 'none'",
                (rule["category_id"], t["id"]),
            )
            changed += 1
    return changed


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
