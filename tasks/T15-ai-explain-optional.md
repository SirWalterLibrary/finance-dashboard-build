# T15 — AI explain (OPTIONAL — skip if time is short)
Needs: T14, T11
Files: app/routers/explain.py, app/main.py, tests/test_explain.py

Do:
1. `POST /api/explain {kind, scope}`: compute the goals simulation (or forecast projection) with the existing pure functions, then call standard Ollama
   `POST {OLLAMA_URL}/api/chat` (`stream:false`, model `EXPLAIN_MODEL`) — a general chat model, NOT the system-one endpoint — to write 3–4 plain sentences describing the already-computed numbers for a non-technical reader.
   The LLM must NOT calculate. Prompt includes the numbers as JSON and says "Do not change any number or date."
2. Response `{text, llm_available}`; on failure `{text:"", llm_available:false}`.
3. Tests with the HTTP call monkeypatched.

Verify: `make test`.
