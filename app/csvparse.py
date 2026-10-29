"""CSV import parser (pure logic, no I/O beyond the text given).

See SPEC.md "Import dedupe" for the dedupe_key and norm_desc rules.
"""
import csv
import hashlib
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

REQUIRED = ("date", "description", "amount")


def norm_desc(s):
    """Uppercase, remove apostrophes, collapse whitespace (SPEC.md)."""
    return " ".join(s.split()).upper().replace("'", "")


def _sniff_delimiter(header_line):
    return "\t" if "\t" in header_line else ","


def _dedupe_key(date, amount_cents, description, seen):
    base = f"{date}|{amount_cents}|{norm_desc(description)}|"
    n = seen.get(base, 0)
    seen[base] = n + 1
    return hashlib.sha1(f"{base}{n}".encode("utf-8")).hexdigest()


def parse_csv(text, invert):
    """Parse a bank/credit-card CSV export.

    Returns (rows, errors, skipped_pending).
    rows: dicts with date (ISO), description, amount_cents, dedupe_key.
    errors: list of "row N: reason" strings. Bad rows are skipped, never fatal.
    skipped_pending: rows skipped because STATUS != posted (0 if no STATUS col).
    """
    text = text.replace("\r\n", "\n").lstrip("\ufeff")
    lines = text.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return [], [], 0
    delimiter = _sniff_delimiter(lines[0])

    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    raw_rows = list(reader)
    if not raw_rows:
        return [], [], 0

    header = [h.strip().upper() for h in raw_rows[0]]
    col = {}
    for i, name in enumerate(header):
        col.setdefault(name, i)
    missing = [name for name in REQUIRED if name.upper() not in col]
    if missing:
        return [], [f"row 1: missing column {missing[0].upper()}"], 0

    rows, errors, skipped_pending = [], [], 0
    seen = {}
    for lineno, record in enumerate(raw_rows[1:], start=2):
        if not record or all(not c.strip() for c in record):
            continue
        if col.get("STATUS") is not None:
            status = record[col["STATUS"]].strip() if len(record) > col["STATUS"] else ""
            if status.upper() != "POSTED":
                skipped_pending += 1
                continue

        raw_date = record[col["DATE"]].strip() if len(record) > col["DATE"] else ""
        description = " ".join(
            record[col["DESCRIPTION"]].split()) if len(record) > col["DESCRIPTION"] else ""
        raw_amount = record[col["AMOUNT"]].strip() if len(record) > col["AMOUNT"] else ""

        try:
            parsed = datetime.strptime(raw_date, "%m/%d/%Y")
        except ValueError:
            errors.append(f"row {lineno}: bad date {raw_date!r}")
            continue
        date_iso = parsed.date().isoformat()

        try:
            cents = int(Decimal(raw_amount.replace("$", "").replace(",", "")) * 100)
        except (InvalidOperation, ValueError, OverflowError):
            errors.append(f"row {lineno}: bad amount {raw_amount!r}")
            continue
        if abs(cents) > 2**62:  # beyond SQLite INTEGER range
            errors.append(f"row {lineno}: bad amount {raw_amount!r}")
            continue
        if invert:
            cents = -cents

        key = _dedupe_key(date_iso, cents, description, seen)
        rows.append({
            "date": date_iso,
            "description": description,
            "amount_cents": cents,
            "dedupe_key": key,
        })
    return rows, errors, skipped_pending
