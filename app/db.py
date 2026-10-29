"""SQLite connection + schema/seed initialization."""
import json
import sqlite3
from pathlib import Path

from . import config

APP_DIR = Path(__file__).parent
SCHEMA_PATH = APP_DIR / "schema.sql"
SEED_PATH = APP_DIR / "seed"


def _db_path() -> Path:
    return Path(config.get("DB_PATH", "data/dev.db"))


def connect() -> sqlite3.Connection:
    """Open a connection to the configured database (WAL, FKs on)."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con


def _seed(con: sqlite3.Connection) -> None:
    """Insert seed categories + rules, but only if categories is empty."""
    if con.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"]:
        return
    with con:
        cats = json.loads((SEED_PATH / "categories.json").read_text(encoding="utf-8"))
        con.executemany(
            "INSERT INTO categories(name, kind, color, description) VALUES (?, ?, ?, ?)",
            [(c["name"], c["kind"], c["color"], c["description"]) for c in cats],
        )
        names = {
            r["name"]: r["id"]
            for r in con.execute("SELECT id, name FROM categories")
        }
        rules = json.loads((SEED_PATH / "rules.json").read_text(encoding="utf-8"))
        con.executemany(
            "INSERT INTO rules(keyword, category_id, min_cents, max_cents)"
            " VALUES (?, ?, ?, ?)",
            [
                (r["keyword"], names[r["category"]],
                 r.get("min_cents"), r.get("max_cents"))
                for r in rules
            ],
        )


def init_db() -> None:
    """Create all tables, then seed categories/rules if the DB is empty."""
    con = connect()
    try:
        con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _seed(con)
        con.commit()
    finally:
        con.close()
