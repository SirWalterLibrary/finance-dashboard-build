# T10b — demo seed: fake transaction generator (pure function)
Needs: T10a. Self-contained: do NOT read SPEC.md. Do not read any other file; every piece of code you need is below. Pick the simplest reading and do not deliberate.
Files: scripts/seed_demo.py (replace the whole file), tests/test_seed_demo.py (append), PROGRESS.md
Read only: nothing.

`generate(today)` returns the FAKE rows for the last six calendar months as plain dicts. It touches no database. Design (already decided): descriptions are chosen so the seed rules categorize most rows; rent, dining and the work reimbursement carry an explicit category; one `UNKNOWN MERCHANT` row per month is left uncategorized on purpose. Each month the AMEX payment, the AMEX autopay credit and the reimbursement deposit all equal that month's AMEX purchases.

Step 1 — tests FIRST. Append (`cat >> tests/test_seed_demo.py <<'PYEOF' ... PYEOF`, not Edit) exactly this:

```python


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
```

Run `make test`: the 6 new tests must FAIL (AttributeError: no `generate`).

Step 2 — implement. Replace scripts/seed_demo.py completely with `cat > scripts/seed_demo.py <<'PYEOF' ... PYEOF` and exactly this content:

```python
"""Demo data (FAKE only, never real transactions).

Run: DB_PATH=data/dev.db python scripts/seed_demo.py   (or `make seed`)
"""
import datetime
import hashlib
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.auth import hash_password
from app.csvparse import norm_desc
from app.db import connect, init_db
from app.rules import apply_rules

# key, name, type, personal-owner?, invert_amounts, opening balance (cents)
ACCOUNTS = [
    ("joint_checking", "Demo Joint Checking", "checking", False, 0, 300000),
    ("joint_savings", "Demo Joint Savings", "savings", False, 0, 1000000),
    ("personal_checking", "Demo Personal Checking", "checking", True, 0, 150000),
    ("amex", "Demo AMEX", "credit", True, 1, 0),
]


def seed_accounts(con):
    """Create users demo1/demo2 and the 4 accounts if missing; returns {key: account_id}."""
    with con:
        for name in ("demo1", "demo2"):
            if con.execute("SELECT 1 FROM users WHERE username = ?", (name,)).fetchone() is None:
                con.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (name, hash_password("demo")),
                )
        demo1 = con.execute("SELECT id FROM users WHERE username = 'demo1'").fetchone()["id"]
        ids = {}
        for key, name, kind, personal, invert, opening in ACCOUNTS:
            row = con.execute("SELECT id FROM accounts WHERE name = ?", (name,)).fetchone()
            if row is None:
                cur = con.execute(
                    "INSERT INTO accounts (name, institution, type, owner_user_id, "
                    "invert_amounts, opening_balance_cents) VALUES (?, 'Demo Bank', ?, ?, ?, ?)",
                    (name, kind, demo1 if personal else None, invert, opening),
                )
                ids[key] = cur.lastrowid
            else:
                ids[key] = row["id"]
    return ids

def _months(today):
    """First day of each of the last six calendar months (current one included), oldest first."""
    out = []
    year, month = today.year, today.month
    for _ in range(6):
        out.append(datetime.date(year, month, 1))
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return out[::-1]


def generate(today):
    """FAKE transactions for the last six calendar months, deterministic, oldest first.

    Each row: {account, date (ISO), description, amount_cents, category}. category is None
    when a seed rule should categorize the row, or a category name set by hand.
    """
    rnd = random.Random(1)
    rows = []

    def add(account, date, desc, cents, category=None):
        if date <= today:
            rows.append({"account": account, "date": date.isoformat(),
                         "description": desc, "amount_cents": cents, "category": category})

    months = _months(today)
    payday = today - datetime.timedelta(days=(today.weekday() - 4) % 7)  # latest Friday
    while payday >= months[0]:
        add("joint_checking", payday, "DIRECT DEP DEMO CORP PAYROLL", 185000)
        payday -= datetime.timedelta(days=14)

    for first in months:
        def day(n):
            return first.replace(day=n)

        add("joint_checking", day(1), "RENT ACH DEMO PROPERTIES", -175000, "Housing")
        add("joint_checking", day(5), "XCEL ENERGY", -rnd.randrange(8000, 12001))
        add("joint_checking", day(10), "QUANTUM FIBER", -6500)
        for n in (4, 11, 18, 25):
            add("joint_checking", day(n), "WM SUPERCENTER #1234", -rnd.randrange(5000, 15001))
        for n in (3, 12, 22):
            add("joint_checking", day(n), "KWIK TRIP #178", -rnd.randrange(3000, 6001))
        for n in (6, 13, 19, 27):
            add("joint_checking", day(n), "LOCAL DINER", -rnd.randrange(1500, 4501), "Food & Dining")
        add("joint_checking", day(15), "UNKNOWN MERCHANT 77", -rnd.randrange(1000, 3001))
        add("joint_checking", day(20), "WAY2SAVE TRANSFER", -50000)
        add("joint_savings", day(20), "WAY2SAVE TRANSFER", 50000)
        add("personal_checking", day(3), "ZELLE TO MAMA", -5000)

        total = 0
        for n in (2, 6, 9, 14, 21):
            desc = rnd.choice(["AMAZON.COM DEMO", "SHELL SERVICE 442", "STEAM PURCHASE", "WAL-MART #556"])
            cents = rnd.randrange(2000, 15001)
            add("amex", day(n), desc, -cents)
            total += cents
        add("personal_checking", day(25), "AMERICAN EXPRESS ACH PMT", -total)
        add("amex", day(25), "AUTOPAY PAYMENT", total)
        add("personal_checking", day(25), "EMPLOYER REIMBURSEMENT DEMO", total, "Work Reimbursement")

    rows.sort(key=lambda r: (r["date"], r["account"], r["description"]))
    return rows

def main():
    init_db()
    con = connect()
    try:
        ids = seed_accounts(con)
    finally:
        con.close()
    print(f"demo users and accounts ready: {sorted(ids)}")


if __name__ == "__main__":
    main()
```

Verify: `make test` all green (6 new tests, the 2 from T10a still pass). Touch nothing else. Tick T10b in PROGRESS.md, add one Log line, commit.
