# T14 — Forecast API
Needs: T13
Files: app/forecast.py, app/routers/forecast.py, app/main.py, tests/test_forecast.py

Do:
1. `forecast.py` (pure): `project(start_balance, baseline_monthly, events, months, today)` → `{points, first_negative_month}` per SPEC.
   Events are plain dicts. Handle: one-time; recurring monthly; recurring yearly; `end_date`; start in the past; income vs expense.
   NO interest of any kind.
2. Endpoints: events CRUD (validate: `recurring` requires frequency; `one_time` ignores frequency/end_date) and `GET /api/forecast/projection`.
   Defaults: `baseline` from `goals.baseline_monthly`, `start_balance` from the savings balance in scope; both overridable by query params.
3. Tests with fixed `today=2026-10-01`: home down payment one-time 4000000 on 2029-06-01 shows a drop exactly in 2029-06;
   child recurring monthly 120000 from 2031-01-01 applies each month; yearly applies every 12 months; end_date stops it;
   `first_negative_month` found / null; privacy of personal events.

Verify: `make test`.
