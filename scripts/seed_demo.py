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
