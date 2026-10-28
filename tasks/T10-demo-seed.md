# T10 — Demo data script (fake data only)
Needs: T09
Files: scripts/seed_demo.py

Do:
1. Script (run with `DB_PATH=data/dev.db`): ensures `init_db()`, creates users `demo1`, `demo2` (password `demo`) if missing,
   a joint checking, joint savings (type savings), personal checking (demo1), AMEX credit (demo1, personal).
2. Generates ~6 months of FAKE transactions with `random.seed(1)`: biweekly paycheck, rent, utilities, groceries, fuel, dining,
   a monthly fake work-reimbursement deposit matching the AMEX payment, a monthly $500 savings transfer (Savings category), AMEX purchases and matching card payments (Credit Card Payment).
   Insert through the same dedupe/rule code paths (use `csvparse` keys or build keys directly). Apply rules afterwards.
3. Idempotent: running twice does not duplicate.

Verify: `make seed && make dev` → login as demo1/demo via `curl -c c.txt -XPOST localhost:8000/api/login -H 'content-type: application/json' -d '{"username":"demo1","password":"demo"}'`
then `curl -b c.txt localhost:8000/api/summary` shows non-zero income and spending.
Milestone: the backend core works. Add a USER CHECK line: "run the curl above and eyeball the numbers".
