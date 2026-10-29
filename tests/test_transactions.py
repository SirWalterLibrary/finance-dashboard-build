"""T06: GET/PATCH/DELETE /api/transactions."""
import pytest

ITEM_KEYS = {
    "id", "date", "description", "amount_cents", "account_id",
    "account_name", "category_id", "category_name", "category_color",
    "category_source", "category_confidence", "suggested_keyword",
}


@pytest.fixture(autouse=True)
def clean_failures():
    import app.auth as auth

    auth._failures.clear()
    yield
    auth._failures.clear()


def _setup(client):
    from conftest import make_user, login

    make_user(client, "alice")
    make_user(client, "bob")
    login(client, "alice")


def _acct(client, name, shared=False):
    res = client.post(
        "/api/accounts", json={"name": name, "type": "checking", "shared": shared}
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _cat(name):
    from app.db import connect

    con = connect()
    try:
        return con.execute(
            "SELECT id FROM categories WHERE name = ?", (name,)
        ).fetchone()["id"]
    finally:
        con.close()


def _add_tx(account_id, amount_cents, date="2026-01-15", desc="deposit",
            category="Savings", source="none", n=0):
    from app.db import connect

    con = connect()
    try:
        cat = _cat(category)
        with con:
            con.execute(
                "INSERT INTO transactions "
                "(account_id, date, description, amount_cents, category_id, "
                "category_source, dedupe_key) VALUES (?,?,?,?,?,?,?)",
                (account_id, date, desc, amount_cents, cat, source,
                 f"{date}|{amount_cents}|{desc}|{n}"),
            )
            return con.execute(
                "SELECT id FROM transactions ORDER BY id DESC LIMIT 1"
            ).fetchone()["id"]
    finally:
        con.close()


def test_requires_auth(client):
    assert client.get("/api/transactions").status_code == 401


def test_list_shape_order_total(client):
    _setup(client)
    a = _acct(client, "House", shared=True)
    _add_tx(a, -1000, date="2026-01-10", desc="Old Shop", n=0)
    _add_tx(a, -2000, date="2026-01-20", desc="New Shop A", n=1)
    _add_tx(a, 500, date="2026-01-20", desc="Paycheck", n=2, category="Income")

    res = client.get("/api/transactions")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 3
    items = body["items"]
    # date DESC, ties broken by id DESC (later insert first)
    assert [i["date"] for i in items] == ["2026-01-20", "2026-01-20", "2026-01-10"]
    assert items[0]["description"] == "Paycheck"
    assert items[1]["description"] == "New Shop A"

    item = items[2]
    assert set(item) == ITEM_KEYS
    assert item["amount_cents"] == -1000
    assert item["account_name"] == "House"
    assert item["category_name"] == "Savings"
    assert item["category_color"] == "#1565c0"
    assert item["category_source"] == "none"
    assert item["category_confidence"] is None
    assert item["suggested_keyword"] == ""


def test_filters(client):
    _setup(client)
    a = _acct(client, "House", shared=True)
    b = _acct(client, "Side", shared=True)
    t_a1 = _add_tx(a, -3818, date="2026-01-05", desc="Sams Club run", n=0)
    t_a2 = _add_tx(a, -2528, date="2026-01-15", desc="Kwik Trip fuel", n=1,
                   category="Transport")
    t_b1 = _add_tx(b, 10000, date="2026-01-10", desc="Salary", n=0, category="Income")
    t_r = _add_tx(a, -700, date="2026-01-12", desc="Rule hit", n=3, source="rule")

    def ids(res):
        return [i["id"] for i in res.json()["items"]]

    # account_id (date DESC, id DESC)
    assert ids(client.get(f"/api/transactions?account_id={a}")) == [t_a2, t_r, t_a1]
    assert ids(client.get(f"/api/transactions?account_id={b}")) == [t_b1]
    # category_id
    assert ids(client.get(f"/api/transactions?category_id={_cat('Transport')}")) == [t_a2]
    # q: case-insensitive substring
    assert ids(client.get("/api/transactions?q=sams")) == [t_a1]
    assert ids(client.get("/api/transactions?q=SAMS")) == [t_a1]
    assert ids(client.get("/api/transactions?q=zorblatt")) == []
    # from / to (inclusive): only t_b1 (01-10) and t_r (01-12) fall inside
    assert ids(client.get("/api/transactions?from=2026-01-06&to=2026-01-14")) == [t_r, t_b1]
    assert len(ids(client.get("/api/transactions?from=2026-01-05"))) == 4
    # direction
    assert [i["amount_cents"] for i in
            client.get("/api/transactions?direction=in").json()["items"]] == [10000]
    assert sorted(i["amount_cents"] for i in
                  client.get("/api/transactions?direction=out").json()["items"]) == [-3818, -2528, -700]
    assert client.get("/api/transactions?direction=side").status_code == 400
    # source
    assert ids(client.get("/api/transactions?source=rule")) == [t_r]
    none_ids = set(ids(client.get("/api/transactions?source=none")))
    assert {t_a1, t_a2, t_b1} <= none_ids and t_r not in none_ids
    assert client.get("/api/transactions?source=magic").status_code == 400


def test_pagination_total(client):
    _setup(client)
    a = _acct(client, "House", shared=True)
    for n in range(7):
        _add_tx(a, -100 - n, date="2026-02-01", desc=f"pay {n}", n=n)

    body = client.get("/api/transactions").json()
    assert body["total"] == 7 and len(body["items"]) == 7

    p1 = client.get("/api/transactions?limit=3&offset=0").json()
    p2 = client.get("/api/transactions?limit=3&offset=3").json()
    p3 = client.get("/api/transactions?limit=3&offset=6").json()
    assert p1["total"] == p2["total"] == p3["total"] == 7
    assert len(p1["items"]) == 3 and len(p2["items"]) == 3 and len(p3["items"]) == 1
    all_ids = [i["id"] for i in p1["items"]] + [i["id"] for i in p2["items"]] \
        + [i["id"] for i in p3["items"]]
    assert len(set(all_ids)) == 7  # pages don't overlap

    assert client.get("/api/transactions?limit=3&offset=10").json()["items"] == []


def test_scope_visibility(client):
    _setup(client)
    joint = _acct(client, "House", shared=True)
    mine = _acct(client, "A Pouch", shared=False)
    t_j = _add_tx(joint, -100, date="2026-01-01", desc="joint tx", n=0)
    t_p = _add_tx(mine, -200, date="2026-01-02", desc="personal tx", n=1)

    def ids(scope=None):
        url = "/api/transactions" + (f"?scope={scope}" if scope else "")
        return {i["id"] for i in client.get(url).json()["items"]}

    # alice
    assert ids("joint") == {t_j}
    assert ids("personal") == {t_p}
    assert ids("combined") == {t_j, t_p}

    from conftest import login

    login(client, "bob")
    assert t_p not in ids("combined")  # no leak via combined
    assert t_p not in ids("personal")
    assert t_j in ids("joint")
    assert client.get("/api/transactions?scope=bogus").status_code == 400


def test_default_scope_is_joint(client):
    _setup(client)
    joint = _acct(client, "House", shared=True)
    mine = _acct(client, "A Pouch", shared=False)
    t_j = _add_tx(joint, -100, date="2026-01-01", desc="joint tx", n=0)
    t_p = _add_tx(mine, -200, date="2026-01-02", desc="personal tx", n=1)

    def ids():
        return {i["id"] for i in client.get("/api/transactions").json()["items"]}

    # no scope param -> default joint; personal accounts never leak
    assert ids() == {t_j}

    from conftest import login

    login(client, "bob")
    assert ids() == {t_j}


def test_from_to_must_be_iso_date(client):
    _setup(client)
    a = _acct(client, "House", shared=True)
    t = _add_tx(a, -100, date="2026-06-15", desc="mid year", n=0)

    assert client.get("/api/transactions?from=banana").status_code == 400
    assert client.get("/api/transactions?to=banana").status_code == 400
    res = client.get("/api/transactions?from=2026-01-01&to=2026-12-31")
    assert res.status_code == 200, res.text
    assert {i["id"] for i in res.json()["items"]} == {t}


def test_patch_sets_manual(client):
    _setup(client)
    a = _acct(client, "House", shared=True)
    t = _add_tx(a, -500, date="2026-01-15", desc="mystery", n=0)
    groceries = _cat("Groceries")

    res = client.patch(f"/api/transactions/{t}", json={"category_id": groceries})
    assert res.status_code == 200, res.text
    item = res.json()
    assert set(item) == ITEM_KEYS
    assert item["id"] == t
    assert item["category_id"] == groceries
    assert item["category_name"] == "Groceries"
    assert item["category_source"] == "manual"

    me = next(i for i in client.get("/api/transactions").json()["items"] if i["id"] == t)
    assert me["category_name"] == "Groceries" and me["category_source"] == "manual"

    assert client.patch("/api/transactions/99999", json={"category_id": groceries}).status_code == 404
    assert client.patch(f"/api/transactions/{t}", json={"category_id": 99999}).status_code == 404
    assert client.patch(f"/api/transactions/{t}", json={}).status_code == 422


def test_delete(client):
    _setup(client)
    a = _acct(client, "House", shared=True)
    t = _add_tx(a, -500, date="2026-01-15", desc="to nuke", n=0)
    assert client.get("/api/transactions").json()["total"] == 1
    assert client.delete(f"/api/transactions/{t}").status_code == 200
    assert client.get("/api/transactions").json()["total"] == 0
    assert client.delete(f"/api/transactions/{t}").status_code == 404
    assert client.delete("/api/transactions/99999").status_code == 404


def test_other_user_tx_404(client):
    _setup(client)
    mine = _acct(client, "A Pouch", shared=False)
    t = _add_tx(mine, -500, date="2026-01-15", desc="alice only", n=0)

    from conftest import login

    login(client, "bob")
    assert client.patch(f"/api/transactions/{t}",
                        json={"category_id": _cat("Groceries")}).status_code == 404
    assert client.delete(f"/api/transactions/{t}").status_code == 404

    # row untouched, and invisible to bob in every scope
    from app.db import connect

    con = connect()
    try:
        row = con.execute(
            "SELECT category_source, description FROM transactions WHERE id = ?",
            (t,),
        ).fetchone()
    finally:
        con.close()
    assert row is not None
    assert row["category_source"] == "none" and row["description"] == "alice only"
    for s in ("joint", "personal", "combined"):
        assert all(i["id"] != t for i in
                   client.get(f"/api/transactions?scope={s}").json()["items"])
