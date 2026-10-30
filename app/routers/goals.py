"""Goals endpoints (T13): CRUD, GET /api/savings, GET /api/goals/simulate."""

import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import current_user
from app.db import connect
from app import goals as g
from app.scope import owner_clause, owner_ids

router = APIRouter(prefix="/api", tags=["goals"])


class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_cents: int = Field(gt=0)
    target_date: str | None = None
    allocated_cents: int = Field(default=0, ge=0)
    scope: str = "joint"


class GoalPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    target_cents: int | None = Field(default=None, gt=0)
    target_date: str | None = None
    allocated_cents: int | None = Field(default=None, ge=0)


def _check_date(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError:
        raise HTTPException(400, "target_date must be YYYY-MM-DD")


def _scope_owner(scope: str):
    """Owner marker for create: personal -> user id, joint -> None, else 400."""
    if scope == "personal":
        return "user"
    if scope == "joint":
        return None
    raise HTTPException(400, "scope must be personal or joint")


def _owner_where(visible: list) -> tuple:
    """(sql_fragment, params) for owner_user_id matching visible (NULL-safe)."""
    parts, params = [], []
    for v in visible:
        if v is None:
            parts.append("owner_user_id IS NULL")
        else:
            parts.append("owner_user_id = ?")
            params.append(v)
    return "(" + " OR ".join(parts) + ")", tuple(params)


def _visible(scope: str, user: dict) -> list:
    try:
        return owner_ids(scope, user["id"])
    except ValueError:
        raise HTTPException(400, "invalid scope")


def _item(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "target_cents": row["target_cents"],
        "target_date": row["target_date"],
        "allocated_cents": row["allocated_cents"],
    }


def _bucket_balance_for(con, visible: list) -> int:
    """Savings-type balance (opening + tx) for the given owner bucket(s)."""
    parts, params = [], []
    for v in visible:
        if v is None:
            parts.append("a.owner_user_id IS NULL")
        else:
            parts.append("a.owner_user_id = ?")
            params.append(v)
    row = con.execute(
        f"SELECT COALESCE(SUM(a.opening_balance_cents),0) + "
        f"COALESCE((SELECT SUM(tx.amount_cents) FROM transactions tx "
        f"WHERE tx.account_id = a.id),0) AS bal "
        f"FROM accounts a WHERE ({' OR '.join(parts)}) AND a.type = 'savings'",
        params,
    ).fetchone()
    return row["bal"]


def _bucket_balance(con, owner_user_id) -> int:
    return _bucket_balance_for(con, [owner_user_id])


def _allocated_total(con, owner_user_id, except_id: int = None) -> int:
    sql = "SELECT COALESCE(SUM(allocated_cents),0) FROM goals WHERE "
    where, params = _owner_where([owner_user_id])
    if except_id is not None:
        sql += f"{where} AND id != ?"
        params = params + (except_id,)
    else:
        sql += where
    return con.execute(sql, params).fetchone()[0]


def _savings_summary(con, scope: str, user: dict) -> dict:
    visible = _visible(scope, user)
    balance = _bucket_balance_for(con, visible)
    where, params = _owner_where(visible)
    rows = con.execute(f"SELECT allocated_cents FROM goals WHERE {where}", params).fetchall()
    return g.savings_summary(balance, [r["allocated_cents"] for r in rows])


def _get_goal(con, goal_id: int, scope: str, user: dict) -> dict:
    row = con.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "goal not found")
    if row["owner_user_id"] not in _visible(scope, user):
        raise HTTPException(404, "goal not found")
    return row


@router.get("/goals")
def list_goals(scope: str = Query("joint"), user: dict = Depends(current_user)):
    con = connect()
    try:
        visible = _visible(scope, user)
        where, params = _owner_where(visible)
        rows = con.execute(f"SELECT * FROM goals WHERE {where} ORDER BY name", params).fetchall()
        return [_item(r) for r in rows]
    finally:
        con.close()


@router.post("/goals", status_code=201)
def create_goal(body: GoalIn, user: dict = Depends(current_user)):
    owner_marker = _scope_owner(body.scope)
    owner = user["id"] if owner_marker == "user" else None
    target_date = _check_date(body.target_date)
    con = connect()
    try:
        if body.allocated_cents + _allocated_total(con, owner) > _bucket_balance(con, owner):
            raise HTTPException(400, "over_allocated")
        with con:
            cur = con.execute(
                "INSERT INTO goals (owner_user_id, name, target_cents, target_date, "
                "allocated_cents) VALUES (?,?,?,?,?)",
                (owner, body.name, body.target_cents, target_date, body.allocated_cents),
            )
        row = con.execute("SELECT * FROM goals WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _item(row)
    finally:
        con.close()


@router.patch("/goals/{goal_id}")
def patch_goal(
    goal_id: int,
    body: GoalPatch,
    scope: str = Query("joint"),
    user: dict = Depends(current_user),
):
    con = connect()
    try:
        row = _get_goal(con, goal_id, scope, user)
        updates = {}
        if body.name is not None:
            updates["name"] = body.name
        if body.target_cents is not None:
            updates["target_cents"] = body.target_cents
        if body.target_date is not None:
            updates["target_date"] = _check_date(body.target_date)
        if body.allocated_cents is not None:
            updates["allocated_cents"] = body.allocated_cents
        if "allocated_cents" in updates:
            # total allocated in this goal's owner bucket must not exceed the
            # bucket's savings balance -> 400 "over_allocated"
            bucket = updates["allocated_cents"] + _allocated_total(
                con, row["owner_user_id"], goal_id
            )
            if bucket > _bucket_balance(con, row["owner_user_id"]):
                raise HTTPException(400, "over_allocated")
        if updates:
            sets = ", ".join(f"{k} = ?" for k in updates)
            with con:
                con.execute(f"UPDATE goals SET {sets} WHERE id = ?", (*updates.values(), goal_id))
        row = con.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        return _item(row)
    finally:
        con.close()


@router.delete("/goals/{goal_id}")
def delete_goal(goal_id: int, scope: str = Query("joint"), user: dict = Depends(current_user)):
    con = connect()
    try:
        _get_goal(con, goal_id, scope, user)
        with con:
            con.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        return {"ok": True}
    finally:
        con.close()


@router.get("/savings")
def get_savings(scope: str = Query("joint"), user: dict = Depends(current_user)):
    con = connect()
    try:
        return _savings_summary(con, scope, user)
    finally:
        con.close()


@router.get("/goals/simulate")
def simulate(
    scope: str = Query("joint"),
    months: int = Query(6, ge=1, le=120),
    monthly_cents: int | None = Query(None, ge=0),
    user: dict = Depends(current_user),
):
    try:
        acct_clause, acct_params = owner_clause(scope, user["id"], "a.owner_user_id")
        visible = _visible(scope, user)
    except ValueError:
        raise HTTPException(400, "invalid scope")
    today = datetime.date.today()
    con = connect()
    try:
        if monthly_cents is None:
            # baseline over the last `months` COMPLETE months before today
            first = datetime.date(today.year, today.month, 1)
            m = first.month - 1 - months
            y = first.year + m // 12
            from_ = datetime.date(y, m % 12 + 1, 1).isoformat()
            to_ = first.isoformat()  # exclusive
            by_month = [
                {
                    "month": r["month"],
                    "income_cents": r["income_cents"],
                    "spending_cents": r["spending_cents"],
                }
                for r in con.execute(
                    "SELECT substr(t.date,1,7) AS month, "
                    "COALESCE(SUM(CASE WHEN c.kind='income' THEN t.amount_cents ELSE 0 END),0) "
                    "AS income_cents, "
                    "COALESCE(SUM(CASE WHEN c.kind='expense' THEN -t.amount_cents ELSE 0 END),0) "
                    "- COALESCE(SUM(CASE WHEN c.kind='reimbursement' THEN t.amount_cents "
                    "ELSE 0 END),0) AS spending_cents "
                    "FROM transactions t "
                    "JOIN accounts a ON a.id = t.account_id "
                    "JOIN categories c ON c.id = t.category_id "
                    f"WHERE {acct_clause} AND t.date >= ? AND t.date < ? "
                    "GROUP BY month",
                    (*acct_params, from_, to_),
                ).fetchall()
            ]
            monthly = g.baseline_monthly(by_month, months, today)
        else:
            monthly = monthly_cents
        where, params = _owner_where(visible)
        goal_rows = con.execute(
            f"SELECT id, name, target_cents, target_date, allocated_cents FROM goals "
            f"WHERE {where} ORDER BY name",
            params,
        ).fetchall()
        goals = []
        for row in goal_rows:
            remaining = max(row["target_cents"] - row["allocated_cents"], 0)
            eta = g.eta(remaining, monthly, today)
            eta_date, months_needed = (None, None) if eta is None else eta
            target_date = (
                datetime.date.fromisoformat(row["target_date"])
                if row["target_date"]
                else None
            )
            goals.append(
                {
                    "id": row["id"],
                    "remaining_cents": remaining,
                    "months_needed": months_needed,
                    "eta_date": eta_date.isoformat() if eta_date else None,
                    "on_track": g.on_track(eta_date, target_date),
                }
            )
        return {"monthly_cents_used": monthly, "goals": goals}
    finally:
        con.close()
