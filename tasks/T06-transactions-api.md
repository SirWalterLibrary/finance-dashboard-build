# T06 — Transactions API
Needs: T05
Files: app/routers/transactions.py, app/main.py, tests/test_transactions.py

Do:
1. `GET /api/transactions` with all filters from SPEC. Scope filter via account owner. `q` = case-insensitive substring on description.
   `direction=in|out` by sign. Order: date DESC, id DESC. Return `{items,total}` using the SPEC item shape. `suggested_keyword` = `""` for now (T07 wires `rules.merchant_key`).
   Add filter `source=`.
2. `PATCH /api/transactions/{id}` with only `{category_id}` for now → sets category, `category_source='manual'`. (T08 adds apply_to_similar.)
3. `DELETE /api/transactions/{id}`. Both 404 when not visible.
4. Tests: filters (account, category, q, from/to, direction), pagination `total`, patch sets source manual, other user's tx → 404.

Verify: `make test`.
