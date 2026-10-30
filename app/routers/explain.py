"""Optional AI explain (T15): POST /api/explain.

Recomputes the goals simulation or forecast projection with the existing
pure functions, then asks the standard Ollama chat endpoint to describe the
already-computed numbers in 3-4 plain sentences. The LLM must not calculate.
"""
import datetime
import json
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import current_user
from app.db import connect
from app import config, forecast as fc, goals as g
from app.scope import owner_clause, owner_ids

router = APIRouter(prefix="/api", tags=["explain"])

INSTRUCTIONS = (
    "In 3 to 4 short plain sentences for a non-technical person, describe the "
    "numbers in the JSON below. Do not change any number or date. Do not "
    "invent new numbers, and do not do any calculations."
)


class ExplainIn(BaseModel):
    kind: Literal["goals", "forecast"]
    scope: str = "joint"


def _numbers_for_goals(con, scope: str, user: dict, today) -> dict:
    try:
        acct_clause, acct_params = owner_clause(scope, user["id"], "a.owner_user_id")
        visible = owner_ids(scope, user["id"])
    except ValueError:
        raise HTTPException(400, "invalid scope")
    first = datetime.date(today.year, today.month, 1)
    m = first.month - 1 - 6
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
    monthly = g.baseline_monthly(by_month, 6, today)
    parts = [f"owner_user_id {'IS NULL' if v is None else '= ?'}" for v in visible]
    where = "(" + " OR ".join(parts) + ")"
    params = tuple(v for v in visible if v is not None)
    goal_rows = con.execute(
        f"SELECT id, name, target_cents, target_date, allocated_cents FROM goals "
        f"WHERE {where} ORDER BY name", params).fetchall()
    goals = []
    for row in goal_rows:
        remaining = max(row["target_cents"] - row["allocated_cents"], 0)
        eta = g.eta(remaining, monthly, today)
        eta_date, months_needed = (None, None) if eta is None else eta
        target_date = (datetime.date.fromisoformat(row["target_date"])
                       if row["target_date"] else None)
        goals.append({
            "name": row["name"],
            "remaining_cents": remaining,
            "months_needed": months_needed,
            "eta_date": eta_date.isoformat() if eta_date else None,
            "on_track": g.on_track(eta_date, target_date),
        })
    return {"monthly_cents_used": monthly, "goals": goals}


def _numbers_for_forecast(con, scope: str, user: dict, today) -> dict:
    visible = owner_ids(scope, user["id"])  # ValueError -> 400 below
    parts = [f"owner_user_id {'IS NULL' if v is None else '= ?'}" for v in visible]
    where = "(" + " OR ".join(parts) + ")"
    params = tuple(v for v in visible if v is not None)
    first = datetime.date(today.year, today.month, 1)
    m = first.month - 1 - 120
    y = first.year + m // 12
    acct_clause, acct_params = owner_clause(scope, user["id"], "a.owner_user_id")
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
    baseline = g.baseline_monthly(by_month, 120, today)
    bal = con.execute(
        "SELECT COALESCE(SUM(a.opening_balance_cents),0) + COALESCE(("
        "SELECT SUM(tx.amount_cents) FROM transactions tx WHERE tx.account_id = a.id),0)"
        f" AS bal FROM accounts a WHERE ({' OR '.join(parts)}) AND a.type = 'savings'",
        params).fetchone()
    events = con.execute(
        "SELECT direction, kind, amount_cents, start_date, end_date, frequency "
        f"FROM forecast_events WHERE {where}", params).fetchall()
    res = fc.project(bal["bal"], baseline,
                     [{"direction": r["direction"], "kind": r["kind"],
                       "amount_cents": r["amount_cents"],
                       "start_date": r["start_date"], "end_date": r["end_date"],
                       "frequency": r["frequency"]} for r in events],
                     120, today)
    return {"baseline_monthly_cents": baseline,
            "start_balance_cents": bal["bal"],
            "points": res["points"],
            "first_negative_month": res["first_negative_month"]}


def _ask_ollama(numbers: dict) -> str:
    model = config.get("EXPLAIN_MODEL")
    base = config.get("OLLAMA_URL")
    if not model or not base:
        return ""
    prompt = (INSTRUCTIONS + "\n"
              f"Numbers as JSON: {json.dumps(numbers)}")
    try:
        resp = httpx.post(
            f"{base.rstrip('/')}/api/chat",
            json={"model": model, "stream": False,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception:
        return ""


@router.post("/explain")
def explain(body: ExplainIn, user: dict = Depends(current_user)):
    try:
        owner_ids(body.scope, user["id"])
    except ValueError:
        raise HTTPException(400, "invalid scope")
    today = datetime.date.today()
    con = connect()
    try:
        if body.kind == "goals":
            numbers = _numbers_for_goals(con, body.scope, user, today)
        else:
            numbers = _numbers_for_forecast(con, body.scope, user, today)
    finally:
        con.close()
    text = _ask_ollama(numbers)
    return {"text": text, "llm_available": text != ""}
