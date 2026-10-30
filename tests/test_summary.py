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
