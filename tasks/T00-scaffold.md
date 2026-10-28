# T00 — Scaffold
Needs: nothing
Files: Makefile, requirements.txt, .gitignore, .env.example, app/__init__.py, app/config.py, app/main.py, tests/conftest.py, tests/test_health.py

Do:
1. Copy from `assets/`: `Makefile`, `requirements.txt`, `.gitignore`, `.env.example`. Run `git init`.
2. `app/config.py`: `get(name, default=None)` reads `os.environ` at CALL time (no caching).
3. `app/main.py`: `create_app()` returns FastAPI app with `GET /api/health` → `{"ok": true}`.
   Module-level `app = create_app()`. If `app/static` exists, mount it at `/` with `html=True` (mount LAST).
4. `tests/conftest.py`: fixture `client` — sets env `DB_PATH` to a tmp file (monkeypatch), builds `create_app()`, returns `TestClient`.
5. `tests/test_health.py`: health returns 200 and `{"ok": true}`.

Verify: `make setup && make test` passes. `make dev` then `curl localhost:8000/api/health` prints `{"ok":true}`.
