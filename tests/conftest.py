import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from fastapi.testclient import TestClient

    from app.main import create_app

    return TestClient(create_app())


def make_user(client, name, password="password123"):
    """Insert a user directly (no password prompt); returns the user id."""
    from app.auth import hash_password
    from app.db import connect

    con = connect()
    try:
        with con:
            con.execute(
                "INSERT INTO users(username, password_hash) VALUES (?, ?)",
                (name, hash_password(password)),
            )
        return con.execute(
            "SELECT id FROM users WHERE username = ?", (name,)
        ).fetchone()["id"]
    finally:
        con.close()


def login(client, name, password="password123"):
    """Login over the API; returns the response (200 on success)."""
    return client.post(
        "/api/login", json={"username": name, "password": password}
    )


@pytest.fixture
def user(client):
    """First user, pre-created."""
    name = "alice"
    make_user(client, name)
    return name


@pytest.fixture
def user2(client):
    """Second user, pre-created."""
    name = "bob"
    make_user(client, name)
    return name
