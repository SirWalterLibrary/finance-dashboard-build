# T09d — GET /api/summary (router + 5 tests)
Needs: T09c. Self-contained: do NOT read SPEC.md. Do not read any other file; every piece of code you need is below. Pick the simplest reading and do not deliberate.
Files: app/routers/summary.py (new), app/main.py, tests/test_summary.py (append), PROGRESS.md
Read only: nothing (the helper `_seed` and the imports of the earlier summary tests are already in tests/test_summary.py).

Decisions (already made): default scope is `joint`; `from` defaults to the first day of the month five months back (so six calendar months including the current one), `to` is unlimited; bad dates or scope -> 400. The privacy rule is enforced by `owner_clause` in the router, never by the client.

Step 1 — tests FIRST. Append (`cat >> tests/test_summary.py <<'PYEOF' ... PYEOF`, not Edit) exactly this:

```python


import datetime

from conftest import login, make_user


def _day(days_ago=0):
    return (datetime.date.today() - datetime.timedelta(days=days_ago)).isoformat()


def test_summary_requires_login(client):
    assert client.get("/api/summary").status_code == 401


def test_summary_response_shape(client):
    make_user(client, "alice")
    login(client, "alice")
    body = client.get("/api/summary").json()
    assert set(body) == {
        "income_cents", "spending_cents", "reimbursed_cents", "net_cents",
        "saved_cents", "tx_count", "uncategorized_count", "by_category", "by_month",
    }


def test_summary_default_range_is_about_six_months(client):
    make_user(client, "alice")
    login(client, "alice")
    _seed([(_day(0), -1000, "Groceries"), (_day(250), -5000, "Groceries")])
    assert client.get("/api/summary").json()["spending_cents"] == 1000
    assert client.get("/api/summary?from=2000-01-01").json()["spending_cents"] == 6000
    assert client.get(f"/api/summary?from=2000-01-01&to={_day(100)}").json()["spending_cents"] == 5000


def test_summary_scope_privacy(client):
    alice = make_user(client, "alice")
    bob = make_user(client, "bob")
    today = _day(0)
    _seed([(today, -1000, "Groceries")])
    _seed([(today, -2000, "Groceries")], owner=alice)
    _seed([(today, -4000, "Groceries")], owner=bob)

    def spent(scope=None):
        url = "/api/summary" + (f"?scope={scope}" if scope else "")
        return client.get(url).json()["spending_cents"]

    login(client, "alice")
    assert spent() == 1000            # default scope is joint
    assert spent("joint") == 1000
    assert spent("personal") == 2000
    assert spent("combined") == 3000
    login(client, "bob")
    assert spent("personal") == 4000
    assert spent("combined") == 5000


def test_summary_bad_dates_and_scope_are_400(client):
    make_user(client, "alice")
    login(client, "alice")
    assert client.get("/api/summary?from=banana").status_code == 400
    assert client.get("/api/summary?to=2026-13-45").status_code == 400
    assert client.get("/api/summary?scope=nope").status_code == 400
```

Run `make test`: the 5 new tests must FAIL (404, the route does not exist).

Step 2 — implement. Create app/routers/summary.py with `cat > app/routers/summary.py <<'PYEOF' ... PYEOF` and exactly this content:

```python
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
```

Step 3 — register it with these TWO small Edits in app/main.py (each oldText occurs once):

Edit 1. oldText: `from .routers import transactions as transactions_router`
newText:
```
from .routers import summary as summary_router
from .routers import transactions as transactions_router
```
Edit 2. oldText: `    app.include_router(transactions_router.router)`
newText:
```
    app.include_router(summary_router.router)
    app.include_router(transactions_router.router)
```

Verify: `make test` all green (5 new tests). If a scope test fails, do not change `owner_clause`; write the failure under Blockers and stop. Touch nothing else. Tick T09d in PROGRESS.md, add one Log line, commit.
