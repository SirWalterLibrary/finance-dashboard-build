import pytest

from app.db import connect
from app.rules import ensure_rule


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
