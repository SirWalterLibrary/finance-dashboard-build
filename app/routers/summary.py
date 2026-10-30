"""GET /api/summary (T09d)."""
import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import current_user
from app.db import connect
from app.scope import owner_clause
from app.summary import build_summary

router = APIRouter(prefix="/api", tags=["summary"])


def _default_from(today: datetime.date) -> str:
    """First day of the month five months back (six calendar months incl. this one)."""
    year, month = today.year, today.month - 5
    if month < 1:
        month += 12
        year -= 1
    return datetime.date(year, month, 1).isoformat()


@router.get("/summary")
def get_summary(
    scope: str = Query("joint"),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    user: dict = Depends(current_user),
):
    for value in (from_, to):
        if value is not None:
            try:
                datetime.date.fromisoformat(value)
            except ValueError:
                raise HTTPException(400, "from/to must be YYYY-MM-DD")
    try:
        clause, params = owner_clause(scope, user["id"], "a.owner_user_id")
    except ValueError:
        raise HTTPException(400, "invalid scope")
    if from_ is None:
        from_ = _default_from(datetime.date.today())
    con = connect()
    try:
        return build_summary(con, clause, params, from_, to)
    finally:
        con.close()
