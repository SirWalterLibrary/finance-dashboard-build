"""Budget math (pure SQL/Python, no FastAPI). Money = integer cents.

spent_cents uses the same spending definition as app.summary: rows of
expense-kind categories, -amount_cents, for that calendar month and scope.
"""

import datetime


def _month_range(month: str):
    """(first_day_iso, next_first_day_iso) for 'YYYY-MM'; spent is [first, next)."""
    year, month_n = int(month[:4]), int(month[5:7])
    first = datetime.date(year, month_n, 1)
    nxt = datetime.date(year + 1, 1, 1) if month_n == 12 else datetime.date(year, month_n + 1, 1)
    return first.isoformat(), nxt.isoformat()


def _status(pct):
    if pct > 100.0:
        return "over"
    return "warn" if pct >= 80.0 else "ok"


def month_status(conn, owner_clause, month, owner_for_budgets):
    """Budget status for one calendar month (SPEC "Budgets").

    owner_clause = (sql_fragment, params) filtering a.owner_user_id (scope).
    owner_for_budgets = (sql_fragment, params) filtering b.owner_user_id.
    Returns a list of {id, name, limit_cents, spent_cents, pct, status}
    sorted by name: every EXPENSE category that has a budget, PLUS expense
    categories with spending but no budget ({id: None, limit_cents: 0,
    pct: 0.0, status: 'ok'}). In combined scope joint+personal limits are
    summed per category; the smallest budget id supplies `id`.
    """
    from_, to = _month_range(month)
    rows = conn.execute(
        "SELECT t.amount_cents, c.id AS cid, c.name AS cname, c.kind AS ckind "
        "FROM transactions t "
        "JOIN accounts a ON a.id = t.account_id "
        "JOIN categories c ON c.id = t.category_id "
        f"WHERE {owner_clause[0]} AND t.date >= ? AND t.date < ?",
        (*owner_clause[1], from_, to),
    ).fetchall()
    spent = {}
    for r in rows:
        if r["ckind"] == "expense":
            spent[r["cid"]] = spent.get(r["cid"], 0) - r["amount_cents"]

    budget_rows = conn.execute(
        "SELECT b.id, b.category_id, c.name AS cname, b.limit_cents "
        "FROM budgets b JOIN categories c ON c.id = b.category_id "
        f"WHERE c.kind = 'expense' AND {owner_for_budgets[0]} "
        "ORDER BY b.id",
        owner_for_budgets[1],
    ).fetchall()
    merged = {}
    for r in budget_rows:
        m = merged.get(r["category_id"])
        if m is None:
            merged[r["category_id"]] = {
                "id": r["id"],
                "name": r["cname"],
                "limit_cents": r["limit_cents"],
            }
        else:  # combined scope: sum joint+personal limits, smallest id wins
            m["limit_cents"] += r["limit_cents"]
    for cid, cents in spent.items():
        if cid not in merged:
            row = conn.execute(
                "SELECT name FROM categories WHERE id = ?", (cid,)
            ).fetchone()
            merged[cid] = {"id": None, "name": row["name"], "limit_cents": 0}

    out = []
    for cid, m in merged.items():
        spent_cents = spent.get(cid, 0)
        pct = round(spent_cents * 100 / m["limit_cents"], 1) if m["limit_cents"] > 0 else 0.0
        out.append(
            {
                "id": m["id"],
                "name": m["name"],
                "limit_cents": m["limit_cents"],
                "spent_cents": spent_cents,
                "pct": pct,
                "status": _status(pct),
            }
        )
    return out
