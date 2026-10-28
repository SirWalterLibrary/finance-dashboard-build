# T13 — Goals API + savings + simulate
Needs: T09
Files: app/goals.py, app/routers/goals.py, app/main.py, tests/test_goals.py

Do:
1. `goals.py` (pure): `savings_summary(balance, allocated_list)`, `baseline_monthly(by_month, months, today)`, `eta(remaining, monthly, today)`.
   Follow SPEC "Math rules" exactly. Use only COMPLETE past months for the baseline (exclude the current month).
2. Endpoints: goals CRUD (scope rules per SPEC), `GET /api/savings`, `GET /api/goals/simulate`.
   Allocation rule: PATCH that would make total allocated in scope exceed savings balance → 400 `"over_allocated"`.
3. Tests: ETA math (remaining 100000, monthly 25000 → 4 months; monthly ≤0 → null; remaining 0 → today);
   `on_track` true/false/null; baseline ignores current month; over-allocation 400; privacy of personal goals.
   Use a fixed `today` argument in pure functions (no `date.today()` inside).

Verify: `make test`.
