# T09b — build_summary: by_category + uncategorized_count
Needs: T09a. Self-contained: do NOT read SPEC.md. Do not read any other file; every piece of code you need is below. Pick the simplest reading and do not deliberate.
Files: app/summary.py (replace the whole file), tests/test_summary.py (append), PROGRESS.md
Read only: nothing.

Decisions (already made): `by_category` lists only `expense`-kind categories, as GROSS cents (refunds subtract, reimbursements are NOT subtracted here). Rows with 0 cents are left out. Sorted by cents descending, ties by name. `pct` = cents / total gross * 100, rounded to 1 decimal (0.0 if gross is 0), so the percentages add up to about 100. `uncategorized_count` = number of rows whose category is named `Uncategorized`.

Step 1 — tests FIRST. Append (do not use Edit; use `cat >> tests/test_summary.py <<'PYEOF' ... PYEOF`) exactly this:

```python


def test_by_category_is_gross_sorted_with_pct(client):
    _seed([
        ("2026-01-05", -10000, "Groceries"),
        ("2026-01-05", 2500, "Groceries"),
        ("2026-01-06", -30000, "Housing"),
        ("2026-01-07", 50000, "Income"),
        ("2026-01-08", -20000, "Credit Card Payment"),
        ("2026-01-09", 4000, "Work Reimbursement"),
    ])
    s = _summary()
    got = [(c["name"], c["cents"], c["pct"]) for c in s["by_category"]]
    assert got == [("Housing", 30000, 80.0), ("Groceries", 7500, 20.0)]
    assert set(s["by_category"][0]) == {"category_id", "name", "color", "cents", "pct"}
    # by_category is gross; the reimbursement only lowers spending_cents
    assert sum(c["cents"] for c in s["by_category"]) == 37500
    assert s["spending_cents"] == 33500


def test_by_category_zero_rows_omitted_and_empty_ok(client):
    assert _summary()["by_category"] == []
    _seed([("2026-01-05", -1000, "Groceries"), ("2026-01-06", 1000, "Groceries")])
    assert _summary()["by_category"] == []


def test_by_category_pct_one_decimal_and_tie_order(client):
    _seed([("2026-01-05", -1000, "Groceries"), ("2026-01-05", -2000, "Housing")])
    got = [(c["name"], c["pct"]) for c in _summary()["by_category"]]
    assert got == [("Housing", 66.7), ("Groceries", 33.3)]


def test_equal_amounts_sort_by_name(client):
    _seed([("2026-01-05", -1000, "Groceries"), ("2026-01-05", -1000, "Fees")])
    names = [c["name"] for c in _summary()["by_category"]]
    assert names == ["Fees", "Groceries"]


def test_uncategorized_count(client):
    _seed([
        ("2026-01-05", -100, "Uncategorized"),
        ("2026-01-06", -200, "Uncategorized"),
        ("2026-01-07", -300, "Groceries"),
    ])
    assert _summary()["uncategorized_count"] == 2
```

Run `make test`: the new tests must FAIL (KeyError `by_category` / `uncategorized_count`).

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
```

Verify: `make test` all green (5 new tests, the 6 from T09a still pass). Touch nothing else. Tick T09b in PROGRESS.md, add one Log line, commit.
