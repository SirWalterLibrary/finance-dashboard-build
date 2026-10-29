"""T05: POST /api/accounts/{id}/import."""
import pathlib

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
MAX_FILE_SIZE = 5 * 1024 * 1024


def _wf():
    return (
        "wf_sample.csv",
        (FIXTURES / "wf_sample.csv").read_bytes(),
        "text/csv",
    )


def _alice(client):
    from conftest import make_user, login

    make_user(client, "alice")
    login(client, "alice")


def test_import_wf_then_again(client):
    _alice(client)
    acct = client.post("/api/accounts", json={"name": "WF", "type": "checking"}).json()
    assert acct["invert_amounts"] == 0

    res = client.post(f"/api/accounts/{acct['id']}/import", files={"file": _wf()})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["added"] == 10
    assert body["skipped_pending"] == 1
    assert body["skipped_duplicates"] == 0
    assert body["errors"] == []

    # re-import: nothing new
    res = client.post(f"/api/accounts/{acct['id']}/import", files={"file": _wf()})
    assert res.status_code == 200
    body = res.json()
    assert body["added"] == 0
    assert body["skipped_duplicates"] == 10
    assert body["skipped_pending"] == 1
    assert body["errors"] == []

    # stored rows: all "Uncategorized", source none
    from app.db import connect

    con = connect()
    try:
        assert con.execute("SELECT COUNT(*) AS c FROM transactions").fetchone()["c"] == 10
        pairs = {
            (r["n"], r["s"])
            for r in con.execute(
                "SELECT c.name AS n, t.category_source AS s FROM transactions t "
                "JOIN categories c ON c.id = t.category_id"
            )
        }
    finally:
        con.close()
    assert pairs == {("Uncategorized", "none")}


def test_import_amex_credit_inverts(client):
    _alice(client)
    acct = client.post("/api/accounts", json={"name": "AMEX", "type": "credit"}).json()
    assert acct["invert_amounts"] == 1

    res = client.post(
        f"/api/accounts/{acct['id']}/import",
        files={"file": ("amex_sample.csv", (FIXTURES / "amex_sample.csv").read_bytes(), "text/csv")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["added"] == 8
    assert body["skipped_duplicates"] == 0
    assert body["skipped_pending"] == 0
    assert body["errors"] == []

    from app.db import connect

    con = connect()
    try:
        amounts = [
            r["a"]
            for r in con.execute("SELECT amount_cents AS a FROM transactions")
        ]
    finally:
        con.close()
    # purchases are money out, the autopay is money in (signs flipped once)
    assert -72054 in amounts and 70497 in amounts and -7138 in amounts and -2014 in amounts
    # 8 rows stored: the two identical DELTA rows differ only by dedupe index
    assert len(amounts) == 8


def test_import_other_users_personal_account_404(client):
    from conftest import make_user, login

    make_user(client, "alice")
    make_user(client, "bob")
    login(client, "alice")
    acct = client.post(
        "/api/accounts", json={"name": "A Only", "type": "checking"}
    ).json()["id"]

    login(client, "bob")
    res = client.post(f"/api/accounts/{acct}/import", files={"file": _wf()})
    assert res.status_code == 404
    # nonexistent account also 404
    res = client.post("/api/accounts/99999/import", files={"file": _wf()})
    assert res.status_code == 404
    # nothing was written
    from app.db import connect

    con = connect()
    try:
        assert (
            con.execute(
                "SELECT COUNT(*) AS c FROM transactions WHERE account_id = ?", (acct,)
            ).fetchone()["c"]
            == 0
        )
    finally:
        con.close()


def test_import_missing_file_422(client):
    _alice(client)
    acct = client.post("/api/accounts", json={"name": "X", "type": "checking"}).json()["id"]
    res = client.post(f"/api/accounts/{acct}/import")
    assert res.status_code == 422


def test_import_invalid_utf8_400(client):
    _alice(client)
    acct = client.post("/api/accounts", json={"name": "X", "type": "checking"}).json()["id"]
    res = client.post(
        f"/api/accounts/{acct}/import",
        files={"file": ("bad.csv", b"\xff\xfe\x00bad", "text/csv")},
    )
    assert res.status_code == 400, res.text
    from app.db import connect

    con = connect()
    try:
        assert con.execute("SELECT COUNT(*) AS c FROM transactions").fetchone()["c"] == 0
    finally:
        con.close()


def test_import_too_large_413(client):
    _alice(client)
    acct = client.post("/api/accounts", json={"name": "Big", "type": "checking"}).json()["id"]
    res = client.post(
        f"/api/accounts/{acct}/import",
        files={"file": ("big.csv", b"DATE,DESCRIPTION,AMOUNT\n" + b"x" * (MAX_FILE_SIZE + 1), "text/csv")},
    )
    assert res.status_code == 413
