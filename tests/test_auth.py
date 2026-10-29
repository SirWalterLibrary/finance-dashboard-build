import time

import pytest


@pytest.fixture(autouse=True)
def clean_failures():
    import app.auth as auth

    auth._failures.clear()
    yield
    auth._failures.clear()


def test_wrong_password_401(client):
    from conftest import make_user

    make_user(client, "alice", "right-pass")
    res = client.post("/api/login", json={"username": "alice", "password": "wrong"})
    assert res.status_code == 401
    assert "sid" not in res.cookies
    assert client.get("/api/me").status_code == 401


def test_right_password_sets_cookie_and_me_works(client):
    from conftest import make_user, login

    make_user(client, "alice", "hunter22")
    login(client, "alice", "hunter22")
    res = client.get("/api/me")
    assert res.status_code == 200
    body = res.json()
    assert body["username"] == "alice"
    assert "id" in body


def test_logout_invalidates_session(client):
    from conftest import make_user, login

    make_user(client, "alice", "hunter22")
    login(client, "alice", "hunter22")
    res = client.post("/api/logout")
    assert res.status_code == 200
    assert client.get("/api/me").status_code == 401


def test_me_without_cookie_401(client):
    assert client.get("/api/me").status_code == 401
    client.cookies.set("sid", "no-such-token")
    assert client.get("/api/me").status_code == 401


def test_sixth_bad_login_429(client):
    from conftest import make_user

    make_user(client, "bob", "right-pass")
    res = None
    for _ in range(6):
        res = client.post("/api/login", json={"username": "bob", "password": "wrong"})
    assert res.status_code == 429
    # the limit is time-boxed, not permanent
    import app.auth as auth

    for key in auth._failures:
        auth._failures[key][1] = time.time() - 301  # expire the window
    assert client.post(
        "/api/login", json={"username": "bob", "password": "wrong"}
    ).status_code == 401


def test_password_hash_roundtrip():
    from app.auth import hash_password, verify_password

    hashed = hash_password("s3cret!")
    assert hashed.count("$") == 1
    assert hashed != "s3cret!"
    assert verify_password("s3cret!", hashed)
    assert not verify_password("s3cret2", hashed)
    assert hash_password("s3cret!") != hash_password("s3cret!")  # random salt


def test_create_session_and_expiry(client):
    from app import auth
    from app.db import connect
    from conftest import make_user

    make_user(client, "alice", "hunter22")
    token = auth.create_session(1)
    client.cookies.set("sid", token)
    assert client.get("/api/me").status_code == 200
    # expired sessions are rejected and pruned
    con = connect()
    try:
        with con:
            con.execute("UPDATE sessions SET expires_at = datetime('now')")
    finally:
        con.close()
    assert client.get("/api/me").status_code == 401
    con = connect()
    try:
        assert con.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"] == 0
    finally:
        con.close()


def test_create_user_script(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "users.db"))
    monkeypatch.setenv("CREATE_USER_PASSWORD", "script-pass-1")
    import app.db as db

    db.init_db()
    import scripts.create_user

    scripts.create_user.main(["alice"])
    from app.auth import verify_password

    con = db.connect()
    try:
        row = con.execute(
            "SELECT username, password_hash FROM users WHERE username = 'alice'"
        ).fetchone()
    finally:
        con.close()
    assert row is not None
    assert verify_password("script-pass-1", row["password_hash"])
