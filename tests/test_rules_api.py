"""T07f tests: rules API + /api/categorize/run."""

from conftest import make_user, login

from app.db import connect


def _uncat_id(con):
    return con.execute(
        "SELECT id FROM categories WHERE name = 'Uncategorized'"
    ).fetchone()["id"]


def test_requires_login(client):
    assert client.get("/api/rules").status_code == 401
    assert client.post(
        "/api/rules", json={"keyword": "TEST", "category_id": 1}
    ).status_code == 401
    assert client.delete("/api/rules/1").status_code == 401
    assert client.post(
        "/api/categorize/run", json={"scope": "joint"}
    ).status_code == 401


def test_create_list_delete(client, user):
    login(client, user)
    con = connect()
    try:
        cat_id = con.execute(
            "SELECT id FROM categories WHERE name = 'Groceries'"
        ).fetchone()["id"]
    finally:
        con.close()

    r = client.post(
        "/api/rules",
        json={"keyword": "test market", "category_id": cat_id},
    )
    assert r.status_code == 201
    item = r.json()
    assert item["keyword"] == "TEST MARKET"  # stored normalized
    assert item["category_id"] == cat_id
    assert item["category_name"] == "Groceries"
    assert item["min_cents"] is None
    assert item["max_cents"] is None
    assert set(item) == {"id", "keyword", "category_id", "category_name",
                         "min_cents", "max_cents"}

    # appears in the list, which is ordered by keyword
    items = client.get("/api/rules").json()
    assert any(i["id"] == item["id"] for i in items)
    keywords = [i["keyword"] for i in items]
    assert keywords == sorted(keywords)
    assert all(set(i) == set(item) for i in items)

    d = client.delete(f"/api/rules/{item['id']}")
    assert d.status_code == 200
    assert d.json() == {"ok": True}
    assert item["id"] not in [i["id"] for i in client.get("/api/rules").json()]
    assert client.delete(f"/api/rules/{item['id']}").status_code == 404


def test_blank_keyword_422(client, user):
    login(client, user)
    cat = client.get("/api/categories").json()[0]["id"]
    assert client.post(
        "/api/rules", json={"keyword": "", "category_id": cat}
    ).status_code == 422
    assert client.post(
        "/api/rules", json={"keyword": "   ", "category_id": cat}
    ).status_code == 422


def test_min_gt_max_422(client, user):
    login(client, user)
    cat = client.get("/api/categories").json()[0]["id"]
    assert client.post(
        "/api/rules",
        json={"keyword": "X1", "category_id": cat,
              "min_cents": 100, "max_cents": 50},
    ).status_code == 422
    # equal bounds are fine
    r = client.post(
        "/api/rules",
        json={"keyword": "X1", "category_id": cat,
              "min_cents": 100, "max_cents": 100},
    )
    assert r.status_code == 201
    client.delete(f"/api/rules/{r.json()['id']}")


def test_unknown_category_404(client, user):
    login(client, user)
    assert client.post(
        "/api/rules", json={"keyword": "X", "category_id": 999999}
    ).status_code == 404


def _insert_tx(account_id: int, desc: str, amount_cents: int, dedupe_key: str):
    con = connect()
    try:
        with con:
            cur = con.execute(
                "INSERT INTO transactions "
                "(account_id, date, description, amount_cents, "
                " category_id, category_source, dedupe_key) "
                "VALUES (?,?,?, ?, ?, 'none', ?)",
                (account_id, "2024-01-05", desc, amount_cents,
                 _uncat_id(con), dedupe_key),
            )
            tx_id = cur.lastrowid
    finally:
        con.close()
    return tx_id


def test_categorize_run_changes_none_row(client, user):
    login(client, user)
    con = connect()
    try:
        cat_id = con.execute(
            "SELECT id FROM categories WHERE name = 'Transport'"
        ).fetchone()["id"]
    finally:
        con.close()
    acct = client.post(
        "/api/accounts",
        json={"name": "Joint Checking", "type": "checking", "shared": True},
    ).json()
    tx_id = _insert_tx(acct["id"], "SAMS CLUB FUEL #123", 1234, "k1")

    r = client.post("/api/categorize/run", json={"scope": "joint"})
    assert r.status_code == 200
    assert r.json() == {"by_rule": 1, "by_llm": 0, "left": 0,
                        "llm_available": False}

    con = connect()
    try:
        row = con.execute(
            "SELECT category_id, category_source FROM transactions WHERE id = ?",
            (tx_id,),
        ).fetchone()
    finally:
        con.close()
    assert row["category_source"] == "rule"
    assert row["category_id"] == cat_id


def test_categorize_run_scope_isolation(client, user, user2):
    # alice puts a rule-matchable 'none' row in her PERSONAL account
    login(client, user)
    acct = client.post(
        "/api/accounts",
        json={"name": "Alice Personal", "type": "checking", "shared": False},
    ).json()
    tx_id = _insert_tx(acct["id"], "SAMS CLUB FUEL #456", 999, "k2")

    # bob running scope=joint must never touch alice's personal rows
    login(client, user2)
    r = client.post("/api/categorize/run", json={"scope": "joint"})
    assert r.status_code == 200
    body = r.json()
    assert body["by_rule"] == 0
    assert body["left"] == 0
    assert body["llm_available"] is False

    con = connect()
    try:
        row = con.execute(
            "SELECT category_source FROM transactions WHERE id = ?",
            (tx_id,),
        ).fetchone()
    finally:
        con.close()
    assert row["category_source"] == "none"


def test_categorize_run_bad_scope_400(client, user):
    login(client, user)
    assert client.post(
        "/api/categorize/run", json={"scope": "bogus"}
    ).status_code == 400
