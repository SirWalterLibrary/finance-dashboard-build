# T03 — Scope helper + accounts API
Needs: T02
Files: app/scope.py, app/routers/accounts.py, app/main.py, tests/test_accounts.py

Do:
1. `scope.py`: `owner_ids(scope, user_id)` → list of owners (may contain `None`) per SPEC "Scope".
   `owner_clause(scope, user_id, column="owner_user_id")` → `(sql_fragment, params)` handling NULL correctly (`IS NULL OR = ?`).
   Invalid scope → ValueError (router maps to 400).
2. `routers/accounts.py`: GET/POST/DELETE per SPEC. `shared=true` → owner NULL else current user. `invert_amounts = 1` when type=='credit'.
   `balance_cents` = opening + sum(tx). Add `PUT /api/accounts/{id}/balance {current_balance_cents}` → sets `opening_balance_cents = current − sum(tx)`. DELETE of an account not visible to the user → 404 (do not allow combined-scope leaks).
3. Tests (IMPORTANT privacy tests):
   - user A creates personal account; user B with scope=personal/combined/joint never sees it; B gets 404 on DELETE.
   - joint account visible to both. Default scope is joint. `scope=bogus` → 400.
   - `balance_cents` correct with opening balance; after PUT balance, `balance_cents` equals the given value.

Verify: `make test`.
