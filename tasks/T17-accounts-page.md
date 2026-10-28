# T17 — Accounts + import page
Needs: T16
Files: app/static/js/pages/accounts.js, app/static/css/app.css

Do:
1. List accounts (card per account: name, institution, type badge, "Joint" or "Personal" badge, balance, transaction count, Delete with confirm dialog).
2. "Add account" dialog: name, institution, type (checking/savings/credit), "Shared with spouse" checkbox (default on), opening balance (dollars → cents).
3. Each card has "Import CSV": file input → `POST /api/accounts/{id}/import`, then show a plain message
   "Added N new transactions, skipped M duplicates" plus any errors in a collapsible list. Offer button "Categorize now" → `POST /api/categorize/run`.
4. After the first import into an account, prompt: "What is this account's balance today?" → `PUT /api/accounts/{id}/balance` (CSV files have no balances). Card shows a "Set balance" link any time.
5. Import result message also shows "skipped N pending transactions" when `skipped_pending>0`.
6. Empty state text explaining what to do first.

Verify: `make check-js`.
USER CHECK: add an account, import `tests/fixtures/wf_sample.csv` (a real file works too), import it again (0 added), delete the account. Joint vs Personal badges correct; switching scope hides personal accounts.
