"""Rule endpoints + POST /api/categorize/run (SPEC "Rules").

Rules are global. Keywords are stored normalized (norm_desc).
categorize/run applies keyword rules to 'none' rows in the requested
scope; the LLM step (T11) is not available yet, so by_llm is always 0.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import current_user
from app.db import connect
from app.csvparse import norm_desc
from app.rules import apply_rules
from app.scope import owner_clause

router = APIRouter(prefix="/api", tags=["rules"])


class RuleIn(BaseModel):
    keyword: str = Field(min_length=1)
    category_id: int
    min_cents: int | None = None
    max_cents: int | None = None


class CategorizeIn(BaseModel):
    scope: str = "joint"


def _row_item(row) -> dict:
    return {
        "id": row["id"],
        "keyword": row["keyword"],
        "category_id": row["category_id"],
        "category_name": row["category_name"],
        "min_cents": row["min_cents"],
        "max_cents": row["max_cents"],
    }


@router.get("/rules")
def list_rules(user: dict = Depends(current_user)):
    con = connect()
    try:
        rows = con.execute(
            "SELECT r.id, r.keyword, r.category_id, c.name AS category_name, "
            "r.min_cents, r.max_cents "
            "FROM rules r JOIN categories c ON c.id = r.category_id "
            "ORDER BY r.keyword, r.id"
        ).fetchall()
        return [_row_item(r) for r in rows]
    finally:
        con.close()


@router.post("/rules", status_code=201)
def create_rule(body: RuleIn, user: dict = Depends(current_user)):
    if not body.keyword.strip():
        raise HTTPException(422, "keyword must not be blank")
    if body.min_cents is not None and body.max_cents is not None \
            and body.min_cents > body.max_cents:
        raise HTTPException(422, "min_cents cannot be greater than max_cents")
    con = connect()
    try:
        if con.execute(
            "SELECT id FROM categories WHERE id = ?", (body.category_id,)
        ).fetchone() is None:
            raise HTTPException(404, "category not found")
        keyword = norm_desc(body.keyword)
        with con:
            cur = con.execute(
                "INSERT INTO rules (keyword, category_id, min_cents, max_cents) "
                "VALUES (?,?,?,?)",
                (keyword, body.category_id, body.min_cents, body.max_cents),
            )
        row = con.execute(
            "SELECT r.id, r.keyword, r.category_id, c.name AS category_name, "
            "r.min_cents, r.max_cents "
            "FROM rules r JOIN categories c ON c.id = r.category_id "
            "WHERE r.id = ?",
            (cur.lastrowid,),
        ).fetchone()
        return _row_item(row)
    finally:
        con.close()


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, user: dict = Depends(current_user)):
    con = connect()
    try:
        with con:
            cur = con.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "rule not found")
        return {"ok": True}
    finally:
        con.close()


@router.post("/categorize/run")
def categorize_run(body: CategorizeIn, user: dict = Depends(current_user)):
    try:
        clause, params = owner_clause(body.scope, user["id"], "a.owner_user_id")
    except ValueError:
        raise HTTPException(400, "scope must be personal, joint, or combined")
    con = connect()
    try:
        ids = [
            r["id"]
            for r in con.execute(
                "SELECT t.id FROM transactions t JOIN accounts a "
                "ON a.id = t.account_id "
                f"WHERE t.category_source = 'none' AND {clause}",
                params,
            ).fetchall()
        ]
        changed = apply_rules(con, ids)
        left = con.execute(
            "SELECT COUNT(*) AS c FROM transactions t JOIN accounts a "
            f"ON a.id = t.account_id "
            f"WHERE t.category_source = 'none' AND {clause}",
            params,
        ).fetchone()["c"]
        return {
            "by_rule": changed,
            "by_llm": 0,
            "left": left,
            "llm_available": False,
        }
    finally:
        con.close()
