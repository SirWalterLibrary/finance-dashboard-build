"""T11 tests: LLM categorizer (app/llm.py) + /api/categorize/run LLM step.

`llm.classify` is always monkeypatched — no real server is ever called.
The one payload test patches `httpx.post` instead, to inspect the exact
request JSON.
"""
from contextlib import contextmanager

from conftest import login

import app.llm as llm
from app.db import connect
from app.scope import owner_clause


@contextmanager
def db():
    con = connect()
    try:
        yield con
    finally:
        con.close()


def _cat_id(con, name):
    return con.execute(
        "SELECT id FROM categories WHERE name = ?", (name,)
    ).fetchone()["id"]


def _tx(con, acct, desc, amount_cents, key, source="none", cat=None):
    with con:
        cur = con.execute(
            "INSERT INTO transactions (account_id, date, description, "
            "amount_cents, category_id, category_source, dedupe_key) "
            "VALUES (?,?,?,?,?,?,?)",
            (acct, "2024-01-05", desc, amount_cents,
             cat or _cat_id(con, "Uncategorized"), source, key),
        )
    return cur.lastrowid


def _setup(client, user, specs):
    """specs: (desc, amount, key, source, cat-name|None) -> (user_id, ids)."""
    login(client, user)
    acct = client.post(
        "/api/accounts",
        json={"name": "Joint Checking", "type": "checking", "shared": True},
    ).json()["id"]
    with db() as con:
        uid = con.execute(
            "SELECT id FROM users WHERE username = ?", (user,)
        ).fetchone()["id"]
        ids = []
        for desc, amt, key, source, cat in specs:
            ids.append(_tx(con, acct, desc, amt, key, source,
                           _cat_id(con, cat) if cat else None))
    return uid, ids


def _run(client):
    r = client.post("/api/categorize/run", json={"scope": "joint"})
    assert r.status_code == 200
    return r.json()


def _row(con, tx_id):
    return con.execute(
        "SELECT category_id, category_source, category_confidence "
        "FROM transactions WHERE id = ?", (tx_id,)
    ).fetchone()


def _none_left(con, user_id):
    clause, params = owner_clause("joint", user_id, "a.owner_user_id")
    return con.execute(
        "SELECT t.id FROM transactions t JOIN accounts a "
        "ON a.id = t.account_id "
        f"WHERE t.category_source = 'none' AND {clause} ORDER BY t.id",
        params,
    ).fetchall()


def test_valid_answer_applied_and_confidence_stored(client, user, monkeypatch):
    uid, (t1, t2) = _setup(client, user, [
        ("GROCERY STORE #1", -1500, "k1", "none", None),
        ("BIG BOX RETAIL #2", -700, "k2", "none", None),
    ])

    calls = []

    def fake(d, a, criteria):
        calls.append((d, a))
        assert "Food & Dining" in criteria  # criteria keyed by name
        return ("Food & Dining", 0.93)

    monkeypatch.setattr(llm, "classify", fake)
    body = _run(client)
    assert (body["by_llm"], body["left"], body["llm_available"]) == (2, 0, True)
    assert len(calls) == 2  # one call per (merchant_key, sign) group

    with db() as con:
        food = _cat_id(con, "Food & Dining")
        for tx_id in (t1, t2):
            row = _row(con, tx_id)
            assert (row["category_source"], row["category_id"]) == ("llm", food)
            assert abs(row["category_confidence"] - 0.93) < 1e-9
        assert _none_left(con, uid) == []


def test_unknown_category_ignored(client, user, monkeypatch):
    _, (t1,) = _setup(client, user,
                      [("GROCERY STORE #9", -500, "k9", "none", None)])
    monkeypatch.setattr(llm, "classify", lambda d, a, c: ("Nope Cat", 0.99))
    body = _run(client)
    assert (body["by_llm"], body["left"], body["llm_available"]) == (0, 1, True)
    with db() as con:
        row = _row(con, t1)
        assert row["category_source"] == "none"
        assert row["category_confidence"] is None


def test_repeated_merchant_classify_called_once(client, user, monkeypatch):
    uid, ids = _setup(client, user, [
        ("GROCERY STORE #1", -1500, "g1", "none", None),
        ("GROCERY STORE #2", -2500, "g2", "none", None),
        ("GROCERY STORE #3", -500, "g3", "none", None),
        ("MIXER MART #4", 1200, "m1", "none", None),
    ])
    calls = []

    def fake(d, a, c):
        calls.append((d, a))
        return ("Food & Dining", 0.9)

    monkeypatch.setattr(llm, "classify", fake)
    body = _run(client)
    assert body["by_llm"] == 4
    assert len(calls) == 2  # one call per group, not per row

    with db() as con:
        for tx_id in ids:
            assert _row(con, tx_id)["category_source"] == "llm"
        assert _none_left(con, uid) == []


def test_first_call_none_means_unavailable_and_no_changes(client, user,
                                                          monkeypatch):
    _, (t1, t2) = _setup(client, user, [
        ("GROCERY STORE #7", -900, "k7", "none", None),
        ("BIG BOX RETAIL #8", -1100, "k8", "none", None),
    ])
    monkeypatch.setattr(llm, "classify", lambda d, a, c: (None, None))
    body = _run(client)
    assert (body["by_llm"], body["left"], body["llm_available"]) == (0, 2, False)
    with db() as con:
        for tx_id in (t1, t2):
            row = _row(con, tx_id)
            assert row["category_source"] == "none"
            assert row["category_confidence"] is None


def test_manual_rows_never_sent(client, user, monkeypatch):
    _, (t1, t2) = _setup(client, user, [
        ("GROCERY STORE #11", -1500, "km1", "manual", None),
        ("GROCERY STORE #12", -1500, "km2", "none", None),
    ])
    sent = []

    def fake(d, a, c):
        sent.append(d)
        return ("Food & Dining", 0.88)

    monkeypatch.setattr(llm, "classify", fake)
    body = _run(client)
    assert (body["by_llm"], body["left"], body["llm_available"]) == (1, 0, True)
    assert sent == ["GROCERY STORE #12"]  # only the 'none' row

    with db() as con:
        row = _row(con, t1)
        assert row["category_source"] == "manual"
        assert row["category_confidence"] is None


def test_build_criteria_includes_example_text(client, user):
    login(client, user)
    acct = client.post(
        "/api/accounts",
        json={"name": "Joint Checking", "type": "checking", "shared": True},
    ).json()["id"]
    with db() as con:
        food = _cat_id(con, "Food & Dining")
        con.execute(
            "UPDATE categories SET description = 'Nice food places' "
            "WHERE id = ?", (food,),
        )
        con.commit()
        for i in range(1, 6):
            _tx(con, acct, f"KWIK TRIP #{i}", -100 * i, f"b{i}",
                "manual", food)
        # a manual row for a different category must not leak in
        _tx(con, acct, "OTHER PLACE #9", -100, "bx", "manual",
            _cat_id(con, "Transport"))
        criteria = llm.build_criteria(con)

    assert "Nice food places" in criteria["Food & Dining"]
    assert "Examples: KWIK TRIP" in criteria["Food & Dining"]
    assert "OTHER PLACE" not in criteria["Food & Dining"]
    assert "Uncategorized" in criteria  # description-only entries remain


def test_payload_shape(monkeypatch):
    import httpx

    def fake_post(url, json=None, timeout=None, **kw):
        fake_post.url, fake_post.json, fake_post.timeout = url, json, timeout

        class R:
            def raise_for_status(self):
                return None

            def json(self):
                return {"answers": {"category": {
                    "choice": "Food & Dining", "confidence": 0.9,
                }}}
        return R()

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setenv("LLM_URL", "http://127.0.0.1:11434/v1/systemone")
    monkeypatch.setenv("LLM_MODEL", "d3:9b")

    choice, conf = llm.classify("GROCERY STORE #1", -1500,
                                {"Food & Dining": "Nice food places"})
    assert (choice, conf) == ("Food & Dining", 0.9)

    sent = fake_post.json
    assert fake_post.url == "http://127.0.0.1:11434/v1/systemone"
    assert fake_post.timeout == 30
    assert sent["model"] == "d3:9b"
    assert "state" in sent
    q = sent["questions"]["category"]
    assert {"type", "instructions", "criteria"} <= set(q)


def test_classify_exceptions_return_none(monkeypatch):
    import httpx

    monkeypatch.setenv("LLM_URL", "http://127.0.0.1:11434/v1/systemone")
    monkeypatch.setenv("LLM_MODEL", "d3:9b")

    def boom(url, json=None, timeout=None, **kw):
        raise httpx.ConnectError("no server", request=None)

    monkeypatch.setattr(httpx, "post", boom)
    assert llm.classify("ANYTHING", -1, {"A": "a"}) == (None, None)

    def bad_json(url, json=None, timeout=None, **kw):
        class R:
            def raise_for_status(self):
                return None

            def json(self):
                raise ValueError("not json")
        return R()

    monkeypatch.setattr(httpx, "post", bad_json)
    assert llm.classify("ANYTHING", -1, {"A": "a"}) == (None, None)
