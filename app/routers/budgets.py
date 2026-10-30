"""Budget endpoints (T12). Budgets are per-owner or joint (owner NULL)."""

import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import current_user
from app.budgets import month_status
from app.db import connect
from app.scope import owner_clause, owner_ids

router = APIRouter(prefix="/api", tags=["budgets"])


class BudgetIn(BaseModel):
    scope: str = "joint"
    category_id: int
    limit_cents: int = Field(ge=0)


def _validate_month(month: str | None) -> str:
    if month is None:
        return datetime.date.today().strftime("%Y-%m")
    try:
        y, m = int(month[:4]), int(month[5:7])
    except (ValueError, IndexError):
        raise HTTPException(400, "month must be YYYY-MM")
    if len(month) != 7 or month[4] != "-" or not 1 <= m <= 12:
        raise HTTPException(400, "month must be YYYY-MM")
    return month


def _budget_owner_clause(scope: str, user_id) -> tuple:
    """(sql_fragment, params) filtering b.owner_user_id for this scope."""
    if scope == "personal":
        return f"(b.owner_user_id = ?)", (user_id,)
    if scope == "joint":
        return "(b.owner_user_id IS NULL)", ()
    return "(b.owner_user_id IS NULL OR b.owner_user_id = ?)", (user_id,)


def _item(con, row) -> dict:
    name = con.execute(
        "SELECT name FROM categories WHERE id = ?", (row["category_id"],)
    ).fetchone()["name"]
    return {
        "id": row["id"],
        "name": name,
        "limit_cents": row["limit_cents"],
    }


@router.get("/budgets")
def get_budgets(
    scope: str = Query("joint"),
    month: str | None = Query(None),
    user: dict = Depends(current_user),
):
    month = _validate_month(month)
    try:
        acct_clause, acct_params = owner_clause(scope, user["id"], "a.owner_user_id")
    except ValueError:
        raise HTTPException(400, "invalid scope")
    con = connect()
    try:
        b_clause, b_params = _budget_owner_clause(scope, user["id"])
        return month_status(con, (acct_clause, acct_params), month, (b_clause, b_params))
    finally:
        con.close()


@router.put("/budgets")
def put_budget(body: BudgetIn, user: dict = Depends(current_user)):
    if body.scope == "combined":
        raise HTTPException(400, "scope must be personal or joint")
    if body.scope not in ("personal", "joint"):
        raise HTTPException(400, "invalid scope")
    owner = None if body.scope == "joint" else user["id"]
    con = connect()
    try:
        cat = con.execute(
            "SELECT id, kind FROM categories WHERE id = ?", (body.category_id,)
        ).fetchone()
        if cat is None:
            raise HTTPException(404, "category not found")
        if cat["kind"] != "expense":
            raise HTTPException(422, "only expense categories can have a budget")
        with con:
            existing = con.execute(
                "SELECT id FROM budgets "
                "WHERE IFNULL(owner_user_id,0) = IFNULL(?,0) AND category_id = ?",
                (owner, body.category_id),
            ).fetchone()
            if existing is None:
                con.execute(
                    "INSERT INTO budgets (owner_user_id, category_id, limit_cents) "
                    "VALUES (?,?,?)",
                    (owner, body.category_id, body.limit_cents),
                )
                budget_id = con.execute(
                    "SELECT last_insert_rowid() AS id"
                ).fetchone()["id"]
            else:
                budget_id = existing["id"]
                con.execute(
                    "UPDATE budgets SET limit_cents = ? WHERE id = ?",
                    (body.limit_cents, budget_id),
                )
        row = con.execute(
            "SELECT id, category_id, limit_cents FROM budgets WHERE id = ?",
            (budget_id,),
        ).fetchone()
        return _item(con, row)
    finally:
        con.close()


@router.delete("/budgets/{budget_id}")
def delete_budget(
    budget_id: int,
    scope: str = Query("joint"),
    user: dict = Depends(current_user),
):
    try:
        visible_ids = owner_ids(scope, user["id"])
    except ValueError:
        raise HTTPException(400, "invalid scope")
    con = connect()
    try:
        row = con.execute(
            "SELECT owner_user_id FROM budgets WHERE id = ?", (budget_id,)
        ).fetchone()
        if row is None or row["owner_user_id"] not in visible_ids:
            raise HTTPException(404, "budget not found")
        with con:
            con.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
        return {"ok": True}
    finally:
        con.close()
