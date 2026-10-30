"""T12 tests: budgets API (month_status + endpoints)."""

import datetime

from conftest import login
from app.db import connect


def _cat_id(name):
    con = connect()
    try:
        return con.execute(
            "SELECT id FROM categories WHERE name = ?", (name,)
        ).fetchone()["id"]
    finally:
        con.close()


def _account(client, name, shared):
    return client.post(
        "/api/accounts", json={"name": name, "type": "checking", "shared": shared}
    ).json()


def _tx(account_id, date, amount_cents, category_id, key):
    con = connect()
    try:
        with con:
            con.execute(
                "INSERT INTO transactions (account_id, date, description, "
                "amount_cents, category_id, category_source, dedupe_key) "
                "VALUES (?,?,?,?,?,'manual',?)",
                (account_id, date, "test merchant", amount_cents, category_id, key),
            )
    finally:
        con.close()


def _get(client, scope="joint", month="2024-01"):
    return client.get(f"/api/budgets?scope={scope}&month={month}").json()


def _item(items, name):
    return next(i for i in items if i["name"] == name)


def test_requires_login(client):
    assert client.get("/api/budgets").status_code == 401
    assert client.put(
        "/api/budgets",
        json={"scope": "joint", "category_id": 1, "limit_cents": 100},
    ).status_code == 401
    assert client.delete("/api/budgets/1").status_code == 401


def test_pct_status_boundaries(client, user):
    login(client, user)
    acct = _account(client, "Joint Checking", True)
    groceries = _cat_id("Groceries")
    assert client.put(
        "/api/budgets",
        json={"scope": "joint", "category_id": groceries, "limit_cents": 10000},
    ).status_code == 200

    _tx(acct["id"], "2024-01-05", -7900, groceries, "b1")
    item = _item(_get(client), "Groceries")
    assert set(item) == {"id", "name", "limit_cents", "spent_cents", "pct", "status"}
    assert item["spent_cents"] == 7900
    assert item["pct"] == 79.0
    assert item["status"] == "ok"

    _tx(acct["id"], "2024-01-06", -100, groceries, "b2")
    item = _item(_get(client), "Groceries")
    assert item["pct"] == 80.0
    assert item["status"] == "warn"

    client.put(
        "/api/budgets", json={"scope": "joint", "category_id": groceries, "limit_cents": 8000}
    )
    item = _item(_get(client), "Groceries")
    assert item["limit_cents"] == 8000
    assert item["pct"] == 100.0
    assert item["status"] == "warn"

    client.put(
        "/api/budgets", json={"scope": "joint", "category_id": groceries, "limit_cents": 10000}
    )
    _tx(acct["id"], "2024-01-07", -2100, groceries, "b3")
    item = _item(_get(client), "Groceries")
    assert item["spent_cents"] == 10100
    assert item["pct"] == 101.0
    assert item["status"] == "over"


def test_upsert_replaces(client, user):
    login(client, user)
    groceries = _cat_id("Groceries")
    r1 = client.put(
        "/api/budgets", json={"scope": "joint", "category_id": groceries, "limit_cents": 5000}
    )
    r2 = client.put(
        "/api/budgets", json={"scope": "joint", "category_id": groceries, "limit_cents": 7000}
    )
    assert r1.status_code == 200 and r2.status_code == 200
    assert r2.json()["id"] == r1.json()["id"]  # same budget row, replaced
    assert r2.json()["limit_cents"] == 7000
    con = connect()
    try:
        n = con.execute(
            "SELECT COUNT(*) AS n FROM budgets "
            "WHERE category_id = ? AND owner_user_id IS NULL",
            (groceries,),
        ).fetchone()["n"]
    finally:
        con.close()
    assert n == 1


def test_spent_without_budget_and_zero_spending(client, user):
    login(client, user)
    acct = _account(client, "Joint Checking", True)
    dining = _cat_id("Food & Dining")
    transport = _cat_id("Transport")
    _tx(acct["id"], "2024-01-10", -4525, dining, "s1")
    rb = client.put(
        "/api/budgets", json={"scope": "joint", "category_id": transport, "limit_cents": 3000}
    )
    items = _get(client)
    assert _item(items, "Food & Dining") == {
        "id": None, "name": "Food & Dining", "limit_cents": 0,
        "spent_cents": 4525, "pct": 0.0, "status": "ok",
    }
    assert _item(items, "Transport") == {
        "id": rb.json()["id"], "name": "Transport", "limit_cents": 3000,
        "spent_cents": 0, "pct": 0.0, "status": "ok",
    }


def test_personal_budget_invisible_to_other_user(client, user, user2):
    login(client, user)
    groceries = _cat_id("Groceries")
    acct = _account(client, "Alice Personal", False)
    r = client.put(
        "/api/budgets", json={"scope": "personal", "category_id": groceries, "limit_cents": 3000}
    )
    budget_id = r.json()["id"]
    _tx(acct["id"], "2024-01-11", -2000, groceries, "p1")

    # bob: no joint budgets, and alice's personal budget must not leak in combined
    login(client, user2)
    assert _get(client, "joint") == []
    assert _get(client, "combined") == []
    assert client.delete(f"/api/budgets/{budget_id}", params={"scope": "personal"}).status_code == 404
    assert client.delete(f"/api/budgets/{budget_id}", params={"scope": "combined"}).status_code == 404

    # alice sees it in personal scope and combined
    login(client, user)
    item = _item(_get(client, "personal"), "Groceries")
    assert item["id"] == budget_id
    assert item["limit_cents"] == 3000
    assert item["spent_cents"] == 2000
    merged = _item(_get(client, "combined"), "Groceries")
    assert merged["id"] == budget_id
    assert merged["limit_cents"] == 3000

    assert client.delete(f"/api/budgets/{budget_id}", params={"scope": "personal"}).status_code == 200
    assert client.delete(f"/api/budgets/{budget_id}").status_code == 404


def test_combined_merges_limits(client, user):
    login(client, user)
    groceries = _cat_id("Groceries")
    joint_acct = _account(client, "Joint Checking", True)
    personal_acct = _account(client, "Alice Personal", False)
    rj = client.put(
        "/api/budgets", json={"scope": "joint", "category_id": groceries, "limit_cents": 5000}
    )
    client.put(
        "/api/budgets", json={"scope": "personal", "category_id": groceries, "limit_cents": 2000}
    )
    _tx(joint_acct["id"], "2024-01-12", -3000, groceries, "m1")
    _tx(personal_acct["id"], "2024-01-13", -1500, groceries, "m2")

    joint_item = _item(_get(client, "joint"), "Groceries")
    assert joint_item["id"] == rj.json()["id"]
    assert joint_item["limit_cents"] == 5000
    assert joint_item["spent_cents"] == 3000

    combined_item = _item(_get(client, "combined"), "Groceries")
    assert combined_item["limit_cents"] == 7000  # 5000 joint + 2000 personal
    assert combined_item["spent_cents"] == 4500
    assert combined_item["id"] == rj.json()["id"]  # joint budget id wins

    personal_item = _item(_get(client, "personal"), "Groceries")
    assert personal_item["limit_cents"] == 2000
    assert personal_item["spent_cents"] == 1500


def test_month_isolation(client, user):
    login(client, user)
    acct = _account(client, "Joint Checking", True)
    groceries = _cat_id("Groceries")
    client.put(
        "/api/budgets", json={"scope": "joint", "category_id": groceries, "limit_cents": 10000}
    )
    _tx(acct["id"], "2024-01-15", -5000, groceries, "mi1")
    _tx(acct["id"], "2024-02-15", -9999, groceries, "mi2")
    jan = _item(_get(client, "joint", "2024-01"), "Groceries")
    feb = _item(_get(client, "joint", "2024-02"), "Groceries")
    assert jan["spent_cents"] == 5000
    assert jan["pct"] == 50.0
    assert jan["status"] == "ok"
    assert feb["spent_cents"] == 9999
    assert feb["status"] == "warn"  # 99.99 rounds to 100.0, still warn


def test_put_validation(client, user):
    login(client, user)
    groceries = _cat_id("Groceries")
    income = _cat_id("Income")
    assert client.put(
        "/api/budgets", json={"scope": "combined", "category_id": groceries, "limit_cents": 100}
    ).status_code == 400
    assert client.put(
        "/api/budgets", json={"scope": "bogus", "category_id": groceries, "limit_cents": 100}
    ).status_code == 400
    assert client.put(
        "/api/budgets", json={"scope": "joint", "category_id": 999999, "limit_cents": 100}
    ).status_code == 404
    assert client.put(
        "/api/budgets", json={"scope": "joint", "category_id": income, "limit_cents": 100}
    ).status_code == 422
    assert client.put(
        "/api/budgets", json={"scope": "joint", "category_id": groceries, "limit_cents": -5}
    ).status_code == 422


def test_bad_params_400_and_default_month(client, user):
    login(client, user)
    assert client.get("/api/budgets?scope=bogus").status_code == 400
    assert client.get("/api/budgets?month=2024-13").status_code == 400
    assert client.get("/api/budgets?month=20241").status_code == 400
    # default month = the current calendar month
    acct = _account(client, "Joint Checking", True)
    groceries = _cat_id("Groceries")
    _tx(acct["id"], datetime.date.today().isoformat(), -1234, groceries, "dm1")
    items = client.get("/api/budgets").json()
    assert _item(items, "Groceries")["spent_cents"] == 1234


def test_delete_joint_budget(client, user, user2):
    login(client, user)
    groceries = _cat_id("Groceries")
    r = client.put(
        "/api/budgets", json={"scope": "joint", "category_id": groceries, "limit_cents": 1000}
    )
    budget_id = r.json()["id"]
    # joint budgets are visible to both owners
    login(client, user2)
    assert client.delete(f"/api/budgets/{budget_id}").status_code == 200
    assert client.delete(f"/api/budgets/{budget_id}").status_code == 404
    assert client.delete("/api/budgets/999999").status_code == 404
