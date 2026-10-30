"""Rule endpoints + POST /api/categorize/run (SPEC "Rules" + "LLM rules").

Rules are global. Keywords are stored normalized (norm_desc).
categorize/run first applies keyword rules to 'none' rows in the requested
scope, then runs the LLM categorizer (app/llm.py) over the 'none' rows
still left in scope.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import current_user
from app.db import connect
from app.csvparse import norm_desc
from app import llm
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


def _none_rows_in_scope(con, user_id, scope):
    """All 'none' rows in the scope, oldest first."""
    clause, params = owner_clause(scope, user_id, "a.owner_user_id")
    return con.execute(
        "SELECT t.* FROM transactions t JOIN accounts a "
        "ON a.id = t.account_id "
        f"WHERE t.category_source = 'none' AND {clause} ORDER BY t.id",
        params,
    ).fetchall()


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
    scope = body.scope
    con = connect()
    try:
        clause, params = owner_clause(scope, user["id"], "a.owner_user_id")
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
        # LLM pass over whatever the rules left behind in scope
        result = llm.categorize_pending(con, _none_rows_in_scope(
            con, user["id"], scope
        ))
        return {
            "by_rule": changed,
            "by_llm": result["by_llm"],
            "left": len(_none_rows_in_scope(con, user["id"], scope)),
            "llm_available": result["llm_available"],
        }
    except ValueError:
        raise HTTPException(400, "scope must be personal, joint, or combined")
    finally:
        con.close()
