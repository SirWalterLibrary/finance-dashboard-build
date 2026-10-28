# T21 — Goals page
Needs: T19
Files: app/static/js/pages/goals.js, app/static/css/app.css

Do:
1. Top strip from `/api/savings`: "Total savings", "Allocated to goals", "Unallocated".
2. "Add goal" dialog: name, target amount, optional target date. Goal card: name, progress bar (allocated/target), editable "Allocated" input
   (PATCH; show the server's `over_allocated` error in plain words), target date, Delete.
3. "Simulate" button → `GET /api/goals/simulate` (inputs: months of history 3/6/12 select, optional "assume $/month" override).
   Show per goal: "Estimated: <Month YYYY>" and "On track / Behind target date / Not reachable at current pace" (null eta).
   Show "Based on average monthly savings of $X".
4. (Only if T15 is done) "Explain in plain words" button → `POST /api/explain` and show the text; hide button otherwise.

Verify: `make check-js`.
USER CHECK: allocate to two goals; try to over-allocate (error shows); Simulate shows dates; changing the override changes dates.
