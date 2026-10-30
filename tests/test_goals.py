"""T13 — Goals API + savings + simulate."""
import datetime

from conftest import login

from app import goals as g
from app.db import connect


# ---------- pure functions (fixed `today`, no date.today()) ----------


def test_eta_basic():
    # 100000 / 25000 = exactly 4 months -> first day of month today+4
    eta, months = g.eta(100000, 25000, datetime.date(2026, 1, 15))
    assert months == 4
    assert eta == datetime.date(2026, 5, 1)


def test_eta_ceil():
    # 100001 / 25000 = 4.00004 -> 5 months
    eta, months = g.eta(100001, 25000, datetime.date(2026, 1, 15))
    assert months == 5
    assert eta == datetime.date(2026, 6, 1)


def test_eta_zero_remaining():
    # remaining 0 -> eta is today, 0 months needed
    today = datetime.date(2026, 3, 9)
    eta, months = g.eta(0, 25000, today)
    assert eta == today
    assert months == 0


def test_eta_nonpositive_monthly():
    assert g.eta(100000, 0, datetime.date(2026, 1, 15)) is None
    assert g.eta(100000, -5000, datetime.date(2026, 1, 15)) is None


def test_eta_year_rollover():
    eta, months = g.eta(25000, 25000, datetime.date(2026, 12, 3))
    assert months == 1
    assert eta == datetime.date(2027, 1, 1)


def test_savings_summary():
    # balance 100, allocated 30+20=50 -> unallocated 50
    assert g.savings_summary(100, [30, 20]) == {
        "balance_cents": 100,
        "allocated_cents": 50,
        "unallocated_cents": 50,
    }


def test_savings_summary_empty():
    assert g.savings_summary(100, []) == {
        "balance_cents": 100,
        "allocated_cents": 0,
        "unallocated_cents": 100,
    }


def test_baseline_ignores_current_month():
    # 2 complete months: net 10000 and 30000 -> baseline 20000.
    # Current month has net 999999 but must be ignored.
    by_month = [
        {"month": "2025-11", "income_cents": 10000, "spending_cents": 0},
        {"month": "2025-12", "income_cents": 30000, "spending_cents": 0},
        {"month": "2026-01", "income_cents": 999999, "spending_cents": 0},
    ]
    assert g.baseline_monthly(by_month, 6, datetime.date(2026, 1, 15)) == 20000


def test_baseline_month_limit():
    # 3 complete months 10000/20000/30000, months=2 -> last two -> 25000
    by_month = [
        {"month": "2025-10", "income_cents": 10000, "spending_cents": 0},
        {"month": "2025-11", "income_cents": 20000, "spending_cents": 0},
        {"month": "2025-12", "income_cents": 30000, "spending_cents": 0},
    ]
    assert g.baseline_monthly(by_month, 2, datetime.date(2026, 1, 15)) == 25000


def test_baseline_net_uses_spending():
    # net = income - spending per month
    by_month = [
        {"month": "2025-12", "income_cents": 40000, "spending_cents": 10000},
    ]
    assert g.baseline_monthly(by_month, 6, datetime.date(2026, 1, 15)) == 30000


def test_baseline_no_data():
    assert g.baseline_monthly([], 6, datetime.date(2026, 1, 15)) == 0


def test_baseline_min_zero():
    # average of negative nets -> 0
    by_month = [
        {"month": "2025-12", "income_cents": 10000, "spending_cents": 20000},
    ]
    assert g.baseline_monthly(by_month, 6, datetime.date(2026, 1, 15)) == 0


# ---------- on_track (pure helper used by /simulate) ----------


def test_on_track_true_false_null():
    assert g.on_track(datetime.date(2026, 3, 1), datetime.date(2026, 5, 1)) is True
    assert g.on_track(datetime.date(2026, 7, 1), datetime.date(2026, 5, 1)) is False
    assert g.on_track(datetime.date(2026, 5, 1), None) is None
    assert g.on_track(None, datetime.date(2026, 5, 1)) is None


# ---------- API ----------


def _today():
    return datetime.date.today()


def _first_of_month(d, months):
    """First day of the month `months` after (or before) d's month."""
    m = d.month - 1 + months
    y = d.year + m // 12
    return datetime.date(y, m % 12 + 1, 1)


def _account(client, name, shared, account_type="savings", balance=0):
    r = client.post(
        "/api/accounts",
        json={
            "name": name,
            "institution": "T",
            "type": account_type,
            "shared": shared,
            "opening_balance_cents": balance,
        },
    )
    assert r.status_code == 201
    return r.json()["id"]


def _goal_id(client, scope, name, target, allocated, target_date=None):
    body = {
        "name": name,
        "target_cents": target,
        "allocated_cents": allocated,
        "scope": scope,
    }
    if target_date:
        body["target_date"] = target_date
    r = client.post("/api/goals", json=body)
    assert r.status_code == 201
    return r.json()["id"]


def test_auth_required(client):
    assert client.get("/api/goals").status_code == 401
    assert client.post("/api/goals", json={}).status_code == 401
    assert client.get("/api/savings").status_code == 401
    assert client.get("/api/goals/simulate").status_code == 401


def test_goals_crud_and_item_shape(client, user):
    login(client, user)
    _account(client, "Savings", shared=True, balance=1000000)
    gid = _goal_id(client, "joint", "House", 100000, 10000, "2027-01-01")
    r = client.get("/api/goals", params={"scope": "joint"})
    items = r.json()
    assert len(items) == 1
    item = items[0]
    assert set(item) == {
        "id", "name", "target_cents", "target_date", "allocated_cents",
    }
    assert item == {
        "id": gid,
        "name": "House",
        "target_cents": 100000,
        "target_date": "2027-01-01",
        "allocated_cents": 10000,
    }
    # patch
    r = client.patch(f"/api/goals/{gid}", json={"allocated_cents": 20000, "name": "House big"})
    assert r.status_code == 200
    assert r.json() == {
        "id": gid, "name": "House big", "target_cents": 100000,
        "target_date": "2027-01-01", "allocated_cents": 20000,
    }
    # delete
    assert client.delete(f"/api/goals/{gid}").status_code == 200
    assert client.delete(f"/api/goals/{gid}").status_code == 404
    assert client.get("/api/goals", params={"scope": "joint"}).json() == []


def test_goal_create_validation(client, user):
    login(client, user)
    # combined scope not allowed for create
    r = client.post("/api/goals", json={"name": "x", "target_cents": 5, "scope": "combined"})
    assert r.status_code == 400
    # bogus scope
    r = client.post("/api/goals", json={"name": "x", "target_cents": 5, "scope": "bogus"})
    assert r.status_code == 400
    # negative target
    r = client.post("/api/goals", json={"name": "x", "target_cents": -1, "scope": "joint"})
    assert r.status_code == 422
    # bad target_date
    r = client.post(
        "/api/goals",
        json={"name": "x", "target_cents": 5, "target_date": "13/01/2027", "scope": "joint"},
    )
    assert r.status_code == 400


def test_personal_goal_privacy(client, user, user2):
    login(client, user)
    gid = _goal_id(client, "personal", "Car", 50000, 0)
    # alice sees it in personal and combined
    assert [i["id"] for i in client.get("/api/goals", params={"scope": "personal"}).json()] == [gid]
    assert [i["id"] for i in client.get("/api/goals", params={"scope": "combined"}).json()] == [gid]
    # alice: joint scope excludes personal
    assert client.get("/api/goals", params={"scope": "joint"}).json() == []
    # bob: invisible in every scope, and cannot patch or delete it
    from fastapi.testclient import TestClient

    from app.main import create_app

    c2 = TestClient(create_app())
    login(c2, user2)
    for scope in ("joint", "personal", "combined"):
        assert c2.get("/api/goals", params={"scope": scope}).json() == []
    assert c2.patch(f"/api/goals/{gid}", json={"allocated_cents": 1}).status_code == 404
    assert c2.delete(f"/api/goals/{gid}").status_code == 404
    # still there for alice, untouched
    assert client.get("/api/goals", params={"scope": "personal"}).json()[0]["allocated_cents"] == 0


def test_savings_endpoint(client, user):
    login(client, user)
    _account(client, "Savings", shared=True, balance=100000)
    _account(client, "Personal savings", shared=False, balance=99999)
    _goal_id(client, "joint", "G", 100000, 30000)
    # personal goal of alice must not count in joint scope
    _goal_id(client, "personal", "Mine", 100000, 70000)
    r = client.get("/api/savings", params={"scope": "joint"})
    assert r.status_code == 200
    assert r.json() == {"balance_cents": 100000, "allocated_cents": 30000, "unallocated_cents": 70000}
    # combined includes alice's personal savings balance + personal goal
    r = client.get("/api/savings", params={"scope": "combined"})
    assert r.json() == {"balance_cents": 199999, "allocated_cents": 100000, "unallocated_cents": 99999}


def test_over_allocation_400(client, user):
    login(client, user)
    _account(client, "Savings", shared=True, balance=100000)
    g1 = _goal_id(client, "joint", "G1", 100000, 60000)
    _goal_id(client, "joint", "G2", 100000, 40000)  # total 100000 = balance, ok
    # pushing total above balance -> 400 "over_allocated"
    r = client.patch(f"/api/goals/{g1}", json={"allocated_cents": 61000}, params={"scope": "joint"})
    assert r.status_code == 400
    assert r.json() == {"detail": "over_allocated"}
    # exact fit is allowed
    r = client.patch(f"/api/goals/{g1}", json={"allocated_cents": 60000}, params={"scope": "joint"})
    assert r.status_code == 200
    # personal goals check personal balance only
    _account(client, "My savings", shared=False, balance=50000)
    pg = _goal_id(client, "personal", "PG", 50000, 40000)
    _goal_id(client, "personal", "PG2", 50000, 10000)  # total 50000 = balance, ok
    r = client.patch(f"/api/goals/{pg}", json={"allocated_cents": 41000}, params={"scope": "personal"})
    assert r.status_code == 400
    assert r.json() == {"detail": "over_allocated"}
    r = client.patch(f"/api/goals/{pg}", json={"allocated_cents": 40000}, params={"scope": "personal"})
    assert r.status_code == 200


def test_simulate(client, user):
    login(client, user)
    # savings balance 100000 (start_balance default)
    _account(client, "Savings", shared=True, balance=100000)
    t = _today()
    # 2 complete months of data, net 20000 each
    con = connect()
    try:
        cat_income = con.execute("SELECT id FROM categories WHERE name='Income'").fetchone()["id"]
        cat_expense = con.execute(
            "SELECT id FROM categories WHERE name='Food & Dining'"
        ).fetchone()["id"]
        acct = _account(client, "Joint checking", shared=True, account_type="checking")
        with con:
            for date in (
                _first_of_month(t, -2).replace(day=15),
                _first_of_month(t, -1).replace(day=15),
            ):
                con.execute(
                    "INSERT INTO transactions (account_id, date, description, "
                    "amount_cents, category_id, category_source, dedupe_key) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        acct, date.isoformat(), "PAY " + date.isoformat(), 50000,
                        cat_income, "manual", "inc" + date.isoformat(),
                    ),
                )
                con.execute(
                    "INSERT INTO transactions (account_id, date, description, "
                    "amount_cents, category_id, category_source, dedupe_key) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        acct, date.isoformat(), "GROCERY " + date.isoformat(), -30000,
                        cat_expense, "manual", "exp" + date.isoformat(),
                    ),
                )
            # current-month income must NOT feed the baseline
            cur = t.replace(day=1).isoformat()
            con.execute(
                "INSERT INTO transactions (account_id, date, description, "
                "amount_cents, category_id, category_source, dedupe_key) "
                "VALUES (?,?,?,?,?,?,?)",
                (acct, cur, "CUR PAY", 500000, cat_income, "manual", "inc_cur"),
            )
    finally:
        con.close()
    gid = _goal_id(client, "joint", "House", 100000, 0, _first_of_month(t, 10).isoformat())
    r = client.get("/api/goals/simulate", params={"scope": "joint"})
    assert r.status_code == 200
    body = r.json()
    assert body["monthly_cents_used"] == 20000  # baseline of last complete months only
    goal = body["goals"][0]
    assert goal["id"] == gid
    assert goal["remaining_cents"] == 100000
    assert goal["months_needed"] == 5  # ceil(100000/20000)
    assert goal["eta_date"] == _first_of_month(t, 5).isoformat()
    assert goal["on_track"] is True  # 5 months <= target 10 months out
    # explicit monthly override
    r = client.get("/api/goals/simulate", params={"scope": "joint", "monthly_cents": 25000})
    goal = r.json()["goals"][0]
    assert goal["months_needed"] == 4
    assert goal["eta_date"] == _first_of_month(t, 4).isoformat()
    # zero remaining -> eta today, 0 months
    gid2 = _goal_id(client, "joint", "Done", 1000, 1000)
    r = client.get("/api/goals/simulate", params={"scope": "joint"})
    by_id = {g_["id"]: g_ for g_ in r.json()["goals"]}
    assert by_id[gid2]["remaining_cents"] == 0
    assert by_id[gid2]["months_needed"] == 0
    assert by_id[gid2]["eta_date"] == t.isoformat()
    # personal scope: no personal accounts/data -> monthly 0, no goals
    r = client.get("/api/goals/simulate", params={"scope": "personal"})
    assert r.json() == {"monthly_cents_used": 0, "goals": []}


def test_simulate_on_track_true_false_null(client, user):
    login(client, user)
    _account(client, "Savings", shared=True, balance=0)
    t = _today()
    ok = _goal_id(client, "personal", "A", 100000, 0, _first_of_month(t, 10).isoformat())
    late = _goal_id(client, "personal", "B", 100000, 0, _first_of_month(t, 1).isoformat())
    no_date = _goal_id(client, "personal", "C", 100000, 0)
    r = client.get("/api/goals/simulate", params={"scope": "personal", "monthly_cents": 25000})
    by_id = {g_["id"]: g_ for g_ in r.json()["goals"]}
    assert by_id[ok]["on_track"] is True   # eta (4 months) <= target (10 months)
    assert by_id[late]["on_track"] is False  # eta (4 months) > target (1 month)
    assert by_id[no_date]["on_track"] is None  # no target_date -> null
    # no monthly override and no data -> monthly 0 -> eta null, on_track null
    r = client.get("/api/goals/simulate", params={"scope": "personal"})
    by_id = {g_["id"]: g_ for g_ in r.json()["goals"]}
    assert by_id[ok]["eta_date"] is None
    assert by_id[ok]["on_track"] is None
