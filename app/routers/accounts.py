"""Accounts endpoints (SPEC "Accounts").

Money = integer cents. `scope` (default "joint") controls visibility:
owner_user_id NULL = joint, else that user. DELETE of an account not visible
to the user returns 404 (no combined-scope leaks).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import current_user
from app.db import connect
from app.scope import owner_clause

router = APIRouter(prefix="/api", tags=["accounts"])

TYPES = ("checking", "savings", "credit")


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: str = "checking"
    institution: str = ""
    shared: bool = False
    opening_balance_cents: int = 0


class BalanceIn(BaseModel):
    current_balance_cents: int


def _require_visible(con, account_id: int, user: dict) -> dict:
    """Fetch the account; 404 if missing or the user must not see it."""
    row = con.execute(
        "SELECT * FROM accounts WHERE id = ?", (account_id,)
    ).fetchone()
    if row is None or row["owner_user_id"] not in (None, user["id"]):
        raise HTTPException(404, "account not found")
    return row


def _totals(con, account_id: int) -> tuple:
    """(sum(amount_cents), tx_count) for the account."""
    row = con.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) AS s, COUNT(*) AS c "
        "FROM transactions WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    return (row["s"] or 0), row["c"]


def _view(row: dict, total_cents: int, tx_count: int) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "institution": row["institution"],
        "type": row["type"],
        "shared": row["owner_user_id"] is None,
        "opening_balance_cents": row["opening_balance_cents"],
        "invert_amounts": row["invert_amounts"],
        "balance_cents": row["opening_balance_cents"] + total_cents,
        "tx_count": tx_count,
    }


@router.get("/accounts")
def list_accounts(scope: str = Query("joint"), user: dict = Depends(current_user)):
    try:
        clause, params = owner_clause(scope, user["id"])
    except ValueError:
        raise HTTPException(400, "scope must be personal, joint, or combined")
    con = connect()
    try:
        rows = con.execute(
            f"SELECT * FROM accounts WHERE {clause} ORDER BY name", params
        ).fetchall()
        out = []
        for row in rows:
            total, n = _totals(con, row["id"])
            out.append(_view(row, total, n))
        return out
    finally:
        con.close()


@router.post("/accounts", status_code=201)
def create_account(body: AccountIn, user: dict = Depends(current_user)):
    if body.type not in TYPES:
        raise HTTPException(400, f"type must be one of {', '.join(TYPES)}")
    con = connect()
    try:
        with con:
            cur = con.execute(
                "INSERT INTO accounts "
                "(name, institution, type, owner_user_id, opening_balance_cents, "
                "invert_amounts) VALUES (?,?,?,?,?,?)",
                (
                    body.name,
                    body.institution,
                    body.type,
                    None if body.shared else user["id"],
                    body.opening_balance_cents,
                    1 if body.type == "credit" else 0,
                ),
            )
        row = con.execute(
            "SELECT * FROM accounts WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        total, n = _totals(con, row["id"])
        return _view(row, total, n)
    finally:
        con.close()


@router.get("/accounts/{account_id}")
def get_account(account_id: int, user: dict = Depends(current_user)):
    con = connect()
    try:
        row = _require_visible(con, account_id, user)
        total, n = _totals(con, row["id"])
        return _view(row, total, n)
    finally:
        con.close()


@router.put("/accounts/{account_id}/balance")
def set_balance(account_id: int, body: BalanceIn, user: dict = Depends(current_user)):
    con = connect()
    try:
        _require_visible(con, account_id, user)
        total, _ = _totals(con, account_id)
        opening = body.current_balance_cents - total
        with con:
            con.execute(
                "UPDATE accounts SET opening_balance_cents = ? WHERE id = ?",
                (opening, account_id),
            )
        row = con.execute(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        _, n = _totals(con, row["id"])
        return _view(row, total, n)
    finally:
        con.close()


@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, user: dict = Depends(current_user)):
    con = connect()
    try:
        _require_visible(con, account_id, user)
        with con:
            con.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    finally:
        con.close()
    return {"ok": True}
