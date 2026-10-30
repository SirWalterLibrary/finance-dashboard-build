"""T25 hardening: every /api route needs auth, security headers on /api/*,
and no cross-user scope leaks (bob cannot read or modify alice's personal
accounts, transactions, budgets, goals, or forecast events)."""

import re

from fastapi.routing import _EffectiveRouteContext, _IncludedRouter
from fastapi.testclient import TestClient
import pytest

from conftest import login
from app.db import connect

API_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cache-control": "no-store",
}


@pytest.fixture
def seeded(client, user, user2):
    """Alice has one personal account/tx/budget/goal/event; bob is logged in."""
    con = connect()
    try:
        with con:
            ids = {
                name: con.execute(
                    "SELECT id FROM users WHERE username = ?", (name,)
                ).fetchone()["id"]
                for name in (user, user2)
            }
            cat = con.execute(
                "SELECT id FROM categories WHERE name = 'Groceries'"
            ).fetchone()["id"]
            ids["groceries"] = cat
            cur = con.execute(
                "INSERT INTO accounts (name, institution, type, owner_user_id, "
                "opening_balance_cents, invert_amounts) VALUES "
                "('Alice Savings', '', 'savings', ?, 1000000, 0)",
                (ids[user],),
            )
            ids["acct"] = cur.lastrowid
            cur = con.execute(
                "INSERT INTO transactions (account_id, date, description, "
                "amount_cents, category_id, category_source, dedupe_key) "
                "VALUES (?, '2025-01-15', 'ALICE SHOP', -12345, ?, 'none', ?)",
                (ids["acct"], cat, "t25-alice-tx"),
            )
            ids["tx"] = cur.lastrowid
    finally:
        con.close()
    login(client, user)  # alice creates her personal resources
    ids["budget"] = client.put(
        "/api/budgets",
        json={"scope": "personal", "category_id": cat, "limit_cents": 50000},
    ).json()["id"]
    ids["goal"] = client.post(
        "/api/goals",
        json={"name": "Alice Goal", "target_cents": 500000,
              "scope": "personal", "allocated_cents": 100000},
    ).json()["id"]
    ids["event"] = client.post(
        "/api/forecast/events",
        json={"name": "Alice Event", "direction": "expense",
              "kind": "one_time", "amount_cents": 10000,
              "start_date": "2027-01-01", "scope": "personal"},
    ).json()["id"]
    login(client, user2)  # bob makes the leak-check requests
    return ids


def test_every_api_route_requires_auth(client):
    from app.main import app as root_app

    anon = TestClient(root_app)
    skipped = {"/api/login", "/api/health"}

    def iter_routes(routes):
        for r in routes:
            if isinstance(r, _IncludedRouter):  # FastAPI >= 0.162 lazy routers
                yield from iter_routes(r.effective_candidates())
            elif isinstance(r, _EffectiveRouteContext):
                yield r

    checked = 0
    seen = set()
    for ctx in iter_routes(root_app.routes):
        path, methods = ctx.path, ctx.methods
        if not path.startswith("/api") or path in skipped or not methods:
            continue
        concrete = re.sub(r"\{\w+\}", "1", path)  # valid param values
        for method in sorted(methods):
            if (path, method) in seen:
                continue
            seen.add((path, method))
            kwargs = {"json": {}} if method in ("POST", "PUT", "PATCH") else {}
            r = anon.request(method, concrete, **kwargs)
            assert r.status_code == 401, f"{method} {path} -> {r.status_code}"
            checked += 1
    assert checked >= 25


def test_security_headers_on_api_responses(client, user):
    from app.main import app as root_app

    login(client, user)
    r = client.get("/api/summary")
    assert r.status_code == 200
    assert {k: r.headers[k] for k in API_HEADERS} == API_HEADERS
    anon = TestClient(root_app)  # 401 responses carry the headers too
    r2 = anon.get("/api/summary")
    assert r2.status_code == 401
    assert {k: r2.headers[k] for k in API_HEADERS} == API_HEADERS


def test_personal_data_invisible_in_combined(client, seeded):
    ids = seeded
    accts = client.get("/api/accounts", params={"scope": "combined"}).json()
    assert all(a["name"] != "Alice Savings" for a in accts)
    items = client.get(
        "/api/transactions", params={"scope": "combined", "limit": 500}
    ).json()["items"]
    assert all(i["id"] != ids["tx"] for i in items)
    rows = client.get("/api/budgets", params={"scope": "combined"}).json()
    assert all(r["id"] != ids["budget"] for r in rows)
    goals = client.get("/api/goals", params={"scope": "combined"}).json()
    assert all(g["id"] != ids["goal"] for g in goals)
    events = client.get(
        "/api/forecast/events", params={"scope": "combined"}
    ).json()
    assert all(e["id"] != ids["event"] for e in events)
    assert client.get(f"/api/accounts/{ids['acct']}").status_code == 404


def test_cannot_read_modify_or_delete_personal_data(client, seeded):
    ids = seeded
    assert client.get(f"/api/accounts/{ids['acct']}").status_code == 404
    assert client.put(
        f"/api/accounts/{ids['acct']}/balance",
        json={"current_balance_cents": 1},
    ).status_code == 404
    assert client.delete(f"/api/accounts/{ids['acct']}").status_code == 404
    assert client.patch(
        f"/api/transactions/{ids['tx']}",
        json={"category_id": ids["groceries"]},
    ).status_code == 404
    assert client.delete(f"/api/transactions/{ids['tx']}").status_code == 404
    assert client.delete(
        f"/api/budgets/{ids['budget']}", params={"scope": "combined"}
    ).status_code == 404
    assert client.patch(
        f"/api/goals/{ids['goal']}", params={"scope": "combined"},
        json={"name": "Hacked"},
    ).status_code == 404
    assert client.delete(
        f"/api/goals/{ids['goal']}", params={"scope": "combined"}
    ).status_code == 404
    assert client.patch(
        f"/api/forecast/events/{ids['event']}", params={"scope": "combined"},
        json={"name": "Hacked"},
    ).status_code == 404
    assert client.delete(
        f"/api/forecast/events/{ids['event']}", params={"scope": "combined"}
    ).status_code == 404
    con = connect()
    try:
        assert con.execute(
            "SELECT name FROM goals WHERE id = ?", (ids["goal"],)
        ).fetchone()["name"] == "Alice Goal"
        assert con.execute(
            "SELECT description FROM transactions WHERE id = ?", (ids["tx"],)
        ).fetchone()["description"] == "ALICE SHOP"
        for table in ("accounts", "budgets", "forecast_events"):
            key = {"accounts": "acct", "budgets": "budget",
                   "forecast_events": "event"}[table]
            assert con.execute(
                f"SELECT COUNT(*) FROM {table} WHERE id = ?", (ids[key],)
            ).fetchone()[0] == 1
    finally:
        con.close()
