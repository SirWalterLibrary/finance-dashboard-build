# T07d — wire rules into import and into suggested_keyword
Needs: T07c. Self-contained: do NOT read SPEC.md.
Files: app/routers/imports.py, app/routers/transactions.py, tests/test_import_api.py, tests/test_transactions.py
Read only: those four files.

1. `imports.py`: replace the `try: from app import rules / except ImportError` block with a plain `from app import rules`.
   After inserting, call `rules.apply_rules(con, tx_ids)` when `tx_ids` is not empty (keep it where it is now).
2. `transactions.py`: every item's `suggested_keyword` must be `rules.merchant_key(description)` instead of `""`.
3. Update the OLD tests that now change on purpose (do not weaken anything else):
   - `tests/test_transactions.py`: the assertion that `suggested_keyword == ""` -> compare with `rules.merchant_key(item["description"])`.
   - `tests/test_import_api.py`: the assertion that all imported rows are `Uncategorized`/`none` is no longer true. New expectations:
     `wf_sample.csv` (10 rows): 8 get source `rule` -> `SAMS CLUB #6312` Transport, `KWIK TRIP` Transport, `PAYROLL` Income,
     `ZELLE TO MAMA` Family Support, `AMERICAN EXPRESS ACH PMT` Credit Card Payment, the two `WM SUPERCENTER` rows Groceries,
     `INTERNATIONAL PURCHASE TRANSACTION FEE` Fees; the `eBay` and `CAREEM` rows stay `none`/Uncategorized.
     `amex_sample.csv` into a credit account (8 rows): 4 get `rule` -> `SAMS CLUB.COM` Shopping, `WAL-MART` Groceries,
     `AUTOPAY PAYMENT` Credit Card Payment, `SAM'S CLUB FUEL` Transport; the 3 `DELTA` rows and `PARKWHIZ` stay `none`.
   Counts (`added`, `skipped_duplicates`, `skipped_pending`) are unchanged.

Verify: `make test` (all earlier tests green, with only the changes listed above). Touch nothing else.
