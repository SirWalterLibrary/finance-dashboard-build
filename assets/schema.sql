CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS sessions(
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS accounts(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  institution TEXT NOT NULL DEFAULT '',
  type TEXT NOT NULL CHECK(type IN ('checking','savings','credit')),
  owner_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,   -- NULL = joint
  invert_amounts INTEGER NOT NULL DEFAULT 0,
  opening_balance_cents INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS categories(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL CHECK(kind IN ('income','expense','transfer','savings','reimbursement')),
  color TEXT NOT NULL DEFAULT '#888888',
  description TEXT NOT NULL DEFAULT '');   -- fed to the LLM as the category criteria
CREATE TABLE IF NOT EXISTS transactions(
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  date TEXT NOT NULL,                       -- YYYY-MM-DD
  description TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,            -- negative = out
  category_id INTEGER NOT NULL REFERENCES categories(id),
  category_source TEXT NOT NULL DEFAULT 'none' CHECK(category_source IN ('none','rule','llm','manual')),
  category_confidence REAL,                 -- LLM confidence 0..1, NULL otherwise
  dedupe_key TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(account_id, dedupe_key));
CREATE INDEX IF NOT EXISTS ix_tx_acct_date ON transactions(account_id, date);
CREATE INDEX IF NOT EXISTS ix_tx_cat ON transactions(category_id);
CREATE TABLE IF NOT EXISTS rules(
  id INTEGER PRIMARY KEY,
  keyword TEXT NOT NULL,
  category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
  min_cents INTEGER, max_cents INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS budgets(
  id INTEGER PRIMARY KEY,
  owner_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
  limit_cents INTEGER NOT NULL CHECK(limit_cents >= 0));
CREATE UNIQUE INDEX IF NOT EXISTS ux_budget ON budgets(IFNULL(owner_user_id,0), category_id);
CREATE TABLE IF NOT EXISTS goals(
  id INTEGER PRIMARY KEY,
  owner_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  target_cents INTEGER NOT NULL CHECK(target_cents > 0),
  target_date TEXT,
  allocated_cents INTEGER NOT NULL DEFAULT 0 CHECK(allocated_cents >= 0),
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS forecast_events(
  id INTEGER PRIMARY KEY,
  owner_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  group_name TEXT NOT NULL DEFAULT '',
  direction TEXT NOT NULL CHECK(direction IN ('expense','income')),
  kind TEXT NOT NULL CHECK(kind IN ('one_time','recurring')),
  amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
  start_date TEXT NOT NULL,
  end_date TEXT,
  frequency TEXT CHECK(frequency IN ('monthly','yearly')));
