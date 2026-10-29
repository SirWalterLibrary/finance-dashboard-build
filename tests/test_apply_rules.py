from app.db import connect
from app.rules import apply_rules


def _category_id(name):
    con = connect()
    try:
        return con.execute(
            "SELECT id FROM categories WHERE name = ?", (name,)
        ).fetchone()["id"]
    finally:
        con.close()


def _add_joint():
    con = connect()
    try:
        with con:
            cur = con.execute(
                "INSERT INTO accounts (name, type, owner_user_id) "
                "VALUES ('House', 'checking', NULL)"
            )
        return cur.lastrowid
    finally:
        con.close()


def _add_tx(
    account_id,
    amount_cents,
    desc,
    n=0,
    date="2026-01-15",
    source="none",
    category="Uncategorized",
):
    con = connect()
    try:
        cat = con.execute(
            "SELECT id FROM categories WHERE name = ?", (category,)
        ).fetchone()["id"]
        with con:
            cur = con.execute(
                "INSERT INTO transactions "
                "(account_id, date, description, amount_cents, category_id, "
                "category_source, dedupe_key) VALUES (?,?,?,?,?,?,?)",
                (account_id, date, desc, amount_cents, cat, source,
                 f"{date}|{amount_cents}|{desc}|{n}"),
            )
        return cur.lastrowid
    finally:
        con.close()


def _row(tid):
    con = connect()
    try:
        return con.execute(
            "SELECT category_id, category_source FROM transactions WHERE id = ?",
            (tid,),
        ).fetchone()
    finally:
        con.close()


def test_none_row_becomes_transport_rule(client):
    acct = _add_joint()
    tid = _add_tx(acct, -524, "KWIK TRIP #178 SOUTH ST PAUL")
    con = connect()
    try:
        assert apply_rules(con) == 1
    finally:
        con.close()
    row = _row(tid)
    assert row["category_id"] == _category_id("Transport")
    assert row["category_source"] == "rule"


def test_manual_row_untouched(client):
    acct = _add_joint()
    tid = _add_tx(
        acct, -524, "KWIK TRIP #178 SOUTH ST PAUL",
        source="manual", category="Savings",
    )
    con = connect()
    try:
        assert apply_rules(con) == 0
    finally:
        con.close()
    row = _row(tid)
    assert row["category_id"] == _category_id("Savings")
    assert row["category_source"] == "manual"


def test_tx_ids_only_changes_given_row(client):
    acct = _add_joint()
    id1 = _add_tx(acct, -524, "KWIK TRIP #1 SOUTH ST PAUL")
    id2 = _add_tx(acct, -624, "KWIK TRIP #2 NORTH AVE")
    con = connect()
    try:
        assert apply_rules(con, tx_ids=[id1]) == 1
        assert apply_rules(con, tx_ids=[]) == 0
    finally:
        con.close()
    assert _row(id1)["category_source"] == "rule"
    assert _row(id2)["category_source"] == "none"


def test_no_match_stays_none_uncategorized(client):
    acct = _add_joint()
    tid = _add_tx(acct, -123, "ODD PLACE NOWHERE")
    con = connect()
    try:
        assert apply_rules(con) == 0
    finally:
        con.close()
    row = _row(tid)
    assert row["category_id"] == _category_id("Uncategorized")
    assert row["category_source"] == "none"


def test_second_call_returns_zero(client):
    acct = _add_joint()
    _add_tx(acct, -524, "KWIK TRIP #178 SOUTH ST PAUL")
    con = connect()
    try:
        assert apply_rules(con) == 1
        assert apply_rules(con) == 0
    finally:
        con.close()
