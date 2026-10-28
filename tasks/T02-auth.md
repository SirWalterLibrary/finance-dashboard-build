# T02 — Auth (sessions in DB)
Needs: T01
Files: app/auth.py, app/routers/__init__.py, app/routers/auth.py, scripts/create_user.py, app/main.py, tests/test_auth.py, tests/conftest.py

Do:
1. `auth.py`: `hash_password(pw)` / `verify_password(pw, hash)` using `hashlib.scrypt` + random salt (stdlib only; store `salt$hash` hex).
   `create_session(user_id)` → random token (`secrets.token_urlsafe(32)`), expires in 30 days, stored in `sessions`.
   `current_user(request)` FastAPI dependency: reads cookie `sid`, returns user row or raises 401.
2. Router: `POST /api/login`, `POST /api/logout`, `GET /api/me` per SPEC. Cookie: HttpOnly, SameSite=Lax,
   `secure = config.get("COOKIE_SECURE","0")=="1"`.
3. Rate limit: in-memory, 5 failed logins per IP per 5 minutes → 429.
4. `scripts/create_user.py <username>`: prompts password with `getpass`, inserts user. (Works inside docker too.)
5. `conftest.py`: add helpers/fixtures `make_user(name)` and `login(client, name)` used by later tests; second user fixture too.
6. Tests: wrong password 401; right password sets cookie and `/api/me` works; logout invalidates; `/api/me` without cookie 401; 6th bad login 429.

Verify: `make test`.
