# PROGRESS  (agent updates this; human reads it)

## Tasks
- [x] T00 Scaffold
- [ ] T01 Database + seed
- [ ] T02 Auth
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
