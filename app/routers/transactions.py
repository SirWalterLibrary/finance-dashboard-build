"""Transactions endpoints (T06).

GET    /api/transactions      - list with filters (scope, account_id, category_id,
                                q, from, to, direction, source) + limit/offset.
PATCH  /api/transactions/{id} - set category_id; stored with category_source
                                'manual' (T08 adds apply_to_similar).
DELETE /api/transactions/{id} - remove the row.

PATCH/DELETE on a transaction not visible to the caller (or unknown) -> 404.
Money = integer cents; dates are ISO YYYY-MM-DD text.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import current_user
from app.db import connect
from app.scope import owner_clause

router = APIRouter(prefix="/api", tags=["transactions"])

_DIRECTIONS = ("in", "out")
_SOURCES = ("none", "rule", "llm", "manual")


class PatchIn(BaseModel):
    category_id: int


def _item(tx: dict, acc_name: str, cat_name: str, cat_color: str) -> dict:
    return {
        "id": tx["id"],
        "date": tx["date"],
        "description": tx["description"],
        "amount_cents": tx["amount_cents"],
        "account_id": tx["account_id"],
        "account_name": acc_name,
        "category_id": tx["category_id"],
        "category_name": cat_name,
        "category_color": cat_color,
        "category_source": tx["category_source"],
        "category_confidence": tx["category_confidence"],
        # T07 will wire rules.merchant_key; until then always ""
        "suggested_keyword": "",
    }


def _where(user: dict, scope: str, account_id: int | None, category_id: int | None,
           q: str | None, from_: str | None, to: str | None,
           direction: str | None, source: str | None) -> tuple[str, list]:
    """Shared WHERE for the count and the page query (NULL-safe scoping)."""
    clause, params = owner_clause(scope, user["id"])  # ValueError -> 400
    conds = [f"({clause})"]
    params = list(params)
    if account_id is not None:
        conds.append("t.account_id = ?")
        params.append(account_id)
    if category_id is not None:
        conds.append("t.category_id = ?")
        params.append(category_id)
    if q is not None:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conds.append("t.description LIKE ? ESCAPE '\\'")
        params.append(f"%{escaped}%")
    if from_ is not None:
        conds.append("t.date >= ?")
        params.append(from_)
    if to is not None:
        conds.append("t.date <= ?")
        params.append(to)
    if direction == "in":
        conds.append("t.amount_cents > 0")
    elif direction == "out":
        conds.append("t.amount_cents < 0")
    if source is not None:
        conds.append("t.category_source = ?")
        params.append(source)
    return " AND ".join(conds), params


@router.get("/transactions")
def list_transactions(
    scope: str = Query("combined"),
    account_id: int | None = Query(None),
    category_id: int | None = Query(None),
    q: str | None = Query(None),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    direction: str | None = Query(None),
    source: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict = Depends(current_user),
):
    if direction not in (None, *_DIRECTIONS):
        raise HTTPException(400, f"direction must be one of: {' | '.join(_DIRECTIONS)}")
    if source not in (None, *_SOURCES):
        raise HTTPException(400, f"source must be one of: {' | '.join(_SOURCES)}")
    try:
        where, params = _where(
            user, scope, account_id, category_id, q, from_, to, direction, source
        )
    except ValueError:
        raise HTTPException(400, "scope must be personal, joint, or combined")

    con = connect()
    try:
        total = con.execute(
            "SELECT COUNT(*) AS c FROM transactions t "
            "JOIN accounts a ON a.id = t.account_id WHERE " + where,
            params,
        ).fetchone()["c"]
        rows = con.execute(
            "SELECT t.*, a.name AS account_name, c.name AS category_name, "
            "c.color AS category_color "
            "FROM transactions t "
            "JOIN accounts a ON a.id = t.account_id "
            "JOIN categories c ON c.id = t.category_id "
            "WHERE " + where +
            " ORDER BY t.date DESC, t.id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        items = [
            _item(
                tx,
                tx["account_name"],
                tx["category_name"],
                tx["category_color"],
            )
            for tx in rows
        ]
    finally:
        con.close()
    return {"items": items, "total": total}


@router.patch("/transactions/{tx_id}")
def patch_transaction(tx_id: int, body: PatchIn, user: dict = Depends(current_user)):
    con = connect()
    try:
        with con:
            cur = con.execute(
                "UPDATE transactions "
                "SET category_id = ?, category_source = 'manual' "
                "WHERE id = ? AND account_id IN "
                "(SELECT id FROM accounts WHERE owner_user_id IS NULL "
                "OR owner_user_id = ?) "
                "AND EXISTS (SELECT 1 FROM categories WHERE id = ?)",
                (body.category_id, tx_id, user["id"], body.category_id),
            )
        if cur.rowcount == 0:
            raise HTTPException(404, "transaction not found")
        row = con.execute(
            "SELECT t.*, a.name AS account_name, c.name AS category_name, "
            "c.color AS category_color "
            "FROM transactions t "
            "JOIN accounts a ON a.id = t.account_id "
            "JOIN categories c ON c.id = t.category_id "
            "WHERE t.id = ?",
            (tx_id,),
        ).fetchone()
    finally:
        con.close()
    if row is None:
        raise HTTPException(404, "transaction not found")
    return _item(row, row["account_name"], row["category_name"], row["category_color"])


@router.delete("/transactions/{tx_id}")
def delete_transaction(tx_id: int, user: dict = Depends(current_user)):
    con = connect()
    try:
        with con:
            cur = con.execute(
                "DELETE FROM transactions WHERE id = ? AND account_id IN "
                "(SELECT id FROM accounts WHERE owner_user_id IS NULL "
                "OR owner_user_id = ?)",
                (tx_id, user["id"]),
            )
    finally:
        con.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "transaction not found")
    return {"ok": True}
