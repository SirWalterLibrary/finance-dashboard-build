# Agent rules (loaded every session — obey exactly)

You are building "Finance Dashboard". ONE task per session. Stop when it is done.

1. Input = SPEC.md + one task file. Do only that task. No extra features, no refactors.
2. Only create/edit files listed under **Files** in the task.
3. Keep files small (<200 lines). Python 3 + packages in requirements.txt only.
   No ORM, no frontend framework, no build step, no new dependencies unless the task says so.
4. Money = integer cents. Dates = ISO `YYYY-MM-DD` text. Never use floats for money.
5. Test first: write the tests named in the task, watch them fail, implement, make them pass.
6. Run `make test` (and `make check-js` for frontend tasks). Everything must pass.
   Never edit a test just to make it pass unless it contradicts SPEC.md.
7. Never use real financial data. Use `fixtures/` and `scripts/seed_demo.py`. Never log descriptions or amounts.
8. Finish: tick the task in PROGRESS.md (`[x]`), add one line to Log, then
   `git add -A && git commit -m "T<id>: <short title>"`. Then stop.
9. Blocked after 3 attempts: write the problem under Blockers in PROGRESS.md and stop. Do not improvise.
10. Frontend tasks: also add the task's "USER CHECK" steps to PROGRESS.md under User Checks.
