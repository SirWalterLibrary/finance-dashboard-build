# T08 — Manual correction learns
Needs: T07
Files: app/rules.py, app/routers/transactions.py, tests/test_correction.py

Do:
1. Extend `PATCH /api/transactions/{id}` with `apply_to_similar` (bool, default false) and `keyword` (optional str).
2. If `apply_to_similar`: keyword = given keyword (uppercased) or `merchant_key(description)`. If keyword is empty → 400.
   Insert a rule (keyword, category) unless an identical keyword+category rule with no amount bounds already exists.
   Then update every OTHER visible transaction whose normalized description contains the keyword and whose source is
   `none`, `rule` or `llm` → that category, source `rule`. Never touch `manual`.
3. Response: the SAME item object T06 already returns, plus two extra fields `updated` (count of transactions changed incl. this one) and `rule_id` (int or null).
   Existing T06 patch tests must keep passing unchanged.
4. Tests: correct one Kwik Trip row to Food & Dining with apply_to_similar → other Kwik Trip rows change, rule exists;
   a previously manual row is untouched; without apply_to_similar only one row changes and no rule is added;
   a later imported Kwik Trip row is auto-categorized by the new rule.

Verify: `make test`.
