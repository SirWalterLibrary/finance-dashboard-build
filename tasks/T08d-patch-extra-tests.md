# T08d — PATCH apply_to_similar: 3 more tests (tests only)
Needs: T08c. Self-contained: do NOT read SPEC.md. Do NOT read any file except tests/test_correction.py (last 60 lines) and PROGRESS.md.
Files: tests/test_correction.py, PROGRESS.md

Append (use bash `cat >> tests/test_correction.py <<'PYEOF' ... PYEOF`, not Edit) exactly this block. It reuses `_patch`, `_kwik_rows`, `_category_id`, `_state` from T08c.

```python


def test_patch_explicit_keyword_creates_that_rule(client, user):
    login(client, user)
    food = _category_id("Food & Dining")
    ids = _kwik_rows()
    res = _patch(client, ids["t2"], category_id=food, apply_to_similar=True, keyword="kwik")
    assert res.status_code == 200
    con = connect()
    try:
        rule = con.execute(
            "SELECT keyword, category_id FROM rules WHERE id = ?", (res.json()["rule_id"],)
        ).fetchone()
        assert (rule["keyword"], rule["category_id"]) == ("KWIK", food)
    finally:
        con.close()


def test_patch_twice_reuses_the_same_rule(client, user):
    login(client, user)
    food = _category_id("Food & Dining")
    ids = _kwik_rows()
    r1 = _patch(client, ids["t2"], category_id=food, apply_to_similar=True).json()
    r2 = _patch(client, ids["t3"], category_id=food, apply_to_similar=True).json()
    assert r1["rule_id"] == r2["rule_id"]
    con = connect()
    try:
        n = con.execute(
            "SELECT COUNT(*) AS c FROM rules WHERE keyword = 'KWIK TRIP' AND category_id = ?",
            (food,),
        ).fetchone()["c"]
        assert n == 1
    finally:
        con.close()


def test_later_import_uses_the_learned_rule(client, user):
    login(client, user)
    food = _category_id("Food & Dining")
    ids = _kwik_rows()
    _patch(client, ids["t2"], category_id=food, apply_to_similar=True)
    acct = client.post(
        "/api/accounts", json={"name": "Joint Checking", "type": "checking", "shared": True}
    ).json()["id"]
    csv = b"DATE,DESCRIPTION,AMOUNT\n10/05/2026,KWIK TRIP #999 MINNEAPOLIS,-12.00\n"
    res = client.post(
        f"/api/accounts/{acct}/import", files={"file": ("k.csv", csv, "text/csv")}
    )
    assert res.status_code == 200
    con = connect()
    try:
        row = con.execute(
            "SELECT category_id, category_source FROM transactions "
            "WHERE account_id = ? AND description LIKE 'KWIK TRIP #999%'",
            (acct,),
        ).fetchone()
        assert (row["category_id"], row["category_source"]) == (food, "rule")
    finally:
        con.close()
```

These tests are expected to PASS right away (T08c already did the work), so there is no red step. Run `make test`.
If one fails, do NOT change application code: write the test name and the assertion error under Blockers in PROGRESS.md and stop.
(The new rule wins the import because it has the same keyword length as the seed `KWIK TRIP` -> Transport rule and a higher id.)

PROGRESS.md: tick T08d, add a Log line. Commit. Touch nothing else.
