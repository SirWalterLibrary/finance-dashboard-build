import pytest

from conftest import make_user

from app.db import connect
from app.rules import ensure_rule, relabel_similar


def _category_id(name):
    con = connect()
    try:
        return con.execute(
            "SELECT id FROM categories WHERE name = ?", (name,)
        ).fetchone()["id"]
    finally:
        con.close()


def _rows(keyword, category_id):
    con = connect()
    try:
        return con.execute(
            "SELECT id, keyword, category_id, min_cents, max_cents FROM rules "
            "WHERE keyword = ? AND category_id = ?",
            (keyword, category_id),
        ).fetchall()
    finally:
        con.close()


def test_new_keyword_returns_int_and_row_uppercased(client):
    cat = _category_id("Groceries")
    con = connect()
    try:
        with con:
            rid = ensure_rule(con, "kwik trip", cat)
        assert isinstance(rid, int)
    finally:
        con.close()
    rows = _rows("KWIK TRIP", cat)
    assert len(rows) == 1
    assert rows[0]["id"] == rid
    assert rows[0]["keyword"] == "KWIK TRIP"
    assert rows[0]["category_id"] == cat
    assert rows[0]["min_cents"] is None
    assert rows[0]["max_cents"] is None


def test_same_keyword_and_category_returns_same_id(client):
    cat = _category_id("Groceries")
    con = connect()
    try:
        with con:
            rid1 = ensure_rule(con, "kwik trip", cat)
            rid2 = ensure_rule(con, "kwik trip", cat)
    finally:
        con.close()
    assert rid1 == rid2
    assert len(_rows("KWIK TRIP", cat)) == 1


def test_same_keyword_different_category_creates_new_rule(client):
    cat1 = _category_id("Groceries")
    cat2 = _category_id("Food & Dining")
    con = connect()
    try:
        with con:
            rid1 = ensure_rule(con, "kwik trip", cat1)
            rid2 = ensure_rule(con, "kwik trip", cat2)
    finally:
        con.close()
    assert rid2 != rid1
    assert len(_rows("KWIK TRIP", cat1)) == 1
    assert len(_rows("KWIK TRIP", cat2)) == 1


def test_bounded_rule_is_not_a_duplicate(client):
    cat = _category_id("Groceries")
    con = connect()
    try:
        with con:
            bounded = con.execute(
                "INSERT INTO rules (keyword, category_id, min_cents, max_cents) "
                "VALUES ('KWIK TRIP', ?, NULL, 5000)",
                (cat,),
            ).lastrowid
            rid = ensure_rule(con, "kwik trip", cat)
    finally:
        con.close()
    assert rid != bounded
    rows = _rows("KWIK TRIP", cat)
    assert len(rows) == 2
    assert any(r["id"] == bounded and r["max_cents"] == 5000 for r in rows)
    assert any(
        r["id"] == rid and r["min_cents"] is None and r["max_cents"] is None
        for r in rows
    )


def test_blank_keyword_raises_value_error(client):
    cat = _category_id("Groceries")
    con = connect()
    try:
        with pytest.raises(ValueError):
            ensure_rule(con, "   ", cat)
    finally:
        con.close()


def _account(con, owner_user_id):
    cur = con.execute(
        "INSERT INTO accounts (name, institution, type, owner_user_id) "
        "VALUES ('test account', '', 'checking', ?)",
        (owner_user_id,),
    )
    return cur.lastrowid


def _tx(con, account_id, description, category_id, source, seq):
    cur = con.execute(
        "INSERT INTO transactions "
        "(account_id, date, description, amount_cents, category_id, "
        "category_source, dedupe_key) "
        "VALUES (?, '2024-01-10', ?, ?, ?, ?, ?)",
        (account_id, description, -1000, category_id, source, f"t{seq}"),
    )
    return cur.lastrowid


def _state(con, tx_id):
    row = con.execute(
        "SELECT category_id, category_source FROM transactions WHERE id = ?",
        (tx_id,),
    ).fetchone()
    return row["category_id"], row["category_source"]


def test_relabel_similar_updates_none_rule_llm_rows(client):
    alice = make_user(client, "alice")
    unc = _category_id("Uncategorized")
    trans = _category_id("Transport")
    con = connect()
    try:
        with con:
            acct = _account(con, None)
            t1 = _tx(con, acct, "KWIK TRIP #1 SOUTH ST PAUL", unc, "none", 1)
            t2 = _tx(con, acct, "KWIK TRIP #2", trans, "rule", 2)
            t3 = _tx(con, acct, "KWIK TRIP #3", trans, "llm", 3)
        assert relabel_similar(con, alice, "kwik trip", trans, None) == 3
        for t in (t1, t2, t3):
            assert _state(con, t) == (trans, "rule")
    finally:
        con.close()


def test_relabel_similar_manual_row_untouched(client):
    alice = make_user(client, "alice")
    trans = _category_id("Transport")
    con = connect()
    try:
        with con:
            acct = _account(con, None)
            t = _tx(con, acct, "KWIK TRIP #1", trans, "manual", 1)
        assert relabel_similar(con, alice, "KWIK TRIP", trans, None) == 0
        assert _state(con, t) == (trans, "manual")
    finally:
        con.close()


def test_relabel_similar_exclude_id_untouched_and_not_counted(client):
    alice = make_user(client, "alice")
    unc = _category_id("Uncategorized")
    trans = _category_id("Transport")
    con = connect()
    try:
        with con:
            acct = _account(con, None)
            t_keep = _tx(con, acct, "KWIK TRIP #1", unc, "none", 1)
            t_other = _tx(con, acct, "KWIK TRIP #2", unc, "none", 2)
        assert relabel_similar(con, alice, "KWIK TRIP", trans, t_keep) == 1
        assert _state(con, t_keep) == (unc, "none")
        assert _state(con, t_other) == (trans, "rule")
    finally:
        con.close()


def test_relabel_similar_no_keyword_row_untouched(client):
    alice = make_user(client, "alice")
    unc = _category_id("Uncategorized")
    trans = _category_id("Transport")
    con = connect()
    try:
        with con:
            acct = _account(con, None)
            t = _tx(con, acct, "SAMS CLUB FUEL #1", unc, "none", 1)
        assert relabel_similar(con, alice, "KWIK TRIP", trans, None) == 0
        assert _state(con, t) == (unc, "none")
    finally:
        con.close()


def test_relabel_similar_ignores_other_users_personal_account(client):
    alice = make_user(client, "alice")
    bob = make_user(client, "bob")
    unc = _category_id("Uncategorized")
    trans = _category_id("Transport")
    con = connect()
    try:
        with con:
            joint = _account(con, None)
            bob_personal = _account(con, bob)
            t_joint = _tx(con, joint, "KWIK TRIP #1", unc, "none", 1)
            t_bob = _tx(con, bob_personal, "KWIK TRIP #9", unc, "none", 9)
        assert relabel_similar(con, alice, "KWIK TRIP", trans, None) == 1
        assert _state(con, t_joint) == (trans, "rule")
        assert _state(con, t_bob) == (unc, "none")
    finally:
        con.close()


def test_relabel_similar_no_matches_returns_zero(client):
    alice = make_user(client, "alice")
    trans = _category_id("Transport")
    con = connect()
    try:
        with con:
            acct = _account(con, None)
            _tx(con, acct, "SAMS CLUB FUEL #1", _category_id("Uncategorized"), "none", 1)
        assert relabel_similar(con, alice, "KWIK TRIP", trans, None) == 0
    finally:
        con.close()
