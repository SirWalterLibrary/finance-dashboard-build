# T08b — relabel_similar (database helper)
Needs: T08a. Self-contained: do NOT read SPEC.md.
Files: app/rules.py (add one function), tests/test_correction.py (add tests)
Read only: app/rules.py, app/scope.py (function `owner_clause(scope, user_id, column)` returns `(sql_fragment, params)`), tests/test_correction.py.

Add to `app/rules.py`:
`relabel_similar(conn, user_id, keyword, category_id, exclude_id) -> int`
- `kw = norm_desc(keyword)`.
- Select candidate rows: `SELECT t.id, t.description FROM transactions t JOIN accounts a ON a.id = t.account_id WHERE <owner_clause("combined", user_id, "a.owner_user_id")> AND t.category_source IN ('none','rule','llm') AND t.id != ?`.
  (Use the clause and params from `owner_clause`. "combined" = joint accounts plus this user's own personal accounts; another user's personal accounts are never touched.)
- Keep only rows where `kw in norm_desc(description)` (do the matching in Python).
- `UPDATE transactions SET category_id = ?, category_source = 'rule' WHERE id = ?` for each kept row, all inside one `with conn:`. Rows with source `manual` are never touched. Return how many rows were updated.

Tests FIRST (add to tests/test_correction.py). Make a helper that inserts a joint account and transactions with plain SQL (`with con:`), like tests/test_apply_rules.py:
- rows `KWIK TRIP #1 SOUTH ST PAUL` (source none), `KWIK TRIP #2` (source rule, category Transport), `KWIK TRIP #3` (source llm) all become the target category with source `rule`; return value 3.
- a `manual` KWIK TRIP row is untouched.
- `exclude_id` row is untouched (and not counted).
- a row without the keyword (`SAMS CLUB`) is untouched.
- privacy: user B's PERSONAL account row `KWIK TRIP #9` is NOT changed when user A calls it (create the two users with `make_user` from conftest, create the personal account with plain SQL `owner_user_id = <B id>`).
- a call with no matches returns 0.

Verify: `make test`. Touch nothing else (apart from a Log line in PROGRESS.md). Tick T08b.
