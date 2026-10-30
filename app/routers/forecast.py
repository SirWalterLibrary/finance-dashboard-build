"""Forecast endpoints (T14): events CRUD + GET /api/forecast/projection."""

import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import current_user
from app.db import connect
from app import forecast as fc
from app import goals as g
from app.scope import owner_clause, owner_ids

router = APIRouter(prefix="/api", tags=["forecast"])

EVENT_COLS = ("id", "name", "group_name", "direction", "kind",
              "amount_cents", "start_date", "end_date", "frequency")


class EventIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    group_name: str = Field(default="", max_length=200)
    direction: str = Field(pattern="^(expense|income)$")
    kind: str = Field(pattern="^(one_time|recurring)$")
    amount_cents: int = Field(ge=0)
    start_date: str = Field(min_length=10, max_length=10)
    end_date: str | None = None
    frequency: str | None = Field(default=None, pattern="^(monthly|yearly)$")
    scope: str = "joint"


class EventPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    group_name: str | None = None
    direction: str | None = Field(default=None, pattern="^(expense|income)$")
    kind: str | None = Field(default=None, pattern="^(one_time|recurring)$")
    amount_cents: int | None = Field(default=None, ge=0)
    start_date: str | None = None
    end_date: str | None = None
    frequency: str | None = Field(default=None, pattern="^(monthly|yearly)$")


def _date(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    try:
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError:
        raise HTTPException(400, f"{label} must be YYYY-MM-DD")


def _visible(scope: str, user: dict) -> list:
    try:
        return owner_ids(scope, user["id"])
    except ValueError:
        raise HTTPException(400, "invalid scope")


def _owner_where(visible: list) -> tuple:
    parts = [f"owner_user_id {'IS NULL' if v is None else '= ?'}" for v in visible]
    return "(" + " OR ".join(parts) + ")", tuple(v for v in visible if v is not None)


def _normalize(kind: str, frequency: str | None, end_date: str | None):
    """recurring requires frequency; one_time ignores frequency/end_date."""
    if kind == "recurring" and frequency is None:
        raise HTTPException(400, "recurring requires frequency")
    return (None, None) if kind == "one_time" else (frequency, end_date)


def _item(row) -> dict:
    return {k: row[k] for k in EVENT_COLS}


def _savings_balance(con, visible: list) -> int:
    parts, params = [], []
    for v in visible:
        if v is None:
            parts.append("a.owner_user_id IS NULL")
        else:
            parts.append("a.owner_user_id = ?")
            params.append(v)
    row = con.execute(
        "SELECT COALESCE(SUM(a.opening_balance_cents),0) + COALESCE(("
        "SELECT SUM(tx.amount_cents) FROM transactions tx WHERE tx.account_id = a.id),0)"
        f" AS bal FROM accounts a WHERE ({' OR '.join(parts)}) AND a.type = 'savings'",
        params).fetchone()
    return row["bal"]


def _baseline(con, scope: str, user: dict, months: int, today) -> int:
    try:
        acct_clause, acct_params = owner_clause(scope, user["id"], "a.owner_user_id")
    except ValueError:
        raise HTTPException(400, "invalid scope")
    first = datetime.date(today.year, today.month, 1)
    m = first.month - 1 - months
    y = first.year + m // 12
    by_month = [
        {"month": r["month"], "income_cents": r["income_cents"],
         "spending_cents": r["spending_cents"]}
        for r in con.execute(
            "SELECT substr(t.date,1,7) AS month, "
            "COALESCE(SUM(CASE WHEN c.kind='income' THEN t.amount_cents ELSE 0 END),0)"
            " AS income_cents, "
            "COALESCE(SUM(CASE WHEN c.kind='expense' THEN -t.amount_cents ELSE 0 END),0) - "
            "COALESCE(SUM(CASE WHEN c.kind='reimbursement' THEN t.amount_cents ELSE 0 END),0)"
            " AS spending_cents FROM transactions t JOIN accounts a ON a.id = t.account_id "
            "JOIN categories c ON c.id = t.category_id "
            f"WHERE {acct_clause} AND t.date >= ? AND t.date < ? GROUP BY month",
            (*acct_params, datetime.date(y, m % 12 + 1, 1).isoformat(),
             first.isoformat()),
        ).fetchall()
    ]
    return g.baseline_monthly(by_month, months, today)


def _get_event(con, event_id: int, scope: str, user: dict) -> dict:
    row = con.execute("SELECT * FROM forecast_events WHERE id = ?", (event_id,)).fetchone()
    if row is None or row["owner_user_id"] not in _visible(scope, user):
        raise HTTPException(404, "event not found")
    return row


@router.get("/forecast/events")
def list_events(scope: str = Query("joint"), user: dict = Depends(current_user)):
    con = connect()
    try:
        where, params = _owner_where(_visible(scope, user))
        rows = con.execute(f"SELECT * FROM forecast_events WHERE {where} "
                           "ORDER BY start_date, id", params).fetchall()
        return [_item(r) for r in rows]
    finally:
        con.close()


@router.post("/forecast/events", status_code=201)
def create_event(body: EventIn, user: dict = Depends(current_user)):
    if body.scope == "personal":
        owner = user["id"]
    elif body.scope == "joint":
        owner = None
    else:
        raise HTTPException(400, "scope must be personal or joint")
    frequency, end_date = _normalize(body.kind, body.frequency,
                                     _date(body.end_date, "end_date"))
    con = connect()
    try:
        with con:
            cur = con.execute(
                "INSERT INTO forecast_events (owner_user_id, name, group_name, "
                "direction, kind, amount_cents, start_date, end_date, frequency) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (owner, body.name, body.group_name, body.direction, body.kind,
                 body.amount_cents, _date(body.start_date, "start_date"),
                 end_date, frequency))
        row = con.execute("SELECT * FROM forecast_events WHERE id = ?",
                          (cur.lastrowid,)).fetchone()
        return _item(row)
    finally:
        con.close()


@router.patch("/forecast/events/{event_id}")
def patch_event(event_id: int, body: EventPatch, scope: str = Query("joint"),
                user: dict = Depends(current_user)):
    con = connect()
    try:
        row = _get_event(con, event_id, scope, user)
        state = {k: (getattr(body, k) if getattr(body, k) is not None else row[k])
                 for k in EVENT_COLS if k != "id"}
        for k in ("start_date", "end_date"):
            state[k] = _date(state[k], k)
        state["frequency"], state["end_date"] = _normalize(
            state["kind"], state["frequency"], state["end_date"])
        with con:
            con.execute("UPDATE forecast_events SET "
                        + ", ".join(f"{k} = ?" for k in state) + " WHERE id = ?",
                        (*state.values(), event_id))
        row = con.execute("SELECT * FROM forecast_events WHERE id = ?", (event_id,)).fetchone()
        return _item(row)
    finally:
        con.close()


@router.delete("/forecast/events/{event_id}")
def delete_event(event_id: int, scope: str = Query("joint"),
                 user: dict = Depends(current_user)):
    con = connect()
    try:
        _get_event(con, event_id, scope, user)
        with con:
            con.execute("DELETE FROM forecast_events WHERE id = ?", (event_id,))
        return {"ok": True}
    finally:
        con.close()


@router.get("/forecast/projection")
def projection(scope: str = Query("joint"), months: int = Query(120, ge=1, le=240),
               monthly_cents: int | None = Query(None, ge=0),
               start_balance_cents: int | None = Query(None),
               user: dict = Depends(current_user)):
    visible = _visible(scope, user)
    today = datetime.date.today()
    con = connect()
    try:
        baseline = (monthly_cents if monthly_cents is not None
                    else _baseline(con, scope, user, months, today))
        start_balance = (start_balance_cents if start_balance_cents is not None
                         else _savings_balance(con, visible))
        where, params = _owner_where(visible)
        rows = con.execute(
            "SELECT direction, kind, amount_cents, start_date, end_date, frequency "
            f"FROM forecast_events WHERE {where}", params).fetchall()
        events = [{"direction": r["direction"], "kind": r["kind"],
                   "amount_cents": r["amount_cents"], "start_date": r["start_date"],
                   "end_date": r["end_date"], "frequency": r["frequency"]} for r in rows]
        res = fc.project(start_balance, baseline, events, months, today)
        return {"baseline_monthly_cents": baseline,
                "start_balance_cents": start_balance,
                "points": res["points"],
                "first_negative_month": res["first_negative_month"]}
    finally:
        con.close()
