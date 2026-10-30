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
