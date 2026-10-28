# T22 — Forecast page
Needs: T21
Files: app/static/js/pages/forecast.js, app/static/css/app.css

Do:
1. Line chart from `/api/forecast/projection` (balance over time; red area/marker where below zero; horizon select 5/10/15 years → `months`).
   Show "Balance first goes negative in <Month YYYY>" or "Stays positive".
2. Inputs above chart: "Assume saving $/month" (default = baseline from API) and "Starting balance" (default from API). Changes recalc.
3. Events list grouped by `group_name`, each with name, "One-time $X on <date>" or "$X per month/year from <date> to <date|ongoing>", Edit, Delete.
4. "Add item" dialog: name, group (free text), Expense/Income, One-time/Recurring, amount, start date, end date (recurring only), frequency (recurring only).
5. Two starter buttons that only PREFILL the dialog with blank amounts: "Home" (creates two items when saved: one-time down payment + recurring monthly mortgage)
   and "Child" (recurring monthly). Do not invent dollar amounts.

Verify: `make check-js`.
USER CHECK: add a one-time and a recurring item; chart changes at the right month; delete works; scope toggle hides personal items.
