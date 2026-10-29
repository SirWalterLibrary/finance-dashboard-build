# T07f — Rules API + categorize/run
Needs: T07e. Self-contained: do NOT read SPEC.md.
Files: app/routers/rules.py (new), app/main.py (include router), tests/test_rules_api.py (new)
Read only: app/routers/categories.py, app/rules.py, app/scope.py (`owner_clause(scope, user_id, column)`), app/main.py.

Endpoints under `/api`, all require login:
- `GET /rules` -> list of `{id,keyword,category_id,category_name,min_cents,max_cents}` ordered by keyword.
- `POST /rules` body `{keyword,category_id,min_cents?,max_cents?}` -> 201 item. Store `keyword` as `norm_desc(keyword)`.
  Blank keyword -> 422; `min_cents > max_cents` -> 422; unknown category -> 404.
- `DELETE /rules/{id}` -> `{"ok": true}`; unknown -> 404.
- `POST /categorize/run` body `{scope}` (`joint|personal|combined`, bad value -> 400):
  find the ids of transactions with `category_source='none'` whose account is visible in that scope
  (join `accounts a`, filter with `owner_clause(scope, user_id, "a.owner_user_id")`), call `rules.apply_rules(con, ids)`,
  and return `{"by_rule": <changed>, "by_llm": 0, "left": <rows still 'none' in that scope>, "llm_available": false}`.
  (T11 will extend this later; keep it simple.)

Tests FIRST: 401 without login; create/list/delete a rule; blank keyword 422; min>max 422; unknown category 404;
categorize/run changes a `none` joint row (insert with plain SQL, a description matching a seed rule) and reports `by_rule` 1 and `left` 0;
scope isolation: user B running `scope=joint` never touches user A's personal-account rows (they stay `none`); bad scope 400.

Verify: `make test`. Touch nothing else.
