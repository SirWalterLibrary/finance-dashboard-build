# T05 — Import endpoint
Needs: T03, T04
Files: app/routers/imports.py, app/main.py, tests/test_import_api.py

Do:
1. `POST /api/accounts/{id}/import` (multipart `file`, max 5 MB → 413). Account must be visible to the user (else 404).
2. Decode UTF-8 (with BOM tolerance). Call `parse_csv(text, invert=account.invert_amounts)` (returns rows, errors, skipped_pending).
3. Insert with `INSERT OR IGNORE`; every new row gets category "Uncategorized", source `none`. Then apply rules via
   `rules.apply_rules(conn, tx_ids)` IF that module exists (T07 adds it; until then skip — T07 will wire it in).
4. Return `{added, skipped_duplicates, skipped_pending, errors}`.
5. Tests: import `wf_sample.csv` to a checking account → added 10, skipped_pending 1; import again → added 0, skipped_duplicates 10;
   AMEX tsv into a credit account → amounts negated; another user's personal account → 404; file missing → 422.

Verify: `make test`.
