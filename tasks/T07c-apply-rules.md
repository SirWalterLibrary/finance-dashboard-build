# T07c — apply_rules (database function)
Needs: T07b. Self-contained: do NOT read SPEC.md.
Files: app/rules.py (add two functions), tests/test_apply_rules.py (new)
Read only: app/rules.py, app/schema.sql (tables `rules`, `transactions`, `categories`), tests/test_accounts.py (copy its `_add_tx` style for inserting rows).

Add to `app/rules.py`:
1. `load_rules(conn) -> list[dict]`: `SELECT id, keyword, category_id, min_cents, max_cents FROM rules`; normalize each keyword with `norm_desc`.
2. `apply_rules(conn, tx_ids=None) -> int`:
   - Select transactions with `category_source = 'none'` (and `id IN tx_ids` when given; an empty list means nothing to do).
   - For each, `match_rule(rules, norm_desc(description), amount_cents)`; on a match set `category_id = rule.category_id`, `category_source = 'rule'`.
   - Do all updates inside one `with conn:` block. Return how many rows changed. Never touch rows whose source is `manual`, `rule` or `llm`.
The seed rules are already in the database (created by `init_db`), so tests can rely on e.g. `KWIK TRIP` -> Transport.

Tests FIRST (use the `client` fixture so the DB exists; insert one joint account and transactions with plain SQL):
- a `none` row `KWIK TRIP #178 SOUTH ST PAUL` becomes Transport with source `rule`; return value 1.
- a `manual` row with the same description is untouched.
- `tx_ids=[one id]` only changes that row.
- a row nothing matches stays `none` / Uncategorized.
- calling again returns 0.

Verify: `make test`. Touch nothing else.
