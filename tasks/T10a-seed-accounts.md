# T10a — demo seed: users and accounts
Needs: T09d. Self-contained: do NOT read SPEC.md. Do not read any other file; every piece of code you need is below. Pick the simplest reading and do not deliberate.
Files: scripts/seed_demo.py (new), tests/test_seed_demo.py (new), PROGRESS.md

All data in this script is FAKE (rule 7). This task only creates 2 demo users (`demo1`, `demo2`, password `demo`) and 4 accounts, safely re-runnable.

Step 0. In PROGRESS.md replace the line `- [ ] T10 Demo seed script` with these three lines and nothing else:
- [ ] T10a demo users + accounts
- [ ] T10b demo transaction generator
- [ ] T10c insert demo transactions + make seed

Step 1 — tests FIRST. Create tests/test_seed_demo.py with `cat > tests/test_seed_demo.py <<'PYEOF' ... PYEOF` and exactly this content:

```python
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
```

Run `make test`: the 2 new tests must FAIL (the script does not exist yet: FileNotFoundError at import).

Step 2 — implement. Create scripts/seed_demo.py with `cat > scripts/seed_demo.py <<'PYEOF' ... PYEOF` and exactly this content:

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

Verify: `make test` all green (2 new tests). Touch nothing else. Tick T10a in PROGRESS.md, add one Log line, commit.
