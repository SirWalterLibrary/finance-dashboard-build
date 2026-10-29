"""Create a dashboard user: python scripts/create_user.py <username>

Prompts for a password twice via getpass (works inside docker:
`docker compose exec web python scripts/create_user.py alice`).
Pass the password via CREATE_USER_PASSWORD to skip the prompt (non-interactive).
"""
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.db as db
from app.auth import hash_password


def create_user(username: str, password: str) -> None:
    con = db.connect()
    try:
        with con:
            con.execute(
                "INSERT INTO users(username, password_hash)"
                " VALUES (?, ?)",
                (username, hash_password(password)),
            )
    finally:
        con.close()


def main(argv: list[str]) -> None:
    if len(argv) != 1 or not argv[0]:
        print("usage: create_user.py <username>", file=sys.stderr)
        raise SystemExit(2)
    username = argv[0]
    password = os.environ.get("CREATE_USER_PASSWORD")
    if password is None:
        password = getpass.getpass(f"Password for {username}: ")
        confirm = getpass.getpass("Repeat password: ")
        if password != confirm:
            print("passwords do not match", file=sys.stderr)
            raise SystemExit(1)
    if len(password) < 8:
        print("password must be at least 8 characters", file=sys.stderr)
        raise SystemExit(1)
    db.init_db()
    try:
        create_user(username, password)
    except Exception:
        print(f"could not create user {username!r} (already exists?)", file=sys.stderr)
        raise SystemExit(1)
    print(f"user {username!r} created")


if __name__ == "__main__":
    main(sys.argv[1:])
