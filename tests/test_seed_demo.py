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
