from conftest import make_user, login

KINDS = ("income", "expense", "transfer", "savings", "reimbursement")


def _keys(body):
    return set(body.keys())


def test_requires_login(client):
    assert client.get("/api/categories").status_code == 401
    assert client.post("/api/categories", json={"name": "X", "kind": "expense"}).status_code == 401
    assert client.patch("/api/categories/1", json={"name": "X"}).status_code == 401
    assert client.delete("/api/categories/1").status_code == 401


def test_list_seeded_categories(client):
    make_user(client, "alice")
    login(client, "alice")
    res = client.get("/api/categories")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 21
    names = [c["name"] for c in items]
    assert "Uncategorized" in names
    assert names == sorted(names)  # ordered by name
    for c in items:
        assert _keys(c) == {"id", "name", "kind", "color", "description"}
        assert c["kind"] in KINDS


def test_create_patch_delete_happy_path(client):
    make_user(client, "alice")
    login(client, "alice")
    # create with defaults
    res = client.post("/api/categories", json={"name": "Coffee", "kind": "expense"})
    assert res.status_code == 201
    body = res.json()
    assert _keys(body) == {"id", "name", "kind", "color", "description"}
    assert body["name"] == "Coffee"
    assert body["kind"] == "expense"
    assert body["color"] == "#888888"
    assert body["description"] == ""
    cid = body["id"]
    # create with color/description
    res = client.post(
        "/api/categories",
        json={"name": "Airfare", "kind": "expense",
              "color": "#ff0000", "description": "flights"},
    )
    assert res.status_code == 201
    assert res.json()["color"] == "#ff0000"
    assert res.json()["description"] == "flights"
    # duplicate name -> 409 (new name and seeded name)
    assert client.post("/api/categories", json={"name": "Coffee", "kind": "income"}).status_code == 409
    assert client.post("/api/categories", json={"name": "Income", "kind": "expense"}).status_code == 409
    # bad kind -> 422, blank name -> 422, missing kind -> 422
    assert client.post("/api/categories", json={"name": "X", "kind": "nope"}).status_code == 422
    assert client.post("/api/categories", json={"name": "  ", "kind": "expense"}).status_code == 422
    assert client.post("/api/categories", json={"name": "X"}).status_code == 422

    # patch: rename
    res = client.patch(f"/api/categories/{cid}", json={"name": "Coffee Shop"})
    assert res.status_code == 200
    assert res.json()["name"] == "Coffee Shop"
    # patch: other fields, partial
    res = client.patch(
        f"/api/categories/{cid}",
        json={"kind": "savings", "color": "#00ff00", "description": "cafe"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Coffee Shop"
    assert body["kind"] == "savings"
    assert body["color"] == "#00ff00"
    assert body["description"] == "cafe"
    # patch: bad kind -> 422
    assert client.patch(f"/api/categories/{cid}", json={"kind": "nope"}).status_code == 422
    # patch: duplicate name -> 409 (rename over an existing category)
    airfare_id = client.get("/api/categories").json()
    airfare_id = [c for c in airfare_id if c["name"] == "Airfare"][0]["id"]
    assert client.patch(f"/api/categories/{cid}", json={"name": "Airfare"}).status_code == 409
    # patch: unknown id -> 404
    assert client.patch("/api/categories/99999", json={"name": "Nope"}).status_code == 404
    # renaming the category named Uncategorized -> 409
    unc_id = [c for c in client.get("/api/categories").json() if c["name"] == "Uncategorized"][0]["id"]
    assert client.patch(f"/api/categories/{unc_id}", json={"name": "Other"}).status_code == 409
    assert [c for c in client.get("/api/categories").json() if c["id"] == unc_id][0]["name"] == "Uncategorized"

    # delete
    res = client.delete(f"/api/categories/{cid}")
    assert res.status_code == 200
    assert res.json() == {"ok": True}
    names = [c["name"] for c in client.get("/api/categories").json()]
    assert "Coffee Shop" not in names
    # delete again / unknown id -> 404
    assert client.delete(f"/api/categories/{cid}").status_code == 404
    assert client.delete("/api/categories/99999").status_code == 404


def _add_tx_with_category(client, account_id, category_id):
    from app.db import connect

    con = connect()
    try:
        with con:
            con.execute(
                "INSERT INTO transactions "
                "(account_id, date, description, amount_cents, category_id, "
                "dedupe_key) VALUES (?,?,?,?,?,?)",
                (account_id, "2026-02-01", "plain sql tx", -500, category_id,
                 "2026-02-01|used-cat|1"),
            )
    finally:
        con.close()


def test_delete_uncategorized_409(client):
    make_user(client, "alice")
    login(client, "alice")
    unc_id = [c for c in client.get("/api/categories").json() if c["name"] == "Uncategorized"][0]["id"]
    assert client.delete(f"/api/categories/{unc_id}").status_code == 409
    names = [c["name"] for c in client.get("/api/categories").json()]
    assert "Uncategorized" in names


def test_delete_used_category_409(client):
    make_user(client, "alice")
    login(client, "alice")
    acct_id = client.post("/api/accounts", json={"name": "A", "type": "checking"}).json()["id"]
    cat_id = client.post("/api/categories", json={"name": "Used", "kind": "expense"}).json()["id"]
    _add_tx_with_category(client, acct_id, cat_id)
    assert client.delete(f"/api/categories/{cat_id}").status_code == 409
    names = [c["name"] for c in client.get("/api/categories").json()]
    assert "Used" in names


def test_delete_removes_rules_cascade(client):
    from app.db import connect

    make_user(client, "alice")
    login(client, "alice")
    cat_id = client.post("/api/categories", json={"name": "HasRule", "kind": "expense"}).json()["id"]
    con = connect()
    try:
        with con:
            con.execute(
                "INSERT INTO rules (keyword, category_id) VALUES (?, ?)",
                ("FOO", cat_id),
            )
        assert client.delete(f"/api/categories/{cat_id}").status_code == 200
        n = con.execute(
            "SELECT COUNT(*) AS c FROM rules WHERE category_id = ?", (cat_id,)
        ).fetchone()["c"]
        assert n == 0  # rule gone via FK cascade
    finally:
        con.close()
