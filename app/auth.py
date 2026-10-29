"""Password hashing (scrypt), DB-backed sessions, and the auth dependency."""
import hashlib
import os
import secrets
import time

from fastapi import HTTPException, Request

from . import config, db

SESSION_COOKIE = "sid"
SESSION_DAYS = 30
FAIL_WINDOW = 300  # seconds
FAIL_LIMIT = 5  # max failed logins per IP per window

# Rate limiter state: ip -> [failed_attempts, window_start]
_failures: dict[str, list] = {}


def hash_password(pw: str) -> str:
    """Hash a password with scrypt + random salt; stored as 'salt$hash' hex."""
    salt = os.urandom(16)
    digest = hashlib.scrypt(pw.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + "$" + digest.hex()


def verify_password(pw: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.scrypt(pw.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
        return secrets.compare_digest(digest.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def create_session(user_id: int) -> str:
    """Store a new session token for the user; returns the token."""
    token = secrets.token_urlsafe(32)
    con = db.connect()
    try:
        with con:
            con.execute(
                "INSERT INTO sessions(token, user_id, expires_at)"
                " VALUES (?, ?, datetime('now', '+30 days'))",
                (token, user_id),
            )
    finally:
        con.close()
    return token


def current_user(request: Request) -> dict:
    """FastAPI dependency: resolve the `sid` cookie to a user row, else 401."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="not authenticated")
    con = db.connect()
    try:
        with con:
            con.execute("DELETE FROM sessions WHERE expires_at <= datetime('now')")
            row = con.execute(
                "SELECT u.id, u.username FROM users u"
                " JOIN sessions s ON s.user_id = u.id"
                " WHERE s.token = ?",
                (token,),
            ).fetchone()
    finally:
        con.close()
    if row is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return dict(row)


def _bump_failure(ip: str) -> None:
    """Record a failed login; raise 429 once the limit is hit."""
    now = time.time()
    entry = _failures.get(ip)
    if entry is None or now - entry[1] > FAIL_WINDOW:
        _failures[ip] = [1, now]
        return
    entry[0] += 1
    if entry[0] > FAIL_LIMIT:
        raise HTTPException(status_code=429, detail="too many failed logins")


def reset_failures(ip: str) -> None:
    _failures.pop(ip, None)
