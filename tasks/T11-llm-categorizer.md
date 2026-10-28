# T11 — LLM categorizer (system-one model `d3:9b`)
Needs: T08
Files: app/llm.py, app/routers/categories.py, tests/test_llm.py

Do (follow SPEC "LLM rules" exactly; the user's existing script is the reference for the request/response shape):
1. `llm.py`:
   - `classify(description, amount_cents, criteria) -> (category|None, confidence|None)`: builds the payload from SPEC, POSTs with `httpx` (timeout 30),
     returns `(choice, confidence)` from `answers.category`; any exception / missing keys → `(None, None)`.
   - `build_criteria(conn)`: dict name → description (+ ` Examples: A, B` from up to 5 most recent distinct `merchant_key`s of `manual` rows in that category).
   - `categorize_pending(conn, tx_rows)` → `{by_llm, llm_available}`: group rows by `(merchant_key, sign)`; call `classify` once per group;
     validate `choice` is an existing category and `confidence >= LLM_MIN_CONFIDENCE`; update all rows in the group (source `llm`, store confidence).
     First call returns `(None,None)` → `llm_available:false`, stop, change nothing. Later failures → skip that group.
2. Extend `POST /api/categorize/run`: after rules, run `categorize_pending` on remaining `none` rows in scope. Response per SPEC.
3. Tests (monkeypatch `llm.classify`; NEVER call a real server): valid answers applied and confidence stored; unknown category ignored;
   repeated merchant → `classify` called once; first call None → `llm_available:false` and no changes; `manual` rows never sent;
   `build_criteria` includes the example text; payload test (monkeypatch `httpx.post`, assert JSON keys `model,state,questions.category.{type,instructions,criteria}`).

Verify: `make test`.
USER CHECK (needs your Ollama running): `make dev`, import a CSV, then
`curl -b c.txt -XPOST localhost:8000/api/categorize/run -H 'content-type: application/json' -d '{"scope":"joint"}'` (or the button after T23).
