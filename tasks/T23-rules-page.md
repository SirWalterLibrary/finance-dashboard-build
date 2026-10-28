# T23 — Rules page + AI categorize button
Needs: T18, T11
Files: app/static/js/pages/rules.js, app/static/css/app.css

Do:
1. Table of rules: keyword, category pill, optional amount range ("≤ $60"), Delete. "Add rule" form: keyword, category, optional min/max dollars.
2. Button "Categorize uncategorized (rules + AI)" → `POST /api/categorize/run` (current scope). Show result: "Rules: N, AI: M, still uncategorized: K".
   If `llm_available` is false show "AI is offline — rules were applied only."
3. Categories section: list with kind, color and an editable **description** (this text is what the AI model sees as the category criteria — add a hint
   line saying so); add / rename / recolor / delete (error text on 409).

Verify: `make check-js`.
USER CHECK: add a rule, run categorize, see counts; with Ollama stopped, the offline message shows and nothing breaks.
