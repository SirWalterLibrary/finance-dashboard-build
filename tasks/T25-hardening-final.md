# T25 — Hardening + final check
Needs: all
Files: tests/test_security.py, app/main.py, PROGRESS.md

Do:
1. Add response header middleware: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` on `/api/*`.
2. Tests: every `/api/*` route except login/health returns 401 without a cookie (iterate `app.routes`); scope-leak test matrix
   (user B cannot read or modify user A's personal accounts, transactions, budgets, goals, events via any endpoint); security headers present.
3. Grep the code for `print(` / logging of descriptions or amounts; remove any.
4. In PROGRESS.md write a "Final status" section: what works, what is skipped (e.g. T15), known gaps.

Verify: `make test` and `make check-js` pass.
