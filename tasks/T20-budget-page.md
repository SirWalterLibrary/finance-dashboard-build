# T20 — Budget page
Needs: T19
Files: app/static/js/pages/budget.js, app/static/css/app.css

Do:
1. Month picker (prev/next arrows + label). Call `/api/budgets?month=`.
2. One row per category: name, "$spent of $limit", progress bar (green <80%, amber 80–100%, red >100% and show "Over by $X"), and an inline editable limit
   (click → input → Enter saves via `PUT /api/budgets`). Categories without a budget show "Set budget".
3. Top summary: total budgeted vs total spent for the month.
4. Not shown in `combined` scope for editing: when scope is `combined`, show limits read-only with a note "Switch to Joint or Mine to edit".

Verify: `make check-js`.
USER CHECK: set a budget, see the bar; set a low budget to see red "Over by"; change month.
