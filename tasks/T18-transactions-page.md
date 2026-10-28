# T18 — Transactions page
Needs: T17
Files: app/static/js/pages/transactions.js, app/static/css/app.css

Do:
1. Filters row: search box (debounced 300 ms), account select, category select, direction (All/Money in/Money out), from/to dates. Table columns:
   Date, Description (truncate, full text in `title`), Account, Category, Amount (green/red). Pagination 50/page with Prev/Next and total.
2. Category cell = a colored pill that opens a `<select>` of categories. On change, show a small dialog:
   "Apply to all similar transactions ('KEYWORD')?" with a keyword input prefilled from the row's `suggested_keyword` (user can edit),
   buttons "Only this one" / "Apply to all similar". Send `PATCH` accordingly, then reload and toast "Updated N transactions".
3. Pill style differs for `category_source`: manual = solid, rule/llm = outlined with a tiny "auto" label (llm shows confidence % in the tooltip), none = dashed "Uncategorized".
   Add filter chips "Needs review" (`source=none`) and "AI-guessed" (`source=llm`).
4. Row delete button with confirm.

Verify: `make check-js`.
USER CHECK: change one category with/without "similar"; filters narrow results; pagination works; auto vs manual pill styles visible.
