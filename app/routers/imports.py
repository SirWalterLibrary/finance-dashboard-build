"""Import endpoint (T05): POST /api/accounts/{id}/import (multipart `file`)."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.auth import current_user
from app.csvparse import parse_csv
from app.db import connect

try:  # added by T07; until then imports skip rule application
    from app import rules
except ImportError:
    rules = None

router = APIRouter(prefix="/api", tags=["imports"])

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB


def _require_visible(con, account_id: int, user: dict) -> dict:
    """Fetch the account; 404 if missing or the user must not see it."""
    row = con.execute(
        "SELECT * FROM accounts WHERE id = ?", (account_id,)
    ).fetchone()
    if row is None or row["owner_user_id"] not in (None, user["id"]):
        raise HTTPException(404, "account not found")
    return row


@router.post("/accounts/{account_id}/import")
def import_file(account_id: int, file: UploadFile, user: dict = Depends(current_user)):
    data = file.file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "file too large")
    con = connect()
    try:
        account = _require_visible(con, account_id, user)
        text = data.decode("utf-8-sig")  # UTF-8, BOM tolerated
        rows, errors, skipped_pending = parse_csv(
            text, invert=account["invert_amounts"]
        )
        cat = con.execute(
            "SELECT id FROM categories WHERE name = 'Uncategorized'"
        ).fetchone()
        added = skipped_duplicates = 0
        tx_ids = []
        with con:
            for r in rows:
                cur = con.execute(
                    "INSERT OR IGNORE INTO transactions "
                    "(account_id, date, description, amount_cents, category_id, "
                    "category_source, dedupe_key) "
                    "VALUES (?,?,?,?,?, 'none', ?)",
                    (
                        account_id,
                        r["date"],
                        r["description"],
                        r["amount_cents"],
                        cat["id"],
                        r["dedupe_key"],
                    ),
                )
                if cur.rowcount:
                    added += 1
                    tx_ids.append(cur.lastrowid)
                else:
                    skipped_duplicates += 1
        if tx_ids and rules is not None:
            rules.apply_rules(con, tx_ids)
    finally:
        con.close()
    return {
        "added": added,
        "skipped_duplicates": skipped_duplicates,
        "skipped_pending": skipped_pending,
        "errors": errors,
    }
