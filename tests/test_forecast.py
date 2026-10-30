"""T14 — Forecast API: pure project() + events CRUD + projection endpoint."""
import datetime

from conftest import login
from app import forecast as fc
from app.db import connect

TODAY = datetime.date(2026, 10, 1)
ITEM_KEYS = {"id", "name", "group_name", "direction", "kind",
             "amount_cents", "start_date", "end_date", "frequency"}


def ev(**kw):
    d = {"name": "x", "direction": "expense", "kind": "one_time", "amount_cents": 1000,
         "start_date": "2026-10-01", "end_date": None, "frequency": None}
    d.update(kw)
    return d


# ---------- pure project() (fixed `today`, no date.today()) ----------


def test_project_one_time_drop():
    res = fc.project(100000, 0, [ev(amount_cents=4000000, start_date="2029-06-01")],
                    48, TODAY)
    assert len(res["points"]) == 48
    assert res["points"][31] == {"month": "2029-05", "balance_cents": 100000,
                                 "events_cents": 0}
    p = res["points"][32]
    assert (p["month"], p["events_cents"], p["balance_cents"]) == (
        "2029-06", -4000000, -3900000)
    assert res["first_negative_month"] == "2029-06"


def test_project_recurring_monthly():
    res = fc.project(0, 0, [ev(kind="recurring", amount_cents=120000,
                               start_date="2031-01-01", frequency="monthly")],
                    60, TODAY)
    pts = res["points"]
    assert pts[50] == {"month": "2030-12", "balance_cents": 0, "events_cents": 0}
    assert pts[51] == {"month": "2031-01", "balance_cents": -120000,
                       "events_cents": -120000}
    assert pts[52]["events_cents"] == -120000
    assert (pts[59]["month"], pts[59]["balance_cents"]) == ("2031-09", -120000 * 9)
    assert res["first_negative_month"] == "2031-01"


def test_project_recurring_yearly():
    res = fc.project(0, 0, [ev(kind="recurring", amount_cents=30000,
                               start_date="2027-03-01", frequency="yearly")],
                    26, TODAY)
    pts = res["points"]
    idx = {p["month"]: i for i, p in enumerate(pts)}
    assert idx["2027-03"] == 5 and pts[5]["events_cents"] == -30000
    assert pts[6]["events_cents"] == 0
    assert pts[idx["2028-03"]]["events_cents"] == -30000
    assert pts[idx["2028-04"]]["events_cents"] == 0
    assert pts[25]["balance_cents"] == -60000
    assert res["first_negative_month"] == "2027-03"


def test_project_end_date_stops_recurring():
    res = fc.project(50000, 0, [ev(kind="recurring", amount_cents=10000,
                                   start_date="2026-11-01", end_date="2026-12-31",
                                   frequency="monthly")], 6, TODAY)
    pts = res["points"]
    assert pts[0]["month"] == "2026-10" and pts[0]["events_cents"] == 0
    assert pts[1]["events_cents"] == -10000 and pts[2]["events_cents"] == -10000
    assert pts[3]["month"] == "2027-01" and pts[3]["events_cents"] == 0
    assert pts[5]["balance_cents"] == 30000
    assert res["first_negative_month"] is None


def test_project_income_and_past_start():
    res = fc.project(100000, 1000, [
        ev(amount_cents=20000, start_date="2026-05-01"),          # past one_time: ignored
        ev(amount_cents=3000, kind="recurring", start_date="2026-01-01",
           frequency="monthly"),                                   # past: starts at m0
        ev(direction="income", kind="recurring", amount_cents=5000,
           start_date="2026-10-15", frequency="monthly"),
    ], 3, TODAY)
    pts = res["points"]
    assert pts[0] == {"month": "2026-10", "balance_cents": 102000,
                      "events_cents": 2000}
    assert pts[1]["balance_cents"] == 105000
    assert pts[2]["balance_cents"] == 108000
    assert res["first_negative_month"] is None


def test_project_baseline_only():
    res = fc.project(100000, 25000, [], 2, TODAY)
    assert res["points"][0]["balance_cents"] == 100000
    assert res["points"][1]["balance_cents"] == 125000
    assert res["first_negative_month"] is None


# ---------- API ----------


def _post(client, **kw):
    body = {"name": "e", "direction": "expense", "kind": "one_time",
            "amount_cents": 1000, "start_date": "2026-10-01", "scope": "joint"}
    body.update(kw)
    return client.post("/api/forecast/events", json=body)


def test_events_require_auth(client):
    assert client.get("/api/forecast/events").status_code == 401
    assert _post(client).status_code == 401


def test_events_crud(client, user):
    login(client, user)
    r = _post(client, name="Home down payment", amount_cents=4000000,
              start_date="2029-06-01")
    assert r.status_code == 201
    item = r.json()
    assert set(item) == ITEM_KEYS and item["group_name"] == ""
    eid = item["id"]
    assert [i["id"] for i in client.get("/api/forecast/events",
                                        params={"scope": "joint"}).json()] == [eid]
    p = client.patch(f"/api/forecast/events/{eid}",
                     json={"name": "House", "amount_cents": 3000000,
                           "kind": "recurring", "frequency": "yearly"})
    assert p.status_code == 200
    j = p.json()
    assert j["name"] == "House" and j["amount_cents"] == 3000000
    assert j["kind"] == "recurring" and j["frequency"] == "yearly"
    assert client.delete(f"/api/forecast/events/{eid}").json() == {"ok": True}
    assert client.get("/api/forecast/events").json() == []


def test_events_validation(client, user):
    login(client, user)
    assert _post(client, kind="recurring").status_code == 400
    r = _post(client, frequency="monthly", end_date="2030-01-01")  # one_time ignores
    assert r.status_code == 201
    assert r.json()["frequency"] is None and r.json()["end_date"] is None
    assert _post(client, direction="both").status_code == 422
    assert _post(client, kind="recurring", frequency="weekly").status_code == 422
    assert _post(client, start_date="2026-13-01").status_code == 400
    assert _post(client, kind="recurring", frequency="monthly",
                 end_date="2026-02-30").status_code == 400
    assert _post(client, amount_cents=-5).status_code == 422
    assert _post(client, scope="combined").status_code == 400


def test_projection_defaults_and_override(client, user):
    login(client, user)
    con = connect()
    with con:
        con.execute("INSERT INTO accounts (name, type, owner_user_id, "
                    "opening_balance_cents) VALUES ('sav','savings',NULL,1000000)")
    con.close()
    assert _post(client, name="Home", amount_cents=4000000,
                 start_date="2029-06-01").status_code == 201
    j = client.get("/api/forecast/projection",
                   params={"scope": "joint", "months": 48}).json()
    assert set(j) == {"baseline_monthly_cents", "start_balance_cents",
                      "points", "first_negative_month"}
    assert j["start_balance_cents"] == 1000000 and j["baseline_monthly_cents"] == 0
    assert j["first_negative_month"] == "2029-06"
    pts = j["points"]
    assert pts[31] == {"month": "2029-05", "balance_cents": 1000000,
                       "events_cents": 0}
    assert (pts[32]["balance_cents"], pts[32]["events_cents"]) == (-3000000, -4000000)
    # query overrides win; default scope is joint
    j2 = client.get("/api/forecast/projection",
                    params={"months": 12, "monthly_cents": 100000,
                            "start_balance_cents": 5000}).json()
    assert j2["start_balance_cents"] == 5000
    assert j2["baseline_monthly_cents"] == 100000
    assert j2["points"][0]["balance_cents"] == 5000
    assert client.get("/api/forecast/projection",
                      params={"scope": "bogus"}).status_code == 400


def test_projection_baseline_from_tx(client, user):
    login(client, user)
    con = connect()
    inc = con.execute("SELECT id FROM categories WHERE name='Income'").fetchone()[0]
    exp = con.execute("SELECT id FROM categories WHERE name='Groceries'").fetchone()[0]
    with con:
        con.execute("INSERT INTO accounts (name, type) VALUES ('chk','checking')")
        acct = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        for date, cat, amt in [("2026-07-05", inc, 200000),
                               ("2026-08-05", inc, 200000),
                               ("2026-08-09", exp, -100000),
                               ("2026-10-05", inc, 999999)]:  # current month excluded
            con.execute(
                "INSERT INTO transactions (account_id, date, description, "
                "amount_cents, category_id, dedupe_key) VALUES (?,?,?,?,?,?)",
                (acct, date, "T", amt, cat, f"k{date}{amt}"))
    con.close()
    # nets: 2026-07 -> 200000, 2026-08 -> 100000, avg 150000
    j = client.get("/api/forecast/projection",
                   params={"scope": "joint", "months": 12}).json()
    assert j["baseline_monthly_cents"] == 150000 and j["start_balance_cents"] == 0


def test_projection_and_events_privacy(client, user, user2):
    login(client, user2)
    r = _post(client, name="mine", amount_cents=999999, start_date="2026-10-01",
              scope="personal")
    assert r.status_code == 201
    eid = r.json()["id"]
    b = client.get("/api/forecast/projection",
                   params={"scope": "personal", "months": 3}).json()
    assert b["points"][0]["events_cents"] == -999999
    # alice: invisible in every scope, no CRUD access
    login(client, user)
    for scope in ("joint", "personal", "combined"):
        j = client.get("/api/forecast/projection",
                       params={"scope": scope, "months": 3}).json()
        assert all(p["events_cents"] == 0 for p in j["points"])
    assert client.get("/api/forecast/events",
                      params={"scope": "combined"}).json() == []
    assert client.patch(f"/api/forecast/events/{eid}",
                        json={"name": "hack"}).status_code == 404
    assert client.delete(f"/api/forecast/events/{eid}").status_code == 404
    # bob can still see it
    login(client, user2)
    lst = client.get("/api/forecast/events", params={"scope": "personal"}).json()
    assert [i["id"] for i in lst] == [eid]
