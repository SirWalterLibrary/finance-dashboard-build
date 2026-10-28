# T01 — Database + seed
Needs: T00
Files: app/schema.sql, app/seed/categories.json, app/seed/rules.json, app/db.py, app/main.py, tests/test_db.py

Do:
1. Copy `assets/schema.sql` → `app/schema.sql`; `assets/seed/*.json` → `app/seed/`.
2. `app/db.py`: `connect()` (sqlite3 at `config.get("DB_PATH","data/dev.db")`, create parent dir, `row_factory=sqlite3.Row`,
   `PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL`). `init_db()` runs schema.sql, then if `categories` is empty inserts
   categories.json and rules.json (rule `category` is a NAME → look up id; optional `min_cents`/`max_cents`).
3. `create_app()` calls `init_db()` at startup.
4. `categories` rows include `description` (from seed). Tests: all 9 tables exist; seed counts match the JSON files; calling `init_db()` twice does not duplicate rows;
   category "Uncategorized" exists with kind `expense`.

Verify: `make test`.
