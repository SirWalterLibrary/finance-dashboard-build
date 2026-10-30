# T08a — ensure_rule (database helper)
Needs: T07. Self-contained: do NOT read SPEC.md.
Files: app/rules.py (add one function), tests/test_correction.py (new)
Read only: app/rules.py, the `rules` table in app/schema.sql, tests/test_apply_rules.py (copy its helper style).

First, in PROGRESS.md replace the line `- [ ] T08 Manual correction learns` with these three lines, and nothing else:
- [ ] T08a ensure_rule helper
- [ ] T08b relabel_similar helper
- [ ] T08c PATCH apply_to_similar

Add to `app/rules.py`:
`ensure_rule(conn, keyword, category_id) -> int`
- `kw = norm_desc(keyword)`. If `kw` is empty, raise `ValueError`.
- If a rule with the same `keyword` (compare to `kw`), the same `category_id`, `min_cents IS NULL` and `max_cents IS NULL` already exists, return its id.
- Otherwise `INSERT INTO rules (keyword, category_id) VALUES (?, ?)` (check schema.sql: leave the other columns at their defaults) and return `cursor.lastrowid`.
- It must NOT commit; the caller wraps it in `with conn:`.

Tests FIRST in tests/test_correction.py (use the `client` fixture so the DB exists; `connect()` is not autocommit, so test inserts need `with con:`):
- new keyword -> returns an int; the row exists with keyword uppercased (`"kwik trip"` -> `KWIK TRIP`).
- calling again with the same keyword + category -> same id, still one row.
- same keyword + a different category -> a NEW id (two rows).
- an existing rule with the same keyword + category but `max_cents = 5000` does not count as a duplicate -> new id.
- `ensure_rule(conn, "   ", cat)` raises ValueError.

Verify: `make test`. Touch nothing else (apart from the PROGRESS.md edit above and a Log line). Tick T08a.
