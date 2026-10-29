# PROGRESS  (agent updates this; human reads it)

## Tasks
- [x] T00 Scaffold
- [x] T01 Database + seed
- [x] T02 Auth
- [x] T03 Scope + accounts API
- [x] T03b Fixes from T02/T03 review
- [x] T04 CSV parser
- [ ] T05 Import endpoint
- [ ] T06 Transactions API
- [ ] T07 Categories + rules engine
- [ ] T08 Manual correction learns
- [ ] T09 Summary API
- [ ] T10 Demo seed script
- [ ] T11 LLM categorizer (Ollama)
- [ ] T12 Budgets API
- [ ] T13 Goals API + simulate
- [ ] T14 Forecast API
- [ ] T15 AI explain (optional)
- [ ] T16 Frontend shell + login + scope toggle
- [ ] T17 Accounts + import page
- [ ] T18 Transactions page
- [ ] T19 Home page
- [ ] T20 Budget page
- [ ] T21 Goals page
- [ ] T22 Forecast page
- [ ] T23 Rules page + AI categorize button
- [ ] T24 Docker + deploy + backup
- [ ] T25 Hardening + final check

## Blockers
(none)

## User Checks (human verifies in browser)
(none yet)

## Log
- T00: scaffold done — assets copied, git init, app/config.py (env at call time), app/main.py (create_app + /api/health, static mount last), tests/conftest.py + test_health.py pass; `make dev` + curl verified.
- T01: database + seed — copied assets/schema.sql + assets/seed/*.json into app/; app/db.py (connect with WAL/FKs, init_db runs schema then seeds categories+rules only when categories is empty); create_app() calls init_db(); tests/test_db.py (9 tables, seed counts match JSON, idempotent re-init, Uncategorized=expense) pass.
- T02: auth — app/auth.py (scrypt hash salt$hash, token_urlsafe sessions expiring in 30 days, current_user dependency w/ expired-session pruning, in-memory rate limit 5/IP/5min), app/routers/auth.py (login/logout/me; sid cookie HttpOnly SameSite=Lax, secure per COOKIE_SECURE), scripts/create_user.py (getpass, works standalone/in docker), conftest gains make_user/login/user/user2; tests/test_auth.py (5 required + 3 extra) pass, live uvicorn smoke OK.
- T03: scope + accounts — app/scope.py (owner_ids per SPEC scope rules; owner_clause NULL-safe, invalid scope -> ValueError -> 400), app/routers/accounts.py (GET/POST/DELETE; shared -> owner NULL else current user; invert_amounts=1 for credit; balance_cents = opening + sum(tx); tx_count; PUT /api/accounts/{id}/balance {current_balance_cents} sets opening = current - sum(tx); GET-by-id/PUT/DELETE of a not-visible account -> 404, no combined-scope leaks), included in main.py; tests/test_accounts.py (scope helpers incl. NULL-safety, privacy: A's personal account hidden from B in every scope + 404 DELETE by B, joint visible to both, default scope joint, bogus scope 400, POST defaults/invert_amounts/validation, balance math with opening + tx + PUT balance, delete cascade) — `make test` 21 passed.
- T03b: T02/T03 review fixes — login lockout now precedes the password check: app/auth.py gains is_locked(ip) (>= FAIL_LIMIT failures within FAIL_WINDOW) and _bump_failure no longer raises (only failed attempts recorded; success still clears the counter; same constants); POST /api/login returns 429 before touching the password when locked; tests/test_auth.py: test_sixth_bad_login_429 -> test_lockout_after_five_failures_429 (wrong-pw 429 kept) + new test_lockout_precedes_password_check (5 wrong -> 401 each, then CORRECT password -> 429, after 301 s window shift correct password -> 200); accounts.py set_balance already used the plain `return _view(row, total, n)` (no `if False` present) so item 3 needed no change; `make test` 22 passed (new test verified red against pre-fix code).
- T04: CSV parser — assets/fixtures/* copied to tests/fixtures/; app/csvparse.py (norm_desc = uppercase + collapse whitespace + drop apostrophes per SPEC; parse_csv(text,invert)->(rows,errors,skipped_pending): sniff comma/tab, required header matched case-insensitively, missing column -> "missing column X" + no rows, MM/DD/YYYY via strptime (unpadded ok) -> ISO, Decimal amounts with $/, stripped -> cents then negated if invert, STATUS column -> only posted kept + count, bad rows skipped and reported as "row N: reason", dedupe_key = sha1(f"{date}|{amount_cents}|{norm_desc}|{n}") with occurrence index n per SPEC); tests/test_csvparse.py covers wf_sample (10 rows + 1 pending, WM dup keys differ, eBay backslash, SAM'S->SAMS), amex_sample inverted (720.54->-72054, -704.97->+70497, DELTA dup keys, quoted PARKWHIZ comma), tab_sample (2 rows, unpadded dates), deterministic keys, missing column, bad date/amount non-fatal, status filtering, extra columns ignored, $/comma amounts — `make test` 33 passed.
