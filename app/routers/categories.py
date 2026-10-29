"""Category endpoints (SPEC "Categories + rules").

Categories are global (shared across users). Name is unique. The seeded
`Uncategorized` category can neither be renamed nor deleted. Deleting a
category in use by a transaction is refused (409); rules pointing at it
are removed automatically by the foreign-key cascade.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import current_user
from app.db import connect

router = APIRouter(prefix="/api", tags=["categories"])

KINDS = ("income", "expense", "transfer", "savings", "reimbursement")


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=200, pattern=r"\S")
    kind: str
    color: str = "#888888"
    description: str = ""


class CategoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200, pattern=r"\S")
    kind: str | None = None
    color: str | None = None
    description: str | None = None


def _view(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "kind": row["kind"],
        "color": row["color"],
        "description": row["description"],
    }


def _get(con, category_id: int):
    row = con.execute(
        "SELECT * FROM categories WHERE id = ?", (category_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "category not found")
    return row


def _check_kind(kind: str) -> None:
    if kind not in KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(KINDS)}")


def _check_unique(con, name: str, exclude_id: int | None = None) -> None:
    row = con.execute(
        "SELECT id FROM categories WHERE name = ?"
        + (" AND id != ?" if exclude_id is not None else ""),
        (name, exclude_id) if exclude_id is not None else (name,),
    ).fetchone()
    if row is not None:
        raise HTTPException(409, "a category with this name exists")


@router.get("/categories")
def list_categories(user: dict = Depends(current_user)):
    con = connect()
    try:
        rows = con.execute(
            "SELECT * FROM categories ORDER BY name"
        ).fetchall()
        return [_view(r) for r in rows]
    finally:
        con.close()


@router.post("/categories", status_code=201)
def create_category(body: CategoryIn, user: dict = Depends(current_user)):
    _check_kind(body.kind)
    con = connect()
    try:
        _check_unique(con, body.name)
        with con:
            cur = con.execute(
                "INSERT INTO categories (name, kind, color, description) "
                "VALUES (?,?,?,?)",
                (body.name, body.kind, body.color, body.description),
            )
        row = con.execute(
            "SELECT * FROM categories WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return _view(row)
    finally:
        con.close()


@router.patch("/categories/{category_id}")
def patch_category(category_id: int, body: CategoryPatch,
                   user: dict = Depends(current_user)):
    if body.kind is not None:
        _check_kind(body.kind)
    con = connect()
    try:
        row = _get(con, category_id)
        updates, params = [], []
        if body.name is not None:
            if row["name"] == "Uncategorized" and body.name != "Uncategorized":
                raise HTTPException(409, "the Uncategorized category cannot be renamed")
            _check_unique(con, body.name, exclude_id=category_id)
            updates.append("name = ?")
            params.append(body.name)
        if body.kind is not None:
            updates.append("kind = ?")
            params.append(body.kind)
        if body.color is not None:
            updates.append("color = ?")
            params.append(body.color)
        if body.description is not None:
            updates.append("description = ?")
            params.append(body.description)
        if updates:
            with con:
                con.execute(
                    f"UPDATE categories SET {', '.join(updates)} WHERE id = ?",
                    (*params, category_id),
                )
        row = con.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        return _view(row)
    finally:
        con.close()


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, user: dict = Depends(current_user)):
    con = connect()
    try:
        row = _get(con, category_id)
        if row["name"] == "Uncategorized":
            raise HTTPException(409, "the Uncategorized category cannot be deleted")
        n = con.execute(
            "SELECT COUNT(*) AS c FROM transactions WHERE category_id = ?",
            (category_id,),
        ).fetchone()["c"]
        if n:
            raise HTTPException(409, "category is used by transactions")
        with con:
            con.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    finally:
        con.close()
    return {"ok": True}
