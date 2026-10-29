"""Auth endpoints: login, logout, current user."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from .. import auth, config, db
from ..auth import current_user

router = APIRouter(prefix="/api")


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response):
    client_ip = request.client.host if request.client else "unknown"
    row = None
    con = db.connect()
    try:
        row = con.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (body.username,),
        ).fetchone()
    finally:
        con.close()
    if row is None or not auth.verify_password(body.password, row["password_hash"]):
        auth._bump_failure(client_ip)  # raises 429 past the limit
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = auth.create_session(row["id"])
    auth.reset_failures(client_ip)
    response.set_cookie(
        auth.SESSION_COOKIE,
        token,
        max_age=auth.SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=config.get("COOKIE_SECURE", "0") == "1",
    )
    return {"ok": True}


@router.post("/logout")
def logout(
    request: Request, response: Response, user: dict = Depends(current_user)
):
    token = request.cookies.get(auth.SESSION_COOKIE, "")
    con = db.connect()
    try:
        with con:
            con.execute("DELETE FROM sessions WHERE token = ?", (token,))
    finally:
        con.close()
    response.delete_cookie(auth.SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return {"id": user["id"], "username": user["username"]}
