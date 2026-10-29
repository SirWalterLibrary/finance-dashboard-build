# PROGRESS  (agent updates this; human reads it)

## Tasks
- [x] T00 Scaffold
- [x] T01 Database + seed
- [x] T02 Auth
- [x] T03 Scope + accounts API
- [x] T03b Fixes from T02/T03 review
- [x] T04 CSV parser
- [x] T05 Import endpoint
- [x] T06 Transactions API
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
- T05: import endpoint — app/routers/imports.py (POST /api/accounts/{id}/import multipart `file`: >5 MB -> 413, account must be visible else 404, decode utf-8-sig, parse_csv(invert=account.invert_amounts), INSERT OR IGNORE with category Uncategorized + source 'none', optional app.rules.apply_rules(conn, tx_ids) guarded by try/ImportError until T07, returns {added, skipped_duplicates, skipped_pending, errors}); wired in app/main.py; tests/test_import_api.py (wf_sample into checking -> added 10 / pending 1, re-import -> added 0 / dups 10, all rows Uncategorized+none; amex into credit -> added 8, amounts negated once (720.54->-72054, autopay +70497); bob -> alice's personal account 404 + nonexistent 404 with no rows written; missing file 422; 5 MB+ file 413) — `make test` 38 passed.
- T06: transactions API — app/routers/transactions.py (GET /api/transactions: shared WHERE builder for count+page, scope via app.scope.owner_clause (invalid -> 400), filters account_id/category_id/q (case-insensitive substring, %-escaped LIKE)/from/to (inclusive ISO dates, `from_` aliased to query param `from`)/direction=in|out by sign/source none|rule|llm|manual, ORDER BY date DESC, id DESC, limit 50 capped at 500, returns {items,total} with the SPEC item shape + suggested_keyword="" until T07; PATCH /api/transactions/{id} {category_id} -> category_source='manual' inside one transaction, unknown id / unknown category / not visible -> 404; DELETE /api/transactions/{id} -> 200 {ok:true}, invisible/unknown -> 404); wired in app/main.py before static mount; tests/test_transactions.py (auth 401; item shape exact keys + order/total; all filters incl. 400 on bad direction/source; pagination non-overlapping pages with stable total; scope joint/personal/combined visibility incl. no personal leak via combined + bogus scope 400; patch -> manual + 404s + 422 on empty body; delete; bob: alice's personal tx -> PATCH/DELETE 404, row untouched, invisible in every scope) — `make test` 46 passed.
