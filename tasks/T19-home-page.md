# T19 — Home page
Needs: T18
Files: app/static/js/pages/home.js, app/static/css/app.css

Do:
1. Range buttons: 1M, 3M, 6M (default), YTD, ALL, Custom (two date inputs). Call `/api/summary`.
2. Four stat cards: Income (green), Spending (red; small subtext "after $X work reimbursements" when `reimbursed_cents>0`), Net (green/red by sign), Saved to savings. Show "N uncategorized — Review" link to `#/transactions` when `uncategorized_count>0`.
3. Left: doughnut chart of `by_category` (Chart.js, top 8 + "Other"). Right: Breakdown table (colored dot, name, amount, %). Clicking a row filters the
   "Transactions — <category>" table below (call `/api/transactions?category_id=`), with a Clear link.
4. Toggle "By category | By month": month view = stacked bar of spending per month using `by_month` (and an income line if simple).
5. Destroy previous Chart instances on re-render (avoid canvas reuse errors).

Verify: `make check-js`.
USER CHECK: numbers match the Transactions page; card payments and savings transfers are NOT counted as spending; range buttons update everything.
