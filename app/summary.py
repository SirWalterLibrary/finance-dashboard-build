"""Summary math (pure SQL/Python, no FastAPI). Money = integer cents."""


def _rows(conn, clause, params, from_, to):
    sql = (
        "SELECT t.date, t.amount_cents, c.id AS cid, c.name AS cname, "
        "c.color AS ccolor, c.kind AS ckind, a.type AS atype "
        "FROM transactions t "
        "JOIN accounts a ON a.id = t.account_id "
        "JOIN categories c ON c.id = t.category_id "
        f"WHERE {clause}"
    )
    params = list(params)
    if from_ is not None:
        sql += " AND t.date >= ?"
        params.append(from_)
    if to is not None:
        sql += " AND t.date <= ?"
        params.append(to)
    return conn.execute(sql, params).fetchall()


def _totals(rows):
    """(income, reimbursed, gross_expense, saved) in cents for these rows."""
    income = reimbursed = gross = saved = 0
    for r in rows:
        kind, amt = r["ckind"], r["amount_cents"]
        if kind == "income":
            income += amt
        elif kind == "reimbursement":
            reimbursed += amt
        elif kind == "expense":
            gross -= amt
        elif kind == "savings" and r["atype"] != "savings":
            saved -= amt
    return income, reimbursed, gross, saved

def _by_category(rows, gross):
    cats = {}
    for r in rows:
        if r["ckind"] != "expense":
            continue
        c = cats.setdefault(
            r["cid"],
            {"category_id": r["cid"], "name": r["cname"], "color": r["ccolor"], "cents": 0},
        )
        c["cents"] -= r["amount_cents"]
    out = []
    for c in sorted(cats.values(), key=lambda c: (-c["cents"], c["name"])):
        if c["cents"] == 0:
            continue
        c["pct"] = round(c["cents"] * 100 / gross, 1) if gross > 0 else 0.0
        out.append(c)
    return out


def build_summary(conn, clause, params, from_=None, to=None):
    """clause/params come from scope.owner_clause(scope, user_id, "a.owner_user_id")."""
    rows = _rows(conn, clause, params, from_, to)
    income, reimbursed, gross, saved = _totals(rows)
    spending = gross - reimbursed
    return {
        "income_cents": income,
        "spending_cents": spending,
        "reimbursed_cents": reimbursed,
        "net_cents": income - spending,
        "saved_cents": saved,
        "tx_count": len(rows),
        "uncategorized_count": sum(1 for r in rows if r["cname"] == "Uncategorized"),
        "by_category": _by_category(rows, gross),
    }
