# T06b — Fixes from review of T04–T06
Needs: T06. Self-contained: do NOT read SPEC.md.
Files: app/routers/transactions.py, app/routers/imports.py, app/csvparse.py, tests/test_transactions.py, tests/test_import_api.py, tests/test_csvparse.py
Read only: those six files.

Do these four small fixes, tests first for each:
1. **Default scope must be `joint`** (privacy: a request without `scope` must never include personal accounts).
   In `list_transactions` change `Query("combined")` to `Query("joint")`.
   Test: user A has a personal account with a transaction and a joint account with one; `GET /api/transactions` (no scope) returns only the joint one
   for A and for B. Fix any old test that relied on the old default by passing `?scope=combined` explicitly.
2. **Invalid UTF-8 upload -> 400** in `imports.py`: catch `UnicodeDecodeError` from the decode and raise `HTTPException(400, "file must be UTF-8 text")`.
   Test: upload bytes `b"\xff\xfe\x00bad"` -> 400.
3. **Odd amounts must be reported, not crash** in `csvparse.py`: in the amount parsing also catch `ValueError` and `OverflowError`
   (not only `InvalidOperation`), so `NaN`, `Infinity` and `1e999` become `row N: bad amount ...` errors.
   Test: a CSV with those three amounts plus one good row -> 1 row, 3 errors.
4. **Validate `from` / `to`** in `list_transactions`: each must parse with `datetime.date.fromisoformat` else `HTTPException(400, "from/to must be YYYY-MM-DD")`.
   Test: `?from=banana` -> 400; `?from=2026-01-01&to=2026-12-31` still works.

Do not change anything else. Verify: `make test` (all earlier tests still green).
