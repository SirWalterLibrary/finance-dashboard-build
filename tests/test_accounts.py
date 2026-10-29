import pytest


def _ids(res):
    return [a["id"] for a in res.json()]


@pytest.fixture(autouse=True)
def clean_failures():
    import app.auth as auth

    auth._failures.clear()
    yield
    auth._failures.clear()


def test_scope_helpers():
    from app import scope

    assert scope.owner_ids("personal", "alice") == ["alice"]
    assert scope.owner_ids("joint", "alice") == [None]
    assert scope.owner_ids("combined", "alice") == [None, "alice"]
    # owner_clause: NULL-safe (sql_fragment, params)
    cases = {
        "personal": ("(owner_user_id = ?)", ("alice",)),
        "joint": ("(owner_user_id IS NULL)", ()),
        "combined": (
            "(owner_user_id IS NULL OR owner_user_id = ?)", ("alice",)
        ),
    }
    for s, expect in cases.items():
        assert scope.owner_clause(s, "alice") == expect
    assert scope.owner_clause("combined", 7, column="a") == (
        "(a IS NULL OR a = ?)", (7,)
    )
    with pytest.raises(ValueError):
        scope.owner_ids("bogus", "alice")
    with pytest.raises(ValueError):
        scope.owner_clause("nope", "alice")


def test_guards(client):
    from conftest import make_user, login

    assert client.get("/api/accounts").status_code == 401
    make_user(client, "alice", "hunter22")
    login(client, "alice", "hunter22")
    assert client.get("/api/accounts?scope=bogus").status_code == 400


def test_personal_account_hidden_from_other_user_in_every_scope(client):
    from conftest import make_user, login

    make_user(client, "alice", "hunter22")
    make_user(client, "bob", "hunter22")
    login(client, "alice", "hunter22")
    res = client.post(
        "/api/accounts", json={"name": "Alice Wallet", "type": "savings"}
    )
    assert res.status_code == 201
    acct_id = res.json()["id"]

    login(client, "bob", "hunter22")
    for s in ("personal", "combined", "joint"):
        res = client.get(f"/api/accounts?scope={s}")
        assert res.status_code == 200
        assert acct_id not in _ids(res), f"leak in scope={s}"
        assert client.get(f"/api/accounts/{acct_id}").status_code == 404

    # DELETE by a non-member must 404 and leave the account intact
    assert client.delete(f"/api/accounts/{acct_id}").status_code == 404
    login(client, "alice", "hunter22")
    assert client.get(f"/api/accounts/{acct_id}").status_code == 200


def test_joint_and_default_scope(client):
    from conftest import make_user, login

    make_user(client, "alice", "hunter22")
    make_user(client, "bob", "hunter22")
    login(client, "alice", "hunter22")
    personal = client.post(
        "/api/accounts",
        json={"name": "P", "type": "savings", "shared": False},
    ).json()["id"]
    res = client.post(
        "/api/accounts",
        json={"name": "House", "type": "checking", "shared": True,
              "opening_balance_cents": 1000},
    )
    assert res.status_code == 201
    body = res.json()
    acct_id = body["id"]
    assert body["shared"] is True
    assert body["balance_cents"] == 1000

    ids = _ids(client.get("/api/accounts"))  # default scope = joint
    assert acct_id in ids and personal not in ids

    login(client, "bob", "hunter22")
    assert acct_id in _ids(client.get("/api/accounts"))
    assert client.get(f"/api/accounts/{acct_id}").status_code == 200
    assert acct_id not in _ids(client.get("/api/accounts?scope=personal"))

    # bob modifies a joint account; alice sees the change
    assert client.put(
        f"/api/accounts/{acct_id}/balance",
        json={"current_balance_cents": 2500},
    ).status_code == 200
    login(client, "alice", "hunter22")
    assert client.get(f"/api/accounts/{acct_id}").json()["balance_cents"] == 2500


def test_post_and_validation(client):
    from conftest import make_user, login

    make_user(client, "alice", "hunter22")
    login(client, "alice", "hunter22")
    res = client.post(
        "/api/accounts",
        json={"name": "Main", "type": "checking", "institution": "Bank A"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["shared"] is False
    assert body["institution"] == "Bank A"
    assert body["type"] == "checking"
    assert body["balance_cents"] == 0
    assert body["tx_count"] == 0
    assert body["invert_amounts"] == 0  # non-credit
    card = client.post(
        "/api/accounts",
        json={"name": "Card", "type": "credit", "opening_balance_cents": -12345},
    ).json()
    assert card["invert_amounts"] == 1  # credit
    assert card["balance_cents"] == -12345
    # validation: missing name 422, invalid type 400, empty name 422
    assert client.post("/api/accounts", json={"type": "checking"}).status_code == 422
    assert client.post("/api/accounts", json={"name": "X", "type": "nope"}).status_code == 400
    assert client.post("/api/accounts", json={"name": "", "type": "checking"}).status_code == 422


def _add_tx(account_id, amount_cents, n=0, date="2026-01-15", desc="deposit"):
    from app.db import connect

    con = connect()
    try:
        cat = con.execute(
            "SELECT id FROM categories WHERE name = 'Savings'"
        ).fetchone()["id"]
        with con:
            con.execute(
                "INSERT INTO transactions "
                "(account_id, date, description, amount_cents, category_id, "
                "dedupe_key) VALUES (?,?,?,?,?,?)",
                (account_id, date, desc, amount_cents, cat,
                 f"{date}|{amount_cents}|{desc}|{n}"),
            )
    finally:
        con.close()


def test_balance_cents_and_put_balance(client):
    from conftest import make_user, login

    make_user(client, "alice", "hunter22")
    login(client, "alice", "hunter22")
    acct_id = client.post("/api/accounts", json={"name": "Wallet", "type": "checking", "opening_balance_cents": 5000}).json()["id"]

    _add_tx(acct_id, 2000)
    res = client.get(f"/api/accounts/{acct_id}")
    assert res.status_code == 200
    assert res.json()["balance_cents"] == 7000
    assert res.json()["tx_count"] == 1

    # PUT balance sets opening so total == given value
    res = client.put(
        f"/api/accounts/{acct_id}/balance",
        json={"current_balance_cents": 9000},
    )
    assert res.status_code == 200
    assert res.json()["balance_cents"] == 9000
    _add_tx(acct_id, 1000, n=1)
    # 10000 only holds if opening became 7000 (9000-2000)
    assert client.get(f"/api/accounts/{acct_id}").json()["balance_cents"] == 10000
    assert client.put(f"/api/accounts/{acct_id}/balance", json={}).status_code == 422


def test_delete(client):
    from conftest import make_user, login

    make_user(client, "alice", "hunter22")
    login(client, "alice", "hunter22")
    acct_id = client.post("/api/accounts", json={"name": "Tmp", "type": "savings"}).json()["id"]
    _add_tx(acct_id, -100)
    assert client.delete(f"/api/accounts/{acct_id}").status_code == 200
    assert client.get(f"/api/accounts/{acct_id}").status_code == 404
