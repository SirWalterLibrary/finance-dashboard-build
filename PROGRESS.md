# PROGRESS  (agent updates this; human reads it)

## Tasks
- [x] T00 Scaffold
- [x] T01 Database + seed
- [x] T02 Auth
- [ ] T03 Scope + accounts API
- [ ] T04 CSV parser
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
