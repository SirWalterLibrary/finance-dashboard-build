import json
from pathlib import Path

import pytest

SEED_DIR = Path(__file__).parent.parent / "app" / "seed"
TABLES = {
    "users", "sessions", "accounts", "categories", "transactions",
    "rules", "budgets", "goals", "forecast_events",
}


@pytest.fixture
def dbmod(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    import app.db as dbmod
    dbmod.init_db()
    return dbmod


def test_all_nine_tables_exist(dbmod):
    con = dbmod.connect()
    try:
        names = {r["name"] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()
    assert TABLES <= names
    assert len(TABLES) == 9


def test_seed_counts_match_json(dbmod):
    cats = json.loads((SEED_DIR / "categories.json").read_text())
    rules = json.loads((SEED_DIR / "rules.json").read_text())
    con = dbmod.connect()
    try:
        assert con.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"] == len(cats)
        assert con.execute("SELECT COUNT(*) AS c FROM rules").fetchone()["c"] == len(rules)
        # every category row matches its seed entry (incl. description)
        rows = {r["name"]: r for r in con.execute("SELECT * FROM categories")}
        for c in cats:
            assert rows[c["name"]]["kind"] == c["kind"]
            assert rows[c["name"]]["color"] == c["color"]
            assert rows[c["name"]]["description"] == c["description"]
        # every rule row matches: keyword, category name -> id, optional bounds
        ids = {r["name"]: r["id"] for r in con.execute("SELECT id, name FROM categories")}
        expected = sorted(
            (r["keyword"], ids[r["category"]], r.get("min_cents"), r.get("max_cents"))
            for r in rules
        )
        actual = sorted(
            (r["keyword"], r["category_id"], r["min_cents"], r["max_cents"])
            for r in con.execute("SELECT keyword, category_id, min_cents, max_cents FROM rules")
        )
        assert actual == expected
    finally:
        con.close()


def test_init_db_twice_does_not_duplicate(dbmod):
    dbmod.init_db()  # second call must be a no-op
    cats = json.loads((SEED_DIR / "categories.json").read_text())
    rules = json.loads((SEED_DIR / "rules.json").read_text())
    con = dbmod.connect()
    try:
        assert con.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"] == len(cats)
        assert con.execute("SELECT COUNT(*) AS c FROM rules").fetchone()["c"] == len(rules)
    finally:
        con.close()


def test_uncategorized_is_expense(dbmod):
    con = dbmod.connect()
    try:
        row = con.execute(
            "SELECT kind FROM categories WHERE name = 'Uncategorized'"
        ).fetchone()
    finally:
        con.close()
    assert row is not None
    assert row["kind"] == "expense"


def test_create_app_seeds_database(client):
    # client fixture runs create_app(), which must initialize the DB
    import app.db as dbmod

    cats = json.loads((SEED_DIR / "categories.json").read_text())
    con = dbmod.connect()
    try:
        assert con.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"] == len(cats)
    finally:
        con.close()
