# T09c — build_summary: by_month
Needs: T09b. Self-contained: do NOT read SPEC.md. Do not read any other file; every piece of code you need is below. Pick the simplest reading and do not deliberate.
Files: app/summary.py (replace the whole file), tests/test_summary.py (append), PROGRESS.md
Read only: nothing.

Decisions (already made): `by_month` has one entry per calendar month (`YYYY-MM`) that contains at least one transaction in range, sorted ascending. Each entry has `income_cents`, `spending_cents` (= that month's gross - reimbursed), `reimbursed_cents` and `by_category` (`{category name: gross cents}`, expense kinds only, zero entries left out). A month that only has transfers is still listed, with zeros and `{}`.

Step 1 — tests FIRST. Append (`cat >> tests/test_summary.py <<'PYEOF' ... PYEOF`, not Edit) exactly this:

```python


def test_by_month_ascending_with_per_month_numbers(client):
    _seed([
        ("2026-02-03", -5000, "Groceries"),
        ("2026-02-10", 2000, "Work Reimbursement"),
        ("2026-01-05", -10000, "Groceries"),
        ("2026-01-06", 50000, "Income"),
    ])
    assert _summary()["by_month"] == [
        {"month": "2026-01", "income_cents": 50000, "spending_cents": 10000,
         "reimbursed_cents": 0, "by_category": {"Groceries": 10000}},
        {"month": "2026-02", "income_cents": 0, "spending_cents": 3000,
         "reimbursed_cents": 2000, "by_category": {"Groceries": 5000}},
    ]


def test_by_month_totals_match_overall(client):
    _seed([
        ("2026-01-05", -10000, "Groceries"),
        ("2026-01-06", 50000, "Income"),
        ("2026-02-03", -5000, "Housing"),
        ("2026-02-04", 2500, "Groceries"),
        ("2026-02-10", 2000, "Work Reimbursement"),
        ("2026-03-01", -700, "Fees"),
    ])
    s = _summary()
    months = s["by_month"]
    assert sum(m["income_cents"] for m in months) == s["income_cents"]
    assert sum(m["spending_cents"] for m in months) == s["spending_cents"]
    assert sum(m["reimbursed_cents"] for m in months) == s["reimbursed_cents"]
    month_cats = sum(v for m in months for v in m["by_category"].values())
    assert month_cats == sum(c["cents"] for c in s["by_category"])


def test_month_with_only_transfers_is_listed_with_zeros(client):
    _seed([("2026-03-05", -20000, "Credit Card Payment")])
    assert _summary()["by_month"] == [
        {"month": "2026-03", "income_cents": 0, "spending_cents": 0,
         "reimbursed_cents": 0, "by_category": {}}
    ]
```

Run `make test`: the 3 new tests must FAIL (KeyError `by_month`).

Step 2 — implement. Replace app/summary.py completely with `cat > app/summary.py <<'PYEOF' ... PYEOF` and exactly this content:

```python
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


def _by_month(rows):
    months = {}
    for r in rows:
        months.setdefault(r["date"][:7], []).append(r)
    out = []
    for month in sorted(months):
        income, reimbursed, gross, _ = _totals(months[month])
        cats = {}
        for r in months[month]:
            if r["ckind"] == "expense":
                cats[r["cname"]] = cats.get(r["cname"], 0) - r["amount_cents"]
        out.append(
            {
                "month": month,
                "income_cents": income,
                "spending_cents": gross - reimbursed,
                "reimbursed_cents": reimbursed,
                "by_category": {k: v for k, v in cats.items() if v != 0},
            }
        )
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
        "by_month": _by_month(rows),
    }
```

Verify: `make test` all green (3 new tests, 11 earlier summary tests still pass). Touch nothing else. Tick T09c in PROGRESS.md, add one Log line, commit.
