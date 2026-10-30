# T08c — PATCH /api/transactions/{id}: apply_to_similar (endpoint + 3 core tests)
Needs: T08b. Self-contained: do NOT read SPEC.md. Do NOT read any file except the ones listed.
Files: app/routers/transactions.py, tests/test_correction.py, PROGRESS.md
Read only: app/routers/transactions.py (lines around `PatchIn` and `patch_transaction`), and the last 40 lines of tests/test_correction.py.

Step 0. Run `git status --short`. If any tracked file is modified, STOP and write that in PROGRESS.md under Blockers. (Untracked `pi-session-*.html` files are fine.)

Step 1 — tests FIRST. Append (do not use Edit for this; use bash `cat >> tests/test_correction.py <<'PYEOF' ... PYEOF`) exactly this block. It reuses the helpers `_category_id`, `_account`, `_tx`, `_state` that already exist in the file.

```python


from conftest import login


def _patch(client, tx_id, **body):
    return client.patch(f"/api/transactions/{tx_id}", json=body)


def _kwik_rows():
    unc = _category_id("Uncategorized")
    trans = _category_id("Transport")
    con = connect()
    try:
        with con:
            acct = _account(con, None)
            ids = {
                "t1": _tx(con, acct, "KWIK TRIP #1", trans, "rule", 1),
                "t2": _tx(con, acct, "KWIK TRIP #2", unc, "none", 2),
                "t3": _tx(con, acct, "KWIK TRIP #3", unc, "none", 3),
                "manual": _tx(con, acct, "KWIK TRIP #4", trans, "manual", 4),
                "sams": _tx(con, acct, "SAMS CLUB #5", unc, "none", 5),
            }
    finally:
        con.close()
    return ids


def test_patch_apply_to_similar_learns_rule(client, user):
    login(client, user)
    unc = _category_id("Uncategorized")
    trans = _category_id("Transport")
    food = _category_id("Food & Dining")
    ids = _kwik_rows()
    res = _patch(client, ids["t1"], category_id=food, apply_to_similar=True)
    assert res.status_code == 200
    body = res.json()
    assert body["updated"] == 3
    assert isinstance(body["rule_id"], int)
    assert body["category_id"] == food
    assert body["category_source"] == "manual"
    con = connect()
    try:
        assert _state(con, ids["t1"]) == (food, "manual")
        assert _state(con, ids["t2"]) == (food, "rule")
        assert _state(con, ids["t3"]) == (food, "rule")
        assert _state(con, ids["manual"]) == (trans, "manual")
        assert _state(con, ids["sams"]) == (unc, "none")
        rule = con.execute(
            "SELECT keyword, category_id FROM rules WHERE id = ?", (body["rule_id"],)
        ).fetchone()
        assert (rule["keyword"], rule["category_id"]) == ("KWIK TRIP", food)
    finally:
        con.close()


def test_patch_without_apply_to_similar_changes_one_row(client, user):
    login(client, user)
    unc = _category_id("Uncategorized")
    food = _category_id("Food & Dining")
    ids = _kwik_rows()
    con = connect()
    try:
        rules_before = con.execute("SELECT COUNT(*) AS c FROM rules").fetchone()["c"]
    finally:
        con.close()
    res = _patch(client, ids["t2"], category_id=food)
    assert res.status_code == 200
    body = res.json()
    assert body["updated"] == 1
    assert body["rule_id"] is None
    con = connect()
    try:
        assert _state(con, ids["t2"]) == (food, "manual")
        assert _state(con, ids["t3"]) == (unc, "none")
        assert con.execute("SELECT COUNT(*) AS c FROM rules").fetchone()["c"] == rules_before
    finally:
        con.close()


def test_patch_blank_keyword_400_and_nothing_changes(client, user):
    login(client, user)
    unc = _category_id("Uncategorized")
    food = _category_id("Food & Dining")
    ids = _kwik_rows()
    res = _patch(client, ids["t2"], category_id=food, apply_to_similar=True, keyword="  ")
    assert res.status_code == 400
    con = connect()
    try:
        assert _state(con, ids["t2"]) == (unc, "none")
    finally:
        con.close()
```

Run `make test`: the 3 new tests must FAIL (that is the expected red). Then:

Step 2 — implement with these FOUR small Edits in app/routers/transactions.py (copy oldText exactly; each occurs once):

Edit 1. oldText:
```
class PatchIn(BaseModel):
    category_id: int
```
newText:
```
class PatchIn(BaseModel):
    category_id: int
    apply_to_similar: bool = False
    keyword: str | None = None


def _learn(con, user: dict, tx_id: int, body: PatchIn) -> tuple:
    """Learn a rule from a manual correction. Returns (rule_id, updated)."""
    if not body.apply_to_similar:
        return None, 1
    desc = con.execute(
        "SELECT description FROM transactions WHERE id = ?", (tx_id,)
    ).fetchone()["description"]
    kw = norm_desc(body.keyword) if body.keyword is not None else rules.merchant_key(desc)
    if not kw:
        raise HTTPException(400, "keyword must not be empty")
    rule_id = rules.ensure_rule(con, kw, body.category_id)
    n = rules.relabel_similar(con, user["id"], kw, body.category_id, tx_id)
    return rule_id, 1 + n
```
Edit 2. oldText:
```
from app.auth import current_user
```
newText:
```
from app.auth import current_user
from app.csvparse import norm_desc
```
Edit 3. oldText:
```
                (body.category_id, tx_id, user["id"], body.category_id),
            )
        if cur.rowcount == 0:
            raise HTTPException(404, "transaction not found")
```
newText:
```
                (body.category_id, tx_id, user["id"], body.category_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "transaction not found")
            rule_id, updated = _learn(con, user, tx_id, body)
```
Edit 4. oldText (the last line of `patch_transaction`, it occurs once):
```
    return _item(row, row["account_name"], row["category_name"], row["category_color"])
```
newText:
```
    item = _item(row, row["account_name"], row["category_name"], row["category_color"])
    item["updated"] = updated
    item["rule_id"] = rule_id
    return item
```
(The 404 now sits inside the `with con:` block on purpose: an HTTPException there rolls the whole transaction back, which is what makes the blank-keyword test pass.)

Verify: `make test` must be all green, the old patch test in tests/test_transactions.py unchanged. Do not change anything else.
In PROGRESS.md: tick T08c, add the line `- [ ] T08d PATCH extra tests` right under it, add a Log line. Commit.
