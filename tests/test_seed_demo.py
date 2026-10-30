import importlib.util
import pathlib

from app.auth import verify_password
from app.db import connect

_path = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "seed_demo.py"
_spec = importlib.util.spec_from_file_location("seed_demo", _path)
seed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed)


def _count(con, table):
    return con.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]


def test_seed_accounts_creates_demo_users_and_accounts(client):
    con = connect()
    try:
        ids = seed.seed_accounts(con)
        assert set(ids) == {"joint_checking", "joint_savings", "personal_checking", "amex"}
        assert _count(con, "users") == 2
        assert _count(con, "accounts") == 4
        demo1 = con.execute("SELECT id, password_hash FROM users WHERE username = 'demo1'").fetchone()
        assert verify_password("demo", demo1["password_hash"])
        acct = {k: con.execute("SELECT * FROM accounts WHERE id = ?", (v,)).fetchone() for k, v in ids.items()}
        assert acct["joint_checking"]["owner_user_id"] is None
        assert acct["joint_savings"]["owner_user_id"] is None
        assert acct["joint_savings"]["type"] == "savings"
        assert acct["personal_checking"]["owner_user_id"] == demo1["id"]
        assert acct["amex"]["owner_user_id"] == demo1["id"]
        assert acct["amex"]["type"] == "credit"
        assert acct["amex"]["invert_amounts"] == 1
    finally:
        con.close()


def test_seed_accounts_is_idempotent(client):
    con = connect()
    try:
        first = seed.seed_accounts(con)
        second = seed.seed_accounts(con)
        assert first == second
        assert _count(con, "users") == 2
        assert _count(con, "accounts") == 4
    finally:
        con.close()


import datetime

TODAY = datetime.date(2026, 10, 30)
ACCOUNT_KEYS = {"joint_checking", "joint_savings", "personal_checking", "amex"}


def test_generate_is_deterministic():
    assert seed.generate(TODAY) == seed.generate(TODAY)


def test_generate_row_shape():
    rows = seed.generate(TODAY)
    assert len(rows) > 150
    for r in rows:
        assert set(r) == {"account", "date", "description", "amount_cents", "category"}
        assert r["account"] in ACCOUNT_KEYS
        assert isinstance(r["amount_cents"], int) and r["amount_cents"] != 0


def test_generate_covers_six_months_and_never_future():
    dates = [r["date"] for r in seed.generate(TODAY)]
    assert min(dates) >= "2026-05-01"
    assert max(dates) <= "2026-10-30"
    assert {d[:7] for d in dates} == {"2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"}


def test_paychecks_are_biweekly():
    days = sorted(
        datetime.date.fromisoformat(r["date"])
        for r in seed.generate(TODAY)
        if r["description"].startswith("DIRECT DEP")
    )
    assert len(days) >= 12
    assert all((b - a).days == 14 for a, b in zip(days, days[1:]))


def test_amex_payment_and_reimbursement_match_the_months_purchases():
    rows = seed.generate(TODAY)
    months = {r["date"][:7] for r in rows}
    for m in months:
        mine = [r for r in rows if r["date"][:7] == m]
        purchases = -sum(r["amount_cents"] for r in mine
                         if r["account"] == "amex" and r["description"] != "AUTOPAY PAYMENT")
        pay = [r["amount_cents"] for r in mine if r["description"] == "AMERICAN EXPRESS ACH PMT"]
        autopay = [r["amount_cents"] for r in mine if r["description"] == "AUTOPAY PAYMENT"]
        reimb = [r["amount_cents"] for r in mine if r["category"] == "Work Reimbursement"]
        assert pay == [-purchases] and autopay == [purchases] and reimb == [purchases]


def test_monthly_savings_transfer_has_both_sides():
    rows = seed.generate(TODAY)
    out = [r for r in rows if r["description"] == "WAY2SAVE TRANSFER" and r["account"] == "joint_checking"]
    inn = [r for r in rows if r["description"] == "WAY2SAVE TRANSFER" and r["account"] == "joint_savings"]
    assert len(out) == len(inn) == 6
    assert all(r["amount_cents"] == -50000 for r in out)
    assert all(r["amount_cents"] == 50000 for r in inn)
