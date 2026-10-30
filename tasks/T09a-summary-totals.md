# T09a — build_summary: totals (pure function)
Needs: T08. Self-contained: do NOT read SPEC.md. Do not read any other file; every piece of code you need is below. Pick the simplest reading and do not deliberate.
Files: app/summary.py (new), tests/test_summary.py (new), PROGRESS.md

Money rules (already decided, just implement them): amounts are integer cents, negative = money out. Category `kind` decides everything:
- `income` kind -> income. `reimbursement` kind -> reimbursed (it is NOT income).
- `expense` kind -> gross spending = minus the sum of amounts (a refund is a positive amount, so it lowers spending).
- `spending = gross - reimbursed`; `net = income - spending`.
- `transfer` kind (Credit Card Payment, Transfer) is never counted. `savings` kind only counts as `saved_cents` (= minus the sum of amounts) when the account type is not `savings`.
- `from_`/`to` are inclusive ISO dates; `None` = no limit.

Step 0. In PROGRESS.md replace the line `- [ ] T09 Summary API` with these four lines and nothing else:
- [ ] T09a build_summary totals
- [ ] T09b by_category + uncategorized_count
- [ ] T09c by_month
- [ ] T09d GET /api/summary

Step 1 — tests FIRST. Create tests/test_summary.py by running `cat > tests/test_summary.py <<'PYEOF' ... PYEOF` with exactly this content:

```python
from app.db import connect
from app.summary import build_summary

JOINT = "(a.owner_user_id IS NULL)"


def _seed(txs, atype="checking", owner=None):
    """Insert one account and (date, cents, category_name) rows with plain SQL."""
    con = connect()
    try:
        with con:
            acct = con.execute(
                "INSERT INTO accounts (name, type, owner_user_id) VALUES ('t', ?, ?)",
                (atype, owner),
            ).lastrowid
            for i, (date, cents, cat) in enumerate(txs):
                cid = con.execute(
                    "SELECT id FROM categories WHERE name = ?", (cat,)
                ).fetchone()["id"]
                con.execute(
                    "INSERT INTO transactions (account_id, date, description, "
                    "amount_cents, category_id, category_source, dedupe_key) "
                    "VALUES (?, ?, ?, ?, ?, 'manual', ?)",
                    (acct, date, f"tx {i}", cents, cid, f"k{i}"),
                )
    finally:
        con.close()
    return acct


def _summary(**kw):
    con = connect()
    try:
        return build_summary(con, JOINT, (), **kw)
    finally:
        con.close()


def test_totals_exclude_transfers_and_count_savings_move(client):
    _seed([
        ("2026-01-05", -10000, "Groceries"),
        ("2026-01-06", 50000, "Income"),
        ("2026-01-07", -20000, "Credit Card Payment"),
        ("2026-01-08", -5000, "Savings"),
        ("2026-01-09", -300, "Transfer"),
    ])
    s = _summary()
    assert s["income_cents"] == 50000
    assert s["spending_cents"] == 10000
    assert s["reimbursed_cents"] == 0
    assert s["net_cents"] == 40000
    assert s["saved_cents"] == 5000
    assert s["tx_count"] == 5


def test_refund_reduces_spending(client):
    _seed([("2026-01-05", -10000, "Groceries"), ("2026-01-06", 2500, "Groceries")])
    assert _summary()["spending_cents"] == 7500


def test_reimbursement_lowers_spending_but_is_not_income(client):
    _seed([
        ("2026-01-05", -10000, "Groceries"),
        ("2026-01-06", 4000, "Work Reimbursement"),
        ("2026-01-07", 50000, "Income"),
    ])
    s = _summary()
    assert s["reimbursed_cents"] == 4000
    assert s["spending_cents"] == 6000
    assert s["income_cents"] == 50000
    assert s["net_cents"] == 44000


def test_saved_counts_only_moves_out_of_non_savings_accounts(client):
    _seed([("2026-01-05", -5000, "Savings")], atype="checking")
    _seed([("2026-01-05", 5000, "Savings")], atype="savings")
    assert _summary()["saved_cents"] == 5000


def test_date_range_is_inclusive(client):
    _seed([
        ("2026-01-31", -100, "Groceries"),
        ("2026-02-01", -200, "Groceries"),
        ("2026-02-28", -400, "Groceries"),
        ("2026-03-01", -800, "Groceries"),
    ])
    s = _summary(from_="2026-02-01", to="2026-02-28")
    assert s["spending_cents"] == 600
    assert s["tx_count"] == 2


def test_empty_database_is_all_zero(client):
    s = _summary()
    for key in ("income_cents", "spending_cents", "reimbursed_cents",
                "net_cents", "saved_cents", "tx_count"):
        assert s[key] == 0
```

Run `make test`: the new tests must FAIL (ImportError, `app.summary` does not exist yet). That is the expected red.

Step 2 — implement. Create app/summary.py with `cat > app/summary.py <<'PYEOF' ... PYEOF` and exactly this content:

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
    }
```

Verify: `make test` all green (6 new tests). Touch nothing else. Tick T09a in PROGRESS.md, add one Log line, commit.
