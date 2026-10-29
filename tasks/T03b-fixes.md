# T03b — Fixes from review of T02/T03
Needs: T03
Files: app/auth.py, app/routers/auth.py, app/routers/accounts.py, tests/test_auth.py

Do:
1. Login lockout must come BEFORE the password check. Add `auth.is_locked(ip) -> bool` (True when ≥ `FAIL_LIMIT` failures
   recorded for that ip inside the `FAIL_WINDOW`). In `POST /api/login`: if `is_locked(ip)` → 429 immediately, even if the password is correct.
   Only failed attempts are recorded (`_bump_failure` no longer raises). Success clears the counter. Keep the same constants.
2. Update tests in `tests/test_auth.py`: 5 wrong passwords → 401 each; the next attempt WITH THE CORRECT password → 429;
   after the window expires (move the stored window start back 301 s) the correct password → 200.
3. `routers/accounts.py` `set_balance`: replace the `return _view(...) if False else _view(...)` line with a plain
   `return _view(row, total, _totals(con, account_id)[1])`. No behaviour change.
4. Do NOT add other features. Client IP stays `request.client.host` (production runs uvicorn with `--proxy-headers`, see assets/Dockerfile).

Verify: `make test` passes (all earlier tests still green).
