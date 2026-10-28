# T09 — Summary API
Needs: T07
Files: app/summary.py, app/routers/summary.py, app/main.py, tests/test_summary.py

Do:
1. `summary.py` (pure SQL/Python, no FastAPI): `build_summary(conn, owner_clause, from_, to)` returning the exact shape in SPEC.
   Follow SPEC "Core definitions": spending = expense kind only; transfers/savings excluded; refunds reduce spending;
   income = income kind only; `reimbursed_cents` from `reimbursement` kind (never income); `spending_cents = gross − reimbursed`; by_category stays gross; `saved_cents` per SPEC; `pct` of spending (1 decimal), categories sorted by cents desc, zero rows omitted.
   `by_month` sorted ascending; `uncategorized_count` counts category "Uncategorized".
2. `GET /api/summary` — default range = last 6 months if from/to missing.
3. Tests with hand-built transactions: AMEX payment (Credit Card Payment) and Savings transfer are NOT in spending;
   a refund reduces its category; a reimbursement deposit lowers `spending_cents` but not `by_category` and not `income_cents`; income only from Income category; by_month totals equal overall totals;
   personal tx invisible in joint scope.

Verify: `make test`.
