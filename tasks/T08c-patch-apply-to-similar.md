# T08c — PATCH /api/transactions/{id} with apply_to_similar
Needs: T08b. Self-contained: do NOT read SPEC.md.
Files: app/routers/transactions.py, tests/test_correction.py (add tests)
Read only: app/routers/transactions.py (function `patch_transaction`, class `PatchIn`, `_item`), app/rules.py (the signatures of `ensure_rule`, `relabel_similar`, `merchant_key`), tests/test_correction.py, and the existing patch test in tests/test_transactions.py (it must keep passing UNCHANGED).

1. `PatchIn` gets `apply_to_similar: bool = False` and `keyword: str | None = None`.
2. In `patch_transaction`, keep the current manual UPDATE and 404 logic. Do everything inside ONE `with con:` block so that an HTTPException raised inside it rolls the whole change back.
3. After the manual update, if `body.apply_to_similar`:
   - read the transaction's `description`; `kw = norm_desc(body.keyword)` if `body.keyword` is given, otherwise `rules.merchant_key(description)`.
   - if `kw` is empty -> `HTTPException(400, "keyword must not be empty")` (the manual change is rolled back).
   - `rule_id = rules.ensure_rule(con, kw, body.category_id)`
   - `n = rules.relabel_similar(con, user["id"], kw, body.category_id, tx_id)`
   - `updated = 1 + n`
   otherwise `rule_id = None`, `updated = 1`.
   (Import `norm_desc` from `app.csvparse`. `ensure_rule` and `relabel_similar` must not be given their own commit; the outer `with con:` commits.)
4. Response: the SAME item dict as today (`_item(...)`) plus two extra keys `updated` and `rule_id`. Do not change `_item` itself, so the list endpoint stays the same.

Tests FIRST (add to tests/test_correction.py; insert rows with plain SQL in a joint account; use the `user` fixture and `login`):
- three KWIK TRIP rows (source none), one manual KWIK TRIP row, one SAMS CLUB row. PATCH one KWIK TRIP row to `Food & Dining` with `{"category_id": X, "apply_to_similar": true}` -> response `updated == 3`, `rule_id` is an int, a rule `KWIK TRIP` -> Food & Dining exists, the other two none-rows are Food & Dining with source `rule`, the manual row and the SAMS CLUB row are unchanged, and the patched row has source `manual`.
- the same PATCH without `apply_to_similar` -> only that row changes, `updated == 1`, `rule_id is None`, no new rule exists.
- `{"apply_to_similar": true, "keyword": "  "}` -> 400 and the row is NOT changed (still its old category and source).
- explicit `"keyword": "kwik"` works and creates a rule with keyword `KWIK`.
- PATCH again with the same body -> the same `rule_id` and still only one such rule.
- a later import: after the correction, import a small CSV (`DATE,DESCRIPTION,AMOUNT` + one row `10/05/2026,KWIK TRIP #999 MINNEAPOLIS,-12.00`) into a joint account with `POST /api/accounts/{id}/import`; the stored row is Food & Dining with source `rule` (the new rule has the same keyword length as the seed `KWIK TRIP` -> Transport rule and is newer, so it wins).

Verify: `make test` (all earlier tests green, existing patch tests unchanged). Touch nothing else (apart from a Log line in PROGRESS.md). Tick T08c.
