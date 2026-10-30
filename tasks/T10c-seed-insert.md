# T10c — demo seed: insert transactions + `make seed`
Needs: T10b. Self-contained: do NOT read SPEC.md. Do not read any other file; every piece of code you need is below. Pick the simplest reading and do not deliberate.
Files: scripts/seed_demo.py (replace the whole file), tests/test_seed_demo.py (append), PROGRESS.md
Read only: nothing.

`insert_rows` uses the same dedupe key as CSV import (sha1 of date|amount|normalized description|occurrence index), so running the script twice adds nothing. Rows with an explicit category are stored as source `manual`; the rest start as `Uncategorized`/`none` and `apply_rules` categorizes them.

Step 1 — tests FIRST. Append (`cat >> tests/test_seed_demo.py <<'PYEOF' ... PYEOF`, not Edit) exactly this:

```python


from app.rules import apply_rules
from app.summary import build_summary


def _loaded(con):
    ids = seed.seed_accounts(con)
    rows = seed.generate(TODAY)
    added = seed.insert_rows(con, ids, rows)
    return rows, added


def test_insert_rows_twice_adds_nothing_the_second_time(client):
    con = connect()
    try:
        rows, added = _loaded(con)
        assert added == len(rows)
        assert seed.insert_rows(con, seed.seed_accounts(con), rows) == 0
        assert _count(con, "transactions") == len(rows)
    finally:
        con.close()


def test_rules_categorize_the_demo_rows_and_leave_mystery_rows(client):
    con = connect()
    try:
        _loaded(con)
        assert apply_rules(con) > 0

        def sources(like):
            return {
                (r["n"], r["s"])
                for r in con.execute(
                    "SELECT c.name AS n, t.category_source AS s FROM transactions t "
                    "JOIN categories c ON c.id = t.category_id WHERE t.description LIKE ?",
                    (like,),
                )
            }

        assert sources("KWIK TRIP%") == {("Transport", "rule")}
        assert sources("DIRECT DEP%") == {("Income", "rule")}
        assert sources("AMERICAN EXPRESS ACH PMT") == {("Credit Card Payment", "rule")}
        assert sources("EMPLOYER REIMBURSEMENT%") == {("Work Reimbursement", "manual")}
        assert sources("UNKNOWN MERCHANT%") == {("Uncategorized", "none")}
    finally:
        con.close()


def test_joint_summary_of_demo_data_has_income_spending_and_savings(client):
    con = connect()
    try:
        _loaded(con)
        apply_rules(con)
        s = build_summary(con, "(a.owner_user_id IS NULL)", ())
        assert s["income_cents"] > 0
        assert s["spending_cents"] > 0
        assert s["saved_cents"] == 6 * 50000
        assert s["uncategorized_count"] == 6
    finally:
        con.close()
```

Run `make test`: the 3 new tests must FAIL (AttributeError: no `insert_rows`).

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

def insert_rows(con, ids, rows):
    """INSERT OR IGNORE with the same dedupe key as CSV import; returns how many were added."""
    cats = {r["name"]: r["id"] for r in con.execute("SELECT id, name FROM categories")}
    seen = {}
    added = 0
    with con:
        for r in rows:
            norm = norm_desc(r["description"])
            base = (r["account"], r["date"], r["amount_cents"], norm)
            n = seen.get(base, 0)
            seen[base] = n + 1
            key = hashlib.sha1(f"{r['date']}|{r['amount_cents']}|{norm}|{n}".encode()).hexdigest()
            explicit = r["category"]
            cur = con.execute(
                "INSERT OR IGNORE INTO transactions (account_id, date, description, "
                "amount_cents, category_id, category_source, dedupe_key) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ids[r["account"]], r["date"], r["description"], r["amount_cents"],
                 cats[explicit or "Uncategorized"], "manual" if explicit else "none", key),
            )
            added += cur.rowcount
    return added


def main():
    init_db()
    con = connect()
    try:
        ids = seed_accounts(con)
        added = insert_rows(con, ids, generate(datetime.date.today()))
        categorized = apply_rules(con)
    finally:
        con.close()
    print(f"demo data ready: {added} new transactions, {categorized} categorized by rules")
    print("login: demo1 / demo   (demo2 / demo is the second user)")


if __name__ == "__main__":
    main()
```

Step 3 — run it for real (do NOT start the web server): `make seed` and then `make seed` again. The first run prints `170`-ish new transactions (the exact number depends on today's date); the second must print `0 new transactions, 0 categorized by rules`. If `data/dev.db` already contains demo data from an earlier run, the first run may print 0; that is fine.

Verify: `make test` all green (3 new tests, 8 earlier ones still pass). Touch nothing else.
PROGRESS.md: tick T10c, add one Log line, and add this line under `## User Checks`:
`- T10 (backend milestone): run `make seed && make dev`, then `curl -c c.txt -XPOST localhost:8000/api/login -H 'content-type: application/json' -d '{"username":"demo1","password":"demo"}'` and `curl -b c.txt localhost:8000/api/summary` and eyeball the numbers: income and spending are non-zero, `uncategorized_count` is small.`
Commit.
