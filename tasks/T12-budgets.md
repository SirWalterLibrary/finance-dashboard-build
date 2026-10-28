# T12 — Budgets API
Needs: T09
Files: app/budgets.py, app/routers/budgets.py, app/main.py, tests/test_budgets.py

Do:
1. `budgets.py`: `month_status(conn, owner_clause, month, owner_for_budgets)` → list per SPEC. Includes every EXPENSE category that has a
   budget, PLUS expense categories with spending but no budget (`id:null, limit_cents:0, status:"ok", pct:0`). `spent_cents` uses the same
   spending definition as the summary for that calendar month and scope.
2. Endpoints: `GET /api/budgets`, `PUT /api/budgets` (upsert by owner+category; `scope=combined` → 400), `DELETE /api/budgets/{id}` (404 if not visible).
   In `combined` scope GET merges joint+personal budgets by summing limits per category.
3. Tests: pct/status boundaries (79→ok, 80→warn, 100→warn, 101→over); upsert replaces; other user's personal budget invisible; month isolation.

Verify: `make test`.
